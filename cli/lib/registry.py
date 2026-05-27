"""Local registry for terminal-backed Aura agents.

This complements the legacy mesh socket registry. It records tmux-controlled
runtime sidecars (Claude Code, Hermes, Codex, etc.) so fleet commands can treat
those windows as named agents even before deeper runtime-specific adapters exist.
"""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any
import uuid
import fcntl

from lib import state


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_seat_instance_id() -> str:
    return f"si_{uuid.uuid4().hex[:12]}"


def registry_path():
    return state.registry_path()


def registry_lock_path():
    path = registry_path()
    return path.with_name(f"{path.name}.lock")


def aliases_path():
    return state.seat_aliases_path()


def current_fleet(default: str = "aura") -> str:
    return (
        os.environ.get("AURA_FLEET")
        or os.environ.get("AURA_TMUX_SESSION")
        or os.environ.get("AURA_PROJECT")
        or default
    )


def trace_cell_for_runtime(runtime: str | None) -> str | None:
    if runtime in ("claude", "claude-code"):
        return "claude_code"
    return None


TRANSIENT_AGENT_FIELDS = {
    "agent_map_ready",
    "agent_map_injected",
    "alias_chain",
    "flex_project_packet_delivered",
    "flex_project_packet_delivered_at",
    "flex_project_packet_source",
    "flex_project_packet_manifest",
    "flex_project_packet_session_key",
    "liveness",
    "managed_state",
    "prompt_sent",
    "prompt_submit_retry",
    "restore_ready",
    "restore_reason",
    "resolved_from",
    "risk_flags",
}


def _without_transient_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in TRANSIENT_AGENT_FIELDS}


def _physical_fleet_from_ref(value: str | None) -> str | None:
    if not value:
        return None
    subject = str(value)
    if subject.startswith("tmux:"):
        subject = subject[len("tmux:"):]
    if ":" in subject:
        fleet, _ = subject.split(":", 1)
        return fleet or None
    return None


def _canonical_status(value: Any, default: str | None = None) -> str | None:
    if value is None:
        return default
    normalized = str(value).strip().lower().replace(" ", "_").replace("-", "_")
    if not normalized:
        return default
    aliases = {
        "killed": "dead",
        "terminated": "dead",
        "cut": "dead",
        "swept": "swept_removed",
    }
    return aliases.get(normalized, normalized)


def _canonical_tmux_pane_ref(value: Any, *, fleet: str) -> Any:
    if not value:
        return value
    subject = str(value).strip()
    if not subject:
        return value
    if subject.startswith("tmux:"):
        return subject
    if subject.startswith("%"):
        return f"tmux:{fleet}:{subject}"
    if ":" in subject:
        maybe_fleet, maybe_pane = subject.split(":", 1)
        if maybe_fleet and maybe_pane.startswith("%"):
            return f"tmux:{maybe_fleet}:{maybe_pane}"
    return subject


def normalize_agent_record(record: dict[str, Any], *, fleet: str | None = None, name: str | None = None) -> dict[str, Any]:
    """Normalize persisted registry fields without probing live terminal state."""
    normalized = dict(record)
    final_name = name or normalized.get("name") or normalized.get("seat")
    final_fleet = fleet or normalized.get("fleet") or current_fleet()
    if final_name:
        normalized["name"] = final_name
        normalized["seat"] = final_name
        normalized["fleet"] = final_fleet
        normalized["seat_ref"] = _key(final_fleet, final_name)
        normalized["target"] = normalized["seat_ref"]
    if normalized.get("status") is not None:
        normalized["status"] = _canonical_status(normalized.get("status"))
    for key in ("pane_ref", "backend_ref"):
        if normalized.get(key):
            normalized[key] = _canonical_tmux_pane_ref(normalized.get(key), fleet=final_fleet)
    runtime = normalized.get("runtime")
    if runtime and not normalized.get("runtime_ref"):
        normalized["runtime_ref"] = runtime
    session_id = normalized.get("runtime_session_id") or normalized.get("session_id")
    if session_id:
        normalized["runtime_session_id"] = normalized.get("runtime_session_id") or session_id
        normalized["session_id"] = normalized.get("session_id") or session_id
    launch_id = normalized.get("aura_launch_id") or normalized.get("launch_id") or normalized.get("launch_ref")
    if launch_id:
        normalized["aura_launch_id"] = normalized.get("aura_launch_id") or launch_id
        normalized["launch_id"] = normalized.get("launch_id") or launch_id
        normalized["launch_ref"] = normalized.get("launch_ref") or launch_id
    return normalized


def _with_logical_physical_fields(record: dict[str, Any], *, fleet: str, name: str) -> dict[str, Any]:
    enriched = normalize_agent_record(record, fleet=fleet, name=name)
    enriched["logical_fleet"] = fleet
    enriched["logical_name"] = name
    enriched["logical_ref"] = _key(fleet, name)
    physical_fleet = (
        enriched.get("physical_fleet")
        or _physical_fleet_from_ref(enriched.get("pane_ref"))
        or _physical_fleet_from_ref(enriched.get("terminal_ref"))
        or _physical_fleet_from_ref(enriched.get("backend_ref"))
        or fleet
    )
    enriched.setdefault("physical_fleet", physical_fleet)
    return enriched


def _key(fleet: str | None, name: str) -> str:
    return f"{fleet or current_fleet()}:{name}"


def split_ref(value: str, fleet: str | None = None) -> tuple[str | None, str]:
    if ":" in str(value) and not str(value).startswith("tmux:"):
        maybe_fleet, maybe_name = str(value).split(":", 1)
        if maybe_fleet and maybe_name:
            return maybe_fleet, maybe_name
    return fleet, str(value)


def seat_ref(fleet: str | None, name: str) -> str:
    return _key(fleet, name)


def is_hidden_agent(record: dict[str, Any] | None) -> bool:
    if not record:
        return False
    fleet = str(record.get("fleet") or "")
    return bool(record.get("hidden")) or record.get("kind") == "ether" or fleet.startswith("_")


def is_hidden_fleet(fleet: str | None) -> bool:
    return bool(fleet and str(fleet).startswith("_"))


def read_registry() -> dict[str, dict[str, Any]]:
    path = registry_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict):
        return {str(k): v for k, v in data.items() if isinstance(v, dict)}
    return {}


@contextmanager
def _registry_lock():
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = registry_lock_path()
    with open(lock_path, "a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _write_registry_unlocked(data: dict[str, dict[str, Any]]) -> None:
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="agents-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def write_registry(data: dict[str, dict[str, Any]]) -> None:
    with _registry_lock():
        _write_registry_unlocked(data)


def replace_agent_record(record: dict[str, Any]) -> dict[str, Any]:
    name = record["name"]
    fleet = record.get("fleet") or current_fleet()
    key = _key(fleet, name)
    record = _with_logical_physical_fields(record, fleet=fleet, name=name)
    merged = {
        **record,
        "name": name,
        "seat": record.get("seat") or name,
        "fleet": fleet,
        "seat_ref": key,
        "last_seen": record.get("last_seen") or now_iso(),
    }
    merged = _without_transient_fields(merged)
    with _registry_lock():
        data = read_registry()
        data[key] = merged
        _write_registry_unlocked(data)
    return merged


def update_agent_record(
    name: str,
    fleet: str | None,
    updater,
) -> dict[str, Any] | None:
    with _registry_lock():
        data = read_registry()
        key = _key(fleet, name)
        current = dict(data.get(key, {}))
        updated = updater(current)
        if updated is None:
            return None
        updated = {
            **updated,
            "name": updated.get("name") or name,
            "seat": updated.get("seat") or updated.get("name") or name,
            "fleet": updated.get("fleet") or fleet or current_fleet(),
            "last_seen": updated.get("last_seen") or now_iso(),
        }
        updated = _with_logical_physical_fields(updated, fleet=updated.get("fleet"), name=updated.get("name"))
        updated = _without_transient_fields(updated)
        data[updated["seat_ref"]] = updated
        if updated["seat_ref"] != key:
            data.pop(key, None)
        _write_registry_unlocked(data)
        return updated


def read_aliases() -> dict[str, dict[str, Any]]:
    path = aliases_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if isinstance(data, dict):
        return {str(k): v for k, v in data.items() if isinstance(v, dict)}
    return {}


def write_aliases(data: dict[str, dict[str, Any]]) -> None:
    path = aliases_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="seat-aliases-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def resolve_alias(ref: str, *, max_hops: int = 8) -> tuple[str, list[str]]:
    aliases = read_aliases()
    current = ref
    chain: list[str] = []
    for _ in range(max_hops):
        record = aliases.get(current)
        if not record:
            break
        target = record.get("target")
        if not target or target in chain:
            break
        chain.append(current)
        current = str(target)
    return current, chain


def add_alias(source: str, target: str, *, reason: str = "alias") -> dict[str, Any]:
    aliases = read_aliases()
    record = {
        "schema": "aura.seat_alias.v1",
        "source": source,
        "target": target,
        "reason": reason,
        "created_at": now_iso(),
    }
    aliases[source] = record
    write_aliases(aliases)
    return record


def upsert_agent(record: dict[str, Any]) -> dict[str, Any]:
    name = record["name"]
    fleet = record.get("fleet") or current_fleet()
    runtime = record.get("runtime")
    fleet_record = None
    try:
        from lib import fleets

        fleet_record = fleets.ensure_fleet(fleet, tmux_session=record.get("physical_fleet") or fleet)
    except Exception:
        fleet_record = None
    with _registry_lock():
        data = read_registry()
        key = _key(fleet, name)
        previous = data.get(key, {})
        created_at = previous.get("created_at") or record.get("created_at") or now_iso()
        record = _with_logical_physical_fields(record, fleet=fleet, name=name)
        merged = {
            **previous,
            **record,
            "name": name,
            "seat": record.get("seat") or previous.get("seat") or name,
            "fleet": fleet,
            "fleet_id": record.get("fleet_id") or previous.get("fleet_id") or (fleet_record or {}).get("fleet_id"),
            "seat_ref": _key(fleet, name),
            "transport": record.get("transport") or previous.get("transport") or "tmux",
            "delivery_mode": record.get("delivery_mode") or previous.get("delivery_mode") or "immediate",
            "status": record.get("status") or previous.get("status") or "starting",
            "registered": bool(record.get("registered", previous.get("registered", True))),
            "created_at": created_at,
            "last_seen": record.get("last_seen") or now_iso(),
        }
        merged = _without_transient_fields(merged)
        if "trace_cell" not in merged or merged.get("trace_cell") is None:
            merged["trace_cell"] = trace_cell_for_runtime(runtime or previous.get("runtime"))
        data[key] = merged
        _write_registry_unlocked(data)
    return merged


def get_agent(name: str, fleet: str | None = None) -> dict[str, Any] | None:
    original_fleet = fleet
    fleet, name = split_ref(str(name), fleet=fleet)
    data = read_registry()
    if fleet:
        ref = _key(fleet, name)
        record = data.get(ref)
        if record:
            return record
        resolved, chain = resolve_alias(ref)
        if chain:
            target_fleet, target_name = split_ref(resolved)
            if target_fleet and target_name:
                target = data.get(_key(target_fleet, target_name))
                if target:
                    return {**target, "resolved_from": ref, "alias_chain": chain}
        return None
    matches = [v for v in data.values() if v.get("name") == name]
    if not matches:
        alias_fleet = original_fleet or current_fleet(default="")
        if alias_fleet:
            resolved, chain = resolve_alias(_key(alias_fleet, name))
            if chain:
                target_fleet, target_name = split_ref(resolved)
                target = data.get(_key(target_fleet, target_name)) if target_fleet else None
                if target:
                    return {**target, "resolved_from": _key(alias_fleet, name), "alias_chain": chain}
        return None
    preferred_fleet = current_fleet(default="")
    if preferred_fleet:
        preferred = [v for v in matches if v.get("fleet") == preferred_fleet]
        if preferred:
            preferred.sort(key=lambda r: r.get("last_seen", ""), reverse=True)
            return preferred[0]
    matches.sort(key=lambda r: r.get("last_seen", ""), reverse=True)
    return matches[0]


def list_agents(fleet: str | None = None, *, include_hidden: bool = False) -> list[dict[str, Any]]:
    agents = list(read_registry().values())
    if fleet:
        agents = [a for a in agents if a.get("fleet") == fleet]
    if not include_hidden:
        agents = [a for a in agents if not is_hidden_agent(a)]
    return sorted(agents, key=lambda a: (a.get("fleet", ""), a.get("name", "")))


def mark_status(name: str, status: str, fleet: str | None = None) -> dict[str, Any] | None:
    agent = get_agent(name, fleet=fleet)
    if not agent:
        return None
    agent = dict(agent)
    agent["status"] = status
    agent["last_seen"] = now_iso()
    return upsert_agent(agent)


def remove_agent(name: str, fleet: str | None = None) -> bool:
    with _registry_lock():
        data = read_registry()
        keys = [_key(fleet, name)] if fleet else [k for k, v in data.items() if v.get("name") == name]
        removed = False
        for key in keys:
            if key in data:
                del data[key]
                removed = True
        if removed:
            _write_registry_unlocked(data)
    return removed


def _same_live_incarnation(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    if not left or not right:
        return False
    for key in ("seat_instance_id", "pane_ref"):
        left_value = left.get(key)
        right_value = right.get(key)
        if left_value and right_value and str(left_value) == str(right_value):
            return True
    return False


def rename_preflight(
    source: str,
    *,
    new_name: str | None = None,
) -> dict[str, Any]:
    source_fleet, source_name = split_ref(source)
    if not source_fleet:
        agent = get_agent(source_name)
        if not agent:
            return {"ok": False, "error": f"agent not found: {source}"}
        source_fleet = agent.get("fleet")
        source_name = agent.get("name")
    source_ref = _key(source_fleet, source_name)
    data = read_registry()
    existing = data.get(source_ref)
    if not existing:
        resolved, chain = resolve_alias(source_ref)
        if chain:
            return {"ok": False, "error": f"source is an alias; use canonical target instead: {resolved}", "alias_chain": chain}
        return {"ok": False, "error": f"agent not found: {source_ref}"}

    target_name = new_name or existing.get("name")
    target_fleet = existing.get("fleet")
    target_ref = _key(target_fleet, target_name)
    target_existing = data.get(target_ref)
    repair_duplicate = False
    if target_ref != source_ref and target_existing:
        if not _same_live_incarnation(existing, target_existing):
            return {"ok": False, "error": f"target already exists: {target_ref}", "reason": "target-registry-exists", "target": target_ref}
        repair_duplicate = True

    return {
        "ok": True,
        "source": source_ref,
        "target": target_ref,
        "source_record": existing,
        "target_record": target_existing,
        "repair_duplicate": repair_duplicate,
    }


def rename_agent(
    source: str,
    *,
    new_name: str,
    metadata: dict[str, Any] | None = None,
    alias_old: bool = True,
) -> dict[str, Any]:
    """Rename a seat inside its current fleet without changing fleet ownership."""
    source_fleet, source_name = split_ref(source)
    existing = get_agent(source_name, fleet=source_fleet)
    if not existing:
        resolved, chain = resolve_alias(source)
        if chain:
            return {"ok": False, "error": f"source is an alias; rename canonical target instead: {resolved}", "alias_chain": chain}
        return {"ok": False, "error": f"agent not found: {source}"}
    target_fleet = existing.get("fleet")
    preflight = rename_preflight(source, new_name=new_name)
    if not preflight.get("ok"):
        return preflight

    with _registry_lock():
        source_ref = preflight["source"]
        target_ref = preflight["target"]
        data = read_registry()
        existing = data.get(source_ref) or preflight["source_record"]
        target_existing = data.get(target_ref) if target_ref != source_ref else None

        record = dict(existing)
        if target_existing:
            record.update(target_existing)
        record.update(metadata or {})
        record["name"] = new_name
        record["fleet"] = target_fleet
        record["seat"] = new_name
        record["seat_ref"] = target_ref
        record["logical_fleet"] = target_fleet
        record["logical_name"] = new_name
        record["rename_source"] = source_ref
        record["rename_at"] = now_iso()
        record["last_seen"] = now_iso()
        record.setdefault("physical_fleet", existing.get("physical_fleet") or target_fleet)
        record = _with_logical_physical_fields(record, fleet=target_fleet, name=new_name)
        record = _without_transient_fields(record)

        if target_ref != source_ref:
            data.pop(source_ref, None)
        data[target_ref] = record
        _write_registry_unlocked(data)

    alias = add_alias(source_ref, target_ref, reason="rename") if alias_old and target_ref != source_ref else None
    return {
        "ok": True,
        "source": source_ref,
        "target": target_ref,
        "record": record,
        "alias": alias,
        "repair_duplicate": bool(preflight.get("repair_duplicate")),
    }


def infer_status(name: str, terminal, current: str | None = None, lines: int = 20, target: str | None = None) -> str:
    target_ref = target or name
    exists = terminal.target_exists(target_ref) if hasattr(terminal, "target_exists") else terminal.window_exists(target_ref)
    if not exists:
        return "dead"
    text = "\n".join(terminal.capture_output(target_ref, lines) or [])
    lower = text.lower()
    if "do you trust" in lower or "press enter to continue" in lower or "permission" in lower:
        return "waiting"
    if "❯" in text or "›" in text or lower.rstrip().endswith("$"):
        return "idle"
    return current if current and current not in ("starting", "unknown") else "alive"

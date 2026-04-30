"""Local registry for terminal-backed Aura agents.

This complements the legacy mesh socket registry. It records tmux-controlled
runtime sidecars (Claude Code, Hermes, Codex, etc.) so fleet commands can treat
those windows as named agents even before deeper runtime-specific adapters exist.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from typing import Any

from lib import state


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def registry_path():
    return state.registry_path()


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


def _key(fleet: str | None, name: str) -> str:
    return f"{fleet or current_fleet()}:{name}"


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


def write_registry(data: dict[str, dict[str, Any]]) -> None:
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


def upsert_agent(record: dict[str, Any]) -> dict[str, Any]:
    name = record["name"]
    fleet = record.get("fleet") or current_fleet()
    runtime = record.get("runtime")
    data = read_registry()
    key = _key(fleet, name)
    previous = data.get(key, {})
    created_at = previous.get("created_at") or record.get("created_at") or now_iso()
    merged = {
        **previous,
        **record,
        "name": name,
        "fleet": fleet,
        "transport": record.get("transport") or previous.get("transport") or "tmux",
        "delivery_mode": record.get("delivery_mode") or previous.get("delivery_mode") or "immediate",
        "status": record.get("status") or previous.get("status") or "starting",
        "registered": bool(record.get("registered", previous.get("registered", True))),
        "created_at": created_at,
        "last_seen": record.get("last_seen") or now_iso(),
    }
    if "trace_cell" not in merged or merged.get("trace_cell") is None:
        merged["trace_cell"] = trace_cell_for_runtime(runtime or previous.get("runtime"))
    data[key] = merged
    write_registry(data)
    return merged


def get_agent(name: str, fleet: str | None = None) -> dict[str, Any] | None:
    if not fleet and ":" in str(name) and not str(name).startswith("tmux:"):
        maybe_fleet, maybe_name = str(name).split(":", 1)
        if maybe_fleet and maybe_name:
            fleet = maybe_fleet
            name = maybe_name
    data = read_registry()
    if fleet:
        return data.get(_key(fleet, name))
    matches = [v for v in data.values() if v.get("name") == name]
    if not matches:
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
    data = read_registry()
    keys = [_key(fleet, name)] if fleet else [k for k, v in data.items() if v.get("name") == name]
    removed = False
    for key in keys:
        if key in data:
            del data[key]
            removed = True
    if removed:
        write_registry(data)
    return removed


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

"""Show Aura runtime session identity map."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from commands import list as list_cmd


CONFIDENCE_ORDER = {
    "exact": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}


def _confidence_at_least(value: str | None, minimum: str | None) -> bool:
    if not minimum:
        return True
    return CONFIDENCE_ORDER.get(value or "", 0) >= CONFIDENCE_ORDER.get(minimum, 0)


def run(args):
    if getattr(args, "sessions_action", None) == "self":
        from lib import runtime_session

        return runtime_session.resolve_current_process(getattr(args, "runtime", None))
    if getattr(args, "sessions_action", None) == "bind-current":
        return _bind_current(args)
    if getattr(args, "sessions_action", None) == "bind-nonce":
        return _bind_nonce(args)
    if getattr(args, "sessions_action", None) == "restore-plan":
        return _restore_plan(args)

    rows = list_cmd.run(argparse.Namespace(
        fleet=getattr(args, "fleet", None),
        status=None,
        mode=None,
        include_hidden=bool(getattr(args, "include_hidden", False)),
    ))
    live_only = bool(getattr(args, "live", False))
    minimum = getattr(args, "min_confidence", None)
    mapped = []
    from lib import runtimes, session_ledger

    for row in rows:
        if live_only and row.get("terminal") != "alive":
            continue
        if not _confidence_at_least(row.get("runtime_session_confidence"), minimum):
            continue
        capability = runtimes.capabilities(row.get("runtime"))
        restore = session_ledger.restore_status(row, capability)
        mapped.append({
            "seat": row.get("name"),
            "fleet": row.get("fleet"),
            "runtime": row.get("runtime"),
            "runtime_capabilities": capability,
            "status": row.get("status"),
            "terminal": row.get("terminal"),
            "hidden": bool(row.get("hidden")),
            "kind": row.get("kind"),
            "session_id": row.get("session_id"),
            "runtime_session_id": row.get("runtime_session_id"),
            "runtime_session_source": row.get("runtime_session_source") or row.get("runtime_session_env"),
            "runtime_session_confidence": row.get("runtime_session_confidence"),
            "runtime_session_evidence": row.get("runtime_session_evidence"),
            "aura_launch_id": row.get("aura_launch_id"),
            "pane_ref": row.get("pane_ref"),
            "cwd": row.get("runtime_session_cwd") or row.get("cwd") or row.get("workdir"),
            **restore,
        })
    with_session = [row for row in mapped if row.get("session_id")]
    missing = [row for row in mapped if not row.get("session_id")]
    by_confidence = {}
    for row in with_session:
        key = row.get("runtime_session_confidence") or "unknown"
        by_confidence[key] = by_confidence.get(key, 0) + 1
    return {
        "ok": True,
        "total": len(mapped),
        "with_session_id": len(with_session),
        "missing_session_id": len(missing),
        "by_confidence": by_confidence,
        "rows": mapped,
    }


def _restore_plan(args):
    rows_result = run(argparse.Namespace(
        sessions_action=None,
        fleet=getattr(args, "fleet", None),
        live=getattr(args, "live", False),
        min_confidence=getattr(args, "min_confidence", None),
        include_hidden=getattr(args, "include_hidden", False),
    ))
    from lib import runtimes, session_ledger

    return session_ledger.restore_plan_from_rows(
        rows_result.get("rows", []),
        runtimes.capability_map(),
    )


def _read_codex_session_jsonl(path: Path, nonce: str) -> dict:
    found_nonce = False
    meta = None
    try:
        with path.open(encoding="utf-8") as f:
            for line in f:
                if nonce in line:
                    found_nonce = True
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("type") != "session_meta":
                    continue
                payload = row.get("payload") or {}
                session_id = payload.get("id")
                if session_id:
                    meta = {
                        "session_id": session_id,
                        "runtime_session_id": session_id,
                        "jsonl": str(path),
                        "cwd": payload.get("cwd"),
                        "timestamp": payload.get("timestamp") or row.get("timestamp"),
                    }
    except OSError as exc:
        return {"ok": False, "error": f"failed to read Codex JSONL: {exc}", "nonce": nonce, "jsonl": str(path)}

    if not found_nonce:
        return {"ok": False, "error": "nonce not found in Codex JSONL", "nonce": nonce, "jsonl": str(path)}
    if not meta:
        return {"ok": False, "error": "session_meta not found in matching Codex JSONL", "nonce": nonce, "jsonl": str(path)}
    return {"ok": True, **meta}


def _codex_session_from_nonce(
    nonce: str,
    *,
    expected_cwd: str | None = None,
    jsonl_path: str | None = None,
) -> dict:
    sessions_root = Path.home() / ".codex" / "sessions"
    if jsonl_path:
        pinned = Path(jsonl_path).expanduser()
        if not pinned.exists():
            return {"ok": False, "error": "pinned Codex JSONL not found", "nonce": nonce, "jsonl": str(pinned)}
        found = _read_codex_session_jsonl(pinned, nonce)
        if found.get("ok"):
            found.update({"nonce": nonce, "matches": 1})
        return found

    if not sessions_root.exists():
        return {"ok": False, "error": "codex sessions directory not found", "nonce": nonce}

    try:
        result = subprocess.run(
            ["rg", "-l", nonce, str(sessions_root), "-g", "*.jsonl"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"nonce search failed: {exc}", "nonce": nonce}

    paths = [Path(line) for line in result.stdout.splitlines() if line.strip()]
    if not paths:
        return {"ok": False, "error": "nonce not found in Codex session JSONL", "nonce": nonce}

    candidates = []
    errors = []
    for path in paths:
        found = _read_codex_session_jsonl(path, nonce)
        if found.get("ok"):
            candidates.append(found)
        else:
            errors.append(found)
    if not candidates:
        return errors[0] if errors else {"ok": False, "error": "session_meta not found in matching Codex JSONL", "nonce": nonce}

    if expected_cwd:
        cwd_matches = [candidate for candidate in candidates if candidate.get("cwd") == expected_cwd]
        if cwd_matches:
            candidates = cwd_matches
    elif len(candidates) > 1:
        return {
            "ok": False,
            "error": "nonce matched multiple Codex JSONLs; pass --target with registry cwd evidence or --jsonl",
            "nonce": nonce,
            "matches": len(candidates),
            "jsonls": [candidate.get("jsonl") for candidate in candidates],
        }

    candidates.sort(key=lambda candidate: Path(candidate["jsonl"]).stat().st_mtime if Path(candidate["jsonl"]).exists() else 0, reverse=True)
    selected = candidates[0]
    selected.update({"nonce": nonce, "matches": len(paths)})
    return {"ok": True, **selected}


def _tmux_fleet_seat(target: str | None = None) -> tuple[str | None, str | None]:
    pane_or_target = target or os.environ.get("TMUX_PANE")
    if target and target.startswith("tmux:"):
        pane_or_target = target[len("tmux:"):]
    if not pane_or_target:
        return None, None
    try:
        cmd = ["tmux", "display-message", "-p", "-t", pane_or_target, "#{session_name}\t#{window_name}"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    if result.returncode != 0:
        return None, None
    parts = result.stdout.strip().split("\t", 1)
    if len(parts) != 2:
        return None, None
    return parts[0] or None, parts[1] or None


def _current_tmux_target() -> tuple[str | None, str | None]:
    env_fleet = os.environ.get("AURA_FLEET")
    env_seat = os.environ.get("AURA_SEAT") or os.environ.get("AURA_AGENT_NAME")
    if env_fleet and env_seat:
        return env_fleet, env_seat
    return _tmux_fleet_seat()


def _target_fleet_seat(target: str | None) -> tuple[str | None, str | None]:
    if target and ":" in target and not target.startswith("tmux:"):
        fleet, seat = target.split(":", 1)
        return fleet or None, seat or None
    if target and target.startswith("tmux:"):
        return _tmux_fleet_seat(target)
    if target:
        from lib import registry

        agent = registry.get_agent(target)
        return (agent or {}).get("fleet") or registry.current_fleet(), target
    return _current_tmux_target()


def _bind_nonce(args) -> dict:
    nonce = getattr(args, "nonce", None)
    if not nonce:
        return {"ok": False, "error": "bind-nonce requires a nonce"}

    fleet, seat = _target_fleet_seat(getattr(args, "target", None))
    if not fleet or not seat:
        return {"ok": False, "error": "could not infer target fleet/seat; pass --target fleet:seat"}

    from lib import registry, session_ledger

    previous = registry.get_agent(seat, fleet=fleet) or {
        "name": seat,
        "fleet": fleet,
        "runtime": "codex",
        "registered": True,
        "status": "unknown",
    }
    expected_cwd = previous.get("runtime_session_cwd") or previous.get("cwd") or previous.get("workdir")
    found = _codex_session_from_nonce(
        nonce,
        expected_cwd=expected_cwd,
        jsonl_path=getattr(args, "jsonl", None),
    )
    if not found.get("ok"):
        return found

    evidence = {
        "reason": "codex-jsonl-nonce",
        "nonce": nonce,
        "jsonl": found.get("jsonl"),
        "matches": found.get("matches"),
    }
    return _bind_registry_session(
        fleet=fleet,
        seat=seat,
        previous=previous,
        session_id=found["session_id"],
        source="codex-jsonl:nonce",
        confidence="exact",
        evidence=evidence,
        cwd=found.get("cwd"),
        event="session_bound_nonce",
        extra={
            "jsonl": found.get("jsonl"),
            "cwd": found.get("cwd"),
        },
    )


def _bind_current(args) -> dict:
    from lib import runtime_session

    current = runtime_session.resolve_current_process(getattr(args, "runtime", None))
    if not current.get("ok") or not current.get("session_id"):
        return {
            "ok": False,
            "error": "could not resolve current runtime session id; use bind-nonce fallback",
            "current": current,
        }
    if current.get("runtime_session_confidence") != "exact":
        return {
            "ok": False,
            "error": "current runtime session id is not exact; use bind-nonce fallback",
            "current": current,
        }

    fleet, seat = _target_fleet_seat(getattr(args, "target", None))
    fleet = fleet or current.get("fleet")
    seat = seat or current.get("seat")
    if not fleet or not seat:
        return {"ok": False, "error": "could not infer target fleet/seat; pass --target fleet:seat", "current": current}

    from lib import registry

    previous = registry.get_agent(seat, fleet=fleet) or {
        "name": seat,
        "fleet": fleet,
        "runtime": current.get("runtime") or "codex",
        "registered": True,
        "status": "unknown",
    }
    evidence = {
        "reason": "current-runtime-session",
        "source": current.get("runtime_session_source"),
        "cross_check": current.get("cross_check"),
        "warning": current.get("warning"),
        "pane": current.get("pane"),
        "pane_pid": current.get("pane_pid"),
        "evidence": current.get("evidence"),
    }
    preserved_cwd = previous.get("runtime_session_cwd") or previous.get("cwd") or previous.get("workdir") or current.get("cwd")
    return _bind_registry_session(
        fleet=fleet,
        seat=seat,
        previous=previous,
        session_id=current["session_id"],
        source=current.get("runtime_session_source") or "current-process",
        confidence=current.get("runtime_session_confidence") or "exact",
        evidence=evidence,
        cwd=preserved_cwd,
        event="session_bound_current",
        extra={
            "cwd": preserved_cwd,
            "current_cwd": current.get("cwd"),
            "cross_check": current.get("cross_check"),
            "warning": current.get("warning"),
        },
    )


def _bind_registry_session(
    *,
    fleet: str,
    seat: str,
    previous: dict,
    session_id: str,
    source: str,
    confidence: str,
    evidence: dict,
    cwd: str | None,
    event: str,
    extra: dict | None = None,
) -> dict:
    from lib import registry, session_ledger

    updated = registry.upsert_agent({
        **previous,
        "name": seat,
        "fleet": fleet,
        "runtime": previous.get("runtime") or "codex",
        "session_id": session_id,
        "runtime_session_id": session_id,
        "runtime_session_source": source,
        "runtime_session_confidence": confidence,
        "runtime_session_evidence": evidence,
        "runtime_session_cwd": cwd,
        "registered": True,
    })
    session_ledger.append_record({
        "event": event,
        "seat": seat,
        "name": seat,
        "fleet": fleet,
        "runtime": updated.get("runtime"),
        "session_id": session_id,
        "runtime_session_id": session_id,
        "runtime_session_source": source,
        "runtime_session_confidence": confidence,
        "runtime_session_evidence": evidence,
        "cwd": cwd,
    })
    result = {
        "ok": True,
        "seat": seat,
        "fleet": fleet,
        "runtime": updated.get("runtime"),
        "session_id": session_id,
        "runtime_session_id": session_id,
        "runtime_session_source": source,
        "runtime_session_confidence": confidence,
        "registry_updated": True,
    }
    if extra:
        result.update(extra)
    return result

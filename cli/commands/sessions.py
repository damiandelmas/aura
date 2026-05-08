"""Show Aura runtime session identity map."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from commands import list as list_cmd
from lib import seat_schema


def run(args):
    if getattr(args, "sessions_action", None) == "latest":
        args = argparse.Namespace(
            **{
                **vars(args),
                "sessions_action": None,
            }
        )
    if getattr(args, "sessions_action", None) == "all":
        return _all_history(args)
    if getattr(args, "sessions_action", None) == "self":
        from lib import runtime_session

        return runtime_session.resolve_current_process(getattr(args, "runtime", None))
    if getattr(args, "sessions_action", None) == "seat-history":
        return _seat_history(args)
    if getattr(args, "sessions_action", None) == "bind-current":
        return _bind_current(args)
    if getattr(args, "sessions_action", None) == "bind-hook":
        return _bind_hook(args)
    if getattr(args, "sessions_action", None) == "bind-nonce":
        return _bind_nonce(args)
    if getattr(args, "sessions_action", None) == "restore-plan":
        return _restore_plan(args)
    if getattr(args, "sessions_action", None) == "fleets":
        return _fleets(args)
    if getattr(args, "sessions_action", None) == "fleet-history":
        from commands import fleets as fleets_cmd

        return fleets_cmd.fleet_history(getattr(args, "nonce", None) or getattr(args, "target", None) or getattr(args, "fleet", None))

    rows = list_cmd.run(argparse.Namespace(
        fleet=getattr(args, "fleet", None),
        status=None,
        mode=None,
        include_hidden=bool(getattr(args, "include_hidden", False)),
    ))
    live_only = bool(getattr(args, "live", False))
    mapped = []
    from lib import runtime_session, runtimes, session_ledger

    for row in rows:
        if live_only and row.get("terminal") != "alive":
            continue
        row = runtime_session.mark_binding(dict(row))
        seat = row.get("seat") or row.get("name") or row.get("agent")
        fleet = row.get("fleet")
        fleet_id = row.get("fleet_id")
        if fleet and not fleet_id:
            try:
                from lib import fleets as fleets_lib

                fleet_id = (fleets_lib.ensure_fleet(fleet) or {}).get("fleet_id")
            except Exception:
                fleet_id = None
        target = f"{fleet}:{seat}" if fleet and seat else None
        capability = runtimes.capabilities(row.get("runtime"))
        restore = session_ledger.restore_status(row, capability)
        mapped.append({
            "seat": seat,
            "fleet": fleet,
            "fleet_id": fleet_id,
            "target": target,
            "seat_ref": row.get("seat_ref") or target,
            "runtime": row.get("runtime"),
            "runtime_capabilities": capability,
            "status": row.get("status"),
            "terminal": row.get("terminal"),
            "hidden": bool(row.get("hidden")),
            "kind": row.get("kind"),
            "session_id": row.get("session_id"),
            "runtime_session_id": row.get("runtime_session_id"),
            "runtime_session_source": row.get("runtime_session_source") or row.get("runtime_session_env"),
            "runtime_session_binding": row.get("runtime_session_binding"),
            "runtime_session_bind_method": row.get("runtime_session_bind_method"),
            "runtime_session_bind_source": row.get("runtime_session_bind_source"),
            "runtime_session_evidence": row.get("runtime_session_evidence"),
            "runtime_session_diagnostics": row.get("runtime_session_diagnostics"),
            "runtime_session_possible_matches": row.get("runtime_session_possible_matches"),
            "aura_launch_id": row.get("aura_launch_id"),
            "seat_instance_id": row.get("seat_instance_id"),
            "pane_ref": row.get("pane_ref"),
            "cwd": row.get("runtime_session_cwd") or row.get("cwd") or row.get("workdir"),
            "identity_provider": seat_schema.identity_provider_for(row),
            "identity_id": seat_schema.identity_id_for(row),
            "identity_label": row.get("identity_label") or row.get("desks_current_name"),
            "desks_identity_id": row.get("desks_identity_id"),
            "flex_project_manifest": row.get("flex_project_manifest"),
            "flex_project_root": row.get("flex_project_root"),
            **restore,
        })
    with_session = [row for row in mapped if runtime_session.is_bound_session(row)]
    missing = [row for row in mapped if not runtime_session.is_bound_session(row)]
    by_binding = {}
    for row in mapped:
        key = row.get("runtime_session_binding") or ("bound" if runtime_session.is_bound_session(row) else "unbound")
        by_binding[key] = by_binding.get(key, 0) + 1
    return {
        "ok": True,
        "total": len(mapped),
        "with_session_id": len(with_session),
        "missing_session_id": len(missing),
        "by_binding": by_binding,
        "rows": mapped,
    }


def _all_history(args) -> dict:
    """Return Aura session/seat lifecycle history without restore-plan flags."""
    from lib import session_ledger

    fleet_filter = getattr(args, "fleet", None)
    limit = getattr(args, "limit", None)
    rows = []
    for record in session_ledger.iter_records():
        fleet = (
            record.get("fleet")
            or (record.get("after") or {}).get("fleet")
            or (record.get("before") or {}).get("fleet")
        )
        if not fleet:
            ref = record.get("seat_ref") or record.get("target") or ""
            if ":" in ref:
                fleet = ref.split(":", 1)[0]
        if fleet_filter and fleet != fleet_filter:
            continue
        rows.append(record)

    rows = list(reversed(rows))
    if limit:
        rows = rows[:limit]
    return {
        "ok": True,
        "schema": "aura.sessions_all.v1",
        "source": "session-ledger",
        "fleet": fleet_filter,
        "total": len(rows),
        "rows": rows,
    }


def _fleets(args) -> dict:
    """Roster of fleets: per-fleet live seat count, registry seat count, last lifecycle event."""
    from lib import fleets as fleets_lib, seat_status, session_ledger, terminal

    rows = seat_status.list_seat_statuses(include_hidden=True, terminal=terminal)

    def _new_bucket(fleet: str) -> dict:
        fleet_record = fleets_lib.ensure_fleet(fleet)
        return {
            "fleet_id": (fleet_record or {}).get("fleet_id"),
            "fleet": fleet,
            "tmux_session": (fleet_record or {}).get("tmux_session") or fleet,
            "registry_seats": 0,
            "live_seats": 0,
            "bound_seats": 0,
            "adopted_seats": 0,
            "last_event": None,
            "last_event_at": None,
            "last_event_target": None,
        }

    by_fleet: dict[str, dict] = {}
    for row in rows:
        fleet = row.get("fleet")
        if not fleet:
            continue
        bucket = by_fleet.setdefault(fleet, _new_bucket(fleet))
        bucket["registry_seats"] += 1
        if row.get("terminal") == "alive":
            bucket["live_seats"] += 1
        if row.get("runtime_session_binding") == "bound":
            bucket["bound_seats"] += 1
        if seat_schema.identity_id_for(row):
            bucket["adopted_seats"] += 1

    # Last event per fleet from session ledger
    for record in session_ledger.iter_records():
        fleet = record.get("fleet") or (record.get("after") or {}).get("fleet") or (record.get("before") or {}).get("fleet")
        if not fleet:
            ref = record.get("seat_ref") or ""
            if ":" in ref:
                fleet = ref.split(":", 1)[0]
        if not fleet:
            continue
        bucket = by_fleet.setdefault(fleet, _new_bucket(fleet))
        ts = record.get("timestamp")
        if ts and (bucket["last_event_at"] is None or ts > bucket["last_event_at"]):
            bucket["last_event_at"] = ts
            bucket["last_event"] = record.get("event")
            seat = record.get("seat") or record.get("name") or (record.get("after") or {}).get("seat") or (record.get("before") or {}).get("seat")
            bucket["last_event_target"] = f"{fleet}:{seat}" if seat else fleet

    fleets = sorted(by_fleet.values(), key=lambda b: (b["last_event_at"] or ""), reverse=True)
    live = [fleet for fleet in fleets if fleet.get("live_seats", 0) > 0]
    historical = [fleet for fleet in fleets if fleet.get("live_seats", 0) == 0]
    return {
        "ok": True,
        "schema": "aura.sessions_fleets.v1",
        "total_fleets": len(fleets),
        "live_count": len(live),
        "historical_count": len(historical),
        "live": live,
        "historical": historical,
        "fleets": fleets,
    }


def _restore_plan(args):
    from lib import runtimes, session_ledger

    if getattr(args, "from_ledger", False):
        rows = session_ledger.project_latest_from_ledger(fleet=getattr(args, "fleet", None))
        plan = session_ledger.restore_plan_from_rows(rows, runtimes.capability_map())
        plan["source"] = "ledger"
        plan["latest_per_seat"] = bool(getattr(args, "latest_per_seat", False))
        return plan

    rows_result = run(argparse.Namespace(
        sessions_action=None,
        fleet=getattr(args, "fleet", None),
        live=getattr(args, "live", False),
        include_hidden=getattr(args, "include_hidden", False),
    ))
    return session_ledger.restore_plan_from_rows(
        rows_result.get("rows", []),
        runtimes.capability_map(),
    )


def _seat_history(args) -> dict:
    target = getattr(args, "target", None) or getattr(args, "nonce", None)
    if not target:
        return {"ok": False, "error": "seat-history requires a target seat ref"}
    from lib import session_ledger

    rows = session_ledger.seat_history_for_target(
        target,
        limit=getattr(args, "limit", None),
        follow_aliases=not bool(getattr(args, "no_follow_aliases", False)),
    )
    return {
        "ok": True,
        "schema": "aura.sessions_seat_history.v1",
        "target": target,
        "total": len(rows),
        "rows": rows,
    }


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
        else:
            return {
                "ok": False,
                "error": "nonce matched Codex JSONL but not expected cwd",
                "nonce": nonce,
                "expected_cwd": expected_cwd,
                "matches": len(candidates),
                "jsonls": [candidate.get("jsonl") for candidate in candidates],
            }
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

    from lib import registry, runtime_session, session_ledger

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
    if not runtime_session.is_bound_session(current):
        return {
            "ok": False,
            "error": "current runtime session id is not bound; use bind-nonce fallback",
            "current": current,
        }

    fleet, seat = _target_fleet_seat(getattr(args, "target", None))
    fleet = fleet or current.get("fleet")
    seat = seat or current.get("seat")
    if not fleet or not seat:
        return {"ok": False, "error": "could not infer target fleet/seat; pass --target fleet:seat", "current": current}

    from lib import registry

    fleet, seat, previous, alias_chain = _canonical_bind_target(registry, fleet=fleet, seat=seat)
    previous = previous or {
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
            "alias_chain": alias_chain,
        },
    )


def _normalize_hook_event(event: str | None) -> str:
    if not event:
        return "session-start"
    normalized = str(event).strip().replace("_", "-")
    out = []
    for index, char in enumerate(normalized):
        if char.isupper() and index and normalized[index - 1] not in "-":
            out.append("-")
        out.append(char.lower())
    return "".join(out).strip("-") or "session-start"


def _bind_hook(args) -> dict:
    session_id = getattr(args, "session_id", None) or getattr(args, "nonce", None)
    if not session_id:
        return {"ok": False, "error": "bind-hook requires --session-id"}

    runtime = getattr(args, "runtime", None) or os.environ.get("AURA_RUNTIME") or "codex"
    if runtime != "codex":
        return {
            "ok": False,
            "error": "bind-hook currently supports codex runtime only",
            "runtime": runtime,
        }

    fleet, seat = _target_fleet_seat(getattr(args, "target", None))
    if not fleet or not seat:
        return {"ok": False, "error": "could not infer target fleet/seat; pass --target fleet:seat"}

    from lib import registry

    fleet, seat, previous, alias_chain = _canonical_bind_target(registry, fleet=fleet, seat=seat)
    if not previous:
        return {
            "ok": False,
            "error": "target seat is not registered; adopt or spawn it before hook binding",
            "target": f"{fleet}:{seat}",
        }

    expected_instance = getattr(args, "seat_instance_id", None)
    actual_instance = previous.get("seat_instance_id")
    if expected_instance and actual_instance and expected_instance != actual_instance:
        return {
            "ok": False,
            "error": "seat-instance-mismatch",
            "target": f"{fleet}:{seat}",
            "expected_seat_instance_id": expected_instance,
            "actual_seat_instance_id": actual_instance,
        }

    hook_event = _normalize_hook_event(getattr(args, "hook_event", None))
    source = f"codex-hook:{hook_event}"
    transcript_path = getattr(args, "transcript_path", None)
    cwd = previous.get("runtime_session_cwd") or previous.get("cwd") or previous.get("workdir")
    evidence = {
        "reason": "codex-native-hook",
        "hook_event": getattr(args, "hook_event", None) or hook_event,
        "transcript_path": transcript_path,
        "seat_instance_id": actual_instance,
        "aura_launch_id": previous.get("aura_launch_id"),
    }
    event_name = "session_bound_hook"
    return _bind_registry_session(
        fleet=fleet,
        seat=seat,
        previous=previous,
        session_id=session_id,
        source=source,
        confidence="exact",
        evidence={key: value for key, value in evidence.items() if value is not None},
        cwd=cwd,
        event=event_name,
        extra={
            "target": f"{fleet}:{seat}",
            "transcript_path": transcript_path,
            "alias_chain": alias_chain,
        },
    )


def _canonical_bind_target(registry, *, fleet: str, seat: str) -> tuple[str, str, dict | None, list[str]]:
    requested_ref = registry.seat_ref(fleet, seat)
    resolved, chain = registry.resolve_alias(requested_ref)
    if chain:
        target_fleet, target_seat = registry.split_ref(resolved)
        if target_fleet and target_seat:
            previous = registry.get_agent(resolved)
            if previous:
                return target_fleet, target_seat, previous, chain

    previous = registry.get_agent(seat, fleet=fleet)
    if previous and previous.get("resolved_from"):
        current_ref = previous.get("seat_ref") or registry.seat_ref(previous.get("fleet"), previous.get("name") or previous.get("seat") or seat)
        target_fleet, target_seat = registry.split_ref(current_ref)
        if target_fleet and target_seat:
            return target_fleet, target_seat, previous, list(previous.get("alias_chain") or [])
    return fleet, seat, previous, []


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
    from lib import desks_sessions, registry, runtime_session, session_ledger

    updated = registry.upsert_agent({
        **previous,
        "name": seat,
        "fleet": fleet,
        "runtime": previous.get("runtime") or "codex",
        "session_id": session_id,
        "runtime_session_id": session_id,
        "runtime_session_source": source,
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": runtime_session.binding_method_for_source(source),
        "runtime_session_bind_source": source,
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
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": runtime_session.binding_method_for_source(source),
        "runtime_session_bind_source": source,
        "runtime_session_confidence": confidence,
        "runtime_session_evidence": evidence,
        "cwd": cwd,
    })
    session_ledger.append_seat_event(
        event=event,
        before=previous,
        after=updated,
        evidence=evidence,
        source_command=f"aura sessions {event.removeprefix('session_').replace('_', '-')}",
        cwd=cwd,
    )
    identity_provider = seat_schema.identity_provider_for(updated) or seat_schema.identity_provider_for(previous)
    identity_id = seat_schema.identity_id_for(updated) or seat_schema.identity_id_for(previous)
    desks_result = desks_sessions.append_identity_session(
        identity_id if identity_provider == "desks" else None,
        session_id,
    )
    result = {
        "ok": True,
        "seat": seat,
        "fleet": fleet,
        "runtime": updated.get("runtime"),
        "session_id": session_id,
        "runtime_session_id": session_id,
        "runtime_session_source": source,
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": runtime_session.binding_method_for_source(source),
        "runtime_session_bind_source": source,
        "runtime_session_confidence": confidence,
        "registry_updated": True,
        "desks_session_recorded": bool(desks_result.get("ok")),
    }
    if desks_result.get("ok") or not desks_result.get("skipped"):
        result["desks_session"] = desks_result
    if extra:
        result.update(extra)
    return result

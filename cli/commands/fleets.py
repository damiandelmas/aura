"""Stable fleet identity and history commands."""

from __future__ import annotations

import shlex
from typing import Any

from commands import list as list_cmd
from lib import seat_schema


def run(args) -> dict:
    action = getattr(args, "fleets_action", None)
    if action == "list":
        return _list()
    if action == "resolve":
        return _resolve(getattr(args, "target", None))
    if action == "history":
        return fleet_history(getattr(args, "target", None))
    return {"ok": False, "error": f"unknown fleets action: {action}"}


def _quote(value: Any) -> str:
    return shlex.quote(str(value))


def _known_fleet_names() -> list[str]:
    from lib import registry, session_ledger

    names = set()
    for row in registry.read_registry().values():
        if row.get("fleet"):
            names.add(str(row["fleet"]))
    for row in session_ledger.iter_records():
        fleet = row.get("fleet") or (row.get("after") or {}).get("fleet") or (row.get("before") or {}).get("fleet")
        if not fleet:
            ref = row.get("seat_ref") or ""
            if ":" in ref:
                fleet = ref.split(":", 1)[0]
        if fleet:
            names.add(str(fleet))
    return sorted(names)


def _list() -> dict:
    from lib import fleets

    fleets.ensure_many(_known_fleet_names())
    rows = fleets.list_fleets()
    return {
        "ok": True,
        "schema": "aura.fleets_list.v1",
        "total": len(rows),
        "rows": rows,
    }


def _resolve(target: str | None) -> dict:
    from lib import fleets

    if not target:
        return {"ok": False, "error": "target required"}
    record = fleets.resolve(target)
    if not record and not str(target).startswith("f_"):
        record = fleets.ensure_fleet(target)
    if not record:
        return {"ok": False, "error": "fleet not found", "target": target}
    return {
        "ok": True,
        "schema": "aura.fleet_resolve.v1",
        "target": target,
        "fleet": record,
    }


def _row_fleet(row: dict) -> str | None:
    fleet = row.get("fleet") or (row.get("after") or {}).get("fleet") or (row.get("before") or {}).get("fleet")
    if not fleet:
        ref = row.get("seat_ref") or ""
        if ":" in ref:
            fleet = ref.split(":", 1)[0]
    return str(fleet) if fleet else None


def _row_seat(row: dict) -> str | None:
    seat = (
        row.get("seat")
        or row.get("name")
        or (row.get("after") or {}).get("seat")
        or (row.get("after") or {}).get("name")
        or (row.get("before") or {}).get("seat")
        or (row.get("before") or {}).get("name")
    )
    if seat and ":" in str(seat) and not str(seat).startswith("tmux:"):
        return str(seat).split(":", 1)[1]
    return seat


def _snapshot(row: dict) -> dict:
    from lib import session_ledger

    after = row.get("after") if isinstance(row.get("after"), dict) else None
    before = row.get("before") if isinstance(row.get("before"), dict) else None
    snap = session_ledger.snapshot_seat(after) or session_ledger.snapshot_seat(row) or session_ledger.snapshot_seat(before) or {}
    if row.get("timestamp") and not snap.get("latest_event_at"):
        snap["latest_event_at"] = row.get("timestamp")
    if row.get("event") and not snap.get("latest_event"):
        snap["latest_event"] = row.get("event")
    return snap


def _restore_command(*, fleet_ref: str, seat: str, runtime: str, cwd: str, session_id: str) -> str:
    return " ".join([
        "aura",
        "spawn",
        _quote(seat),
        "--fleet-id",
        _quote(fleet_ref),
        "--runtime",
        _quote(runtime),
        "--cwd",
        _quote(cwd),
        "--resume-session",
        _quote(session_id),
        "--as-pane",
    ])


def fleet_history(target: str | None) -> dict:
    from lib import fleets, runtime_session, runtimes, session_ledger

    if not target:
        return {"ok": False, "error": "fleet target required"}

    fleet_name, fleet_record = fleets.resolve_name_or_id(target)
    if not fleet_record and fleet_name:
        fleet_record = fleets.ensure_fleet(fleet_name)
    if not fleet_name:
        return {"ok": False, "error": "fleet not found", "target": target}

    fleet_id = (fleet_record or {}).get("fleet_id")
    inventory = list_cmd.run(type("Args", (), {
        "fleet": fleet_name,
        "status": None,
        "mode": None,
        "include_hidden": True,
    })())
    live_rows = inventory.get("rows", inventory) if isinstance(inventory, dict) else inventory
    current_by_seat = {}
    for row in live_rows:
        seat = row.get("seat") or row.get("name")
        if seat:
            current_by_seat[seat] = runtime_session.mark_binding(dict(row))

    all_events = [row for row in session_ledger.iter_records() if _row_fleet(row) == fleet_name]
    by_seat: dict[str, dict] = {}
    for row in all_events:
        seat = _row_seat(row)
        if not seat:
            continue
        bucket = by_seat.setdefault(seat, {
            "seat": seat,
            "events": 0,
            "first_seen_at": None,
            "last_seen_at": None,
            "last_event": None,
            "last_event_at": None,
            "last_restore_candidate": None,
        })
        ts = row.get("timestamp")
        bucket["events"] += 1
        if ts and (bucket["first_seen_at"] is None or ts < bucket["first_seen_at"]):
            bucket["first_seen_at"] = ts
        if ts and (bucket["last_seen_at"] is None or ts > bucket["last_seen_at"]):
            bucket["last_seen_at"] = ts
            bucket["last_event"] = row.get("event")
            bucket["last_event_at"] = ts

        snap = _snapshot(row)
        capability = runtimes.capabilities(snap.get("runtime"))
        binding = runtime_session.mark_binding(dict(snap))
        session_id = binding.get("runtime_session_id") or binding.get("session_id")
        if session_ledger.is_keeper_thread_id(session_id):
            continue
        cwd = binding.get("cwd") or binding.get("workdir")
        if (
            session_id
            and cwd
            and binding.get("runtime_session_binding") == "bound"
            and capability.get("supports_resume")
            and snap.get("runtime")
        ):
            bucket["last_restore_candidate"] = {
                "runtime": snap.get("runtime"),
                "cwd": cwd,
                "runtime_session_id": session_id,
                "runtime_session_binding": binding.get("runtime_session_binding"),
                "seat_instance_id": snap.get("seat_instance_id"),
                "identity_provider": seat_schema.identity_provider_for(snap),
                "identity_id": seat_schema.identity_id_for(snap),
                "identity_label": snap.get("identity_label"),
                "source_event": row.get("event"),
                "source_event_at": ts,
            }

    seats = []
    restore_commands = []
    for seat in sorted(set(by_seat) | set(current_by_seat)):
        history = by_seat.get(seat) or {"seat": seat, "events": 0}
        current = current_by_seat.get(seat)
        candidate = history.get("last_restore_candidate")
        restore = {"ready": False, "reason": "no-bound-resume-candidate"}
        if candidate:
            restore = {
                "ready": True,
                "reason": "bound-session-id-and-runtime-resume-supported",
                "command": _restore_command(
                    fleet_ref=fleet_id or fleet_name,
                    seat=seat,
                    runtime=candidate["runtime"],
                    cwd=candidate["cwd"],
                    session_id=candidate["runtime_session_id"],
                ),
            }
            if candidate.get("identity_id"):
                bind_parts = [
                    f"--set identity_provider={_quote(candidate.get('identity_provider') or 'desks')}",
                    f"--set identity_id={_quote(candidate['identity_id'])}",
                ]
                if candidate.get("identity_label"):
                    bind_parts.append(f"--set identity_label={_quote(candidate['identity_label'])}")
                restore["post_bind_command"] = (
                    f"aura seat tag {_quote(fleet_name + ':' + seat)} "
                    + " ".join(bind_parts)
                )
            restore_commands.append(restore["command"])
            if restore.get("post_bind_command"):
                restore_commands.append(restore["post_bind_command"])
        seats.append({
            "seat": seat,
            "current": {
                "registered": bool(current),
                "live": current.get("terminal") == "alive" if current else False,
                "runtime": current.get("runtime") if current else None,
                "cwd": (current.get("runtime_session_cwd") or current.get("cwd") or current.get("workdir")) if current else None,
                "runtime_session_id": (current.get("runtime_session_id") or current.get("session_id")) if current else None,
                "runtime_session_binding": current.get("runtime_session_binding") if current else None,
                "identity_provider": seat_schema.identity_provider_for(current) if current else None,
                "identity_id": seat_schema.identity_id_for(current) if current else None,
                "identity_label": current.get("identity_label") if current else None,
                "pane_ref": current.get("pane_ref") if current else None,
            },
            "history": {k: v for k, v in history.items() if k not in {"last_restore_candidate"}},
            "restore": restore,
        })

    live_count = sum(1 for row in seats if row["current"]["live"])
    ready_count = sum(1 for row in seats if row["restore"]["ready"])
    state = "live" if live_count else "historical"
    latest = None
    for row in all_events:
        if row.get("timestamp") and (latest is None or row["timestamp"] > latest.get("timestamp", "")):
            latest = row
    return {
        "ok": True,
        "schema": "aura.sessions_fleet_history.v1",
        "target": target,
        "fleet": fleet_name,
        "fleet_id": fleet_id,
        "fleet_record": fleet_record,
        "state": state,
        "summary": {
            "known_seats": len(seats),
            "live_seats": live_count,
            "restore_ready_seats": ready_count,
            "events": len(all_events),
            "last_event": latest.get("event") if latest else None,
            "last_event_at": latest.get("timestamp") if latest else None,
            "last_event_target": f"{fleet_name}:{_row_seat(latest)}" if latest and _row_seat(latest) else fleet_name,
        },
        "seats": seats,
        "restore_plan": {
            "ready": bool(seats) and ready_count == len(seats),
            "ready_seats": ready_count,
            "needs_review": len(seats) - ready_count,
            "commands": restore_commands,
        },
    }

"""Stable fleet identity and history commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import shlex
import tempfile
from typing import Any

from lib import seat_schema


def run(args) -> dict:
    action = getattr(args, "fleets_action", None)
    if action == "list":
        return _list()
    if action == "resolve":
        return _resolve(getattr(args, "target", None))
    if action == "history":
        return fleet_history(getattr(args, "target", None))
    if action == "rename":
        return _rename(
            getattr(args, "old", None),
            getattr(args, "new", None),
            dry_run=bool(getattr(args, "dry_run", False) or not getattr(args, "confirm", False)),
            confirm=bool(getattr(args, "confirm", False)),
            reason=getattr(args, "reason", None),
        )
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


def _run_tmux(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def _tmux_session_exists(name: str) -> bool:
    return _run_tmux(["has-session", "-t", name]).returncode == 0


def _tmux_live_keys() -> set[tuple[str, str]]:
    from lib import tmux_mirror

    mirror = tmux_mirror.list_physical_panes()
    if not mirror.get("ok"):
        return set()
    keys = set()
    for pane in mirror.get("panes") or []:
        session = pane.get("tmux_session") or pane.get("physical_fleet") or pane.get("session_name") or pane.get("session")
        pane_id = pane.get("pane_id")
        if session and pane_id:
            keys.add((str(session), str(pane_id)))
    return keys


def _pane_ref_key(value: Any) -> tuple[str | None, str | None]:
    from lib import pane_handle
    return pane_handle.pane_ref_parts(value)


def _replace_ref(value: Any, *, old: str, new: str, seats: set[str] | None = None) -> Any:
    if not isinstance(value, str):
        return value
    if value == old:
        return new
    prefix = f"{old}:"
    if value.startswith(prefix):
        seat = value[len(prefix):]
        if seats is None or seat in seats:
            return f"{new}:{seat}"
    tmux_prefix = f"tmux:{old}:"
    if value.startswith(tmux_prefix):
        return f"tmux:{new}:{value[len(tmux_prefix):]}"
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _rewrite_placements(*, old: str, new: str, moved_seats: set[str], dry_run: bool) -> list[dict[str, Any]]:
    from lib import placements

    data = placements.read_placements()
    changed = []
    for pid, record in data.items():
        mutated = False
        members = []
        for member in record.get("members") or []:
            updated = dict(member)
            before = dict(updated)
            updated["seat_ref"] = _replace_ref(updated.get("seat_ref"), old=old, new=new, seats=moved_seats)
            if updated.get("logical_fleet") == old:
                seat = updated.get("logical_seat") or str(before.get("seat_ref") or "").split(":", 1)[-1]
                if seat in moved_seats:
                    updated["logical_fleet"] = new
            if updated.get("physical_fleet") == old:
                seat = updated.get("logical_seat") or str(before.get("seat_ref") or "").split(":", 1)[-1]
                if seat in moved_seats:
                    updated["physical_fleet"] = new
            updated["pane_ref"] = _replace_ref(updated.get("pane_ref"), old=old, new=new, seats=None)
            mutated = mutated or updated != before
            members.append(updated)
        if mutated:
            record["members"] = sorted(members, key=lambda m: m.get("seat_ref") or "")
            changed.append({"placement_id": pid, "name": record.get("name"), "members": len(members)})
    if changed and not dry_run:
        placements.write_placements(data)
    return changed


def _rewrite_queue(*, old: str, new: str, moved_seats: set[str], dry_run: bool) -> list[dict[str, Any]]:
    from lib import queued_messages

    changed = []
    for record in queued_messages.list_records():
        if record.get("status") not in {"pending", "scheduled", "release_failed"}:
            continue
        updated = dict(record)
        before = dict(updated)
        for key in ("target", "sender"):
            updated[key] = _replace_ref(updated.get(key), old=old, new=new, seats=moved_seats)
        if updated != before:
            changed.append({"queue_id": record.get("queue_id"), "status": record.get("status")})
            if not dry_run:
                queued_messages.save(updated)
    return changed


def _rewrite_events(*, old: str, new: str, moved_seats: set[str], dry_run: bool) -> list[dict[str, Any]]:
    from lib import events

    changed = []
    for job in events.iter_jobs():
        if job.get("status") not in {"running", "paused"}:
            continue
        updated = dict(job)
        before = dict(updated)
        for key in ("target", "sender"):
            updated[key] = _replace_ref(updated.get(key), old=old, new=new, seats=moved_seats)
        if updated != before:
            changed.append({"job_id": job.get("job_id"), "name": job.get("name"), "status": job.get("status")})
            if not dry_run:
                events.save_state(updated)
    return changed


def _rewrite_report_subscriptions(*, old: str, new: str, moved_seats: set[str], dry_run: bool) -> list[dict[str, Any]]:
    from lib import report_subscriptions

    changed = []
    for record in report_subscriptions.list_records(include_removed=True):
        if record.get("status") not in {"active", "paused"}:
            continue
        updated = dict(record)
        before = dict(updated)
        if updated.get("fleet") == old:
            updated["fleet"] = new
        for key in ("target", "to", "sender"):
            updated[key] = _replace_ref(updated.get(key), old=old, new=new, seats=moved_seats)
        if updated != before:
            changed.append({"subscription_id": record.get("subscription_id"), "name": record.get("name"), "status": record.get("status")})
            if not dry_run:
                report_subscriptions.save(updated)
    return changed


def _rewrite_discord_bindings(*, old: str, new: str, moved_seats: set[str], dry_run: bool) -> list[dict[str, Any]]:
    from lib import state

    path = state.state_root() / "discord" / "channel-bindings.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [{"path": str(path), "warning": "discord-bindings-unreadable"}]
    if not isinstance(data, dict):
        return [{"path": str(path), "warning": "discord-bindings-unknown-shape"}]

    changed = []
    bindings = data.get("bindings") if isinstance(data.get("bindings"), dict) else data
    if isinstance(bindings, dict):
        for channel, binding in bindings.items():
            if not isinstance(binding, dict):
                continue
            before = json.dumps(binding, sort_keys=True)
            for key in ("default_target", "target", "aura_target"):
                binding[key] = _replace_ref(binding.get(key), old=old, new=new, seats=moved_seats)
            aliases = binding.get("aliases")
            if isinstance(aliases, dict):
                for alias, value in list(aliases.items()):
                    aliases[alias] = _replace_ref(value, old=old, new=new, seats=moved_seats)
            after = json.dumps(binding, sort_keys=True)
            if after != before:
                changed.append({"channel": channel})
    if changed and not dry_run:
        _atomic_write_json(path, data)
    return changed


def _package_manifest_path(row: dict[str, Any]) -> Path | None:
    root = row.get("agent_package_root")
    if root:
        path = Path(str(root)).expanduser() / "manifest.json"
        if path.exists():
            return path
    package_id = row.get("agent_package_id") or row.get("identity_id")
    if package_id and str(package_id).startswith("i_"):
        from lib import agent_packages

        path = agent_packages.package_root(str(package_id)) / "manifest.json"
        if path.exists():
            return path
    return None


def _rewrite_package_manifests(*, rows: list[dict[str, Any]], old: str, new: str, dry_run: bool) -> list[dict[str, Any]]:
    changed = []
    seen: set[str] = set()
    for row in rows:
        path = _package_manifest_path(row)
        if not path or str(path) in seen:
            continue
        seen.add(str(path))
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            changed.append({"path": str(path), "warning": "manifest-unreadable"})
            continue
        if not isinstance(payload, dict):
            changed.append({"path": str(path), "warning": "manifest-unknown-shape"})
            continue
        before = dict(payload)
        for key in ("fleet", "default_fleet"):
            if payload.get(key) == old:
                payload[key] = new
        if payload != before:
            changed.append({"path": str(path), "agent_package_id": row.get("agent_package_id") or row.get("identity_id")})
            if not dry_run:
                _atomic_write_json(path, payload)
    return changed


def _rewrite_live_registry(*, old: str, new: str, live_keys: set[tuple[str, str]], fleet_id: str | None, dry_run: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from lib import registry

    data = registry.read_registry()
    moved: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    rewritten = dict(data)
    aliases = []
    for ref, row in sorted(data.items()):
        if row.get("fleet") != old:
            continue
        pane_session, pane_id = _pane_ref_key(row.get("pane_ref"))
        live = bool(pane_session == old and pane_id and (old, pane_id) in live_keys)
        seat = row.get("seat") or row.get("name")
        if not live:
            kept.append({"ref": ref, "reason": "historical-or-missing-pane"})
            continue
        if not seat:
            kept.append({"ref": ref, "reason": "missing-seat-name"})
            continue
        new_ref = f"{new}:{seat}"
        if new_ref in data and new_ref != ref:
            raise ValueError(f"target seat already exists: {new_ref}")
        updated = dict(row)
        updated["fleet"] = new
        updated["logical_fleet"] = new
        updated["logical_ref"] = new_ref
        updated["seat_ref"] = new_ref
        updated["target"] = new_ref
        updated["physical_fleet"] = new
        updated["pane_ref"] = _replace_ref(updated.get("pane_ref"), old=old, new=new)
        updated["terminal_ref"] = f"{new}:{seat}"
        updated["backend_ref"] = f"{new}:{seat}"
        if fleet_id:
            updated["fleet_id"] = fleet_id
        updated["last_seen"] = registry.now_iso()
        rewritten.pop(ref, None)
        rewritten[new_ref] = updated
        moved.append({"source": ref, "target": new_ref, "seat": seat, "pane_ref": updated.get("pane_ref"), "record": updated})
        aliases.append({"source": ref, "target": new_ref})
    if moved and not dry_run:
        registry.write_registry(rewritten)
        for alias in aliases:
            registry.add_alias(alias["source"], alias["target"], reason="fleet-rename")
    return moved, kept


def _update_fleet_registry(*, old: str, new: str, dry_run: bool) -> dict[str, Any]:
    from lib import fleets

    data = fleets.read_fleets()
    old_record = fleets.resolve(old)
    if not old_record:
        if dry_run:
            old_record = {
                "schema": "aura.fleet.v1",
                "fleet_id": None,
                "current_name": old,
                "aliases": [],
                "tmux_session": old,
            }
        else:
            old_record = fleets.ensure_fleet(old)
    if not old_record:
        raise ValueError(f"fleet not found: {old}")
    fleet_id = old_record.get("fleet_id")
    existing_new = fleets.resolve(new)
    if existing_new and (not fleet_id or existing_new.get("fleet_id") != fleet_id):
        raise ValueError(f"target fleet already exists: {new}")
    updated = dict(old_record)
    aliases = list(updated.get("aliases") or [])
    if old not in aliases:
        aliases.append(old)
    updated["aliases"] = sorted(set(aliases))
    updated["current_name"] = new
    updated["tmux_session"] = new
    updated["last_seen_at"] = fleets.now_iso()
    if not dry_run:
        data[fleet_id] = updated
        fleets.write_fleets(data)
    return updated


def _rename(old: str | None, new: str | None, *, dry_run: bool, confirm: bool, reason: str | None = None) -> dict:
    if not old or not new:
        return {"ok": False, "error": "usage", "detail": "rename requires OLD and NEW fleet names"}
    if ":" in old or ":" in new:
        return {"ok": False, "error": "fleet-name-must-not-contain-colon"}
    if old == new:
        return {"ok": True, "renamed": False, "source": old, "target": new, "dry_run": dry_run}
    if _tmux_session_exists(new):
        return {"ok": False, "error": "target-tmux-session-exists", "target": new}
    if not _tmux_session_exists(old):
        return {"ok": False, "error": "source-tmux-session-missing", "source": old}

    try:
        fleet_record = _update_fleet_registry(old=old, new=new, dry_run=True)
        live_keys = _tmux_live_keys()
        moved, kept = _rewrite_live_registry(
            old=old,
            new=new,
            live_keys=live_keys,
            fleet_id=fleet_record.get("fleet_id"),
            dry_run=True,
        )
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    moved_records = [row["record"] for row in moved]
    moved_seats = {str(row["seat"]) for row in moved if row.get("seat")}
    plan = {
        "tmux": {"rename_session": {"source": old, "target": new}},
        "fleet": fleet_record,
        "moved": [{k: v for k, v in row.items() if k != "record"} for row in moved],
        "kept": kept,
        "active_refs": {
            "placements": _rewrite_placements(old=old, new=new, moved_seats=moved_seats, dry_run=True),
            "queue": _rewrite_queue(old=old, new=new, moved_seats=moved_seats, dry_run=True),
            "events": _rewrite_events(old=old, new=new, moved_seats=moved_seats, dry_run=True),
            "report_subscriptions": _rewrite_report_subscriptions(old=old, new=new, moved_seats=moved_seats, dry_run=True),
            "discord_bindings": _rewrite_discord_bindings(old=old, new=new, moved_seats=moved_seats, dry_run=True),
        },
        "package_manifests": _rewrite_package_manifests(rows=moved_records, old=old, new=new, dry_run=True),
        "reason": reason or "Rename live fleet topology.",
        "warnings": [
            "running process env may still contain the old AURA_FLEET until restart/rollover; alias canonicalization preserves address resolution",
            "historical ledgers, reports, deliveries, and runtime-native transcripts are not rewritten",
        ],
    }
    if dry_run or not confirm:
        return {
            "ok": True,
            "schema": "aura.fleet_rename_plan.v1",
            "dry_run": True,
            "source": old,
            "target": new,
            "plan": plan,
        }

    tmux = _run_tmux(["rename-session", "-t", old, new])
    if tmux.returncode != 0:
        return {"ok": False, "error": tmux.stderr.strip() or "tmux rename-session failed", "plan": plan}
    try:
        applied_fleet = _update_fleet_registry(old=old, new=new, dry_run=False)
        moved, kept = _rewrite_live_registry(
            old=old,
            new=new,
            live_keys=live_keys,
            fleet_id=applied_fleet.get("fleet_id"),
            dry_run=False,
        )
        moved_records = [row["record"] for row in moved]
        moved_seats = {str(row["seat"]) for row in moved if row.get("seat")}
        active_refs = {
            "placements": _rewrite_placements(old=old, new=new, moved_seats=moved_seats, dry_run=False),
            "queue": _rewrite_queue(old=old, new=new, moved_seats=moved_seats, dry_run=False),
            "events": _rewrite_events(old=old, new=new, moved_seats=moved_seats, dry_run=False),
            "report_subscriptions": _rewrite_report_subscriptions(old=old, new=new, moved_seats=moved_seats, dry_run=False),
            "discord_bindings": _rewrite_discord_bindings(old=old, new=new, moved_seats=moved_seats, dry_run=False),
        }
        manifests = _rewrite_package_manifests(rows=moved_records, old=old, new=new, dry_run=False)
        fleet_event = None
        try:
            from lib import session_ledger

            fleet_event = session_ledger.append_fleet_event(
                event="fleet_renamed",
                fleet=new,
                fleet_id=applied_fleet.get("fleet_id"),
                before={"fleet": old, "current_name": old, "tmux_session": old},
                after=applied_fleet,
                evidence={
                    "source_fleet": old,
                    "target_fleet": new,
                    "tmux": {"rename_session": {"source": old, "target": new}},
                    "moved": [{k: v for k, v in row.items() if k != "record"} for row in moved],
                    "kept": kept,
                    "active_refs": active_refs,
                    "package_manifests": manifests,
                },
                movement_kind="fleet-rename",
                subject=f"{old}->{new}",
                reason=plan["reason"],
                source_command="aura fleets rename",
                source_ref=old,
                target_ref=new,
            )
            for row in moved:
                session_ledger.append_seat_event(
                    event="seat_readdressed",
                    before={"fleet": old, "seat": row.get("seat"), "seat_ref": row.get("source")},
                    after=row.get("record"),
                    evidence={"source_fleet": old, "target_fleet": new, "fleet_id": applied_fleet.get("fleet_id")},
                    source_command="aura fleets rename",
                    source_ref=row.get("source"),
                    target_ref=row.get("target"),
                )
        except Exception:
            pass
    except Exception as exc:
        return {"ok": False, "error": f"fleet registry rewrite failed after tmux rename: {exc}", "tmux_renamed": True}
    try:  # membership: the group readdressed → seats re-orient to the new fleet name
        from lib import membership

        membership.emit_membership_change(f"fleet:{new}", "rename", f"fleet:{new}")
    except Exception:
        pass
    return {
        "ok": True,
        "schema": "aura.fleet_rename.v1",
        "dry_run": False,
        "renamed": True,
        "source": old,
        "target": new,
        "fleet": applied_fleet,
        "moved": [{k: v for k, v in row.items() if k != "record"} for row in moved],
        "kept": kept,
        "active_refs": active_refs,
        "package_manifests": manifests,
        "fleet_event": fleet_event,
        "warnings": plan["warnings"],
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
    from lib import fleets, registry, runtime_session, runtimes, seat_status, session_ledger, tmux_mirror

    if not target:
        return {"ok": False, "error": "fleet target required"}

    fleet_name, fleet_record = fleets.resolve_name_or_id(target)
    if not fleet_record and fleet_name:
        fleet_record = fleets.ensure_fleet(fleet_name)
    if not fleet_name:
        return {"ok": False, "error": "fleet not found", "target": target}

    fleet_id = (fleet_record or {}).get("fleet_id")
    live_rows = seat_status.list_seat_statuses(fleet=fleet_name, include_hidden=True)
    current_by_seat = {}
    for row in live_rows:
        seat = row.get("seat") or row.get("name")
        if seat:
            current_by_seat[seat] = runtime_session.mark_binding(dict(row))

    mirror = tmux_mirror.list_physical_panes()
    physical_panes = [
        row for row in mirror.get("panes", [])
        if row.get("tmux_session") == fleet_name or row.get("physical_fleet") == fleet_name
    ] if mirror.get("ok") else []
    registry_rows = registry.list_agents(fleet_name, include_hidden=True)
    joined = tmux_mirror.join_managed(physical_panes, registry_rows) if mirror.get("ok") else {"panes": [], "missing_managed": []}
    unmanaged_physical = [
        {
            "pane_ref": row.get("pane_ref"),
            "terminal_ref": row.get("terminal_ref"),
            "window_name": row.get("window_name"),
            "pane_current_command": row.get("pane_current_command"),
            "pane_current_path": row.get("pane_current_path"),
        }
        for row in joined.get("panes", [])
        if row.get("managed_state") == "unmanaged"
    ]

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
                "liveness": current.get("liveness") if current else None,
                "managed_state": current.get("managed_state") if current else None,
                "runtime": current.get("runtime") if current else None,
                "cwd": (current.get("runtime_session_cwd") or current.get("cwd") or current.get("workdir")) if current else None,
                "runtime_session_id": (current.get("runtime_session_id") or current.get("session_id")) if current else None,
                "runtime_session_binding": current.get("runtime_session_binding") if current else None,
                "identity_provider": seat_schema.identity_provider_for(current) if current else None,
                "identity_id": seat_schema.identity_id_for(current) if current else None,
                "identity_label": current.get("identity_label") if current else None,
                "pane_ref": current.get("pane_ref") if current else None,
                "risk_flags": current.get("risk_flags") if current else [],
            },
            "history": {k: v for k, v in history.items() if k not in {"last_restore_candidate"}},
            "restore": restore,
        })

    live_count = sum(1 for row in seats if row["current"]["live"])
    registered_unbound_count = sum(
        1 for row in seats
        if row["current"]["registered"] and row["current"]["runtime_session_binding"] != "bound"
    )
    stale_registry_count = sum(
        1 for row in seats
        if row["current"]["registered"] and row["current"]["liveness"] == "missing"
    )
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
            "registered_unbound": registered_unbound_count,
            "stale_registry": stale_registry_count,
            "unmanaged_physical": len(unmanaged_physical),
            "restore_ready_seats": ready_count,
            "events": len(all_events),
            "last_event": latest.get("event") if latest else None,
            "last_event_at": latest.get("timestamp") if latest else None,
            "last_event_target": f"{fleet_name}:{_row_seat(latest)}" if latest and _row_seat(latest) else fleet_name,
        },
        "current_source": "seat-status-live-topology",
        "discrepancies": {
            "mirror_available": bool(mirror.get("ok")),
            "unmanaged_physical": unmanaged_physical,
            "stale_registry": [
                {
                    "seat": row["seat"],
                    "pane_ref": row["current"]["pane_ref"],
                    "managed_state": row["current"]["managed_state"],
                    "risk_flags": row["current"]["risk_flags"],
                }
                for row in seats
                if row["current"]["registered"] and row["current"]["liveness"] == "missing"
            ],
            "registered_unbound": [
                {
                    "seat": row["seat"],
                    "runtime": row["current"]["runtime"],
                    "managed_state": row["current"]["managed_state"],
                    "risk_flags": row["current"]["risk_flags"],
                }
                for row in seats
                if row["current"]["registered"] and row["current"]["runtime_session_binding"] != "bound"
            ],
        },
        "seats": seats,
        "restore_plan": {
            "ready": bool(seats) and ready_count == len(seats),
            "ready_seats": ready_count,
            "needs_review": len(seats) - ready_count,
            "commands": restore_commands,
        },
    }

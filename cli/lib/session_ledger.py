"""Durable Aura session ledger and restore planning helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid

from lib import runtime_session, state


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_event_id() -> str:
    return f"aura-seat-history-{uuid.uuid4().hex[:12]}"


def ledger_path() -> Path:
    return state.state_root() / "registry" / "session-ledger.jsonl"


def append_record(record: dict[str, Any]) -> dict[str, Any]:
    enriched = {
        "schema": "aura.session_ledger.v1",
        "timestamp": now_iso(),
        **record,
    }
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(enriched, sort_keys=True))
        f.write("\n")
    return enriched


def seat_ref(fleet: str | None, seat: str | None) -> str | None:
    if not seat:
        return None
    return f"{fleet}:{seat}" if fleet else str(seat)


SNAPSHOT_FIELDS = (
    "name",
    "seat",
    "fleet",
    "fleet_id",
    "seat_ref",
    "seat_instance_id",
    "runtime",
    "command",
    "cwd",
    "workdir",
    "runtime_session_cwd",
    "aura_launch_id",
    "previous_aura_launch_id",
    "session_id",
    "runtime_session_id",
    "runtime_session_source",
    "runtime_session_binding",
    "runtime_session_bind_method",
    "runtime_session_bind_source",
    "runtime_session_bound_at",
    "runtime_session_confidence",
    "runtime_session_evidence",
    "runtime_session_diagnostics",
    "runtime_session_possible_matches",
    "runtime_session_env",
    "runtime_session_created_at_ms",
    "runtime_session_updated_at_ms",
    "runtime_session_pid",
    "source_session_id",
    "previous_runtime_session_id",
    "restart_from_session_id",
    "terminal_ref",
    "backend_ref",
    "pane_ref",
    "runtime_process_pid",
    "runtime_process_cwd",
    "runtime_process_started_at_epoch",
    "runtime_process_argv",
    "status",
    "identity_provider",
    "identity_id",
    "identity_label",
    "desks_identity_id",
    "flex_project_manifest",
    "flex_project_root",
)


def snapshot_seat(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if not record:
        return None
    snap = {key: record.get(key) for key in SNAPSHOT_FIELDS if record.get(key) is not None}
    seat = snap.get("seat") or snap.get("name")
    fleet = snap.get("fleet")
    if seat:
        snap["seat"] = seat
        snap["name"] = snap.get("name") or seat
    if seat and not snap.get("seat_ref"):
        snap["seat_ref"] = seat_ref(fleet, seat)
    if not snap.get("cwd"):
        cwd = snap.get("runtime_session_cwd") or snap.get("workdir")
        if cwd:
            snap["cwd"] = cwd
    if runtime_session.is_bound_session(snap) and not snap.get("session_id") and snap.get("runtime_session_id"):
        snap["session_id"] = snap["runtime_session_id"]
    if snap.get("runtime_session_binding") != "unbound" and not snap.get("runtime_session_id") and snap.get("session_id"):
        snap["runtime_session_id"] = snap["session_id"]
    return snap


def _first_present(*records: dict[str, Any] | None, key: str) -> Any:
    for record in records:
        if record and record.get(key) is not None:
            return record.get(key)
    return None


def append_seat_event(
    *,
    event: str,
    seat: str | None = None,
    fleet: str | None = None,
    runtime: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
    actor: str = "cli",
    source_command: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    before_snap = snapshot_seat(before)
    after_snap = snapshot_seat(after)
    seat = seat or _first_present(after_snap, before_snap, key="seat") or _first_present(after_snap, before_snap, key="name")
    fleet = fleet or _first_present(after_snap, before_snap, key="fleet")
    fleet_id = _first_present(after_snap, before_snap, key="fleet_id")
    runtime = runtime or _first_present(after_snap, before_snap, key="runtime")
    if fleet and not fleet_id:
        try:
            from lib import fleets

            fleet_record = fleets.ensure_fleet(fleet)
            fleet_id = (fleet_record or {}).get("fleet_id")
        except Exception:
            fleet_id = None
    cwd = _first_present(after_snap, before_snap, key="cwd")
    session_id = _first_present(after_snap, before_snap, key="session_id") or _first_present(after_snap, before_snap, key="runtime_session_id")
    runtime_session_id = _first_present(after_snap, before_snap, key="runtime_session_id") or session_id
    launch_id = _first_present(after_snap, before_snap, key="aura_launch_id")
    seat_instance_id = _first_present(after_snap, before_snap, key="seat_instance_id")
    identity_provider = _first_present(after_snap, before_snap, key="identity_provider")
    identity_id = _first_present(after_snap, before_snap, key="identity_id")
    identity_label = _first_present(after_snap, before_snap, key="identity_label")
    desks_identity_id = _first_present(after_snap, before_snap, key="desks_identity_id")
    if not identity_id and desks_identity_id:
        identity_id = desks_identity_id
    if not identity_provider and desks_identity_id:
        identity_provider = "desks"
    record = {
        "schema": "aura.seat_history.v1",
        "event_id": new_event_id(),
        "timestamp": now_iso(),
        "event": event,
        "seat": seat,
        "name": seat,
        "fleet": fleet,
        "fleet_id": fleet_id,
        "seat_ref": seat_ref(fleet, seat),
        "runtime": runtime,
        "cwd": cwd,
        "session_id": session_id,
        "runtime_session_id": runtime_session_id,
        "runtime_session_binding": _first_present(after_snap, before_snap, key="runtime_session_binding"),
        "runtime_session_bind_method": _first_present(after_snap, before_snap, key="runtime_session_bind_method"),
        "runtime_session_bind_source": _first_present(after_snap, before_snap, key="runtime_session_bind_source"),
        "runtime_session_confidence": _first_present(after_snap, before_snap, key="runtime_session_confidence"),
        "runtime_session_source": _first_present(after_snap, before_snap, key="runtime_session_source"),
        "aura_launch_id": launch_id,
        "seat_instance_id": seat_instance_id,
        "identity_provider": identity_provider,
        "identity_id": identity_id,
        "identity_label": identity_label,
        "desks_identity_id": desks_identity_id,
        "actor": actor,
        "source_command": source_command,
        "before": before_snap,
        "after": after_snap,
        "evidence": evidence or {},
        **{key: value for key, value in extra.items() if value is not None},
    }
    clean = {key: value for key, value in record.items() if value is not None}
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(clean, sort_keys=True))
        f.write("\n")
    return clean


def iter_records(limit: int | None = None) -> list[dict[str, Any]]:
    path = ledger_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    if limit is not None:
        return rows[-int(limit):]
    return rows


def read_ledger(limit: int | None = None) -> list[dict[str, Any]]:
    """Compatibility reader for commands that need global session history."""
    return iter_records(limit=limit)


def _row_refs(row: dict[str, Any]) -> set[str]:
    refs = set()
    for key in ("seat_ref", "source_ref", "target_ref"):
        if row.get(key):
            refs.add(str(row[key]))
    for key in ("before", "after"):
        value = row.get(key)
        if isinstance(value, dict) and value.get("seat_ref"):
            refs.add(str(value["seat_ref"]))
    fleet = row.get("fleet")
    seat = row.get("seat") or row.get("name")
    ref = seat_ref(fleet, seat)
    if ref:
        refs.add(ref)
    return refs


def seat_history_for_target(target: str, *, limit: int | None = None, follow_aliases: bool = True) -> list[dict[str, Any]]:
    rows = iter_records()
    wanted = {target}
    if ":" not in target:
        wanted.update(ref for row in rows for ref in _row_refs(row) if ref.endswith(f":{target}"))
    changed = True
    while follow_aliases and changed:
        changed = False
        for row in rows:
            if row.get("event") not in {"seat_rehomed", "seat_alias_created"}:
                continue
            refs = _row_refs(row)
            if refs & wanted and not refs <= wanted:
                wanted.update(refs)
                changed = True
    filtered = [row for row in rows if _row_refs(row) & wanted]
    if limit is not None:
        return filtered[-int(limit):]
    return filtered


TERMINAL_EVENTS = {"seat_cut", "seat_swept_removed", "seat_archived"}


def _state_from_row(row: dict[str, Any]) -> dict[str, Any]:
    after = row.get("after") if isinstance(row.get("after"), dict) else None
    before = row.get("before") if isinstance(row.get("before"), dict) else None
    base = snapshot_seat(after) or snapshot_seat(row) or snapshot_seat(before) or {}
    base.update({
        "latest_event": row.get("event"),
        "latest_event_id": row.get("event_id"),
        "latest_event_at": row.get("timestamp"),
    })
    return base


def project_latest_from_ledger(*, fleet: str | None = None) -> list[dict[str, Any]]:
    projections: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    for row in iter_records():
        schema = row.get("schema")
        event = row.get("event")
        if schema in {"aura.seat_history.v1", "aura.seat_lineage.v1"}:
            before = row.get("before") if isinstance(row.get("before"), dict) else None
            after = row.get("after") if isinstance(row.get("after"), dict) else None
            current_ref = row.get("seat_ref") or (after or {}).get("seat_ref") or (before or {}).get("seat_ref")
            if event == "seat_rehomed":
                old_ref = (before or {}).get("seat_ref") or row.get("source_ref")
                new_ref = (after or {}).get("seat_ref") or row.get("target_ref") or current_ref
                if old_ref and new_ref and old_ref in projections:
                    projections.pop(str(old_ref), None)
                if old_ref and new_ref:
                    aliases[str(old_ref)] = str(new_ref)
                current_ref = new_ref
            if event == "seat_alias_created":
                source = row.get("source_ref") or (before or {}).get("seat_ref")
                target = row.get("target_ref") or (after or {}).get("seat_ref") or current_ref
                if source and target:
                    aliases[str(source)] = str(target)
                continue
            if not current_ref:
                continue
            state = _state_from_row(row)
            if event in TERMINAL_EVENTS:
                state["terminal_state"] = "terminal"
                state["restore_suppressed"] = True
            elif event == "seat_restart_failed":
                state["repair_needed"] = True
            projections[str(current_ref)] = state
            continue

        # Compatibility fallback for older rows. Prefer explicit seat-history rows
        # when they exist, but keep old spawn/bind rows useful for recovery.
        if schema != "aura.session_ledger.v1":
            continue
        seat = row.get("seat") or row.get("name")
        ref = seat_ref(row.get("fleet"), seat)
        if not ref:
            continue
        if ref in projections and projections[ref].get("latest_event_id"):
            continue
        state = snapshot_seat(row) or {}
        state.update({
            "latest_event": row.get("event"),
            "latest_event_at": row.get("timestamp"),
        })
        projections[ref] = state

    resolved: dict[str, dict[str, Any]] = {}
    for ref, state in projections.items():
        target = aliases.get(ref, ref)
        if target != ref and target in projections:
            continue
        resolved[target] = state
    rows = list(resolved.values())
    if fleet:
        rows = [row for row in rows if row.get("fleet") == fleet]
    return sorted(rows, key=lambda row: (row.get("fleet") or "", row.get("seat") or row.get("name") or ""))


def restore_status(row: dict[str, Any], capability: dict[str, Any] | None = None) -> dict[str, Any]:
    capability = capability or {}
    if row.get("restore_suppressed") or row.get("terminal_state") == "terminal":
        return {
            "restore_ready": False,
            "restore_reason": "latest-seat-state-is-terminal",
        }
    binding = runtime_session.mark_binding(dict(row))
    session_id = binding.get("session_id") or binding.get("runtime_session_id")
    supports_resume = bool(capability.get("supports_resume"))
    if not session_id and binding.get("runtime_session_possible_matches"):
        return {
            "restore_ready": False,
            "restore_reason": "runtime-session-unbound",
        }
    if not session_id:
        return {
            "restore_ready": False,
            "restore_reason": "missing-session-id",
        }
    if not runtime_session.is_bound_session(binding):
        return {
            "restore_ready": False,
            "restore_reason": "runtime-session-unbound",
        }
    if not supports_resume:
        return {
            "restore_ready": False,
            "restore_reason": "runtime-does-not-support-resume",
        }
    return {
        "restore_ready": True,
        "restore_reason": "bound-session-id-and-runtime-resume-supported",
    }


def _shell_quote(value: Any) -> str:
    import shlex

    return shlex.quote(str(value))


def restore_command(row: dict[str, Any], capability: dict[str, Any] | None = None) -> str | None:
    capability = capability or {}
    status = restore_status(row, capability)
    if not status["restore_ready"]:
        return None
    seat = row.get("seat") or row.get("name")
    fleet = row.get("fleet")
    runtime = row.get("runtime")
    cwd = row.get("cwd") or row.get("workdir")
    session_id = row.get("session_id") or row.get("runtime_session_id")
    if not seat or not runtime or not session_id:
        return None
    parts = ["aura", "spawn", _shell_quote(seat), "--runtime", _shell_quote(runtime)]
    if fleet:
        parts.extend(["--fleet", _shell_quote(fleet)])
    if cwd:
        parts.extend(["--cwd", _shell_quote(cwd)])
    resume_template = capability.get("resume_command")
    if resume_template:
        parts.extend(["--command", _shell_quote(resume_template.format(session_id=session_id))])
    elif runtime in ("claude", "claude-code"):
        parts.extend(["--memory", _shell_quote(session_id)])
    else:
        return None
    return " ".join(parts)


def restore_plan_from_rows(rows: list[dict[str, Any]], capabilities: dict[str, dict[str, Any]]) -> dict[str, Any]:
    plan_rows: list[dict[str, Any]] = []
    for row in rows:
        runtime = row.get("runtime")
        capability = capabilities.get(runtime or "", {})
        status = restore_status(row, capability)
        command = restore_command(row, capability)
        plan_rows.append({
            "seat": row.get("seat") or row.get("name"),
            "fleet": row.get("fleet"),
            "runtime": runtime,
            "terminal": row.get("terminal"),
            "session_id": row.get("session_id") or row.get("runtime_session_id"),
            "runtime_session_binding": row.get("runtime_session_binding"),
            "runtime_session_bind_method": row.get("runtime_session_bind_method"),
            "runtime_session_bind_source": row.get("runtime_session_bind_source"),
            "runtime_session_confidence": row.get("runtime_session_confidence"),
            "runtime_session_source": row.get("runtime_session_source"),
            "cwd": row.get("cwd") or row.get("workdir"),
            "restore_ready": status["restore_ready"],
            "restore_reason": status["restore_reason"],
            "restore_command": command,
            "latest_event": row.get("latest_event"),
            "latest_event_id": row.get("latest_event_id"),
            "latest_event_at": row.get("latest_event_at"),
            "identity_provider": row.get("identity_provider") or ("desks" if row.get("desks_identity_id") else None),
            "identity_id": row.get("identity_id") or row.get("desks_identity_id"),
            "identity_label": row.get("identity_label"),
            "desks_identity_id": row.get("desks_identity_id"),
            "warnings": row.get("warnings") or [],
        })
    ready = [row for row in plan_rows if row["restore_ready"]]
    review = [row for row in plan_rows if not row["restore_ready"]]
    return {
        "ok": True,
        "schema": "aura.restore_plan.v1",
        "dry_run": True,
        "total": len(plan_rows),
        "restore_ready": len(ready),
        "needs_review": len(review),
        "rows": plan_rows,
    }

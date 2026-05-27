"""Live Aura topology projection.

This module is deliberately separate from session-ledger restore projection.
Live topology starts from current tmux panes, joins matching Aura registry rows,
and adds only lightweight current adornments needed by operator views.
"""

from __future__ import annotations

from typing import Any

from lib import placements, registry, reports, runtime_session, tmux_mirror


def _seat_name(record: dict[str, Any]) -> str | None:
    return record.get("seat") or record.get("name")


def _target_for(record: dict[str, Any]) -> str | None:
    seat = _seat_name(record)
    fleet = record.get("fleet")
    if not seat:
        return None
    return f"{fleet}:{seat}" if fleet else str(seat)


def _row_target(row: dict[str, Any]) -> str | None:
    return row.get("target") or row.get("seat_ref") or _target_for(row)


def _pane_ref_parts(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    parts = str(value).split(":")
    pane_id = next((part for part in parts if part.startswith("%")), None)
    if not pane_id:
        return None, None
    pane_index = parts.index(pane_id)
    session = parts[pane_index - 1] if pane_index > 0 and parts[pane_index - 1] != "tmux" else None
    return session, pane_id


def _physical_refs(panes: list[dict[str, Any]]) -> set[str]:
    refs: set[str] = set()
    for pane in panes:
        for key in ("pane_ref", "terminal_ref"):
            value = pane.get(key)
            if value:
                refs.add(str(value))
                if str(value).startswith("tmux:"):
                    refs.add(str(value)[len("tmux:"):])
        session = pane.get("tmux_session") or pane.get("physical_fleet")
        pane_id = pane.get("pane_id")
        window = pane.get("window_name")
        if pane_id:
            refs.add(str(pane_id))
            if session:
                refs.add(f"{session}:{pane_id}")
                refs.add(f"tmux:{session}:{pane_id}")
        if window and session:
            refs.add(f"{session}:{window}")
            refs.add(f"tmux:{session}:{window}")
    return refs


def _record_refs(record: dict[str, Any]) -> set[str]:
    refs = set()
    for key in ("pane_ref", "terminal_ref", "backend_ref"):
        value = record.get(key)
        if value:
            refs.add(str(value))
            if str(value).startswith("tmux:"):
                refs.add(str(value)[len("tmux:"):])
    target = _target_for(record)
    if target:
        refs.add(target)
        refs.add(f"tmux:{target}")
    return refs


def _record_hidden_from_live(record: dict[str, Any]) -> bool:
    if record.get("terminal_state") == "terminal" or record.get("restore_suppressed"):
        return True
    if record.get("managed_state") == "stopped":
        return True
    status = str(record.get("status") or "").lower()
    return status in {"dead", "killed", "cut", "quarantined", "archived"}


def _record_matches_physical_pane(record: dict[str, Any], pane: dict[str, Any]) -> bool:
    pane_ref_session, pane_ref_id = _pane_ref_parts(record.get("pane_ref"))
    if pane_ref_id:
        pane_session = pane.get("tmux_session") or pane.get("physical_fleet")
        if pane_ref_session and pane_session and pane_ref_session != pane_session:
            return False
        return pane_ref_id == pane.get("pane_id")
    return bool(_record_refs(record) & _physical_refs([pane]))


def _live_projected_managed_state(row: dict[str, Any]) -> str:
    state = row.get("managed_state")
    if state and state not in {"missing_pane", "stopped"}:
        return state
    binding = row.get("runtime_session_binding")
    if binding in {"bound", "argv-resume", "runtime-session-bound"} or row.get("runtime_session_id") or row.get("session_id"):
        return "spawned_bound"
    return "spawned_unbound"


def _latest_reports_by_target() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in reports.iter_reports():
        seat = row.get("seat")
        fleet = row.get("fleet")
        if seat:
            latest[f"{fleet}:{seat}" if fleet else str(seat)] = row
    return latest


def _report_summary(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "report_id": row.get("report_id"),
        "timestamp": row.get("timestamp"),
        "state": row.get("state"),
        "work": row.get("work"),
        "next": row.get("next"),
        "blockers": row.get("blockers") or [],
        "receipts": row.get("receipts") or [],
    }


def _compact_identity(record: dict[str, Any]) -> dict[str, Any] | None:
    identity = record.get("identity") if isinstance(record.get("identity"), dict) else {}
    compact = {
        key: value
        for key, value in {
            "provider": identity.get("provider") or record.get("identity_provider"),
            "id": identity.get("id") or record.get("identity_id"),
            "name": identity.get("name") or record.get("identity_label") or record.get("desks_current_name"),
        }.items()
        if value
    }
    return compact or None


def _risk_flags(row: dict[str, Any]) -> list[str]:
    flags = list(row.get("risk_flags") or [])
    if row.get("runtime") not in {"shell", "command"} and row.get("runtime_session_binding") != "bound":
        flags.append("unbound_runtime_session")
    latest_report = row.get("latest_report")
    if isinstance(latest_report, dict) and latest_report.get("stale"):
        flags.append("latest_report_stale")
    return sorted(set(flags))


def live_status_rows(*, include_hidden: bool) -> dict[str, Any]:
    mirror = tmux_mirror.list_physical_panes()
    records = registry.list_agents(include_hidden=include_hidden)
    if not mirror.get("ok"):
        return {
            "ok": False,
            "error": mirror.get("error") or "tmux mirror unavailable",
            "rows": [],
            "historical_count": len(records),
        }

    reports_by_target = _latest_reports_by_target()
    placements_by_target = placements.placements_by_seat()
    rows: list[dict[str, Any]] = []
    seen_targets: set[str] = set()
    for pane in mirror.get("panes") or []:
        for record in records:
            if _record_hidden_from_live(record):
                continue
            if not _record_matches_physical_pane(record, pane):
                continue
            target = _row_target(record)
            if not target or target in seen_targets:
                continue
            seen_targets.add(target)
            bound_record = runtime_session.mark_binding(dict(record))
            raw_runtime_session_id = bound_record.get("runtime_session_id") or bound_record.get("session_id")
            binding = "bound" if raw_runtime_session_id or runtime_session.is_bound_session(bound_record) else (
                bound_record.get("runtime_session_binding") or "unbound"
            )
            runtime_session_id = raw_runtime_session_id if binding == "bound" else None
            latest_report = _report_summary(reports_by_target.get(target))
            enriched = {
                **record,
                "target": target,
                "seat_ref": record.get("seat_ref") or target,
                "fleet": record.get("fleet"),
                "seat": _seat_name(record),
                "pane_ref": pane.get("pane_ref") or record.get("pane_ref"),
                "terminal_ref": pane.get("terminal_ref") or record.get("terminal_ref"),
                "physical_fleet": pane.get("physical_fleet") or pane.get("tmux_session"),
                "physical_seat": pane.get("window_name"),
                "pane_id": pane.get("pane_id"),
                "liveness": "alive",
                "terminal": "alive",
                "status": record.get("status") or "idle",
                "runtime_session_binding": binding,
                "runtime_session_id": runtime_session_id,
                "session_id": runtime_session_id,
                "identity": _compact_identity(record),
                "latest_report": latest_report,
                "placements": placements_by_target.get(target) or [],
            }
            enriched["managed_state"] = _live_projected_managed_state(enriched)
            enriched["risk_flags"] = _risk_flags(enriched)
            rows.append(enriched)

    return {
        "ok": True,
        "rows": rows,
        "historical_count": len(records),
    }

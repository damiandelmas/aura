"""Show the current bounded mesh view."""

from __future__ import annotations

from lib import deferred, queued_messages, reports, seat_status


def _role_field(record: dict, name: str) -> str | None:
    role = record.get("role") or {}
    return record.get(name) or role.get(name)


def _infer_scope(context: dict, explicit: str | None = None) -> dict:
    if explicit:
        if explicit.startswith("fleet:"):
            return {"kind": "fleet", "name": explicit.removeprefix("fleet:"), "fleet": explicit.removeprefix("fleet:")}
        if explicit.startswith("product:"):
            return {"kind": "product", "name": explicit.removeprefix("product:"), "product": explicit.removeprefix("product:")}
        if explicit.startswith("unit:"):
            value = explicit.removeprefix("unit:")
            parts = value.split(":", 1)
            if len(parts) == 2:
                return {"kind": "unit", "name": value, "product": parts[0], "unit": parts[1]}
            return {"kind": "unit", "name": value, "unit": value}
        return {"kind": "named", "name": explicit}

    role = context.get("role") or {}
    product = role.get("desks_product")
    unit = role.get("desks_unit")
    if product and unit:
        return {"kind": "unit", "name": f"{product}:{unit}", "product": product, "unit": unit}
    if product:
        return {"kind": "product", "name": product, "product": product}
    if context.get("fleet"):
        return {"kind": "fleet", "name": context["fleet"], "fleet": context["fleet"]}
    return {"kind": "global", "name": "global"}


def _matches_scope(record: dict, scope: dict) -> bool:
    kind = scope.get("kind")
    if kind == "global":
        return True
    fleet = record.get("fleet")
    product = _role_field(record, "desks_product")
    unit = _role_field(record, "desks_unit")
    name = scope.get("name")
    if kind == "fleet":
        return fleet == scope.get("fleet")
    if kind == "product":
        expected = scope.get("product")
        return product == expected or bool(fleet and str(fleet).startswith(f"{expected}-"))
    if kind == "unit":
        expected_product = scope.get("product")
        expected_unit = scope.get("unit")
        if expected_product and expected_unit:
            return product == expected_product and unit == expected_unit
        return unit == expected_unit or bool(fleet and str(fleet).startswith(f"{expected_unit}-"))
    return (
        product == name
        or unit == name
        or fleet == name
        or bool(fleet and name and str(fleet).startswith(f"{name}-"))
    )


def _target_in_scope(record: dict, scope: dict, seats: set[str], fleets: set[str]) -> bool:
    target = str(record.get("target") or "")
    if not target:
        return False
    if ":" in target and not target.startswith("tmux:"):
        fleet, seat = target.split(":", 1)
        return fleet in fleets or seat in seats
    if scope.get("kind") == "fleet" and target in seats:
        return True
    return target in seats


def _target_for(row: dict) -> str | None:
    seat = row.get("seat") or row.get("name")
    fleet = row.get("fleet")
    if not seat:
        return None
    return f"{fleet}:{seat}" if fleet else str(seat)


def _last_reports_by_target(rows: list[dict]) -> dict[str, dict]:
    latest = {}
    for row in rows:
        target = _target_for(row)
        if target:
            latest[target] = row
    return latest


def _report_summary(row: dict | None) -> dict | None:
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


def run(args):
    limit = int(getattr(args, "limit", None) or 10)
    include_hidden = bool(getattr(args, "include_hidden", False))
    context = reports.infer_context()
    scope = _infer_scope(context, getattr(args, "scope", None))

    agents = [
        agent
        for agent in seat_status.list_seat_statuses(include_hidden=include_hidden)
        if _matches_scope(agent, scope)
    ]
    report_rows = [
        row
        for row in reports.iter_reports()
        if _matches_scope(row, scope)
    ]
    report_rows = report_rows[-limit:]
    last_reports = _last_reports_by_target(report_rows)

    all_colleagues = []
    for agent in agents:
        seat = agent.get("name")
        all_colleagues.append({
            "seat": seat,
            "fleet": agent.get("fleet"),
            "runtime": agent.get("runtime"),
            "status": agent.get("status"),
            "terminal": agent.get("terminal"),
            "session_id": agent.get("session_id") or agent.get("runtime_session_id"),
            "managed_state": agent.get("managed_state"),
            "runtime_session_binding": agent.get("runtime_session_binding"),
            "seat_instance_id": agent.get("seat_instance_id"),
            "identity": agent.get("identity"),
            "org": agent.get("org"),
            "risk_flags": agent.get("risk_flags") or [],
            "role": {
                key: agent.get(key)
                for key in ("desks_role_id", "desks_product", "desks_unit", "desks_role_home")
                if agent.get(key)
            },
            "last_report": _report_summary(last_reports.get(_target_for(agent))),
        })
    colleagues = all_colleagues[:limit]

    fleets = sorted({agent.get("fleet") for agent in agents if agent.get("fleet")})
    seats = {agent.get("name") for agent in agents if agent.get("name")}
    fleet_set = set(fleets)
    pending_deferred = [
        row
        for row in deferred.list_records(status="pending")
        if _target_in_scope(row, scope, seats, fleet_set)
    ][-limit:]
    pending_queue = [
        row
        for row in queued_messages.list_records(status="pending")
        if _target_in_scope(row, scope, seats, fleet_set)
    ][-limit:]

    return {
        "ok": True,
        "schema": "aura.view.v1",
        "scope": scope,
        "current": context,
        "counts": {
            "fleets": len(fleets),
            "colleagues": len(all_colleagues),
            "colleagues_returned": len(colleagues),
            "recent_reports": len(report_rows),
            "pending_queue": len(pending_queue),
            "pending_deferred": len(pending_deferred),
        },
        "fleets": fleets,
        "colleagues": colleagues,
        "recent_reports": [_report_summary(row) | {"seat": row.get("seat"), "fleet": row.get("fleet")} for row in report_rows],
        "pending_queue": pending_queue,
        "pending_deferred": pending_deferred,
    }

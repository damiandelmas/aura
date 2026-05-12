"""Show Aura managed-seat views."""

from __future__ import annotations

from lib import deferred, queued_messages, reports, seat_status


def _compact_identity(row: dict) -> dict | None:
    identity = row.get("identity")
    if not isinstance(identity, dict):
        return None
    current = identity.get("current") if isinstance(identity.get("current"), dict) else {}
    result = {
        "provider": identity.get("provider") or row.get("identity_provider"),
        "id": identity.get("id") or row.get("identity_id"),
        "name": identity.get("name") or row.get("identity_label"),
        "current_position": current.get("position"),
    }
    return {key: value for key, value in result.items() if value}


def _current_position(row: dict) -> str | None:
    identity = row.get("identity")
    if isinstance(identity, dict):
        current = identity.get("current")
        if isinstance(current, dict) and current.get("position"):
            return current.get("position")
    org = row.get("org")
    if isinstance(org, dict):
        return org.get("role")
    return None


def _compact_status(row: dict) -> dict:
    return {
        key: value
        for key, value in {
            "target": row.get("target") or _target_for(row),
            "fleet": row.get("fleet"),
            "seat": row.get("seat") or row.get("name"),
            "status": row.get("status"),
            "liveness": row.get("liveness"),
            "managed_state": row.get("managed_state"),
            "runtime": row.get("runtime"),
            "runtime_session_binding": row.get("runtime_session_binding"),
            "runtime_session_id": row.get("runtime_session_id") or row.get("session_id"),
            "seat_instance_id": row.get("seat_instance_id"),
            "identity": _compact_identity(row),
            "current_position": _current_position(row),
            "risk_flags": row.get("risk_flags") or [],
            "last_report": row.get("latest_report"),
        }.items()
        if value not in (None, {}, [])
    }


def _report_text(row: dict) -> str | None:
    report = row.get("latest_report")
    if not isinstance(report, dict):
        return None
    for key in ("summary", "work", "next"):
        value = report.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    state = report.get("state")
    return str(state).strip() if state else None


def _agent_status(row: dict | None) -> dict | None:
    if not row:
        return None
    identity = _compact_identity(row) or {}
    return {
        "target": row.get("target") or _target_for(row),
        "status": row.get("status"),
        "runtime": row.get("runtime"),
        "session_id": row.get("runtime_session_id") or row.get("session_id"),
        "identity": identity.get("id"),
        "name": identity.get("name") or row.get("identity_label"),
        "report": _report_text(row),
    }


def _row_matches_pane(row: dict, pane: str | None) -> bool:
    if not pane:
        return False
    for key in ("pane_ref", "terminal_ref", "backend_ref"):
        value = str(row.get(key) or "")
        if value == pane or value.endswith(f":{pane}"):
            return True
    return False


def _row_target(row: dict) -> str | None:
    return row.get("target") or row.get("seat_ref") or _target_for(row)


def _is_routable(row: dict) -> bool:
    return row.get("managed_state") not in {"missing_pane", "stopped"}


def _is_live(row: dict) -> bool:
    return row.get("liveness") == "alive" and _is_routable(row)


def _one_self_match(rows: list[dict], matches: list[dict], source: str) -> dict:
    routable = [row for row in matches if _is_routable(row)]
    selected = routable or matches
    if len(selected) == 1:
        return {"ok": True, "source": source, "row": selected[0]}
    if len(selected) > 1:
        return {
            "ok": False,
            "source": source,
            "error": "self-resolved-to-multiple-seats",
            "match_count": len(selected),
            "matches": [_row_target(row) for row in selected],
        }
    return {"ok": False, "source": source, "error": "self-not-resolved", "match_count": 0}


def _resolve_self(rows: list[dict], context: dict) -> dict:
    pane_match = _one_self_match(
        rows,
        [row for row in rows if _row_matches_pane(row, context.get("pane"))],
        "tmux-pane",
    )
    if pane_match.get("ok") or pane_match.get("match_count"):
        return pane_match

    env_target = (
        f"{context.get('fleet')}:{context.get('seat')}"
        if context.get("fleet") and context.get("seat")
        else None
    )
    if env_target:
        env_match = _one_self_match(
            rows,
            [row for row in rows if _row_target(row) == env_target],
            "aura-env",
        )
        if env_match.get("ok") or env_match.get("match_count"):
            return env_match

    session_id = context.get("runtime_session_id") or context.get("session_id")
    if session_id:
        session_match = _one_self_match(
            rows,
            [
                row for row in rows
                if session_id in {row.get("runtime_session_id"), row.get("session_id")}
            ],
            "runtime-session",
        )
        if session_match.get("ok") or session_match.get("match_count"):
            return session_match

    return {"ok": False, "source": "none", "error": "self-not-resolved", "match_count": 0}


def _status_rows(*, include_hidden: bool):
    from lib import terminal

    return seat_status.list_seat_statuses(include_hidden=include_hidden, terminal=terminal)


def _run_self(*, include_hidden: bool) -> dict:
    context = reports.infer_context()
    rows = _status_rows(include_hidden=include_hidden)
    resolved = _resolve_self(rows, context)
    if not resolved.get("ok"):
        return {
            "ok": False,
            "schema": "aura.view.self.v1",
            "current": context,
            "error": resolved.get("error"),
            "source": resolved.get("source"),
            "match_count": resolved.get("match_count", 0),
            "matches": resolved.get("matches") or [],
        }
    return {
        "ok": True,
        "schema": "aura.view.self.v1",
        "source": resolved.get("source"),
        "self": _compact_status(resolved["row"]),
    }


def _run_fleets(*, include_hidden: bool) -> dict:
    rows = _status_rows(include_hidden=include_hidden)
    live_rows = [row for row in rows if _is_live(row)]
    counts: dict[str, int] = {}
    for row in live_rows:
        fleet = row.get("fleet")
        if fleet:
            counts[fleet] = counts.get(fleet, 0) + 1
    return {
        "fleets": [
            {"fleet": fleet, "seats": counts[fleet]}
            for fleet in sorted(counts)
        ],
    }


def _run_fleet(*, include_hidden: bool, fleet_name: str | None = None) -> dict:
    context = reports.infer_context()
    rows = _status_rows(include_hidden=include_hidden)
    resolved = _resolve_self(rows, context)
    fleet = None
    self_row = None
    if resolved.get("ok"):
        self_row = resolved["row"]
        fleet = self_row.get("fleet")
    fleet = fleet_name or fleet or context.get("fleet")
    fleet_rows = [row for row in rows if row.get("fleet") == fleet and _is_live(row)] if fleet else []
    if fleet_name:
        return {
            "fleet": fleet,
            "seats": [_agent_status(row) for row in sorted(fleet_rows, key=lambda row: row.get("seat") or row.get("name") or "")],
        }
    return {
        "ok": bool(fleet),
        "schema": "aura.view.fleet.v1",
        "fleet": fleet,
        "self": _compact_status(self_row) if self_row else None,
        "source": resolved.get("source"),
        "counts": {"seats": len(fleet_rows)},
        "seats": [_compact_status(row) for row in fleet_rows],
    }


def _run_roster(*, include_hidden: bool) -> dict:
    rows = _status_rows(include_hidden=include_hidden)
    live_rows = [row for row in rows if _is_live(row)]
    fleets = sorted({row.get("fleet") for row in live_rows if row.get("fleet")})
    return {
        "ok": True,
        "schema": "aura.view.roster.v1",
        "scope": "live",
        "counts": {"fleets": len(fleets), "seats": len(live_rows), "historical_seats": len(rows)},
        "fleets": fleets,
        "seats": [_compact_status(row) for row in live_rows],
    }


def _run_historical(*, include_hidden: bool) -> dict:
    rows = _status_rows(include_hidden=include_hidden)
    fleets = sorted({row.get("fleet") for row in rows if row.get("fleet")})
    return {
        "ok": True,
        "schema": "aura.view.historical.v1",
        "counts": {"fleets": len(fleets), "seats": len(rows)},
        "fleets": fleets,
        "seats": [_compact_status(row) for row in rows],
    }


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
    action = getattr(args, "view_action", None)
    target = getattr(args, "view_target", None)
    include_hidden = bool(getattr(args, "include_hidden", False))
    if action == "self":
        return _run_self(include_hidden=include_hidden)
    if action == "fleets":
        return _run_fleets(include_hidden=include_hidden)
    if action == "fleet":
        return _run_fleet(include_hidden=include_hidden, fleet_name=target)
    if action == "roster":
        return _run_roster(include_hidden=include_hidden)
    if action == "historical":
        return _run_historical(include_hidden=include_hidden)

    limit = int(getattr(args, "limit", None) or 10)
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

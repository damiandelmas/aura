"""Show Aura managed-seat views."""

from __future__ import annotations

from lib import deferred, placements, queued_messages, registry, reports, seat_status, tmux_mirror


def _compact_identity(row: dict) -> dict | None:
    identity = row.get("identity") if isinstance(row.get("identity"), dict) else {}
    current = identity.get("current") if isinstance(identity.get("current"), dict) else {}
    result = {
        "provider": identity.get("provider") or row.get("identity_provider"),
        "id": identity.get("id") or row.get("identity_id"),
        "name": identity.get("name") or row.get("identity_label"),
        "current_position": current.get("position") or row.get("current_position"),
    }
    compact = {key: value for key, value in result.items() if value}
    return compact or None


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
            "runtime_profile": row.get("runtime_profile"),
            "runtime_profile_ref": row.get("runtime_profile_ref"),
            "runtime_profile_runtime": row.get("runtime_profile_runtime"),
            "runtime_profile_source": row.get("runtime_profile_source"),
            "runtime_session_binding": row.get("runtime_session_binding"),
            "runtime_session_id": row.get("runtime_session_id") or row.get("session_id"),
            "seat_instance_id": row.get("seat_instance_id"),
            "identity": _compact_identity(row),
            "current_position": _current_position(row),
            "risk_flags": row.get("risk_flags") or [],
            "last_report": row.get("latest_report"),
            "placements": row.get("placements") or [],
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
        "liveness": row.get("liveness"),
        "managed_state": row.get("managed_state"),
        "runtime": row.get("runtime"),
        **{
            key: row.get(key)
            for key in (
                "runtime_profile",
                "runtime_profile_ref",
                "runtime_profile_runtime",
                "runtime_profile_source",
            )
            if row.get(key)
        },
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
    live = [row for row in matches if _is_live(row)]
    routable = [row for row in matches if _is_routable(row)]
    selected = live or routable
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
    if matches:
        return {
            "ok": False,
            "source": source,
            "error": "self-not-live",
            "match_count": len(matches),
            "matches": [_row_target(row) for row in matches],
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


def _status_rows(*, include_hidden: bool, fleet: str | None = None):
    from lib import terminal

    return seat_status.list_seat_statuses(fleet=fleet, include_hidden=include_hidden, terminal=terminal)


def _physical_refs(panes: list[dict]) -> set[str]:
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


def _record_refs(record: dict) -> set[str]:
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


def _record_hidden_from_live(record: dict) -> bool:
    if record.get("terminal_state") == "terminal" or record.get("restore_suppressed"):
        return True
    if record.get("managed_state") == "stopped":
        return True
    status = str(record.get("status") or "").lower()
    return status in {"dead", "killed", "cut", "quarantined", "archived"}


def _live_view_failure(*, schema: str, detail: str | None = None, **extra) -> dict:
    return {
        "ok": False,
        "schema": schema,
        "view_scope": "live",
        "scope": "live",
        "error": "tmux-mirror-unavailable",
        "detail": detail or "tmux mirror unavailable",
        **extra,
    }


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


def _record_matches_physical_pane(record: dict, pane: dict) -> bool:
    pane_ref_session, pane_ref_id = _pane_ref_parts(record.get("pane_ref"))
    if pane_ref_id:
        pane_session = pane.get("tmux_session") or pane.get("physical_fleet")
        if pane_ref_session and pane_session and pane_ref_session != pane_session:
            return False
        return pane_ref_id == pane.get("pane_id")
    return bool(_record_refs(record) & _physical_refs([pane]))


def _live_projected_managed_state(row: dict) -> str:
    state = row.get("managed_state")
    if state and state not in {"missing_pane", "stopped"}:
        return state
    binding = row.get("runtime_session_binding")
    if binding in {"bound", "argv-resume", "runtime-session-bound"} or row.get("runtime_session_id") or row.get("session_id"):
        return "spawned_bound"
    return "spawned_unbound"


def _live_status_rows(*, include_hidden: bool) -> dict:
    mirror = tmux_mirror.list_physical_panes()
    if not mirror.get("ok"):
        return {
            "ok": False,
            "error": mirror.get("error") or "tmux mirror unavailable",
            "rows": [],
            "historical_count": len(registry.list_agents(include_hidden=include_hidden)),
        }

    records = registry.list_agents(include_hidden=include_hidden)
    status_by_target = {
        _row_target(row): row
        for row in _status_rows(include_hidden=include_hidden)
        if _row_target(row)
    }
    rows = []
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
            enriched = {
                **(status_by_target.get(target) or {}),
                **record,
                "target": target,
                "fleet": record.get("fleet"),
                "seat": record.get("seat") or record.get("name"),
                "pane_ref": pane.get("pane_ref") or record.get("pane_ref"),
                "terminal_ref": pane.get("terminal_ref") or record.get("terminal_ref"),
                "physical_fleet": pane.get("physical_fleet"),
                "physical_seat": pane.get("window_name"),
                "pane_id": pane.get("pane_id"),
                "liveness": "alive",
            }
            enriched["managed_state"] = _live_projected_managed_state(enriched)
            rows.append(enriched)

    return {
        "ok": True,
        "rows": rows,
        "historical_count": len(records),
    }


def _run_self(*, include_hidden: bool) -> dict:
    context = reports.infer_context()
    rows = _status_rows(include_hidden=include_hidden)
    resolved = _resolve_self(rows, context)
    if not resolved.get("ok"):
        return {
            "ok": False,
            "schema": "aura.view.self.v1",
            "view_scope": "self",
            "current": context,
            "error": resolved.get("error"),
            "source": resolved.get("source"),
            "match_count": resolved.get("match_count", 0),
            "matches": resolved.get("matches") or [],
        }
    return {
        "ok": True,
        "schema": "aura.view.self.v1",
        "view_scope": "self",
        "source": resolved.get("source"),
        "self": _compact_status(resolved["row"]),
    }


def _run_fleets(*, include_hidden: bool) -> dict:
    live = _live_status_rows(include_hidden=include_hidden)
    if not live.get("ok"):
        return _live_view_failure(
            schema="aura.view.fleets.v1",
            detail=live.get("error"),
            fleets=[],
        )
    counts: dict[str, int] = {}
    for row in live.get("rows") or []:
        fleet = row.get("fleet")
        if fleet:
            counts[fleet] = counts.get(fleet, 0) + 1
    return {
        "ok": True,
        "schema": "aura.view.fleets.v1",
        "view_scope": "live",
        "scope": "live",
        "fleets": [
            {"fleet": fleet, "seats": counts[fleet]}
            for fleet in sorted(counts)
        ],
    }


def _run_fleet(*, include_hidden: bool, fleet_name: str | None = None) -> dict:
    context = reports.infer_context()
    live = _live_status_rows(include_hidden=include_hidden)
    if not live.get("ok"):
        failure = _live_view_failure(
            schema="aura.view.fleet.v1",
            detail=live.get("error"),
            fleet=fleet_name or context.get("fleet"),
            seats=[],
        )
        failure["view_scope"] = "fleet"
        return failure
    rows = live.get("rows") or []
    if fleet_name:
        fleet_rows = [row for row in rows if row.get("fleet") == fleet_name and _is_live(row)]
        return {
            "fleet": fleet_name,
            "seats": [_agent_status(row) for row in sorted(fleet_rows, key=lambda row: row.get("seat") or row.get("name") or "")],
        }

    context_fleet = context.get("fleet")
    resolved = _resolve_self(rows, context)
    fleet = None
    self_row = None
    if resolved.get("ok"):
        self_row = resolved["row"]
        fleet = self_row.get("fleet")
    fleet = fleet or context_fleet
    fleet_rows = [row for row in rows if row.get("fleet") == fleet and _is_live(row)] if fleet else []
    return {
        "ok": bool(fleet),
        "schema": "aura.view.fleet.v1",
        "view_scope": "fleet",
        "scope_source": "context" if fleet else "global",
        "fleet": fleet,
        "self": _compact_status(self_row) if self_row else None,
        "source": resolved.get("source"),
        "counts": {"seats": len(fleet_rows)},
        "seats": [_compact_status(row) for row in fleet_rows],
    }


def _run_roster(*, include_hidden: bool) -> dict:
    live = _live_status_rows(include_hidden=include_hidden)
    if not live.get("ok"):
        return _live_view_failure(
            schema="aura.view.roster.v1",
            detail=live.get("error"),
            counts={"fleets": 0, "seats": 0, "historical_seats": live.get("historical_count", 0)},
            fleets=[],
            seats=[],
        )
    live_rows = [row for row in live.get("rows") or [] if _is_live(row)]
    fleets = sorted({row.get("fleet") for row in live_rows if row.get("fleet")})
    return {
        "ok": True,
        "schema": "aura.view.roster.v1",
        "view_scope": "live",
        "scope": "live",
        "counts": {"fleets": len(fleets), "seats": len(live_rows), "historical_seats": live.get("historical_count", 0)},
        "fleets": fleets,
        "seats": [_compact_status(row) for row in live_rows],
    }


def _run_live(*, include_hidden: bool) -> dict:
    result = _run_roster(include_hidden=include_hidden)
    result["schema"] = "aura.view.live.v1"
    result["alias_of"] = "roster"
    return result


def _member_ref(member: dict) -> str | None:
    return member.get("seat_ref") or member.get("target")


def _placement_member_refs(record: dict) -> list[str]:
    refs = []
    for member in record.get("members") or []:
        if not isinstance(member, dict):
            continue
        ref = _member_ref(member)
        if ref:
            refs.append(ref)
    return refs


def _placement_ref_matches(row: dict, ref: str) -> bool:
    target = _row_target(row)
    return ref in {target, row.get("seat_ref")}


def _placement_summary(record: dict) -> dict:
    return {
        key: value
        for key, value in {
            "placement_id": record.get("placement_id"),
            "kind": record.get("kind"),
            "name": record.get("name"),
            "label": record.get("label"),
        }.items()
        if value
    }


def _run_placement(*, include_hidden: bool, placement_name: str | None = None) -> dict:
    context = reports.infer_context()
    rows = _status_rows(include_hidden=include_hidden)
    resolved = _resolve_self(rows, context)
    self_row = resolved.get("row") if resolved.get("ok") else None

    record = None
    source = "explicit" if placement_name else "self"
    if placement_name:
        record = placements.get_placement(placement_name)
        if not record:
            return {
                "ok": False,
                "schema": "aura.view.placement.v1",
                "view_scope": "placement",
                "error": "placement-not-found",
                "placement": placement_name,
            }
    else:
        self_placements = self_row.get("placements") if isinstance(self_row, dict) else []
        if not self_placements:
            return {
                "ok": False,
                "schema": "aura.view.placement.v1",
                "view_scope": "placement",
                "error": "placement-not-resolved",
                "source": resolved.get("source"),
                "hint": "Provide a placement name, e.g. aura view placement <name>.",
            }
        if len(self_placements) > 1:
            return {
                "ok": False,
                "schema": "aura.view.placement.v1",
                "view_scope": "placement",
                "error": "placement-ambiguous",
                "placements": [p.get("name") or p.get("placement_id") for p in self_placements],
                "hint": "Provide one placement name, e.g. aura view placement <name>.",
            }
        selected = self_placements[0]
        placement_name = selected.get("name") or selected.get("placement_id")
        record = placements.get_placement(placement_name) if placement_name else None
        if not record:
            return {
                "ok": False,
                "schema": "aura.view.placement.v1",
                "view_scope": "placement",
                "error": "placement-not-found",
                "placement": placement_name,
            }

    member_refs = _placement_member_refs(record)
    live_rows = []
    seen_live_targets = set()
    hidden_non_live = 0
    missing_members = []
    for ref in member_refs:
        matches = [row for row in rows if _placement_ref_matches(row, ref)]
        live_matches = [row for row in matches if _is_live(row)]
        if live_matches:
            row = live_matches[0]
            target = _row_target(row)
            if target not in seen_live_targets:
                live_rows.append(row)
                seen_live_targets.add(target)
        elif matches:
            hidden_non_live += 1
        else:
            hidden_non_live += 1
            missing_members.append(ref)

    live_rows = sorted(live_rows, key=lambda row: _row_target(row) or "")
    return {
        "ok": True,
        "schema": "aura.view.placement.v1",
        "view_scope": "placement",
        "source": source,
        "placement": _placement_summary(record),
        "self": _compact_status(self_row) if self_row else None,
        "counts": {
            "members": len(member_refs),
            "seats": len(live_rows),
            "hidden_non_live_members": hidden_non_live,
            "missing_members": len(missing_members),
        },
        "seats": [_compact_status(row) for row in live_rows],
    }


def _run_physical(*, include_hidden: bool) -> dict:
    result = tmux_mirror.view_physical(include_hidden=include_hidden)
    if isinstance(result, dict):
        result.setdefault("view_scope", "physical")
    return result


def _run_historical(*, include_hidden: bool) -> dict:
    rows = _status_rows(include_hidden=include_hidden)
    fleets = sorted({row.get("fleet") for row in rows if row.get("fleet")})
    return {
        "ok": True,
        "schema": "aura.view.historical.v1",
        "view_scope": "historical",
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


def _scope_source(context: dict, explicit: str | None, scope: dict) -> str:
    if explicit:
        return "explicit"
    if scope.get("kind") == "global":
        return "global"
    return "context"


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
    if action == "live":
        return _run_live(include_hidden=include_hidden)
    if action == "placement":
        return _run_placement(include_hidden=include_hidden, placement_name=target)
    if action == "historical":
        return _run_historical(include_hidden=include_hidden)
    if action == "physical":
        return _run_physical(include_hidden=include_hidden)

    limit = int(getattr(args, "limit", None) or 10)
    context = reports.infer_context()
    explicit_scope = getattr(args, "scope", None)
    scope = _infer_scope(context, explicit_scope)
    scope_source = _scope_source(context, explicit_scope, scope)

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
            **{
                key: agent.get(key)
                for key in (
                    "runtime_profile",
                    "runtime_profile_ref",
                    "runtime_profile_runtime",
                    "runtime_profile_source",
                )
                if agent.get(key)
            },
            "status": agent.get("status"),
            "terminal": agent.get("terminal"),
            "session_id": agent.get("session_id") or agent.get("runtime_session_id"),
            "managed_state": agent.get("managed_state"),
            "runtime_session_binding": agent.get("runtime_session_binding"),
            "seat_instance_id": agent.get("seat_instance_id"),
            "identity": agent.get("identity"),
            "org": agent.get("org"),
            "risk_flags": agent.get("risk_flags") or [],
            "placements": agent.get("placements") or [],
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
        "view_scope": "scoped",
        "scope_source": scope_source,
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

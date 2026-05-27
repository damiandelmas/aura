"""Canonical Aura seat status projection."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from lib import (
    deferred,
    holding,
    queued_messages,
    registry,
    reports,
    runtimes,
    runtime_session,
    seat_schema,
    placements,
    session_ledger,
)


def _seat_name(record: dict[str, Any]) -> str | None:
    return record.get("seat") or record.get("name")


def _target(fleet: str | None, seat: str | None) -> str | None:
    if not seat:
        return None
    return f"{fleet}:{seat}" if fleet else seat


def _seat_targets(record: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    targets: list[str] = []
    for key in ("pane_ref", "terminal_ref", "backend_ref"):
        value = record.get(key)
        if value and value not in seen:
            seen.add(str(value))
            targets.append(str(value))
    return targets


def _target_exists(terminal, target: str | None) -> bool:
    if not terminal or not target:
        return False
    try:
        if hasattr(terminal, "target_exists"):
            return bool(terminal.target_exists(target))
        if hasattr(terminal, "window_exists"):
            return bool(terminal.window_exists(target))
    except Exception:
        return False
    return False


def _terminal_status(record: dict[str, Any], terminal=None) -> tuple[str, str, list[str]]:
    targets = _seat_targets(record)
    if not terminal:
        return "unknown", record.get("status") or "unknown", targets

    fleet = record.get("fleet")
    if fleet and hasattr(terminal, "configure_session"):
        try:
            terminal.configure_session(fleet)
        except Exception:
            pass

    alive_target = next((target for target in targets if _target_exists(terminal, target)), None)
    if not alive_target:
        return "missing", record.get("status") or "unknown", targets

    seat = _seat_name(record) or alive_target
    try:
        status = registry.infer_status(seat, terminal, record.get("status", "unknown"), target=alive_target)
    except Exception:
        status = record.get("status") or "alive"
    return "alive", status, targets


def _latest_reports_by_target() -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in reports.iter_reports():
        seat = row.get("seat")
        if not seat:
            continue
        target = _target(row.get("fleet"), seat)
        if target:
            latest[target] = row
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


def _desks_root() -> Path:
    return Path(os.environ.get("DESKS_ROOT", Path.home() / ".desks")).expanduser()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _identity_from_record(record: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    provider = seat_schema.identity_provider_for(record)
    identity_id = seat_schema.identity_id_for(record)
    if not provider or not identity_id:
        return None, None
    identity: dict[str, Any] = {
        "provider": provider,
        "id": identity_id,
        "name": record.get("identity_label"),
        "current": {},
    }
    if provider == "desks" and identity_id:
        identity_home = (_desks_root() / "identities" / str(identity_id)).expanduser()
        identity_json = _read_json(identity_home / "identity.json")
        if identity_json:
            identity["name"] = identity_json.get("current_name") or identity.get("name")
        else:
            return identity, "identity_join_failed"
    return identity, None


def _read_yaml(path: Path) -> dict[str, Any] | None:
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _org_from_identity(record: dict[str, Any], identity: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
    if not identity or identity.get("provider") != "desks" or not identity.get("id"):
        return None, None
    product = str(identity["name"]).split(":", 1)[0] if identity.get("name") else None
    if not product:
        return None, None

    org_root = _desks_root() / "organizations" / str(product)
    path = org_root / "current-organization.yaml"
    if not path.is_file():
        path = org_root / "current" / "organization.yaml"
    data = _read_yaml(path)
    if not data:
        return {"product": product}, None

    wanted = identity.get("id")
    for unit in data.get("units") or []:
        for program in unit.get("programs") or []:
            for fleet in program.get("fleets") or []:
                for seat in fleet.get("seats") or []:
                    if seat.get("identity_id") != wanted:
                        continue
                    current = identity.setdefault("current", {})
                    current["position"] = seat.get("role")
                    return {
                        "product": data.get("product") or product,
                        "unit": unit.get("unit"),
                        "program": program.get("program"),
                        "fleet": fleet.get("fleet/project") or fleet.get("fleet"),
                        "seat": seat.get("seat"),
                        "role": seat.get("role"),
                    }, None
    return {"product": data.get("product") or product}, "org_position_missing"


def _pending_for_target(target: str | None) -> tuple[bool, bool]:
    if not target:
        return False, False
    pending_queue = bool(queued_messages.list_records(status="pending", target=target))
    pending_deferred = any(row.get("target") == target for row in deferred.list_records(status="pending"))
    return pending_queue, pending_deferred


def _nearby_holding(fleet: str | None) -> list[dict[str, Any]]:
    if not fleet:
        return []
    return holding.list_records(fleet=fleet)


def _derive_managed_state(record: dict[str, Any], *, liveness: str, binding: str) -> str:
    if record.get("terminal_state") == "terminal" or record.get("restore_suppressed"):
        return "stopped"
    if liveness == "missing":
        return "missing_pane"
    stored = record.get("managed_state")
    if stored in {"spawned_bound", "spawned_unbound", "adopted_bound", "adopted_unbound", "stopped", "missing_pane"}:
        return stored
    adopted = bool(record.get("adoption_id") or str(record.get("registered_via") or "").startswith(("adopt", "holding-adopt")))
    prefix = "adopted" if adopted else "spawned"
    return f"{prefix}_{'bound' if binding == 'bound' else 'unbound'}"


def _base_rows(*, fleet: str | None, include_hidden: bool, include_ledger: bool = True) -> list[dict[str, Any]]:
    ledger_by_ref = {}
    if include_ledger:
        ledger_by_ref = {
            row.get("seat_ref") or _target(row.get("fleet"), _seat_name(row)): row
            for row in session_ledger.project_latest_from_ledger(fleet=fleet)
        }
    rows: list[dict[str, Any]] = []
    for agent in registry.list_agents(fleet, include_hidden=include_hidden):
        seat = _seat_name(agent)
        ref = agent.get("seat_ref") or _target(agent.get("fleet"), seat)
        merged = {**(ledger_by_ref.get(ref) or {}), **agent}
        if ref:
            merged.setdefault("seat_ref", ref)
        rows.append(merged)
    return rows


def build_from_record(
    record: dict[str, Any],
    *,
    terminal=None,
    latest_reports: dict[str, dict[str, Any]] | None = None,
    placements_by_target: dict[str, list[dict[str, Any]]] | None = None,
    pending_by_target: dict[str, tuple[bool, bool]] | None = None,
    keeper_ids: set[str] | None = None,
) -> dict[str, Any]:
    seat = _seat_name(record)
    fleet = record.get("fleet")
    target = _target(fleet, seat)
    liveness, status, checked_targets = _terminal_status(record, terminal=terminal)

    bound_record = runtime_session.mark_binding(dict(record))
    binding = bound_record.get("runtime_session_binding") or (
        "bound" if runtime_session.is_bound_session(bound_record) else "unbound"
    )
    runtime_session_id = bound_record.get("runtime_session_id") if binding == "bound" else None
    possible_matches = bound_record.get("runtime_session_possible_matches") or []
    identity, identity_flag = _identity_from_record(record)
    org, org_flag = _org_from_identity(record, identity)
    if not org and isinstance(record.get("org"), dict):
        org = dict(record["org"])
        org_flag = None
    restore = session_ledger.restore_status(
        {**bound_record, "runtime_session_id": runtime_session_id, "session_id": runtime_session_id},
        runtimes.capabilities(record.get("runtime")),
        keeper_ids=keeper_ids,
    )
    latest_report = (latest_reports or _latest_reports_by_target()).get(target or "")
    if pending_by_target is not None:
        pending_queue, pending_deferred = pending_by_target.get(target, (False, False))
    else:
        pending_queue, pending_deferred = _pending_for_target(target)
    nearby_holding = _nearby_holding(fleet)

    risk_flags: list[str] = []
    if binding != "bound" and record.get("runtime") not in {"shell", "command"}:
        risk_flags.append("unbound_runtime_session")
    if possible_matches:
        risk_flags.append("possible_runtime_session_matches")
    if liveness == "missing":
        risk_flags.append("missing_pane")
    if not identity:
        risk_flags.append("identity_missing")
    if identity_flag:
        risk_flags.append(identity_flag)
    if org_flag:
        risk_flags.append(org_flag)
    if latest_report and latest_report.get("stale"):
        risk_flags.append("latest_report_stale")
    if pending_queue:
        risk_flags.append("queued_messages_pending")
    if pending_deferred:
        risk_flags.append("deferred_deliveries_pending")
    if nearby_holding:
        risk_flags.append("holding_records_nearby")

    managed_state = _derive_managed_state(record, liveness=liveness, binding=binding)
    row = {
        "target": target,
        "name": seat,
        "seat": seat,
        "seat_ref": record.get("seat_ref") or target,
        "fleet": fleet,
        "logical_ref": record.get("logical_ref") or target,
        "logical_fleet": record.get("logical_fleet") or fleet,
        "logical_seat": record.get("logical_name") or seat,
        "physical_fleet": record.get("physical_fleet"),
        "fleet_id": record.get("fleet_id"),
        "managed_state": managed_state,
        "registered": bool(record.get("registered")),
        "hidden": bool(record.get("hidden")) or registry.is_hidden_fleet(fleet),
        "seat_instance_id": record.get("seat_instance_id"),
        "pane_ref": record.get("pane_ref"),
        "terminal_ref": record.get("terminal_ref"),
        "backend": record.get("backend"),
        "backend_ref": record.get("backend_ref"),
        "checked_targets": checked_targets,
        "runtime": record.get("runtime"),
        "runtime_profile": record.get("runtime_profile"),
        "runtime_profile_ref": record.get("runtime_profile_ref"),
        "runtime_profile_runtime": record.get("runtime_profile_runtime"),
        "runtime_profile_source": record.get("runtime_profile_source"),
        "cwd": record.get("runtime_session_cwd") or record.get("cwd") or record.get("workdir"),
        "liveness": liveness,
        "terminal": "alive" if liveness == "alive" else ("missing" if liveness == "missing" else record.get("terminal") or "unknown"),
        "status": status,
        "mode": record.get("delivery_mode") or record.get("mode"),
        "runtime_session_binding": binding,
        "runtime_session_id": runtime_session_id,
        "session_id": runtime_session_id,
        "runtime_session_possible_matches": possible_matches,
        "runtime_session_bind_method": bound_record.get("runtime_session_bind_method"),
        "runtime_session_bind_source": bound_record.get("runtime_session_bind_source"),
        "runtime_session_source": bound_record.get("runtime_session_source"),
        "runtime_session_confidence": bound_record.get("runtime_session_confidence"),
        "aura_launch_id": record.get("aura_launch_id"),
        "restore_ready": bool(restore.get("restore_ready")),
        "restore_reason": restore.get("restore_reason"),
        "identity": identity,
        "org": org,
        "latest_report": _report_summary(latest_report),
        "placements": (
            (placements_by_target or {}).get(target)
            if placements_by_target is not None
            else placements.placements_for_seat(target)
        ) or [],
        "risk_flags": risk_flags,
        "latest_event": record.get("latest_event"),
        "latest_event_id": record.get("latest_event_id"),
        "latest_event_at": record.get("latest_event_at"),
        "identity_provider": seat_schema.identity_provider_for(record),
        "identity_id": seat_schema.identity_id_for(record),
        "identity_label": (identity or {}).get("name") or record.get("identity_label"),
        "flex_project_manifest": record.get("flex_project_manifest"),
        "flex_project_root": record.get("flex_project_root"),
        "trace_cell": record.get("trace_cell"),
        "last_seen": record.get("last_seen"),
    }
    return seat_schema.enrich(row)


def build_seat_status(target: str, *, terminal=None) -> dict[str, Any]:
    record = registry.get_agent(target)
    if not record:
        return {"ok": False, "error": f"seat not found: {target}", "target": target}
    return {"ok": True, **build_from_record(record, terminal=terminal)}


def list_seat_statuses(
    fleet: str | None = None,
    *,
    include_hidden: bool = False,
    terminal=None,
    include_ledger: bool = True,
) -> list[dict[str, Any]]:
    latest_reports = _latest_reports_by_target()
    placements_by_target = placements.placements_by_seat()
    keeper_ids = session_ledger.keeper_thread_ids()
    pending_queue_targets = {
        row.get("target")
        for row in queued_messages.list_records(status="pending")
        if row.get("target")
    }
    pending_deferred_targets = {
        row.get("target")
        for row in deferred.list_records(status="pending")
        if row.get("target")
    }
    pending_by_target = {
        target: (target in pending_queue_targets, target in pending_deferred_targets)
        for target in pending_queue_targets | pending_deferred_targets
    }
    return [
        build_from_record(
            record,
            terminal=terminal,
            latest_reports=latest_reports,
            placements_by_target=placements_by_target,
            pending_by_target=pending_by_target,
            keeper_ids=keeper_ids,
        )
        for record in _base_rows(fleet=fleet, include_hidden=include_hidden, include_ledger=include_ledger)
    ]

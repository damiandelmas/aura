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
    if getattr(args, "sessions_action", None) == "footer":
        return _footer_candidate(args)
    if getattr(args, "sessions_action", None) == "bind-footer":
        return _bind_footer(args)
    if getattr(args, "sessions_action", None) == "resolve-pane":
        return _resolve_pane(args)
    if getattr(args, "sessions_action", None) == "bind-pane":
        return _bind_pane(args)
    if getattr(args, "sessions_action", None) == "restore-plan":
        return _restore_plan(args)
    if getattr(args, "sessions_action", None) == "heal":
        return _heal(args)
    if getattr(args, "sessions_action", None) == "reconcile-orphans":
        return _reconcile_orphans(args)
    if getattr(args, "sessions_action", None) == "compact-ledger":
        from lib import session_ledger

        return session_ledger.compact_ledger(force=bool(getattr(args, "force", False)))
    if getattr(args, "sessions_action", None) == "fleets":
        return _fleets(args)
    if getattr(args, "sessions_action", None) == "fleet-history":
        from commands import fleets as fleets_cmd

        return fleets_cmd.fleet_history(getattr(args, "nonce", None) or getattr(args, "target", None) or getattr(args, "fleet", None))

    inventory = list_cmd.run(argparse.Namespace(
        fleet=getattr(args, "fleet", None),
        status=None,
        mode=None,
        include_hidden=bool(getattr(args, "include_hidden", False)),
    ))
    rows = inventory.get("rows", inventory) if isinstance(inventory, dict) else inventory
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
            "identity_label": row.get("identity_label"),
            "agent_package_id": row.get("agent_package_id"),
            "agent_package_address": row.get("agent_package_address"),
            "agent_package_alias": row.get("agent_package_alias"),
            "agent_package_root": row.get("agent_package_root"),
            "codex_package_root": row.get("codex_package_root"),
            "codex_package_codex_home": row.get("codex_package_codex_home"),
            "omx_package_root": row.get("omx_package_root"),
            "omx_package_codex_home": row.get("omx_package_codex_home"),
            "omx_package_omx_root": row.get("omx_package_omx_root"),
            "omx_package_omx_state": row.get("omx_package_omx_state"),
            "omx_package_team_state_root": row.get("omx_package_team_state_root"),
            "runtime_home": row.get("runtime_home"),
            "codex_box_root": row.get("codex_box_root"),
            "codex_box_codex_home": row.get("codex_box_codex_home"),
            "omx_box_root": row.get("omx_box_root"),
            "omx_box_codex_home": row.get("omx_box_codex_home"),
            "omx_box_omx_root": row.get("omx_box_omx_root"),
            "omx_box_team_state_root": row.get("omx_box_team_state_root"),
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
    from lib import runtime_session, runtimes, session_ledger

    if getattr(args, "from_ledger", False):
        rows = session_ledger.project_latest_from_ledger(fleet=getattr(args, "fleet", None))
        rows = _enrich_restore_rows_from_launch_history(rows, runtime_session=runtime_session)
        plan = session_ledger.restore_plan_from_rows(rows, runtimes.capability_map())
        plan["source"] = "ledger"
        plan["latest_per_seat"] = bool(getattr(args, "latest_per_seat", False))
        return _add_restore_reconciliation(plan)

    rows_result = run(argparse.Namespace(
        sessions_action=None,
        fleet=getattr(args, "fleet", None),
        live=getattr(args, "live", False),
        include_hidden=getattr(args, "include_hidden", False),
    ))
    rows = _enrich_restore_rows_from_launch_history(
        rows_result.get("rows", []),
        runtime_session=runtime_session,
    )
    plan = session_ledger.restore_plan_from_rows(
        rows,
        runtimes.capability_map(),
    )
    return _add_restore_reconciliation(plan)


def _add_restore_reconciliation(plan: dict) -> dict:
    rows = []
    totals = {
        "placements": 0,
        "event_jobs": 0,
        "report_subscriptions": 0,
    }
    for row in plan.get("rows") or []:
        reconciliation = _restore_reconciliation_for_row(row)
        for key in totals:
            totals[key] += len(reconciliation.get(key) or [])
        rows.append({**row, "reconciliation": reconciliation})
    return {
        **plan,
        "rows": rows,
        "reconciliation": totals,
    }


def _restore_reconciliation_for_row(row: dict) -> dict:
    fleet = row.get("fleet")
    seat = row.get("seat") or row.get("name")
    target = f"{fleet}:{seat}" if fleet and seat else row.get("target") or row.get("seat_ref")
    placements_for_target = []
    event_jobs = []
    report_subscription_refs = []
    try:
        from lib import placements

        placements_for_target = placements.placements_for_seat(target)
    except Exception:
        placements_for_target = []
    placement_names = {record.get("name") for record in placements_for_target if record.get("name")}
    try:
        from lib import events

        for job in events.iter_jobs():
            if job.get("target") != target:
                continue
            event_jobs.append({
                "job_id": job.get("job_id"),
                "name": job.get("name"),
                "status": job.get("status"),
                "owner": job.get("sender"),
                "target": job.get("target"),
                "interval_seconds": job.get("interval_seconds"),
                "tick": job.get("tick"),
                "ticks": job.get("ticks"),
                "last_run_at": job.get("last_tick_at"),
                "next_tick_at": job.get("next_tick_at"),
                "last_error": job.get("last_error"),
                "consecutive_errors": job.get("consecutive_errors"),
            })
    except Exception:
        event_jobs = []
    try:
        from lib import report_subscriptions

        for subscription in report_subscriptions.list_records(include_removed=False):
            reasons = []
            if subscription.get("to") == target:
                reasons.append("recipient")
            if subscription.get("target") == target:
                reasons.append("source-target")
            if fleet and subscription.get("fleet") == fleet:
                reasons.append("source-fleet")
            if subscription.get("placement") in placement_names:
                reasons.append("source-placement")
            if not reasons:
                continue
            report_subscription_refs.append({
                "subscription_id": subscription.get("subscription_id"),
                "name": subscription.get("name"),
                "status": subscription.get("status"),
                "to": subscription.get("to"),
                "fleet": subscription.get("fleet"),
                "target": subscription.get("target"),
                "placement": subscription.get("placement"),
                "states": subscription.get("states") or [],
                "reasons": reasons,
            })
    except Exception:
        report_subscription_refs = []
    return {
        "target": target,
        "placements": placements_for_target,
        "event_jobs": event_jobs,
        "report_subscriptions": report_subscription_refs,
    }


def _enrich_restore_rows_from_launch_history(rows: list[dict], *, runtime_session) -> list[dict]:
    enriched = []
    for row in rows:
        enriched.append(_enrich_restore_row_from_launch_history(row, runtime_session=runtime_session))
    return enriched


def _enrich_restore_row_from_launch_history(row: dict, *, runtime_session) -> dict:
    runtime = str(row.get("runtime") or "").strip().lower()
    launch_id = row.get("aura_launch_id")
    if runtime not in {"codex", "omx"} or not launch_id:
        return row
    if runtime_session.is_bound_session(row):
        return row

    expected_cwd = row.get("runtime_session_cwd") or row.get("cwd") or row.get("workdir")
    found = _codex_session_from_nonce(
        str(launch_id),
        expected_cwd=expected_cwd,
        record=row,
    )
    if not found.get("ok"):
        warnings = list(row.get("warnings") or [])
        warning = "launch-history-session-not-found"
        if warning not in warnings:
            warnings.append(warning)
        return {
            **row,
            "warnings": warnings,
            "restore_launch_history_error": found.get("error"),
        }

    session_id = found.get("session_id") or found.get("runtime_session_id")
    if not session_id:
        return row
    evidence = {
        "reason": "launch-history-codex-jsonl",
        "nonce": launch_id,
        "jsonl": found.get("jsonl"),
        "matches": found.get("matches"),
    }
    return {
        **row,
        "session_id": session_id,
        "runtime_session_id": session_id,
        "runtime_session_source": "codex-jsonl:nonce",
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": "nonce-jsonl",
        "runtime_session_bind_source": "codex-jsonl:nonce",
        "runtime_session_confidence": "exact",
        "runtime_session_evidence": {key: value for key, value in evidence.items() if value is not None},
        "runtime_session_cwd": found.get("cwd") or expected_cwd,
        "runtime_session_jsonl": found.get("jsonl"),
        "runtime_session_timestamp": found.get("timestamp"),
        "restore_launch_history_recovered": True,
    }


def _heal(args) -> dict:
    """Re-attempt binding for alive + unbound codex/omx/claude-code seats.

    Selector (exactly one required):
      --target fleet:seat  → single seat
      --fleet NAME         → all seats in that fleet
      --all                → all registered seats

    Each candidate is classified: skip (unsupported-runtime / already-bound /
    not-alive), refused (body-gate failure), or healed (nonce or pane method).
    `--dry-run` performs zero registry writes and reports what would happen.
    """
    from lib import registry, runtime_session, terminal as terminal_mod

    target = getattr(args, "target", None)
    fleet_filter = getattr(args, "fleet", None)
    all_seats = bool(getattr(args, "all", False))
    dry_run = bool(getattr(args, "dry_run", False))
    repair = bool(getattr(args, "repair", False))

    # Require exactly one selector
    selectors = sum([bool(target), bool(fleet_filter), bool(all_seats)])
    if selectors == 0:
        return {
            "ok": False,
            "error": "heal requires one of --target, --fleet, or --all",
        }

    # Build the candidate records
    if target:
        fleet_t, seat_t = _target_fleet_seat(target)
        if not fleet_t or not seat_t:
            return {
                "ok": False,
                "error": "could not resolve target; pass --target fleet:seat",
                "target": target,
            }
        record = registry.get_agent(seat_t, fleet=fleet_t)
        if not record:
            return {
                "ok": False,
                "error": "target-seat-not-registered",
                "target": f"{fleet_t}:{seat_t}",
            }
        candidates = [record]
    elif fleet_filter:
        candidates = registry.list_agents(fleet=fleet_filter, include_hidden=True)
    else:
        candidates = registry.list_agents(include_hidden=True)

    results = []
    healed_count = 0
    refused_count = 0
    skipped_count = 0

    for record in candidates:
        seat = record.get("name") or record.get("seat") or ""
        fleet = record.get("fleet") or ""
        seat_target = f"{fleet}:{seat}" if fleet and seat else seat

        runtime = str(record.get("runtime") or "").strip().lower()

        # Heal-able runtimes: codex/omx bind via the launch nonce; claude-code binds
        # via the pane->session FK (the statusline-captured map) through attempt b.
        # Without claude-code here, the self-heal loop never rebinds claude seats —
        # bind-pane/bind-hook supported them, but heal (the sweep) did not.
        if runtime not in {"codex", "omx", "claude-code", "claude"}:
            results.append({
                "seat": seat_target,
                "status": "skipped",
                "reason": "unsupported-runtime",
                "runtime": runtime,
            })
            skipped_count += 1
            continue

        # Skip ONLY genuinely-bound seats — bound AND carrying a real
        # runtime_session_id. A PHANTOM-bound row (binding=bound but
        # runtime_session_id null) must NOT be skipped: it flows to the pane->session
        # FK resolve below and gets the real live session written. Without this the
        # phantom is invisible to the healer and stays stuck forever.
        if runtime_session.is_bound_session(record) and record.get("runtime_session_id"):
            results.append({
                "seat": seat_target,
                "status": "skipped",
                "reason": "already-bound",
                "session_id": record.get("runtime_session_id") or record.get("session_id"),
            })
            skipped_count += 1
            continue

        # Check liveness: seat must have a reachable terminal
        from lib import seat_status
        status_row = seat_status.build_from_record(record, terminal=terminal_mod)
        if status_row.get("terminal") != "alive":
            results.append({
                "seat": seat_target,
                "status": "skipped",
                "reason": "not-alive",
                "terminal": status_row.get("terminal"),
            })
            skipped_count += 1
            continue

        # Occupant-mismatch precheck: if the live pane carrying this seat's name
        # was born under a different seat_instance_id than the registry row, the
        # name was reused onto a stale row. Do not heal a fresh pane onto it.
        registry_si = record.get("seat_instance_id")
        pane_ref = record.get("pane_ref") or ""
        pane_id = None
        if "%" in pane_ref:
            last_segment = pane_ref.rsplit(":", 1)[-1]
            if last_segment.startswith("%"):
                pane_id = last_segment
        if registry_si and pane_id:
            try:
                from lib import pane_resolver
                res = pane_resolver.resolve_pane(pane=pane_id)
                if res.get("ok"):
                    pane_birth_si = pane_resolver._read_birth_env(res.get("pane_pid")).get(
                        "AURA_SEAT_INSTANCE_ID"
                    )
                    if pane_birth_si and str(pane_birth_si) != str(registry_si):
                        results.append({
                            "seat": seat_target,
                            "status": "skipped",
                            "reason": "occupant-mismatch-born-pane",
                            "expected_seat_instance_id": registry_si,
                            "actual_seat_instance_id": pane_birth_si,
                        })
                        skipped_count += 1
                        continue
            except Exception:
                pass

        # Attempt bind — nonce first, then pane fallback
        launch_id = record.get("aura_launch_id")
        expected_cwd = record.get("runtime_session_cwd") or record.get("cwd") or record.get("workdir")
        heal_result = None

        # --- attempt a: nonce via launch_id (codex/omx only; claude has no jsonl nonce) ---
        if launch_id and runtime in {"codex", "omx"}:
            found = _codex_session_from_nonce(
                str(launch_id),
                expected_cwd=expected_cwd,
                record=record,
            )
            if found.get("ok") and found.get("session_id"):
                session_id = found["session_id"]
                if dry_run:
                    heal_result = {
                        "seat": seat_target,
                        "status": "would-heal",
                        "method": "nonce",
                        "session_id": session_id,
                        "nonce": launch_id,
                        "jsonl": found.get("jsonl"),
                    }
                else:
                    evidence = {
                        "reason": "heal-nonce",
                        "nonce": launch_id,
                        "bound_after_spawn": True,
                        "jsonl": found.get("jsonl"),
                        "matches": found.get("matches"),
                    }
                    bind_result = _bind_registry_session(
                        fleet=fleet,
                        seat=seat,
                        previous=record,
                        session_id=session_id,
                        source="codex-jsonl:nonce",
                        confidence="exact",
                        evidence={k: v for k, v in evidence.items() if v is not None},
                        cwd=found.get("cwd") or expected_cwd,
                        event="session_bound_nonce",
                        repair=repair,
                    )
                    if bind_result.get("ok"):
                        heal_result = {
                            "seat": seat_target,
                            "status": "healed",
                            "method": "nonce",
                            "session_id": session_id,
                        }
                    else:
                        heal_result = {
                            "seat": seat_target,
                            "status": "refused",
                            "method": "nonce",
                            "reason": bind_result.get("reason") or bind_result.get("error"),
                            "detail": bind_result.get("detail"),
                        }

        # --- attempt b: pane resolve (fallback) ---
        if heal_result is None:
            pane_ref = record.get("pane_ref") or ""
            # Extract the %N pane id from a ref like "tmux:fleet:%26"
            pane_id = None
            if "%" in pane_ref:
                # last segment after the final ":"
                last_segment = pane_ref.rsplit(":", 1)[-1]
                if last_segment.startswith("%"):
                    pane_id = last_segment

            if pane_id:
                try:
                    from lib import pane_resolver
                    res = pane_resolver.resolve_pane(pane=pane_id)
                    gate = pane_resolver.bind_gates(res, previous=record, repair=repair)
                    if (
                        gate.get("ok")
                        and res.get("runtime_session_confidence") == "exact"
                        and res.get("runtime_session_id")
                    ):
                        session_id = res["runtime_session_id"]
                        source = res.get("runtime_session_source") or "tmux-pane:env"
                        if dry_run:
                            heal_result = {
                                "seat": seat_target,
                                "status": "would-heal",
                                "method": "pane",
                                "session_id": session_id,
                                "pane_ref": pane_ref,
                            }
                        else:
                            evidence = {
                                "reason": "heal-pane-resolve",
                                "pane_ref": pane_ref,
                                "pane_id": pane_id,
                            }
                            bind_result = _bind_registry_session(
                                fleet=fleet,
                                seat=seat,
                                previous=record,
                                session_id=session_id,
                                source=source,
                                confidence="exact",
                                evidence={k: v for k, v in evidence.items() if v is not None},
                                cwd=expected_cwd,
                                event="session_bound_pane",
                                repair=repair,
                            )
                            if bind_result.get("ok"):
                                heal_result = {
                                    "seat": seat_target,
                                    "status": "healed",
                                    "method": "pane",
                                    "session_id": session_id,
                                }
                            else:
                                heal_result = {
                                    "seat": seat_target,
                                    "status": "refused",
                                    "method": "pane",
                                    "reason": bind_result.get("reason") or bind_result.get("error"),
                                    "detail": bind_result.get("detail"),
                                }
                except Exception:
                    pass

        # If both attempts produced no exact evidence
        if heal_result is None:
            heal_result = {
                "seat": seat_target,
                "status": "skipped",
                "reason": "no-exact-evidence",
            }

        results.append(heal_result)
        status = heal_result.get("status")
        if status in ("healed", "would-heal"):
            healed_count += 1
        elif status == "refused":
            refused_count += 1
        else:
            skipped_count += 1

    return {
        "ok": True,
        "dry_run": dry_run,
        "results": results,
        "healed": healed_count,
        "refused": refused_count,
        "skipped": skipped_count,
    }


def _reconcile_orphaned_born_panes(*, fleet_filter: str | None = None, dry_run: bool = False) -> dict:
    """Recover registry rows for Aura-born panes that have no managed row.

    Iterates live tmux panes, skips any already in the registry by pane_ref,
    keeps only panes with complete birth env (AURA_SEAT_INSTANCE_ID required),
    reconstructs the thin row, and (unless dry-run) upserts it. Fork children
    are rejected by `_resolve_from_birth_env` and never reconstructed.
    """
    from lib import pane_resolver, registry, tmux_mirror

    mirror = tmux_mirror.list_physical_panes()
    if not mirror.get("ok"):
        return {"ok": False, "error": "tmux-mirror-unavailable", "detail": mirror.get("error")}

    known_pane_refs = {
        str(row.get("pane_ref"))
        for row in registry.read_registry().values()
        if row.get("pane_ref")
    }

    reconciled = 0
    skipped = 0
    results: list[dict] = []
    for pane in mirror.get("panes") or []:
        pane_ref = pane.get("pane_ref")
        if pane_ref and str(pane_ref) in known_pane_refs:
            skipped += 1
            continue
        birth_env = pane_resolver._read_birth_env(pane_resolver._pane_pid(pane))
        if fleet_filter and birth_env.get("AURA_FLEET") != fleet_filter:
            skipped += 1
            continue
        # Reconciliation requires a real occupant id to key continuity safely.
        if not birth_env.get("AURA_SEAT_INSTANCE_ID"):
            skipped += 1
            continue
        thin = pane_resolver._resolve_from_birth_env(pane, birth_env)
        if thin is None:
            skipped += 1
            continue
        target = f"{thin['fleet']}:{thin['seat']}"
        if dry_run:
            results.append({
                "target": target,
                "status": "would-reconcile",
                "pane_ref": pane_ref,
                "seat_instance_id": thin.get("seat_instance_id"),
            })
        else:
            registry.upsert_agent(thin)
            results.append({
                "target": target,
                "status": "reconciled",
                "pane_ref": pane_ref,
                "seat_instance_id": thin.get("seat_instance_id"),
            })
        reconciled += 1

    return {
        "ok": True,
        "dry_run": dry_run,
        "reconciled": reconciled,
        "skipped": skipped,
        "results": results,
    }


def _reconcile_orphans(args) -> dict:
    fleet_filter = getattr(args, "fleet", None)
    all_fleets = bool(getattr(args, "all", False))
    dry_run = bool(getattr(args, "dry_run", False))
    if not fleet_filter and not all_fleets:
        return {
            "ok": False,
            "error": "reconcile-orphans requires --fleet NAME or --all",
        }
    return _reconcile_orphaned_born_panes(
        fleet_filter=None if all_fleets else fleet_filter,
        dry_run=dry_run,
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
    record: dict | None = None,
) -> dict:
    if jsonl_path:
        pinned = Path(jsonl_path).expanduser()
        if not pinned.exists():
            return {"ok": False, "error": "pinned Codex JSONL not found", "nonce": nonce, "jsonl": str(pinned)}
        found = _read_codex_session_jsonl(pinned, nonce)
        if found.get("ok"):
            found.update({"nonce": nonce, "matches": 1})
        return found

    roots: list[Path] = []
    try:
        from lib import runtime_capsules

        roots.extend(runtime_capsules.capsule_codex_session_roots(record))
    except Exception:
        pass
    roots.extend(_package_codex_session_roots(record))
    roots.append(Path.home() / ".codex" / "sessions")

    seen = set()
    existing_roots = []
    for root in roots:
        resolved = str(root.expanduser())
        if resolved in seen:
            continue
        seen.add(resolved)
        if root.exists():
            existing_roots.append(root)
    if not existing_roots:
        return {"ok": False, "error": "codex sessions directory not found", "nonce": nonce}

    paths: list[Path] = []
    try:
        for root in existing_roots:
            result = subprocess.run(
                ["rg", "-l", nonce, str(root), "-g", "*.jsonl"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            paths.extend(Path(line) for line in result.stdout.splitlines() if line.strip())
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"nonce search failed: {exc}", "nonce": nonce}

    deduped_paths: list[Path] = []
    seen_paths = set()
    for path in paths:
        key = str(path)
        if key in seen_paths:
            continue
        seen_paths.add(key)
        deduped_paths.append(path)
    paths = deduped_paths
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


def _package_codex_session_roots(record: dict | None) -> list[Path]:
    if not record:
        return []
    roots = []
    for key in ("codex_package_codex_home", "omx_package_codex_home"):
        value = record.get(key)
        if value:
            roots.append(Path(str(value)).expanduser() / "sessions")
    package_root = record.get("agent_package_root") or record.get("codex_package_root") or record.get("omx_package_root")
    if package_root:
        roots.append(Path(str(package_root)).expanduser() / ".codex" / "sessions")
    return roots


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


FOOTER_KEYWORDS = ("session", "thread", "ctx", "context", "codex")


def _footer_candidate(args) -> dict:
    target_arg = getattr(args, "target", None)
    if not target_arg:
        return {"ok": False, "error": "footer requires --target"}
    fleet, seat = _target_fleet_seat(target_arg)
    if not fleet or not seat:
        return {"ok": False, "error": "could not resolve target; pass --target fleet:seat"}

    from lib import registry, runtime_session, terminal

    previous = registry.get_agent(seat, fleet=fleet)
    if not previous:
        return {"ok": False, "error": "target-seat-not-registered", "target": f"{fleet}:{seat}"}

    terminal_target = previous.get("pane_ref") or previous.get("terminal_ref") or f"{fleet}:{seat}"
    lines_count = max(int(getattr(args, "lines", None) or 80), 1)
    try:
        capture = terminal.capture_output(terminal_target, lines_count) or []
    except Exception as exc:
        return {
            "ok": False,
            "error": "footer-capture-failed",
            "target": f"{fleet}:{seat}",
            "terminal_target": terminal_target,
            "detail": str(exc),
        }
    candidates, source_scope = _footer_candidates_from_lines(capture, runtime_session.UUID_RE)
    registry_session_id = previous.get("runtime_session_id") or previous.get("session_id")
    unique_ids = [candidate["session_id"] for candidate in candidates]
    result = {
        "ok": True,
        "target": f"{fleet}:{seat}",
        "fleet": fleet,
        "seat": seat,
        "terminal_target": terminal_target,
        "line_count": len(capture),
        "source_scope": source_scope,
        "candidate_count": len(unique_ids),
        "candidates": candidates,
        "ambiguous": len(unique_ids) > 1,
        "registry_session_id": registry_session_id,
    }
    if len(unique_ids) == 1:
        result["candidate"] = candidates[0]
        result["stale_registry_session"] = bool(registry_session_id and registry_session_id != unique_ids[0])
    else:
        result["stale_registry_session"] = False
    return result


def _footer_candidates_from_lines(lines: list[str], uuid_re) -> tuple[list[dict], str]:
    indexed = list(enumerate(lines))
    keyword_lines = [
        item for item in indexed
        if any(keyword in str(item[1]).lower() for keyword in FOOTER_KEYWORDS)
    ]
    source_scope = "footer-keyword"
    scan = keyword_lines
    if not scan:
        scan = indexed
        source_scope = "capture-fallback"
    seen = set()
    candidates = []
    for index, line in reversed(scan):
        for match in uuid_re.finditer(str(line)):
            session_id = match.group(0)
            if session_id in seen:
                continue
            seen.add(session_id)
            candidates.append({
                "session_id": session_id,
                "line_index": index,
                "line_preview": str(line).strip()[:200],
                "source_scope": source_scope,
            })
    return candidates, source_scope


def _bind_footer(args) -> dict:
    if not getattr(args, "target", None):
        return {"ok": False, "error": "bind-footer requires --target"}
    footer = _footer_candidate(args)
    if not footer.get("ok"):
        return footer
    if footer.get("ambiguous"):
        return {**footer, "ok": False, "error": "footer-session-ambiguous"}
    candidate = footer.get("candidate")
    if not candidate:
        return {**footer, "ok": False, "error": "footer-session-not-found"}

    from lib import registry

    fleet = footer["fleet"]
    seat = footer["seat"]
    previous = registry.get_agent(seat, fleet=fleet)
    if not previous:
        return {"ok": False, "error": "target-seat-not-registered", "target": footer["target"]}
    expected_instance = getattr(args, "seat_instance_id", None)
    actual_instance = previous.get("seat_instance_id")
    if expected_instance and actual_instance and expected_instance != actual_instance:
        return {
            "ok": False,
            "error": "seat-instance-mismatch",
            "target": footer["target"],
            "expected_seat_instance_id": expected_instance,
            "actual_seat_instance_id": actual_instance,
        }
    previous_session_id = previous.get("runtime_session_id") or previous.get("session_id")
    evidence = {
        "reason": "codex-footer-capture",
        "target": footer["target"],
        "terminal_target": footer["terminal_target"],
        "session_id": candidate["session_id"],
        "source_scope": candidate.get("source_scope") or footer.get("source_scope"),
        "line_index": candidate.get("line_index"),
        "line_preview": candidate.get("line_preview"),
        "line_count": footer.get("line_count"),
        "seat_instance_id": actual_instance,
    }
    if previous_session_id and previous_session_id != candidate["session_id"]:
        evidence["stale_previous_session_id"] = previous_session_id
        evidence["stale_previous_session_source"] = previous.get("runtime_session_source")
    plan = {
        "ok": True,
        "target": footer["target"],
        "session_id": candidate["session_id"],
        "runtime_session_id": candidate["session_id"],
        "runtime_session_source": "codex-footer:capture",
        "runtime_session_confidence": "exact",
        "dry_run": bool(getattr(args, "dry_run", False)),
        "evidence": evidence,
    }
    if plan["dry_run"]:
        return plan
    result = _bind_registry_session(
        fleet=fleet,
        seat=seat,
        previous=previous,
        session_id=candidate["session_id"],
        source="codex-footer:capture",
        confidence="exact",
        evidence=evidence,
        cwd=previous.get("runtime_session_cwd") or previous.get("cwd") or previous.get("workdir"),
        event="session_bound_footer",
        extra={
            "target": footer["target"],
            "terminal_target": footer["terminal_target"],
            "stale_previous_session_id": evidence.get("stale_previous_session_id"),
            "stale_previous_session_source": evidence.get("stale_previous_session_source"),
        },
    )
    return result


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
        record=previous,
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


def _resolve_pane(args) -> dict:
    from lib import pane_resolver

    return pane_resolver.resolve_pane(
        pane=getattr(args, "pane", None),
        current=bool(getattr(args, "current", False)),
    )


def _bind_pane(args) -> dict:
    from lib import pane_resolver, registry

    res = pane_resolver.resolve_pane(
        pane=getattr(args, "pane", None),
        current=bool(getattr(args, "current", False)),
    )
    if not res.get("ok"):
        return res

    target = getattr(args, "target", None)
    fleet, seat = _target_fleet_seat(target) if target else (None, None)
    matched = res.get("matched_row") or {}
    fleet = fleet or matched.get("fleet")
    seat = seat or matched.get("seat")

    # Self-heal: an Aura-born pane without a managed row still carries its birth
    # env, so recover fleet/seat from AURA_FLEET/AURA_SEAT before refusing.
    birth_env = pane_resolver._read_birth_env(res.get("pane_pid"))
    if not fleet or not seat:
        fleet = fleet or birth_env.get("AURA_FLEET")
        seat = seat or birth_env.get("AURA_SEAT")
    if not fleet or not seat:
        return {
            "ok": False,
            "error": "no-target",
            "detail": "pane is unmanaged and not Aura-born (no AURA_FLEET/AURA_SEAT env); pass --target fleet:seat",
            "resolved": res,
        }

    fleet, seat, previous, alias_chain = _canonical_bind_target(registry, fleet=fleet, seat=seat)

    # If no live row exists but the pane is Aura-born, synthesize a thin row so
    # bind_gates runs its real si/package vetoes against the seat's birth identity.
    if previous is None and birth_env:
        previous = pane_resolver._resolve_from_birth_env(res, birth_env)

    gate = pane_resolver.bind_gates(
        res,
        previous=previous,
        repair=bool(getattr(args, "repair", False)),
    )
    if not gate.get("ok"):
        return {
            "ok": False,
            "error": gate.get("reason"),
            "detail": gate.get("detail"),
            **{key: value for key, value in gate.items() if key not in {"ok", "reason", "detail"}},
            "resolved": res,
        }

    previous = previous or {
        "name": seat,
        "fleet": fleet,
        "runtime": res.get("runtime_hint") or "codex",
        "registered": True,
        "status": "unknown",
    }
    source = res.get("runtime_session_source") or "tmux-pane:env"
    method = source.split(":", 1)[-1]
    evidence = {
        "reason": "tmux-pane-resolver",
        "method": method,
        "pane_ref": res.get("pane_ref"),
        "pane_pid": res.get("pane_pid"),
        "transcript_path": res.get("transcript_path"),
        "package_env_status": (res.get("package_env_status") or {}).get("status"),
        "evidence": res.get("runtime_session_evidence"),
    }
    cwd = (
        previous.get("runtime_session_cwd")
        or previous.get("cwd")
        or previous.get("workdir")
        or res.get("pane_current_path")
    )
    return _bind_registry_session(
        fleet=fleet,
        seat=seat,
        previous=previous,
        session_id=res["runtime_session_id"],
        source=source,
        confidence="exact",
        evidence={key: value for key, value in evidence.items() if value is not None},
        cwd=cwd,
        event="session_bound_pane",
        extra={
            "target": f"{fleet}:{seat}",
            "pane_ref": res.get("pane_ref"),
            "transcript_path": res.get("transcript_path"),
            "alias_chain": alias_chain,
        },
        # The pane path already ran the full pane-env veto via pane_resolver.bind_gates
        # above; forward repair so the writer's record-internal veto does not
        # double-gate a legitimate operator --repair rebind.
        repair=bool(getattr(args, "repair", False)),
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
    if runtime not in {"codex", "claude-code"}:
        return {
            "ok": False,
            "error": "bind-hook supports codex and claude-code runtimes only",
            "runtime": runtime,
        }

    fleet, seat = _target_fleet_seat(getattr(args, "target", None))
    if not fleet or not seat:
        return {"ok": False, "error": "could not infer target fleet/seat; pass --target fleet:seat"}

    from lib import registry

    expected_instance = getattr(args, "seat_instance_id", None)
    fleet, seat, previous, alias_chain = _canonical_bind_target(registry, fleet=fleet, seat=seat)
    if not previous and expected_instance:
        # Occupant-keyed continuity: the hook carries this seat's instance id.
        # If the launch-time name is stale (e.g. the seat was renamed), rebind by
        # occupant rather than following a name alias — the durable thread of
        # continuity is the seat_instance_id, not the name.
        occupant = registry.resolve_occupant(seat_instance_id=expected_instance)
        if occupant:
            fleet = occupant.get("fleet") or fleet
            seat = occupant.get("name") or occupant.get("seat") or seat
            previous = occupant
    if not previous:
        return {
            "ok": False,
            "error": "target seat is not registered; adopt or spawn it before hook binding",
            "target": f"{fleet}:{seat}",
        }

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
    hook_kind = "claude-hook" if runtime == "claude-code" else "codex-hook"
    source = f"{hook_kind}:{hook_event}"
    transcript_path = getattr(args, "transcript_path", None)
    cwd = previous.get("runtime_session_cwd") or previous.get("cwd") or previous.get("workdir")
    evidence = {
        "reason": f"{hook_kind.replace('-hook', '')}-native-hook",
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
    previous = registry.resolve_live(seat, fleet=fleet)
    return fleet, seat, previous, []


def _is_package_agent_record(record: dict | None) -> bool:
    if not record:
        return False
    if record.get("agent_package_id") or record.get("agent_package_root"):
        return True
    for key in ("runtime_capsule_root", "runtime_home", "omx_box_root", "codex_box_root"):
        raw = record.get(key)
        if not raw:
            continue
        root = Path(str(raw)).expanduser()
        if (root / "manifest.json").exists():
            return True
    return False


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
    env: dict[str, str] | None = None,
    repair: bool = False,
) -> dict:
    from lib import bind_guard, registry, runtime_session, session_ledger

    # Universal body-integrity veto: a real session id must never bind onto a
    # contaminated or wrong body. This is the single chokepoint every bind writer
    # (pane, hook, nonce, current, footer, spawn observe/nonce/resume) flows
    # through. `env` is the body's process env (in-body hook binds pass os.environ;
    # spawner-side binds pass None -> record-internal checks only). `repair=True`
    # is the operator override.
    gate = bind_guard.body_gates(previous, env=env, repair=repair)
    if not gate.get("ok"):
        return {
            "ok": False,
            "error": "body-gate-refused",
            "reason": gate.get("reason"),
            "detail": gate.get("detail"),
            "seat": seat,
            "fleet": fleet,
            "session_id": session_id,
            "runtime_session_source": source,
            "mismatches": gate.get("mismatches"),
            "expected_seat_instance_id": gate.get("expected_seat_instance_id"),
            "actual_seat_instance_id": gate.get("actual_seat_instance_id"),
            "registry_updated": False,
        }

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
    capsule_session = {}
    capsule_record = {**updated, **(extra or {})}
    if _is_package_agent_record(capsule_record):
        capsule_session = {"ok": False, "skipped": True, "reason": "package-agent-native-session-store"}
    else:
        try:
            from lib import runtime_capsules

            capsule_session = runtime_capsules.write_runtime_session(capsule_record)
            if capsule_session.get("ok"):
                updated = registry.upsert_agent({
                    **updated,
                    "runtime_capsule_ref": capsule_session.get("capsule_root"),
                    "runtime_capsule_session": capsule_session.get("path"),
                })
        except Exception as exc:
            capsule_session = {"ok": False, "reason": "capsule-session-write-failed", "error": str(exc)}
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
    }
    if capsule_session.get("ok"):
        result.update({
            "runtime_capsule_ref": capsule_session.get("capsule_root"),
            "runtime_capsule_session": capsule_session.get("path"),
        })
    if extra:
        result.update(extra)
    return result

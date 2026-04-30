"""Deterministic Aura Ether state packets and recommendations."""

from __future__ import annotations

from typing import Any

from lib import delivery, deferred, events, recommendations, session_ledger
from lib.events import now_iso


def _seat_matches(record: dict[str, Any], seats: set[str]) -> bool:
    target = record.get("target")
    sender = record.get("sender")
    return target in seats or sender in seats


def _signal(kind: str, *, subject: str | None, summary: str, severity: str, source: str, provenance: dict[str, Any], at: str | None = None, confidence: str = "high") -> dict[str, Any]:
    return {
        "schema": "aura.ether.signal.v1",
        "kind": kind,
        "subject": subject,
        "summary": summary,
        "confidence": confidence,
        "severity": severity,
        "provenance": {"source": source, **provenance},
        "at": at,
    }


def _delivery_key(record: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    return (record.get("sender"), record.get("target"), record.get("dedupe_key"))


def _active_blocked_records(
    records: list[dict[str, Any]],
    deferred_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return blocked delivery records that have not been resolved by later delivery."""
    delivered_keys = {
        _delivery_key(record)
        for record in records
        if record.get("state") == "delivered" and record.get("dedupe_key")
    }
    delivered_deferred_message_ids = {
        record.get("blocked_message_id")
        for record in deferred_records
        if record.get("status") == "delivered" and record.get("blocked_message_id")
    }
    delivered_deferred_keys = {
        (record.get("sender"), record.get("target"), record.get("dedupe_key"))
        for record in deferred_records
        if record.get("status") == "delivered" and record.get("dedupe_key")
    }

    active = []
    for record in records:
        if record.get("state") != "blocked":
            continue
        key = _delivery_key(record)
        if record.get("message_id") in delivered_deferred_message_ids:
            continue
        if record.get("dedupe_key") and (key in delivered_keys or key in delivered_deferred_keys):
            continue
        active.append(record)
    return active


def build_state_packet(objective: dict[str, Any], *, delivery_limit: int = 200) -> dict[str, Any]:
    objective_id = objective["objective_id"]
    seats = set(objective.get("seats") or [])
    records = [
        record
        for record in delivery.iter_records(limit=delivery_limit)
        if _seat_matches(record, seats)
    ]
    all_deferred_records = [
        record for record in deferred.list_records()
        if _seat_matches(record, seats)
    ]
    blocked = _active_blocked_records(records, all_deferred_records)
    ambiguous = [record for record in records if record.get("state") == "ambiguous"]
    delivered = [record for record in records if record.get("state") == "delivered"]
    signals = []
    for record in blocked:
        signals.append(_signal(
            "delivery.blocked",
            subject=record.get("target"),
            summary=f"delivery to {record.get('target')} blocked: {record.get('error') or record.get('reason')}",
            severity="high",
            source="delivery-ledger",
            provenance={
                "message_id": record.get("message_id"),
                "delivery_id": record.get("delivery_id"),
            },
            at=record.get("updated_at") or record.get("created_at"),
        ))
    for record in ambiguous:
        signals.append(_signal(
            "delivery.ambiguous",
            subject=record.get("target"),
            summary=f"delivery to {record.get('target')} ambiguous",
            severity="medium",
            source="delivery-ledger",
            provenance={"message_id": record.get("message_id"), "delivery_id": record.get("delivery_id")},
            at=record.get("updated_at") or record.get("created_at"),
        ))

    deferred_records = [
        record for record in all_deferred_records
        if record.get("status") in {"pending", "retrying"}
    ]
    for record in deferred_records:
        signals.append(_signal(
            "delivery.deferred",
            subject=record.get("target"),
            summary=f"deferred delivery to {record.get('target')} is {record.get('status')}",
            severity="medium",
            source="deferred-outbox",
            provenance={"deferred_id": record.get("deferred_id"), "blocked_message_id": record.get("blocked_message_id")},
            at=record.get("updated_at") or record.get("created_at"),
        ))

    session_records = [
        record for record in session_ledger.iter_records(limit=delivery_limit)
        if (f"{record.get('fleet')}:{record.get('seat') or record.get('name')}" in seats)
        or ((record.get("seat") or record.get("name")) in seats)
    ]
    for record in session_records[-20:]:
        event = record.get("event") or "session"
        signals.append(_signal(
            f"session.{event}",
            subject=f"{record.get('fleet')}:{record.get('seat') or record.get('name')}" if record.get("fleet") else (record.get("seat") or record.get("name")),
            summary=f"session ledger event {event}",
            severity="info",
            source="session-ledger",
            provenance={"runtime_session_id": record.get("runtime_session_id"), "event": event},
            at=record.get("timestamp"),
            confidence=record.get("runtime_session_confidence") or "medium",
        ))

    event_jobs = [
        job for job in events.iter_jobs()
        if job.get("target") in seats or job.get("sender") in seats
    ]
    for job in event_jobs:
        errors = int(job.get("consecutive_errors") or 0)
        if errors:
            signals.append(_signal(
                "event.errors",
                subject=job.get("target"),
                summary=f"event job {job.get('name') or job.get('job_id')} has {errors} consecutive errors",
                severity="high",
                source="event-scheduler",
                provenance={"job_id": job.get("job_id"), "name": job.get("name"), "consecutive_errors": errors},
                at=job.get("updated_at"),
            ))
    blocked_subjects = {
        signal.get("subject")
        for signal in signals
        if signal.get("subject")
        and (
            signal.get("kind") in {"delivery.blocked", "event.errors"}
            or signal.get("severity") == "high"
        )
    }
    return {
        "schema": "aura.ether.state_packet.v1",
        "objective_id": objective_id,
        "at": now_iso(),
        "observe_vector": {
            "seats": sorted(seats),
            "receipts": [],
            "blockers": signals,
            "drift": [],
            "user_notes": [],
        },
        "state_vector": {
            "active": [],
            "idle_with_next_work": [],
            "blocked": sorted(blocked_subjects),
            "needs_decision": [],
            "parked": [],
            "complete": [],
        },
        "delivery_vector": {
            "blocked_messages": blocked,
            "ambiguous_messages": ambiguous,
            "deferred_messages": deferred_records,
            "delivered_messages": delivered[-20:],
        },
        "session_vector": {
            "records": session_records[-20:],
        },
        "event_vector": {
            "jobs": event_jobs,
        },
        "signals": signals,
        "provenance": [
            {
                "source": "delivery-ledger",
                "record_count": len(records),
                "delivery_limit": delivery_limit,
            },
            {
                "source": "deferred-outbox",
                "record_count": len(deferred_records),
            },
            {
                "source": "session-ledger",
                "record_count": len(session_records),
            },
            {
                "source": "event-scheduler",
                "record_count": len(event_jobs),
            },
        ],
    }


def evaluate_objective(objective: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    packet = build_state_packet(objective)
    blocked = packet["delivery_vector"]["blocked_messages"]
    recommendation = None
    resolved_recommendations = []
    if blocked:
        latest = blocked[-1]
        target = latest.get("target")
        sender = latest.get("sender")
        recommendation = {
            "schema": "aura.ether.recommendation.v1",
            "objective_id": objective["objective_id"],
            "state": "blocked_delivery",
            "signals": packet.get("signals") or [],
            "recommendation": {
                "action": "manager_dialogue",
                "target": target,
                "sender": sender,
                "proposed_message": (
                    f"Delivery from {sender} to {target} is blocked with "
                    f"{latest.get('error') or latest.get('reason')}. Decide whether to defer, retry when ready, "
                    "or ask the sender to refresh the message."
                ),
            },
            "urgency": "high",
            "confidence": "high",
            "rationale": "An objective participant has an undelivered blocked message.",
            "provenance": [{
                "source": "delivery-ledger",
                "message_id": latest.get("message_id"),
                "delivery_id": latest.get("delivery_id"),
            }],
            "status": "open",
            "created_at": now_iso(),
        }
        if not dry_run:
            existing = recommendations.find_open(
                objective_id=objective["objective_id"],
                state="blocked_delivery",
                target=target,
                provenance_key=("delivery_id", latest.get("delivery_id")),
            )
            recommendation = existing or recommendations.append_recommendation(recommendation)
    elif not dry_run:
        resolved_recommendations = recommendations.mark_matching_open(
            objective_id=objective["objective_id"],
            state="blocked_delivery",
            status="superseded",
            reason="state-cleared",
        )
    return {
        "ok": True,
        "objective_id": objective["objective_id"],
        "state_packet": packet,
        "recommendation": recommendation,
        "resolved_recommendations": resolved_recommendations,
        "recorded": bool(recommendation and not dry_run),
        "dry_run": dry_run,
    }

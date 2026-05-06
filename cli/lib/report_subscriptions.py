"""Persistent report subscriptions released through normal Aura send."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid

from lib import events


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_subscription_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%y%m%d_%H%M%S")
    return f"rsub_{stamp}_{uuid.uuid4().hex[:8]}"


def subscriptions_root() -> Path:
    return events.events_root() / "subscriptions" / "reports"


def names_root() -> Path:
    return subscriptions_root() / "names"


def subscription_path(subscription_id: str) -> Path:
    return subscriptions_root() / f"{subscription_id}.json"


def name_path(name: str) -> Path:
    safe = name.replace("/", "_")
    return names_root() / f"{safe}.json"


def _save(record: dict[str, Any]) -> dict[str, Any]:
    record["updated_at"] = now_iso()
    events.atomic_write_json(subscription_path(record["subscription_id"]), record)
    if record.get("name"):
        events.atomic_write_json(
            name_path(record["name"]),
            {
                "schema": "aura.event.report_subscription_name.v1",
                "name": record["name"],
                "subscription_id": record["subscription_id"],
            },
        )
    return record


def create(
    *,
    name: str,
    to: str,
    fleet: str | None = None,
    target: str | None = None,
    states: list[str] | None = None,
    sender: str = "aura-event",
) -> dict[str, Any]:
    now = now_iso()
    record = {
        "schema": "aura.event.report_subscription.v1",
        "subscription_id": new_subscription_id(),
        "name": name,
        "kind": "report_subscription",
        "source": "reports",
        "to": to,
        "sender": sender,
        "fleet": fleet,
        "target": target,
        "states": states or [],
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "reports": {},
    }
    return _save(record)


def resolve_subscription_id(ref: str) -> str:
    direct = subscription_path(ref)
    if direct.exists():
        return ref
    index = name_path(ref)
    if index.exists():
        data = json.loads(index.read_text(encoding="utf-8"))
        return data["subscription_id"]
    raise FileNotFoundError(f"report subscription not found: {ref}")


def load(ref: str) -> dict[str, Any]:
    subscription_id = resolve_subscription_id(ref)
    path = subscription_path(subscription_id)
    return json.loads(path.read_text(encoding="utf-8"))


def list_records(*, status: str | None = None, include_removed: bool = False) -> list[dict[str, Any]]:
    root = subscriptions_root()
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("rsub_*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not include_removed and record.get("status") == "removed":
            continue
        if status and record.get("status") != status:
            continue
        records.append(record)
    return records


def set_status(ref: str, status: str) -> dict[str, Any]:
    if status not in {"active", "paused", "removed"}:
        raise ValueError(f"invalid subscription status: {status}")
    record = load(ref)
    record["status"] = status
    return _save(record)


def _report_targets(report: dict[str, Any]) -> set[str]:
    seat = report.get("seat")
    fleet = report.get("fleet")
    targets = set()
    if seat:
        targets.add(str(seat))
    if seat and fleet:
        targets.add(f"{fleet}:{seat}")
    return targets


def _matches_target(target: str, report: dict[str, Any]) -> bool:
    report_targets = _report_targets(report)
    if target in report_targets:
        return True
    try:
        from lib import registry

        resolved, chain = registry.resolve_alias(target)
        return bool(chain and resolved in report_targets)
    except Exception:
        return False


def matches_report(record: dict[str, Any], report: dict[str, Any]) -> bool:
    if record.get("status") != "active":
        return False
    states = set(record.get("states") or [])
    if states and report.get("state") not in states:
        return False
    if record.get("fleet") and report.get("fleet") != record["fleet"]:
        return False
    if record.get("target") and not _matches_target(str(record["target"]), report):
        return False
    return True


def schedule_for_report(report: dict[str, Any], *, delay_seconds: float = 1.5) -> list[dict[str, Any]]:
    scheduled: list[dict[str, Any]] = []
    report_id = report.get("report_id")
    if not report_id:
        return scheduled
    for record in list_records(status="active"):
        if not matches_report(record, report):
            continue
        reports = dict(record.get("reports") or {})
        prior = reports.get(report_id)
        if prior and prior.get("status") in {"scheduled", "notified", "notify_failed"}:
            continue
        reports[report_id] = {
            "status": "scheduled",
            "scheduled_at": now_iso(),
            "release_delay_seconds": delay_seconds,
        }
        record["reports"] = reports
        scheduled.append(_save(record))
    return scheduled


def render_report_message(report: dict[str, Any]) -> str:
    source = ":".join(part for part in [report.get("fleet"), report.get("seat")] if part) or "unknown"
    lines = [
        f"[AURA REPORT state={report.get('state')} from={source}]",
        f"work: {report.get('work') or ''}",
    ]
    if report.get("done"):
        lines.append("done:")
        lines.extend(f"- {item}" for item in report.get("done") or [])
    if report.get("receipts"):
        lines.append("receipts:")
        lines.extend(f"- {item}" for item in report.get("receipts") or [])
    if report.get("blockers"):
        lines.append("blockers:")
        lines.extend(f"- {item}" for item in report.get("blockers") or [])
    if report.get("next"):
        lines.append(f"next: {report.get('next')}")
    lines.append(f"report_id: {report.get('report_id')}")
    return "\n".join(lines)


def release_for_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    from commands import send

    released: list[dict[str, Any]] = []
    report_id = report.get("report_id")
    if not report_id:
        return released
    for record in list_records():
        reports = dict(record.get("reports") or {})
        state = reports.get(report_id) or {}
        if state.get("status") != "scheduled":
            continue
        args = argparse.Namespace(
            target=record.get("to"),
            message=render_report_message(report),
            sender=record.get("sender") or "aura-event",
            mode=None,
            nudge=False,
            transport="auto",
            dedupe_key=f"report-sub:{record.get('subscription_id')}:{report_id}",
            force=True,
            allow_hidden=False,
            defer_if_busy=False,
            defer_ttl="15m",
            defer_retry_every="15s",
            no_deferred_daemon=True,
        )
        try:
            result = send.run(args)
        except Exception as exc:
            result = {"ok": False, "error": f"report subscription send failed: {exc}"}
        state = {
            **state,
            "notified_at": now_iso(),
            "ok": bool(result and result.get("ok")),
            "result": result,
        }
        if result and result.get("ok"):
            state["status"] = "notified"
            state["message_id"] = result.get("message_id")
        else:
            state["status"] = "notify_failed"
            state["error"] = (result or {}).get("error") or "send failed"
        reports[report_id] = state
        record["reports"] = reports
        released.append(_save(record))
    return released

"""Intentional pending messages released by worker reports."""

from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
import uuid
from pathlib import Path
from typing import Any

from lib import state


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_queue_id() -> str:
    return f"aura-queue-{uuid.uuid4().hex[:12]}"


def queue_root() -> Path:
    return state.state_root() / "queue" / "messages"


def queue_path(queue_id: str) -> Path:
    return queue_root() / f"{queue_id}.json"


def _atomic_write(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, sort_keys=True, indent=2), encoding="utf-8")
    tmp.replace(path)


def create(
    *,
    target: str,
    message: str,
    sender: str,
    sender_kind: str | None = None,
    after: str = "next-report",
) -> dict[str, Any]:
    record = {
        "schema": "aura.queue.v1",
        "queue_id": new_queue_id(),
        "target": target,
        "message": message,
        "sender": sender,
        "after": after,
        "status": "pending",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "attempts": [],
    }
    if sender_kind is not None:
        record["sender_kind"] = sender_kind
    _atomic_write(queue_path(record["queue_id"]), record)
    return record


def save(record: dict[str, Any]) -> dict[str, Any]:
    record["updated_at"] = now_iso()
    _atomic_write(queue_path(record["queue_id"]), record)
    return record


def load(queue_id: str) -> dict[str, Any]:
    path = queue_path(queue_id)
    if not path.exists():
        raise FileNotFoundError(f"queued message not found: {queue_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_records(*, status: str | None = None, target: str | None = None) -> list[dict[str, Any]]:
    root = queue_root()
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("aura-queue-*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if status and record.get("status") != status:
            continue
        if target and record.get("target") != target:
            continue
        records.append(record)
    return records


def _report_targets(report: dict[str, Any]) -> set[str]:
    seat = report.get("seat")
    fleet = report.get("fleet")
    targets = set()
    if seat:
        targets.add(str(seat))
    if seat and fleet:
        targets.add(f"{fleet}:{seat}")
    return targets


def _matches_report(record: dict[str, Any], report: dict[str, Any]) -> bool:
    status = record.get("status")
    if status == "scheduled":
        return record.get("release_report_id") == report.get("report_id")
    if status != "pending":
        return False
    after = record.get("after") or "next-report"
    if after != "next-report":
        return after == report.get("report_id")
    report_targets = _report_targets(report)
    target = record.get("target")
    if target in report_targets:
        return True
    if target:
        try:
            from lib import registry

            resolved, chain = registry.resolve_alias(str(target))
            if chain and resolved in report_targets:
                return True
        except Exception:
            pass
    return False


def schedule_for_report(report: dict[str, Any], *, delay_seconds: float = 1.5) -> list[dict[str, Any]]:
    """Mark matching pending queue records as approved for delayed release."""
    scheduled: list[dict[str, Any]] = []
    for record in list_records(status="pending"):
        if not _matches_report(record, report):
            continue
        record["status"] = "scheduled"
        record["release_report_id"] = report.get("report_id")
        record["scheduled_at"] = now_iso()
        record["release_delay_seconds"] = delay_seconds
        scheduled.append(save(record))
    return scheduled


def release_for_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    """Release queued messages whose condition is satisfied by a report."""
    from commands import send

    released: list[dict[str, Any]] = []
    for record in list_records():
        if not _matches_report(record, report):
            continue
        args = argparse.Namespace(
            target=record.get("target"),
            message=record.get("message") or "",
            sender=None if record.get("sender_kind") == "service" else (record.get("sender") or "queue"),
            service_sender=record.get("sender") if record.get("sender_kind") == "service" else None,
            mode=None,
            nudge=False,
            transport="auto",
            dedupe_key=f"queue:{record.get('queue_id')}",
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
            result = {"ok": False, "error": f"queue release send failed: {exc}"}
        attempts = list(record.get("attempts") or [])
        attempts.append({
            "at": now_iso(),
            "report_id": report.get("report_id"),
            "ok": bool(result and result.get("ok")),
            "result": result,
        })
        record["attempts"] = attempts
        record["release_report_id"] = report.get("report_id")
        if result and result.get("ok"):
            record["status"] = "released"
            record["released_at"] = now_iso()
            record["release_message_id"] = result.get("message_id")
            record.pop("error", None)
        else:
            record["status"] = "release_failed"
            record["error"] = (result or {}).get("error") or "send failed"
        released.append(save(record))
    return released

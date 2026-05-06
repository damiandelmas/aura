"""Record a small semantic worker report."""

from __future__ import annotations

import os
import subprocess
import sys

from lib import reports


QUEUE_RELEASE_DELAY_SECONDS = 1.5
REPORT_SUBSCRIPTION_DELAY_SECONDS = 1.5


def _start_queued_release_worker(report_id: str) -> None:
    env = os.environ.copy()
    cmd = [
        sys.executable,
        sys.argv[0],
        "queue",
        "--release-report",
        report_id,
        "--delay",
        str(QUEUE_RELEASE_DELAY_SECONDS),
    ]
    subprocess.Popen(
        cmd,
        cwd=os.getcwd(),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _start_report_subscription_worker(report_id: str) -> None:
    env = os.environ.copy()
    cmd = [
        sys.executable,
        sys.argv[0],
        "event",
        "release-report-subscriptions",
        report_id,
        "--delay",
        str(REPORT_SUBSCRIPTION_DELAY_SECONDS),
    ]
    subprocess.Popen(
        cmd,
        cwd=os.getcwd(),
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _report_filters(args) -> dict:
    states = set(getattr(args, "state", None) or [])
    target = getattr(args, "target", None)
    fleet = getattr(args, "fleet", None)
    seat = getattr(args, "seat", None)
    if target and ":" in target:
        target_fleet, target_seat = target.split(":", 1)
        fleet = fleet or target_fleet
        seat = seat or target_seat
    elif target:
        seat = seat or target
    return {
        "states": states or None,
        "fleet": fleet,
        "seat": seat,
        "cwd_prefix": getattr(args, "cwd_prefix", None),
    }


def _matches_report(row: dict, filters: dict) -> bool:
    states = filters.get("states")
    if states and row.get("state") not in states:
        return False
    if filters.get("fleet") and row.get("fleet") != filters["fleet"]:
        return False
    if filters.get("seat") and row.get("seat") != filters["seat"]:
        return False
    if filters.get("cwd_prefix") and not str(row.get("cwd") or "").startswith(filters["cwd_prefix"]):
        return False
    return True


def _filtered_reports(args) -> list[dict]:
    filters = _report_filters(args)
    return [row for row in reports.iter_reports() if _matches_report(row, filters)]


def run(args):
    action = getattr(args, "report_action", None)
    if action == "list":
        limit = getattr(args, "limit", None) or 20
        rows = _filtered_reports(args)[-int(limit):]
        return {
            "ok": True,
            "schema": "aura.report_list.v1",
            "count": len(rows),
            "reports_path": str(reports.reports_path()),
            "rows": rows,
        }
    if action == "latest":
        rows = _filtered_reports(args)
        row = rows[-1] if rows else None
        return {
            "ok": bool(row),
            "schema": "aura.report_latest.v1",
            "reports_path": str(reports.reports_path()),
            "record": row,
            "error": None if row else "no reports found",
        }
    if action not in reports.VALID_STATES:
        return {"ok": False, "error": f"unknown report state: {action}"}

    record = {
        "state": action,
        "work": getattr(args, "work", None),
        "done": getattr(args, "done", None) or [],
        "receipts": getattr(args, "receipt", None) or [],
        "next": getattr(args, "next_action", None),
        "blockers": getattr(args, "blocker", None) or [],
    }
    created = reports.append_report(record)
    scheduled = reports.schedule_queued_messages(created, delay_seconds=QUEUE_RELEASE_DELAY_SECONDS)
    if scheduled:
        _start_queued_release_worker(created.get("report_id"))
    scheduled_subscriptions = reports.schedule_report_subscriptions(
        created,
        delay_seconds=REPORT_SUBSCRIPTION_DELAY_SECONDS,
    )
    if scheduled_subscriptions:
        _start_report_subscription_worker(created.get("report_id"))
    if not getattr(args, "ack", False):
        return None
    return {
        "ok": True,
        "schema": "aura.report_ack.v1",
        "report_id": created.get("report_id"),
        "state": created.get("state"),
        "work": created.get("work"),
        "seat": created.get("seat"),
        "fleet": created.get("fleet"),
        "warnings": created.get("warnings") or [],
        "scheduled_queued": len(scheduled),
        "queue_release_delay_seconds": QUEUE_RELEASE_DELAY_SECONDS,
        "scheduled_report_subscriptions": len(scheduled_subscriptions),
        "report_subscription_delay_seconds": REPORT_SUBSCRIPTION_DELAY_SECONDS,
        "reports_path": str(reports.reports_path()),
    }

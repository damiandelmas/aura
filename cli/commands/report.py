"""Record a small semantic worker report."""

from __future__ import annotations

from lib import reports


def run(args):
    action = getattr(args, "report_action", None)
    if action == "list":
        limit = getattr(args, "limit", None) or 20
        rows = reports.iter_reports(limit=limit)
        return {
            "ok": True,
            "schema": "aura.report_list.v1",
            "count": len(rows),
            "reports_path": str(reports.reports_path()),
            "rows": rows,
        }
    if action == "latest":
        row = reports.latest_report()
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
        "reports_path": str(reports.reports_path()),
    }

"""Queue an intentional message until a worker report boundary."""

from __future__ import annotations

import time


def run(args):
    from lib import identity, queued_messages, reports

    release_report_id = getattr(args, "release_report", None)
    if release_report_id:
        delay = float(getattr(args, "delay", None) or 0)
        if delay > 0:
            time.sleep(delay)
        report = reports.find_report(release_report_id)
        if not report:
            return {"ok": False, "error": f"report not found: {release_report_id}"}
        released = queued_messages.release_for_report(report)
        return {
            "ok": True,
            "schema": "aura.queue_release.v1",
            "report_id": release_report_id,
            "released": len(released),
            "records": released,
        }

    if getattr(args, "list", False):
        return {
            "ok": True,
            "records": queued_messages.list_records(
                status=getattr(args, "status", None),
                target=getattr(args, "target", None),
            ),
        }

    if not getattr(args, "target", None):
        return {"ok": False, "error": "queue requires TARGET unless --list is used"}
    if getattr(args, "message", None) is None:
        return {"ok": False, "error": "queue requires MESSAGE unless --list is used"}

    record = queued_messages.create(
        target=args.target,
        message=args.message,
        sender=identity.sender(getattr(args, "sender", None)),
        after=getattr(args, "after", None) or "next-report",
    )
    return {
        "ok": True,
        "schema": "aura.queue_ack.v1",
        "queue_id": record.get("queue_id"),
        "target": record.get("target"),
        "after": record.get("after"),
        "status": record.get("status"),
    }

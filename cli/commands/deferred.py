"""Deferred delivery outbox commands."""

from __future__ import annotations


def run(args):
    from lib import deferred

    action = args.deferred_action
    if action == "list":
        return {"ok": True, "records": deferred.list_records(status=getattr(args, "status", None))}
    if action == "status":
        return {"ok": True, "record": deferred.load(args.deferred_id)}
    if action == "run":
        return deferred.run_once(args.deferred_id)
    if action == "drain":
        return deferred.run_due(limit=getattr(args, "limit", None))
    if action == "daemon":
        return deferred.daemon(args.deferred_id)
    return {"ok": False, "error": f"unknown deferred action: {action}"}

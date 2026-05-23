"""Run and inspect background keeper jobs."""

from __future__ import annotations

from lib import keeper_jobs


def run(args):
    action = getattr(args, "keeper_action", None)
    try:
        if action == "run":
            kind = getattr(args, "keeper_kind", None)
            if kind != "memory":
                return {"ok": False, "error": f"unknown keeper run kind: {kind}"}
            return keeper_jobs.run_memory(
                target_ref=args.target,
                boundary=args.boundary,
                force=getattr(args, "force", False),
            )
        if action == "status":
            return keeper_jobs.read_status(args.job_id)
        if action == "result":
            return keeper_jobs.read_result(args.job_id)
        if action == "tail":
            return keeper_jobs.tail_log(args.job_id, lines=getattr(args, "lines", 80))
        return {"ok": False, "error": f"unknown keeper action: {action}"}
    except Exception as exc:
        return {"ok": False, "error": "keeper-failed", "detail": str(exc)}

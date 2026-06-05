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
        if action == "health":
            return keeper_jobs.health(limit=getattr(args, "limit", 50))
        if action == "backfill":
            return keeper_jobs.backfill(
                limit=getattr(args, "limit", 5),
                dry_run=getattr(args, "dry_run", False),
                diagnostic=getattr(args, "diagnostic", "codex-auth-refresh"),
                agent_id=getattr(args, "agent_id", None),
                session_id=getattr(args, "session_id", None),
                job_ids=getattr(args, "job_id", None) or [],
                wait=getattr(args, "wait", False),
                timeout_seconds=getattr(args, "timeout", 600),
            )
        if action == "hooks":
            hooks_action = getattr(args, "keeper_hooks_action", None)
            if hooks_action != "install":
                return {"ok": False, "error": f"unknown keeper hooks action: {hooks_action}"}
            agents = bool(getattr(args, "agents", False))
            profiles = bool(getattr(args, "profiles", False))
            if not agents and not profiles:
                agents = True
                profiles = True
            return keeper_jobs.install_hooks(
                agents=agents,
                profiles=profiles,
                dry_run=getattr(args, "dry_run", False),
            )
        return {"ok": False, "error": f"unknown keeper action: {action}"}
    except Exception as exc:
        return {"ok": False, "error": "keeper-failed", "detail": str(exc)}

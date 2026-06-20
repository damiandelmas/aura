"""Durable event scheduler commands."""

from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import time

from lib import delivery, events


DEFAULT_TEMPLATE = "event tick {tick}/{ticks} run={run_id}: check in, then return idle."


def _run_id() -> str:
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _iso_from_epoch(value) -> str | None:
    if value in (None, ""):
        return None
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(value)))
    except (TypeError, ValueError, OSError):
        return None


def _job_summary(job: dict) -> dict:
    return {
        "job_id": job.get("job_id"),
        "name": job.get("name"),
        "kind": job.get("kind"),
        "status": job.get("status"),
        "owner": job.get("sender"),
        "sender": job.get("sender"),
        "target": job.get("target"),
        "schedule": {
            "kind": job.get("kind"),
            "interval_seconds": job.get("interval_seconds"),
            "ticks": job.get("ticks"),
            "tick": job.get("tick"),
        },
        "last_run_at": job.get("last_tick_at"),
        "next_run_at": _iso_from_epoch(job.get("next_tick_at")),
        "next_tick_at": job.get("next_tick_at"),
        "running_at": job.get("running_at"),
        "failure": {
            "last_error": job.get("last_error"),
            "consecutive_errors": int(job.get("consecutive_errors") or 0),
        },
        "daemon": job.get("daemon"),
        # Computed liveness from the pid, not the stored record (two-laws read law):
        "daemon_alive": events.daemon_alive(job),
    }


def _aura_bin() -> str:
    return os.environ.get("AURA_BIN") or str((Path(__file__).resolve().parents[1] / "aura"))


def _make_job(args) -> dict:
    now = events.now_iso()
    interval = float(args.every)
    if interval <= 0:
        raise ValueError("--every must be > 0 seconds")
    ticks = int(args.ticks) if args.ticks is not None else None
    if ticks is not None and ticks <= 0:
        raise ValueError("--ticks must be > 0")
    job_id = events.new_job_id()
    run_id = args.run_id or _run_id()

    no_agent = bool(getattr(args, "no_agent", False))
    script = getattr(args, "script", None)
    respawn = None
    if getattr(args, "respawn_runtime", None):
        respawn = {
            "runtime": args.respawn_runtime,
            "cwd": getattr(args, "respawn_cwd", None),
            "prompt": getattr(args, "respawn_prompt", None),
        }
    if no_agent and not script:
        raise ValueError("--no-agent requires --script")
    if no_agent and respawn:
        raise ValueError("--no-agent jobs cannot use --respawn-* (no seat to keep alive)")

    return {
        "schema": "aura.event.job.v1",
        "job_id": job_id,
        "name": args.name,
        "kind": "interval",
        "target": args.target,
        "sender": args.sender or "aura-event",
        "template": args.template or DEFAULT_TEMPLATE,
        "interval_seconds": interval,
        "ticks": ticks,
        "tick": 0,
        "run_id": run_id,
        "status": "running",
        "created_at": now,
        "updated_at": now,
        "next_tick_at": events.now_epoch() + float(args.start_delay or 0),
        "running_at": None,
        "last_tick_at": None,
        "last_error": None,
        "consecutive_errors": 0,
        "no_agent": no_agent,
        "script": script,
        "respawn": respawn,
        "report_state": getattr(args, "report_state", None) or "update",
        "delivery": {
            "mode": "no_agent_script" if no_agent else "terminal_write",
            "ensure_submit": False,
        },
    }


def _update_job(job: dict, args) -> tuple[dict, dict]:
    changes: dict = {}
    old_name = job.get("name")
    if getattr(args, "name", None) is not None:
        job["name"] = args.name
        changes["name"] = args.name
    if getattr(args, "target", None) is not None:
        job["target"] = args.target
        changes["target"] = args.target
    if getattr(args, "sender", None) is not None:
        job["sender"] = args.sender
        changes["sender"] = args.sender
    if getattr(args, "template", None) is not None:
        job["template"] = args.template
        changes["template"] = args.template
    if getattr(args, "every", None) is not None:
        interval = float(args.every)
        if interval <= 0:
            raise ValueError("--every must be > 0 seconds")
        job["interval_seconds"] = interval
        changes["interval_seconds"] = interval
    if getattr(args, "ticks", None) is not None:
        ticks = int(args.ticks)
        if ticks <= 0:
            raise ValueError("--ticks must be > 0")
        job["ticks"] = ticks
        changes["ticks"] = ticks
    if getattr(args, "clear_ticks", False):
        job["ticks"] = None
        changes["ticks"] = None
    if getattr(args, "start_delay", None) is not None:
        job["next_tick_at"] = events.now_epoch() + float(args.start_delay)
        changes["next_tick_at"] = job["next_tick_at"]
    events.save_state(job)
    if old_name and old_name != job.get("name"):
        events.remove_name(str(old_name))
    if job.get("name"):
        events.index_name(str(job["name"]), job["job_id"])
    return job, changes


def _spawn_daemon(job_id: str) -> dict:
    log_dir = events.job_dir(job_id)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "daemon.log"
    cmd = [_aura_bin(), "event", "daemon", job_id]
    with log_path.open("ab") as log:
        proc = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=log,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    return {"pid": proc.pid, "log": str(log_path), "cmd": cmd}


def _target_is_busy(target: str) -> dict:
    cmd = [
        _aura_bin(),
        "check",
        target,
        "--output",
        "--lines",
        "40",
    ]
    result = subprocess.run(cmd, text=True, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        parsed = None
    if result.returncode != 0 or not isinstance(parsed, dict):
        return {"ok": False, "busy": False, "error": result.stderr[-1000:] or result.stdout[-1000:]}

    output_lines = [str(line) for line in parsed.get("output") or []]
    from lib import terminal_submit

    blocker = terminal_submit.delivery_blocker(output_lines)
    return {
        "ok": True,
        "busy": blocker == "target-busy",
        "blocker": blocker,
        "status": parsed.get("status"),
        "terminal": parsed.get("terminal"),
    }


def _stop_daemon(job: dict) -> dict | None:
    daemon = job.get("daemon")
    if not isinstance(daemon, dict):
        return None
    pid = daemon.get("pid")
    if not isinstance(pid, int):
        return None
    try:
        os.kill(pid, signal.SIGTERM)
        return {"pid": pid, "signalled": True}
    except ProcessLookupError:
        return {"pid": pid, "signalled": False, "reason": "missing"}
    except OSError as exc:
        return {"pid": pid, "signalled": False, "reason": str(exc)}


def _is_alive(busy: dict) -> bool:
    """Liveness derived from the same ``aura check`` probe ``_target_is_busy`` runs.

    A dead/missing target returns no (or non-alive) terminal, so the ensure-alive
    branch treats it as needing respawn rather than guessing a name.
    """
    return bool(busy.get("ok")) and busy.get("terminal") == "alive"


def _respawn(job: dict, recipe: dict, tick: int) -> dict:
    """Ensure-alive: respawn a dead target from its stored launch recipe.

    Mirrors the recovery-pain-scout wrapper's dead-branch: spawn the seat with the
    bootstrap prompt instead of writing into a window that does not exist. Routine
    spawn only — physical identity is the spawn command's concern.
    """
    target = job["target"]
    fleet, sep, seat = target.partition(":")
    if not sep:
        seat, fleet = fleet, None
    cmd = [
        _aura_bin(), "spawn", seat,
        "--runtime", recipe.get("runtime") or "codex",
        "--as-pane", "--wait", "--timeout", "45",
    ]
    if fleet:
        cmd += ["--fleet", fleet]
    if recipe.get("cwd"):
        cmd += ["--cwd", recipe["cwd"]]
    prompt = recipe.get("prompt")
    if prompt:
        cmd += ["--prompt", prompt]
    started = events.now_iso()
    result = subprocess.run(cmd, text=True, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        parsed = None
    ok = result.returncode == 0 and isinstance(parsed, dict) and parsed.get("ok") is True
    return {
        "ok": ok,
        "respawned": True,
        "message_id": None,
        "started_at": started,
        "ended_at": events.now_iso(),
        "returncode": result.returncode,
        "stdout": parsed if parsed is not None else result.stdout[-1000:],
        "stderr": result.stderr[-1000:],
        "submitted_verified": None,
        "submit_retry": None,
        "state": "respawned" if ok else None,
    }


def _deliver_no_agent(job: dict, tick: int) -> dict:
    """Run a script with no LLM; non-empty stdout becomes an aura report.

    The Hermes ``no_agent`` short-circuit, ported as the one good idea from that
    scheduler. Empty stdout is a silent success (no token spend, no delivery);
    non-zero exit is a failure alert (backoff applies); non-empty stdout is written
    to the report ledger so existing report subscribers fan out — the bus is the
    report ledger, not a new event bus.
    """
    started = events.now_iso()
    script = job.get("script")
    if not script:
        return {
            "ok": False, "message_id": None, "started_at": started, "ended_at": events.now_iso(),
            "returncode": 1, "stdout": "", "stderr": "no_agent job has no script", "state": None,
        }
    ok, output = events.run_script(script)
    if not ok:
        return {
            "ok": False, "message_id": None, "started_at": started, "ended_at": events.now_iso(),
            "returncode": 1, "stdout": output[-2000:], "stderr": output[-2000:], "state": None,
        }
    output = (output or "").strip()
    if not output:
        return {
            "ok": True, "skipped": True, "reason": "silent", "message_id": None,
            "started_at": started, "ended_at": events.now_iso(),
            "returncode": 0, "stdout": "", "stderr": "", "state": "silent",
        }

    from lib import redact, reports
    output = redact.redact_sensitive_text(output)

    target = job.get("target") or ""
    fleet, sep, seat = target.partition(":")
    if not sep:
        seat, fleet = fleet, None
    record = {
        "state": job.get("report_state") or "update",
        "work": output,
        "sender": job.get("sender") or "aura-event",
        "seat": seat or None,
        "fleet": fleet or None,
        "source": "aura-event:no-agent",
        "job_id": job.get("job_id"),
    }
    report = reports.append_report(record)
    # Match subscribers + deliver NOW, inline. schedule_for_report records the report against
    # matching subscriptions; release_for_report sends them. Both run here because the event
    # daemon has no deferred-release worker (a scheduled-but-unreleased report never fires).
    # A no_agent report is final, so there is no boundary to wait for.
    from lib import report_subscriptions
    reports.schedule_report_subscriptions(report, delay_seconds=0)
    released = report_subscriptions.release_for_report(report)
    return {
        "ok": True, "delivered": True,
        "message_id": report.get("report_id"),
        "report_id": report.get("report_id"),
        "started_at": started, "ended_at": events.now_iso(),
        "returncode": 0,
        "stdout": {"report_id": report.get("report_id"), "released": len(released)},
        "stderr": "", "state": "delivered",
    }


def _deliver(job: dict, tick: int) -> dict:
    if job.get("no_agent"):
        return _deliver_no_agent(job, tick)
    busy = _target_is_busy(job["target"])
    recipe = job.get("respawn")
    if recipe and not _is_alive(busy):
        return _respawn(job, recipe, tick)
    blocker = busy.get("blocker") or ("target-busy" if busy.get("busy") else None)
    if blocker:
        return {
            "ok": True,
            "skipped": True,
            "reason": blocker,
            "message_id": None,
            "started_at": events.now_iso(),
            "ended_at": events.now_iso(),
            "returncode": 0,
            "stdout": busy,
            "stderr": "",
            "submitted_verified": None,
            "submit_retry": None,
            "state": "skipped",
        }

    body = events.render_template(job.get("template") or DEFAULT_TEMPLATE, job, tick, job["run_id"])
    message_id = delivery.new_message_id()
    envelope = delivery.render_envelope(message_id, job.get("sender") or "aura-event", body)
    cmd = [
        _aura_bin(),
        "write",
        job["target"],
        envelope,
        "--as",
        job.get("sender") or "aura-event",
        "--enter",
        "--lines",
        "80",
    ]
    started = events.now_iso()
    result = subprocess.run(cmd, text=True, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    parsed = None
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError:
        parsed = None
    ok = result.returncode == 0 and isinstance(parsed, dict) and parsed.get("ok") is True
    submitted_verified = parsed.get("submitted_verified") if isinstance(parsed, dict) else None
    return {
        "ok": ok,
        "message_id": message_id,
        "started_at": started,
        "ended_at": events.now_iso(),
        "returncode": result.returncode,
        "stdout": parsed if parsed is not None else result.stdout[-1000:],
        "stderr": result.stderr[-1000:],
        "submitted_verified": submitted_verified,
        "submit_retry": parsed.get("submit_retry") if isinstance(parsed, dict) else None,
        "state": (parsed or {}).get("state") if isinstance(parsed, dict) else None,
    }


def _tick(job: dict, *, force: bool = False) -> dict:
    if job.get("status") not in {"running", "paused"}:
        return {"ok": True, "ran": False, "reason": f"status={job.get('status')}"}
    if job.get("status") == "paused" and not force:
        return {"ok": True, "ran": False, "reason": "paused"}
    now = events.now_epoch()
    next_tick_at = float(job.get("next_tick_at") or 0)
    if now < next_tick_at and not force:
        return {"ok": True, "ran": False, "reason": "not-due", "next_tick_at": next_tick_at}
    if job.get("running_at") and not force:
        return {"ok": True, "ran": False, "reason": "already-running"}

    tick = int(job.get("tick") or 0) + 1
    ticks = job.get("ticks")
    if ticks is not None and tick > int(ticks):
        job["status"] = "complete"
        job["next_tick_at"] = None
        events.save_state(job)
        events.append_event(job["job_id"], {"action": "completed", "tick": job.get("tick")})
        return {"ok": True, "ran": False, "reason": "complete"}

    job["running_at"] = events.now_iso()
    events.save_state(job)
    events.append_event(job["job_id"], {"action": "tick-started", "tick": tick})
    result = _deliver(job, tick)

    job["running_at"] = None
    job["last_tick_at"] = events.now_iso()
    job["last_delivery"] = result
    if result.get("skipped"):
        job["last_error"] = None
        job["consecutive_errors"] = 0
        job["next_tick_at"] = events.now_epoch() + float(job["interval_seconds"])
        action = "tick-skipped"
    elif result["ok"]:
        job["tick"] = tick
        job["last_error"] = None
        job["consecutive_errors"] = 0
        if ticks is not None and tick >= int(ticks):
            job["status"] = "complete"
            job["next_tick_at"] = None
        else:
            job["next_tick_at"] = events.now_epoch() + float(job["interval_seconds"])
        action = "tick-finished"
    else:
        job["last_error"] = result.get("stderr") or "delivery failed"
        job["consecutive_errors"] = int(job.get("consecutive_errors") or 0) + 1
        backoff = min(3600, 30 * (2 ** min(job["consecutive_errors"] - 1, 5)))
        job["next_tick_at"] = events.now_epoch() + backoff
        action = "tick-failed"
    events.save_state(job)
    events.append_event(job["job_id"], {"action": action, "tick": tick, "delivery": result})
    return {"ok": result["ok"], "ran": True, "tick": tick, "delivery": result, "job": job}


def _ensure_daemons() -> dict:
    """Supervisor tick: respawn any running-status job whose daemon pid is dead.

    The event daemons are dynamically spawned, so they cannot each be a systemd
    unit. A systemd --user timer runs this every cadence; it is the meta-watchdog
    systemd keeps alive. Liveness is computed from the pid (events.daemon_alive),
    so a corpse pid in the record never reads alive. The supervisor lock makes it
    safe to run concurrently — no double-spawn. Only ``status==running`` jobs are
    touched, so a paused/stopped/retired/complete job is never resurrected.
    """
    results: list[dict] = []
    alive = 0
    respawned = 0
    with events.supervisor_lock():
        for job in events.iter_jobs():
            if job.get("status") != "running":
                continue
            job_id = job["job_id"]
            if events.daemon_alive(job):
                alive += 1
                results.append({"job_id": job_id, "name": job.get("name"), "daemon": "alive"})
                continue
            daemon = _spawn_daemon(job_id)
            fresh = events.load_state(job_id)
            fresh["daemon"] = daemon
            events.save_state(fresh)
            events.append_event(job_id, {"action": "daemon-respawned", "by": "supervisor", **daemon})
            respawned += 1
            results.append({
                "job_id": job_id,
                "name": job.get("name"),
                "daemon": "respawned",
                "pid": daemon.get("pid"),
            })
    return {
        "ok": True,
        "schema": "aura.event.supervise.v1",
        "checked": alive + respawned,
        "alive": alive,
        "respawned": respawned,
        "jobs": results,
    }


def _daemon(job_id: str) -> dict:
    events.append_event(job_id, {"action": "daemon-started", "pid": os.getpid()})
    while True:
        job = events.load_state(job_id)
        if job.get("status") not in {"running", "paused"}:
            events.append_event(job_id, {"action": "daemon-stopped", "status": job.get("status")})
            return {"ok": True, "status": job.get("status")}
        try:
            _tick(job)
        except Exception as exc:
            job = events.load_state(job_id)
            job["running_at"] = None
            job["last_error"] = str(exc)
            job["consecutive_errors"] = int(job.get("consecutive_errors") or 0) + 1
            job["next_tick_at"] = events.now_epoch() + 60
            events.save_state(job)
            events.append_event(job_id, {"action": "tick-error", "error": str(exc)})
        job = events.load_state(job_id)
        next_tick_at = job.get("next_tick_at")
        if not next_tick_at:
            continue
        delay = max(1.0, min(float(next_tick_at) - events.now_epoch(), 60.0))
        time.sleep(delay)


def run(args):
    action = args.event_action
    if action == "subscribe":
        if getattr(args, "subscribe_source", None) == "society":
            from lib import society

            scope = ({"fleet": args.fleet} if getattr(args, "fleet", None)
                     else {"placement": args.placement})
            record = society.create_subscription(
                scope, args.to,
                as_sender=getattr(args, "sender", None) or "service:aura-society",
                kinds=getattr(args, "kind", None),
            )
            return {"ok": True, "schema": "aura.event.society_subscription_ack.v1",
                    "subscription": record}
        if getattr(args, "subscribe_source", None) != "reports":
            return {"ok": False, "error": f"unknown subscription source: {getattr(args, 'subscribe_source', None)}"}
        if not getattr(args, "fleet", None) and not getattr(args, "target", None) and not getattr(args, "placement", None):
            return {"ok": False, "error": "report subscriptions require --fleet, --target, or --placement"}
        from lib import report_subscriptions

        try:
            existing = report_subscriptions.load(args.name)
        except FileNotFoundError:
            existing = None
        if existing and existing.get("status") != "removed":
            return {"ok": False, "error": f"report subscription already exists: {args.name}"}

        record = report_subscriptions.create(
            name=args.name,
            to=args.to,
            fleet=getattr(args, "fleet", None),
            target=getattr(args, "target", None),
            placement=getattr(args, "placement", None),
            states=getattr(args, "state", None) or [],
            sender=getattr(args, "sender", None) or "aura-event",
        )
        return {"ok": True, "schema": "aura.event.report_subscription_ack.v1", "subscription": record}
    if action == "subscriptions":
        from lib import report_subscriptions

        return {
            "ok": True,
            "schema": "aura.event.report_subscription_list.v1",
            "subscriptions": report_subscriptions.list_records(
                status=getattr(args, "status", None),
                include_removed=getattr(args, "include_removed", False),
            ),
        }
    if action == "subscription":
        from lib import report_subscriptions

        subscription_action = getattr(args, "subscription_action", None)
        if subscription_action == "show":
            return {"ok": True, "subscription": report_subscriptions.load(args.ref)}
        if subscription_action == "pause":
            return {"ok": True, "subscription": report_subscriptions.set_status(args.ref, "paused")}
        if subscription_action == "resume":
            return {"ok": True, "subscription": report_subscriptions.set_status(args.ref, "active")}
        if subscription_action == "remove":
            return {"ok": True, "subscription": report_subscriptions.set_status(args.ref, "removed")}
        return {"ok": False, "error": f"unknown subscription action: {subscription_action}"}
    if action == "release-report-subscriptions":
        delay = float(getattr(args, "delay", None) or 0)
        if delay > 0:
            time.sleep(delay)
        from lib import report_subscriptions, reports

        report = reports.find_report(args.ref)
        if not report:
            return {"ok": False, "error": f"report not found: {args.ref}"}
        released = report_subscriptions.release_for_report(report)
        return {
            "ok": True,
            "schema": "aura.event.report_subscription_release.v1",
            "report_id": args.ref,
            "released": len(released),
            "subscriptions": released,
        }
    if action == "start":
        try:
            job = _make_job(args)
        except ValueError as exc:
            return {"ok": False, "error": "event-start-invalid", "detail": str(exc)}
        events.save_state(job)
        if job.get("name"):
            events.index_name(job["name"], job["job_id"])
        events.append_event(job["job_id"], {"action": "created"})
        daemon = None
        if not getattr(args, "no_daemon", False):
            daemon = _spawn_daemon(job["job_id"])
            job["daemon"] = daemon
            events.save_state(job)
            events.append_event(job["job_id"], {"action": "daemon-spawned", **daemon})
        return {"ok": True, "job": job, "daemon": daemon}
    if action == "daemon":
        return _daemon(args.ref)
    if action == "ensure-daemons":
        return _ensure_daemons()
    if action == "status":
        job_id = events.resolve_job_id(args.ref)
        job = events.load_state(job_id)
        return {"ok": True, "job": job, "summary": _job_summary(job)}
    if action == "list":
        jobs = events.iter_jobs()
        return {"ok": True, "jobs": jobs, "job_summaries": [_job_summary(job) for job in jobs]}
    if action == "update":
        job_id = events.resolve_job_id(args.ref)
        job = events.load_state(job_id)
        try:
            job, changes = _update_job(job, args)
        except ValueError as exc:
            return {"ok": False, "error": "event-update-invalid", "detail": str(exc)}
        events.append_event(job_id, {"action": "updated", "changes": changes})
        return {"ok": True, "job": job, "changes": changes}
    if action == "pause":
        job_id = events.resolve_job_id(args.ref)
        job = events.load_state(job_id)
        job["status"] = "paused"
        events.save_state(job)
        events.append_event(job_id, {"action": "paused"})
        return {"ok": True, "job": job}
    if action == "resume":
        job_id = events.resolve_job_id(args.ref)
        job = events.load_state(job_id)
        job["status"] = "running"
        job["next_tick_at"] = events.now_epoch() + float(getattr(args, "start_delay", 0) or 0)
        events.save_state(job)
        daemon = _spawn_daemon(job_id) if not getattr(args, "no_daemon", False) else None
        if daemon:
            job["daemon"] = daemon
            events.save_state(job)
        events.append_event(job_id, {"action": "resumed", "daemon": daemon})
        return {"ok": True, "job": job, "daemon": daemon}
    if action == "stop":
        job_id = events.resolve_job_id(args.ref)
        job = events.load_state(job_id)
        stopped = _stop_daemon(job)
        job["status"] = "stopped"
        job["next_tick_at"] = None
        job["running_at"] = None
        if stopped:
            job["daemon_stop"] = stopped
        events.save_state(job)
        events.append_event(job_id, {"action": "stopped", "daemon": stopped})
        return {"ok": True, "job": job}
    if action == "retire":
        job_id = events.resolve_job_id(args.ref)
        job = events.load_state(job_id)
        stopped = _stop_daemon(job)
        job["status"] = "retired"
        job["next_tick_at"] = None
        job["running_at"] = None
        if stopped:
            job["daemon_stop"] = stopped
        events.save_state(job)
        events.append_event(job_id, {"action": "retired", "daemon": stopped})
        return {"ok": True, "job": job}
    if action == "run":
        job_id = events.resolve_job_id(args.ref)
        return _tick(events.load_state(job_id), force=True)
    return {"ok": False, "error": f"unknown event action: {action}"}

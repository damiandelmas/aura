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
        "delivery": {
            "mode": "terminal_write",
            "ensure_submit": False,
        },
    }


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


def _deliver(job: dict, tick: int) -> dict:
    busy = _target_is_busy(job["target"])
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
    if action == "start":
        job = _make_job(args)
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
    if action == "status":
        job_id = events.resolve_job_id(args.ref)
        return {"ok": True, "job": events.load_state(job_id)}
    if action == "list":
        return {"ok": True, "jobs": events.iter_jobs()}
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
    if action == "run":
        job_id = events.resolve_job_id(args.ref)
        return _tick(events.load_state(job_id), force=True)
    return {"ok": False, "error": f"unknown event action: {action}"}

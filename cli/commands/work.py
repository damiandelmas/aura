"""aura work — a thin work-claim pool (submit / list / status / dispatch).

Submit drops a task into a queue. The dispatcher (one tick, or a background loop)
assigns pending tasks to idle pool members, frees them on the idle-watcher's
completion reports, and requeues a dead worker's task when its lease elapses.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from lib import work


def _jobs_dir() -> Path:
    return work.work_root() / "_dispatchers"


def _job_path(queue: str) -> Path:
    return _jobs_dir() / f"{str(queue).replace('/', '_')}.json"


def _aura_bin() -> str:
    return os.environ.get("AURA_BIN") or str(Path(__file__).resolve().parents[1] / "aura")


def _spawn_loop(args) -> int:
    log_dir = _jobs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{str(args.queue).replace('/', '_')}.log"
    cmd = [
        _aura_bin(), "work", "dispatch-loop", args.queue,
        "--placement", args.placement,
        "--every", str(args.every),
        "--lease", str(args.lease),
    ]
    with log_path.open("ab") as log:
        proc = subprocess.Popen(
            cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
            start_new_session=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    return proc.pid


def run(args):
    action = args.work_action

    if action == "submit":
        body = args.body if isinstance(args.body, str) else " ".join(args.body)
        return {"ok": True, "task": work.submit(args.queue, body)}

    if action == "list":
        rows = work.list_tasks(args.queue, state_filter=getattr(args, "state", None))
        return {"ok": True, "queue": args.queue, "count": len(rows), "tasks": rows}

    if action == "status":
        rows = work.list_tasks(args.queue)
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.get("state")] = counts.get(row.get("state"), 0) + 1
        return {"ok": True, "queue": args.queue, "total": len(rows), "counts": counts}

    if action == "dispatch":
        return work.dispatch_tick(args.queue, args.placement, lease_seconds=args.lease)

    if action == "dispatch-loop":
        while True:
            try:
                work.dispatch_tick(args.queue, args.placement, lease_seconds=args.lease)
            except Exception as exc:  # pragma: no cover - daemon resilience
                print(f"work dispatch error: {exc}", file=sys.stderr, flush=True)
            time.sleep(max(1.0, float(args.every)))

    if action == "dispatch-start":
        pid = _spawn_loop(args)
        job = {"queue": args.queue, "placement": args.placement, "every": args.every, "lease": args.lease, "pid": pid}
        path = _job_path(args.queue)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
        return {"ok": True, "started": job}

    if action == "dispatch-stop":
        path = _job_path(args.queue)
        if not path.exists():
            return {"ok": False, "error": f"no dispatcher for queue: {args.queue}"}
        job = json.loads(path.read_text(encoding="utf-8"))
        pid = job.get("pid")
        signalled = False
        if isinstance(pid, int):
            try:
                os.kill(pid, signal.SIGTERM)
                signalled = True
            except ProcessLookupError:
                signalled = False
        path.unlink(missing_ok=True)
        return {"ok": True, "stopped": {"queue": args.queue, "pid": pid, "signalled": signalled}}

    return {"ok": False, "error": f"unknown work action: {action}"}

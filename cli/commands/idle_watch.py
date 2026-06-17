"""aura idle-watch — the sensed-completion seam (voiceless watcher).

``tick`` runs one watch pass (also the unit a cron/event clock can drive).
``start``/``stop`` manage a background loop; ``status`` shows the per-seat gate.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from lib import idle_watcher, state


def _jobs_dir() -> Path:
    return state.state_root() / idle_watcher.WATCHER_STATE_DIRNAME / "jobs"


def _job_path(placement: str) -> Path:
    return _jobs_dir() / f"{str(placement).replace('/', '_')}.json"


def _aura_bin() -> str:
    return os.environ.get("AURA_BIN") or str(Path(__file__).resolve().parents[1] / "aura")


def _spawn_loop(args) -> int:
    log_dir = _jobs_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{str(args.placement).replace('/', '_')}.log"
    cmd = [
        _aura_bin(), "idle-watch", "loop",
        "--placement", args.placement,
        "--every", str(args.every),
        "--debounce", str(args.debounce),
        "--lines", str(args.lines),
    ]
    if getattr(args, "anchor", False):
        cmd.append("--anchor")
    with log_path.open("ab") as log:
        proc = subprocess.Popen(
            cmd, stdout=log, stderr=log, stdin=subprocess.DEVNULL,
            start_new_session=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    return proc.pid


def run(args):
    action = args.idle_watch_action

    if action == "tick":
        return idle_watcher.tick(args.placement, debounce=args.debounce, lines=args.lines,
                                 with_anchor=getattr(args, "anchor", False))

    if action == "loop":
        while True:
            try:
                idle_watcher.tick(args.placement, debounce=args.debounce, lines=args.lines,
                                  with_anchor=getattr(args, "anchor", False))
            except Exception as exc:  # pragma: no cover - daemon resilience
                print(f"idle-watch tick error: {exc}", file=sys.stderr, flush=True)
            time.sleep(max(1.0, float(args.every)))

    if action == "start":
        pid = _spawn_loop(args)
        job = {
            "placement": args.placement, "every": args.every,
            "debounce": args.debounce, "lines": args.lines, "pid": pid,
        }
        path = _job_path(args.placement)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
        return {"ok": True, "started": job}

    if action == "stop":
        path = _job_path(args.placement)
        if not path.exists():
            return {"ok": False, "error": f"no idle-watch job for placement: {args.placement}"}
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
        return {"ok": True, "stopped": {"placement": args.placement, "pid": pid, "signalled": signalled}}

    if action == "status":
        return {"ok": True, "state_path": str(idle_watcher.watcher_state_path()), "state": idle_watcher.read_state()}

    return {"ok": False, "error": f"unknown idle-watch action: {action}"}

#!/usr/bin/env python3
"""Ledger reaper — kills ledger-* clones that have completed their work.

Contract: every ledger clone spawned by the hook (`~/.claude/hooks/ledger-*.sh`)
has a prompt ending with an instruction to emit a single assistant text line:

    LEDGER_DONE:<clone-name>

This daemon polls all tmux windows matching `ledger-*`, finds their session
JSONL via pane capture, and scans for that sentinel in assistant turns.
When seen, runs `aura cut <clone-name>` and kills the tmux window.

Safety: any ledger-* window older than `MAX_AGE_SEC` is reaped regardless,
in case the clone crashed before emitting the token.

One daemon supervises all clones. Singleton enforced via pidfile.
"""

from __future__ import annotations

import glob
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
PIDFILE = Path("/tmp/aura-ledger-reaper.pid")
POLL_INTERVAL = 5       # seconds between sweeps
MAX_AGE_SEC = 10 * 60   # kill ledger-* windows older than 10 minutes
AURA_BIN = "/home/axp/.local/bin/aura"


def _enforce_singleton() -> None:
    if PIDFILE.exists():
        try:
            old = int(PIDFILE.read_text().strip())
            os.kill(old, 0)
            print(f"[reaper] already running (pid={old}), exiting", file=sys.stderr)
            sys.exit(1)
        except (ProcessLookupError, ValueError):
            pass
    PIDFILE.write_text(str(os.getpid()))


def _cleanup_pidfile(*_) -> None:
    try:
        PIDFILE.unlink()
    except FileNotFoundError:
        pass
    sys.exit(0)


def list_ledger_windows() -> list[dict]:
    """Enumerate every tmux window whose name matches ledger-*."""
    r = subprocess.run(
        ["tmux", "list-windows", "-a",
         "-F", "#{session_name}\t#{window_name}\t#{window_activity}"],
        capture_output=True, text=True, timeout=5,
    )
    out = []
    if r.returncode != 0:
        return out
    now = int(time.time())
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        sess, win = parts[0], parts[1]
        if not win.startswith("ledger-"):
            continue
        activity = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else now
        out.append({
            "session": sess,
            "window": win,
            "target": f"{sess}:{win}",
            "activity": activity,
        })
    return out


def find_session_jsonl(window_target: str) -> Path | None:
    """Pull the session UUID from the window's pane and locate its JSONL."""
    try:
        r = subprocess.run(
            ["tmux", "capture-pane", "-t", window_target, "-p", "-S", "-20"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return None
        for line in r.stdout.splitlines():
            line = line.strip()
            if len(line) == 36 and line.count("-") == 4:
                matches = glob.glob(str(CLAUDE_DIR / "projects" / "*" / f"{line}.jsonl"))
                if matches:
                    return Path(matches[0])
    except Exception:
        pass
    return None


def scan_for_done(jsonl_path: Path, clone_name: str) -> bool:
    """Return True if any assistant text turn contains LEDGER_DONE:<clone_name>."""
    token = f"LEDGER_DONE:{clone_name}"
    try:
        with open(jsonl_path, "r") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if d.get("type") != "assistant":
                    continue
                content = d.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        if token in block.get("text", ""):
                            return True
    except FileNotFoundError:
        return False
    return False


def reap(clone: str) -> None:
    """Best-effort cut + kill. Idempotent."""
    try:
        subprocess.run([AURA_BIN, "cut", clone],
                       capture_output=True, text=True, timeout=10)
    except Exception as e:
        print(f"[reaper] aura cut {clone} failed: {e}", file=sys.stderr)
    try:
        subprocess.run(["tmux", "kill-window", "-t", clone],
                       capture_output=True, text=True, timeout=5)
    except Exception:
        pass
    print(f"[reaper] reaped {clone}")


def main() -> None:
    _enforce_singleton()
    signal.signal(signal.SIGINT, _cleanup_pidfile)
    signal.signal(signal.SIGTERM, _cleanup_pidfile)

    print(f"[reaper] started pid={os.getpid()} poll={POLL_INTERVAL}s max-age={MAX_AGE_SEC}s")
    reaped_session = set()

    while True:
        now = int(time.time())
        try:
            clones = list_ledger_windows()
        except Exception as e:
            print(f"[reaper] list_ledger_windows failed: {e}", file=sys.stderr)
            time.sleep(POLL_INTERVAL)
            continue

        for c in clones:
            clone = c["window"]
            # Already reaped in this process's lifetime — skip rescans.
            if clone in reaped_session:
                continue
            target = c["target"]
            age = now - c["activity"]

            # Parse unix-ts from clone name suffix to bound maximum age.
            ts_suffix = clone.rsplit("-", 1)[-1]
            if ts_suffix.isdigit():
                age = max(age, now - int(ts_suffix))

            jsonl = find_session_jsonl(target)
            done = scan_for_done(jsonl, clone) if jsonl else False

            if done:
                print(f"[reaper] {clone}: sentinel seen, reaping")
                reap(clone)
                reaped_session.add(clone)
            elif age > MAX_AGE_SEC:
                print(f"[reaper] {clone}: age {age}s > {MAX_AGE_SEC}s, reaping by timeout")
                reap(clone)
                reaped_session.add(clone)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

"""Self-schedule a wake-up message.

Agent fires a detached process that re-injects a prompt into itself (or a
target) after N seconds. Zero polling. Agent exits, shell survives via nohup,
wakes and delivers via `aura send`.

Usage:
    aura sleep 300 "Check on the long-running build"
    aura sleep 60 "Ping brother-pti for status" --target pm-flexgraph
    aura sleep 1800 "Re-run test suite" --as dev-smoke-check
"""

import os
import subprocess
import sys


def run(args):
    """Schedule a deferred aura-send."""
    seconds = int(args.seconds)
    if seconds < 1:
        return {"ok": False, "error": "seconds must be >= 1"}

    message = args.message
    target = args.target or os.environ.get("AURA_AGENT_NAME")
    if not target:
        return {
            "ok": False,
            "error": "no target — pass --target <name> or set AURA_AGENT_NAME",
        }

    sender = args.sender or os.environ.get("AURA_AGENT_NAME", "cli")

    # Build the deferred command. Use bash -c so nohup handles redirection.
    # Escape message for shell embedding — use base64 to dodge any quoting issue.
    import base64
    msg_b64 = base64.b64encode(message.encode("utf-8")).decode("ascii")

    aura_bin = "/home/axp/.local/bin/aura"
    script = (
        f"sleep {seconds} && "
        f"{aura_bin} send {target} "
        f'"$(echo {msg_b64} | base64 -d)" '
        f"--as {sender} "
        f">/tmp/aura/sleep-{os.getpid()}.log 2>&1"
    )

    # Fire-and-forget detached
    subprocess.Popen(
        ["nohup", "bash", "-c", script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )

    return {
        "ok": True,
        "target": target,
        "sender": sender,
        "seconds": seconds,
        "message_preview": message[:80] + ("..." if len(message) > 80 else ""),
        "note": f"will fire in {seconds}s via aura send",
    }

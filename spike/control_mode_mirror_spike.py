#!/usr/bin/env python3
"""Rung-1 spike: replace Aura's POLLING tmux mirror with an EVENT-DRIVEN one.

Today `cli/lib/tmux_mirror.list_physical_panes()` shells `tmux list-panes -a`
on every read — a poll. This spike attaches a tmux **control-mode** client
(`tmux -C attach`), which streams structured `%`-notifications for pane/window
lifecycle, and refreshes the pane table ONLY when an event says something
changed. Same data, no polling cadence.

Proof obligations:
  1. The pane table the spike maintains is byte-identical in shape to what the
     PRODUCTION parser (cli/lib/tmux_mirror.parse_panes) produces — we import
     and use the real parser, no reimplementation.
  2. Table refreshes are TRIGGERED by control-mode events (split, new-window,
     kill-pane), not a timer.

Safety: runs on an ISOLATED tmux server (`tmux -L herdr-spike`). It never
touches the default server where the 55 live seats run.
"""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

# Use the REAL production parser/format — the spike must be output-compatible.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))
from lib import tmux_mirror  # noqa: E402

SOCK = "herdr-spike"          # isolated server — not the live default server
SESS = "spike"

# Control-mode async notifications that mean "the pane topology changed".
LIFECYCLE = (
    "%window-add", "%window-close", "%unlinked-window-add",
    "%window-pane-changed", "%layout-change", "%sessions-changed",
    "%session-window-changed",
)


def tmux(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", "-L", SOCK, *args],
                          capture_output=True, text=True, check=check)


def snapshot_table() -> list[dict]:
    """Event-driven refresh: query panes through the REAL production format."""
    fmt = tmux_mirror._FIELD_SEP.join(tmux_mirror._FORMAT_FIELDS)
    out = tmux("list-panes", "-a", "-F", fmt, check=False).stdout
    return tmux_mirror.parse_panes(out)   # production parser, not a copy


def fmt_table(panes: list[dict]) -> str:
    rows = [f"    {p['pane_ref']:<22} win={p['window_name']:<10} "
            f"cmd={p['pane_current_command']:<8} active={p['pane_active']}"
            for p in panes]
    return "\n".join(rows) or "    (none)"


def reader(proc: subprocess.Popen, events: "queue.Queue[str]") -> None:
    for line in proc.stdout:
        line = line.rstrip("\n")
        if line.startswith("%") and not line.startswith("%output"):
            events.put(line)


def main() -> int:
    # Fresh isolated server.
    tmux("kill-server", check=False)
    tmux("new-session", "-d", "-s", SESS, "-n", "root")
    time.sleep(0.3)

    # Attach a control-mode client to the isolated session.
    cc = subprocess.Popen(
        ["tmux", "-L", SOCK, "-C", "attach", "-t", SESS],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1,
    )
    events: "queue.Queue[str]" = queue.Queue()
    threading.Thread(target=reader, args=(cc, events), daemon=True).start()
    time.sleep(0.5)

    refreshes = 0

    def drain_and_refresh(label: str) -> None:
        nonlocal refreshes
        time.sleep(0.6)
        seen = []
        while not events.empty():
            seen.append(events.get_nowait())
        lifecycle = [e for e in seen if any(e.startswith(p) for p in LIFECYCLE)]
        print(f"\n=== after: {label} ===")
        print(f"  control-mode events: {len(seen)} "
              f"({len(lifecycle)} lifecycle) e.g. "
              f"{', '.join(sorted({e.split()[0] for e in seen}))}")
        if lifecycle:
            refreshes += 1
            table = snapshot_table()   # refresh ONLY because an event fired
            print(f"  -> event-triggered refresh #{refreshes}; "
                  f"{len(table)} panes:")
            print(fmt_table(table))
        else:
            print("  -> no lifecycle event; mirror NOT touched (no poll)")

    print("baseline table (1 pane expected):")
    print(fmt_table(snapshot_table()))

    # Drive real topology changes; each should fire a control-mode event.
    tmux("split-window", "-t", f"{SESS}:root", "-h")
    drain_and_refresh("split-window (add a pane)")

    tmux("new-window", "-t", SESS, "-n", "worker")
    drain_and_refresh("new-window (add a window)")

    tmux("split-window", "-t", f"{SESS}:worker", "-v")
    drain_and_refresh("split-window in worker")

    tmux("kill-pane", "-t", f"{SESS}:root.1", check=False)
    drain_and_refresh("kill-pane (remove a pane)")

    # Proof of output-compatibility with production.
    final = snapshot_table()
    keys = set(final[0].keys()) if final else set()
    expected = {"physical_fleet", "tmux_session", "window_id", "window_index",
                "window_name", "pane_id", "pane_index", "pane_pid",
                "pane_current_path", "pane_current_command", "pane_active",
                "pane_ref", "terminal_ref"}
    print("\n=== PROOF ===")
    print(f"  event-triggered refreshes: {refreshes} (0 timer polls)")
    print(f"  production parse_panes() shape match: {keys == expected} "
          f"({len(keys)} fields)")
    print(f"  sample pane_ref format: {final[0]['pane_ref'] if final else 'n/a'} "
          f"(same 'tmux:<session>:%N' the registry/resolver expect)")

    # Teardown — isolated server only.
    cc.terminate()
    tmux("kill-server", check=False)
    print("\n  isolated server killed; live default server untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

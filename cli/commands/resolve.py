"""Resolve agent name or tmux group → session_id + window + status.

Used by skills/tools that observe multiple agents at once (e.g. flex:workers).

  aura resolve dev-goose                  # by agent name
  aura resolve dev                        # by tmux session (enumerates windows)
  aura resolve dev-goose,dev-goose-bench  # by comma-separated names
"""

import os
import subprocess
import sys

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'lib'))


def _ledger_latest_session_id(name):
    """Return the most recent session_id for `name` from aura ledger (or None)."""
    try:
        from ledger import read_ledger
        entries = read_ledger()
    except Exception:
        return None
    matches = [e for e in entries if e.get("name") == name]
    if not matches:
        return None
    matches.sort(key=lambda e: e.get("ts", ""), reverse=True)
    return matches[0].get("session_id")


def _pane_session_id(window):
    """Parse the session_id footer from a tmux pane (bottom ~3 lines).

    Aura's wrapper prints the session UUID in the pane footer. Works even when
    the ledger has rotated entries off.
    """
    import re
    for target in (window, f"aura:{window}", f"dev:{window}"):
        out = subprocess.run(
            ["tmux", "capture-pane", "-t", target, "-p", "-S", "-5"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            for line in out.stdout.splitlines():
                m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", line)
                if m:
                    return m.group(1)
    return None


def _aura_list():
    """Return aura list as list of {name, status, last_seen} dicts."""
    try:
        from mesh import discover, agent_status
        info = discover()
        if info.get("error"):
            return []
        agents = []
        for name in info.get("agents", []):
            st = agent_status(name)
            agents.append({"name": name, "status": st.get("status", "unknown"),
                           "last_seen": st.get("last_seen")})
        return agents
    except Exception:
        return []


def _tmux_windows(session):
    """List window names in a tmux session. Returns [] if session missing."""
    out = subprocess.run(
        ["tmux", "list-windows", "-t", session, "-F", "#{window_name}"],
        capture_output=True, text=True, timeout=5,
    )
    if out.returncode != 0:
        return []
    return [w.strip() for w in out.stdout.splitlines() if w.strip()]


def _resolve_one(name, live_lookup):
    """Build a record for one agent name. Returns dict (or None if no session_id)."""
    sid = _ledger_latest_session_id(name) or _pane_session_id(name)
    if not sid:
        return None
    rec = {
        "name": name,
        "session_id": sid,
        "status": "unknown",
        "last_seen": None,
        "tmux_window": name,
    }
    if name in live_lookup:
        rec["status"] = live_lookup[name]["status"]
        rec["last_seen"] = live_lookup[name]["last_seen"]
    return rec


def run(args):
    """Resolve names or a tmux group into agent records."""
    target = args.target.strip()

    # Build live agent lookup once.
    live = {a["name"]: a for a in _aura_list()}

    # Detect mode: comma-separated names, single name, or tmux group.
    if "," in target:
        names = [n.strip() for n in target.split(",") if n.strip()]
        mode = "names"
    elif target in live:
        names = [target]
        mode = "name"
    else:
        # Try tmux group: enumerate windows and treat each window as an agent name.
        windows = _tmux_windows(target)
        if windows:
            names = windows
            mode = "tmux-group"
        else:
            # Fallback: single name even if not in live mesh (may still be in ledger).
            names = [target]
            mode = "name"

    records = []
    for n in names:
        r = _resolve_one(n, live)
        if r:
            records.append(r)

    return {"ok": True, "mode": mode, "target": target, "count": len(records),
            "agents": records}

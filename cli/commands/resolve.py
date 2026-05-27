"""Resolve agent name or tmux group → session_id + window + status.

Used by skills/tools that observe multiple agents at once (e.g. flex:workers).
Includes terminal-backed sidecars even when no Claude/Flex session_id exists so
callers can fall back to tmux capture instead of dropping them.
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _ledger_latest_session_id(name):
    """Return the most recent session_id for `name` from the legacy ledger file."""
    try:
        from commands.ledger import read_ledger
        entries = read_ledger()
    except Exception:
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


def _pane_session_id(window, sessions=None):
    """Parse a UUID from a tmux pane footer/history."""
    import re
    targets = [window]
    for session in sessions or ("aura", "dev"):
        targets.append(f"{session}:{window}")
    for target in targets:
        out = subprocess.run(
            ["tmux", "capture-pane", "-t", target, "-p", "-S", "-80"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            for line in out.stdout.splitlines():
                m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", line)
                if m:
                    return m.group(1)
    return None


def _mesh_lookup():
    try:
        from lib import mesh
        info = mesh.discover()
        if info.get("error"):
            return {}
        return {a.get("name"): a for a in info.get("agents", []) if a.get("name")}
    except Exception:
        return {}


def _tmux_windows(session):
    """List window names in a tmux session. Returns [] if session missing."""
    out = subprocess.run(
        ["tmux", "list-windows", "-t", session, "-F", "#{window_name}"],
        capture_output=True, text=True, timeout=5,
    )
    if out.returncode != 0:
        return []
    return [w.strip() for w in out.stdout.splitlines() if w.strip()]


def _resolve_one(name, live_lookup, registry_lookup, fleet=None):
    from lib import registry

    reg = registry_lookup.get(name) or registry.get_agent(name, fleet=fleet) or {}
    live = live_lookup.get(name) or {}
    sid = live.get("session_id") or reg.get("session_id") or _ledger_latest_session_id(name) or _pane_session_id(name, sessions=[fleet] if fleet else None)
    terminal_ref = reg.get("terminal_ref") or (f"{fleet}:{name}" if fleet else name)
    status = live.get("status") or reg.get("status") or "unknown"
    rec = {
        "name": name,
        "session_id": sid,
        "status": status,
        "last_seen": live.get("last_seen") or reg.get("last_seen"),
        "tmux_window": name,
        "terminal_ref": terminal_ref,
        "fleet": reg.get("fleet") or fleet,
        "runtime": reg.get("runtime"),
        "registered": bool(live.get("socket_path")) or bool(reg.get("registered")),
        "trace_cell": reg.get("trace_cell"),
    }
    return {k: v for k, v in rec.items() if v is not None or k == "session_id"}


def run(args):
    """Resolve names or a tmux group into agent records."""
    from lib import registry

    target = args.target.strip()
    live = _mesh_lookup()

    if "," in target:
        names = [n.strip() for n in target.split(",") if n.strip()]
        mode = "names"
        fleet = registry.current_fleet()
    elif ":" in target and not target.startswith("tmux:"):
        fleet, name = target.split(":", 1)
        names = [name]
        mode = "fleet-qualified-name"
    elif target in live or registry.get_agent(target):
        names = [target]
        mode = "name"
        fleet = (registry.get_agent(target) or {}).get("fleet") or registry.current_fleet()
    else:
        windows = _tmux_windows(target)
        registered = registry.list_agents(target)
        if windows or registered:
            names = []
            for n in [a.get("name") for a in registered] + windows:
                if n and n not in names:
                    names.append(n)
            mode = "tmux-group"
            fleet = target
        else:
            names = [target]
            mode = "name"
            fleet = registry.current_fleet()

    registry_lookup = {a.get("name"): a for a in registry.list_agents(fleet) if a.get("name")}
    records = [_resolve_one(n, live, registry_lookup, fleet=fleet) for n in names]

    return {"ok": True, "mode": mode, "target": target, "count": len(records),
            "agents": records}

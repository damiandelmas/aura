"""Query the aura agent ledger."""

import json
from pathlib import Path

LEDGER_PATH = Path.home() / ".aura" / "ledger.jsonl"


def read_ledger(limit: int | None = None):
    if not LEDGER_PATH.exists():
        return []
    entries = []
    with open(LEDGER_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    if limit is not None:
        return entries[-int(limit):]
    return entries


def run(args):
    """Query spawned agent history."""
    if not LEDGER_PATH.exists():
        return {"ok": False, "error": "no ledger found", "hint": "agents write ledger entries on startup via SessionStart hook"}

    entries = read_ledger()

    if not entries:
        return {"ok": False, "error": "ledger is empty"}

    # Filter by name if specified
    if args.name:
        entries = [e for e in entries if args.name in e.get("name", "")]

    # Filter by fleet
    if getattr(args, 'fleet', None):
        entries = [e for e in entries if e.get("fleet") == args.fleet]

    # Filter by parent session
    if getattr(args, 'parent', None):
        entries = [e for e in entries if args.parent in e.get("parent", "")]

    # Default: show most recent N
    limit = getattr(args, 'limit', 20) or 20
    entries = entries[-limit:]

    # Format output
    results = []
    for e in entries:
        sid = e.get("session_id", "")
        results.append({
            "ts": e.get("ts", "")[:19],
            "name": e.get("name", ""),
            "fleet": e.get("fleet", ""),
            "session_id": sid,
            "parent": e.get("parent", "")[:8] if e.get("parent") else "",
            "memory": e.get("memory", "")[:8] if e.get("memory") else "",
        })

    return results

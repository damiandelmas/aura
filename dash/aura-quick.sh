#!/bin/bash
# Quick aura status - formatted table view
# Usage: aura-quick [refresh_seconds]

REFRESH="${1:-3}"

watch -n"$REFRESH" -t 'python3 << "PYEND"
import json
import subprocess
import sys
from datetime import datetime

print("╔══════════════════════════════════════════════════════════════════╗")
print("║                      🔮 AURA AGENT MESH                          ║")
print("╚══════════════════════════════════════════════════════════════════╝")
print()

try:
    result = subprocess.run(["aura", "list"], capture_output=True, text=True)
    agents = json.loads(result.stdout)

    if not agents:
        print("  No agents running")
        sys.exit(0)

    # Header
    print(f"  {'NAME':<24} {'STATUS':<10} {'MODE':<12} {'SEEN':<8}")
    print("  " + "─" * 58)

    # Sort by name
    for a in sorted(agents, key=lambda x: x["name"]):
        name = a["name"][:23]
        status = a.get("status", "?")
        mode = a.get("mode", "?")[:11]
        seen = a.get("last_seen", "")[11:19]  # Just time

        # Status indicator
        if status == "busy":
            indicator = "🔴"
        elif status == "idle":
            indicator = "🟢"
        else:
            indicator = "⚪"

        print(f"  {name:<24} {indicator} {status:<7} {mode:<12} {seen}")

    print()
    print(f"  Total: {len(agents)} agents | {datetime.now().strftime('%H:%M:%S')}")

except Exception as e:
    print(f"  Error: {e}")

print()
print("──────────────────────────────────────────────────────────────────")
print("  aura-matrix: full view │ aura-tail <name>: focus one")
print("──────────────────────────────────────────────────────────────────")
PYEND'

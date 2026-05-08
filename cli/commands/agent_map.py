"""Render the Aura agent map packet for one managed seat."""

from __future__ import annotations

from lib import agent_map


def run(args):
    from lib import terminal

    target = getattr(args, "target", None)
    if not target:
        return {"ok": False, "error": "agent-map requires TARGET"}
    result = agent_map.build_agent_map(target, terminal=terminal, require_routable=True)
    if result.get("ok"):
        result["text"] = result.get("packet")
    return result

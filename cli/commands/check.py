"""Check agent status."""


def run(args):
    """Check status of specific agent."""
    from lib import mesh, tmux

    result = mesh.discover()
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "mesh error")}

    agents = result.get("agents", [])
    agent = next((a for a in agents if a.get("name") == args.name), None)

    if not agent:
        return {"ok": False, "error": f"agent not found: {args.name}"}

    response = {
        "ok": True,
        "name": agent.get("name"),
        "status": agent.get("status", "unknown"),
        "mode": agent.get("delivery_mode", "immediate"),
        "registered": True,
        "last_seen": agent.get("last_seen", "")
    }

    if args.output:
        response["output"] = tmux.capture_output(args.name, args.lines)

    return response

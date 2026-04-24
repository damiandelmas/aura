"""Check agent status."""


def run(args):
    """Check status of specific agent."""
    from lib import mesh, terminal

    result = mesh.discover()
    agents = result.get("agents", []) if result.get("ok") else []
    agent = next((a for a in agents if a.get("name") == args.name), None)
    window_alive = terminal.window_exists(args.name)

    if not agent and not window_alive:
        return {"ok": False, "error": f"agent not found: {args.name}", "status": "stopped"}

    response = {
        "ok": True,
        "name": args.name,
        "status": agent.get("status", "unknown") if agent else "unknown",
        "mode": agent.get("delivery_mode", "immediate") if agent else "immediate",
        "registered": bool(agent),
        "terminal": "alive" if window_alive else "missing",
        "terminal_ref": f"tmux:{terminal.SESSION_NAME}:{args.name}" if window_alive else None,
        "last_seen": agent.get("last_seen", "") if agent else ""
    }

    if args.output and window_alive:
        response["output"] = terminal.capture_output(args.name, args.lines)

    return {k: v for k, v in response.items() if v is not None}

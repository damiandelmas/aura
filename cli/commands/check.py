"""Check agent status."""


def run(args):
    """Check status of specific agent."""
    from lib import mesh, registry, terminal

    result = mesh.discover()
    agents = result.get("agents", []) if result.get("ok") else []
    mesh_agent = next((a for a in agents if a.get("name") == args.name), None)
    reg_agent = registry.get_agent(args.name)
    agent = {**(reg_agent or {}), **(mesh_agent or {})} if (reg_agent or mesh_agent) else None
    if (agent or {}).get("fleet") and hasattr(terminal, "configure_session"):
        terminal.configure_session(agent.get("fleet"))
    window_alive = terminal.window_exists(args.name)

    if not agent and not window_alive:
        return {"ok": False, "error": f"agent not found: {args.name}", "status": "stopped"}

    status = registry.infer_status(args.name, terminal, (agent or {}).get("status", "unknown")) if window_alive else (agent or {}).get("status", "dead")
    if reg_agent and status != reg_agent.get("status"):
        registry.mark_status(args.name, status, fleet=reg_agent.get("fleet"))

    response = {
        "ok": True,
        "name": args.name,
        "fleet": (agent or {}).get("fleet", registry.current_fleet()),
        "runtime": (agent or {}).get("runtime"),
        "status": status,
        "mode": (agent or {}).get("delivery_mode", "immediate"),
        "registered": bool((agent or {}).get("socket_path")) or bool((agent or {}).get("registered")),
        "terminal": "alive" if window_alive else "missing",
        "terminal_ref": f"tmux:{terminal.SESSION_NAME}:{args.name}" if window_alive else (agent or {}).get("terminal_ref"),
        "trace_cell": (agent or {}).get("trace_cell"),
        "last_seen": (agent or {}).get("last_seen", "")
    }

    if args.output and window_alive:
        response["output"] = terminal.capture_output(args.name, args.lines)

    return {k: v for k, v in response.items() if v is not None}

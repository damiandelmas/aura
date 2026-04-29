"""Check agent status."""


def run(args):
    """Check status of specific agent."""
    from lib import mesh, registry, terminal

    def _target_exists(target: str) -> bool:
        return terminal.target_exists(target) if hasattr(terminal, "target_exists") else terminal.window_exists(target)

    result = mesh.discover()
    agents = result.get("agents", []) if result.get("ok") else []
    mesh_agent = next((a for a in agents if a.get("name") == args.name), None)
    reg_agent = registry.get_agent(args.name)
    agent = {**(reg_agent or {}), **(mesh_agent or {})} if (reg_agent or mesh_agent) else None
    if (agent or {}).get("fleet") and hasattr(terminal, "configure_session"):
        terminal.configure_session(agent.get("fleet"))
    terminal_target = (agent or {}).get("pane_ref") or (agent or {}).get("terminal_ref") or args.name
    terminal_alive = _target_exists(terminal_target)

    if not agent and not terminal_alive:
        return {"ok": False, "error": f"agent not found: {args.name}", "status": "stopped"}

    status = registry.infer_status(args.name, terminal, (agent or {}).get("status", "unknown"), target=terminal_target) if terminal_alive else (agent or {}).get("status", "dead")
    if reg_agent and status != reg_agent.get("status"):
        registry.mark_status(args.name, status, fleet=reg_agent.get("fleet"))

    from lib import runtime_session

    session_info = runtime_session.discover_for_target((agent or {}).get("runtime"), terminal, terminal_target) if terminal_alive else {}
    if reg_agent and session_info:
        registry.upsert_agent(runtime_session.merge(dict(reg_agent), session_info))

    response = runtime_session.merge({
        "ok": True,
        "name": args.name,
        "fleet": (agent or {}).get("fleet", registry.current_fleet()),
        "runtime": (agent or {}).get("runtime"),
        "status": status,
        "mode": (agent or {}).get("delivery_mode", "immediate"),
        "registered": bool((agent or {}).get("socket_path")) or bool((agent or {}).get("registered")),
        "terminal": "alive" if terminal_alive else "missing",
        "backend": "tmux" if terminal_alive or (agent or {}).get("terminal_ref") else None,
        "terminal_ref": (agent or {}).get("terminal_ref") or (f"tmux:{terminal.SESSION_NAME}:{args.name}" if terminal_alive else None),
        "backend_ref": (agent or {}).get("backend_ref") or ((agent or {}).get("terminal_ref") or "").removeprefix("tmux:"),
        "pane_ref": (agent or {}).get("pane_ref"),
        "trace_cell": (agent or {}).get("trace_cell"),
        "last_seen": (agent or {}).get("last_seen", "")
    }, session_info)

    capture_format = getattr(args, "format", "text") or "text"
    if args.output and terminal_alive:
        response["output"] = terminal.capture_output(terminal_target, args.lines, ansi=capture_format == "ansi")
        response["output_format"] = capture_format

    from lib import seat_schema
    return seat_schema.enrich({k: v for k, v in response.items() if v is not None})

"""Internal mechanical seat-status primitive used by inspect/sense/watch."""


def run(args):
    """Check status of specific agent."""
    from lib import mesh, registry, terminal

    def _target_exists(target: str) -> bool:
        return terminal.target_exists(target) if hasattr(terminal, "target_exists") else terminal.window_exists(target)

    result = mesh.discover()
    agents = result.get("agents", []) if result.get("ok") else []
    mesh_agent = next((a for a in agents if a.get("name") == args.name), None)
    reg_agent = registry.resolve_live(args.name)
    agent = {**(reg_agent or {}), **(mesh_agent or {})} if (reg_agent or mesh_agent) else None
    if (agent or {}).get("fleet") and hasattr(terminal, "configure_session"):
        terminal.configure_session(agent.get("fleet"))
    elif ":" in args.name and not args.name.startswith("tmux:") and hasattr(terminal, "configure_session"):
        terminal.configure_session(args.name.split(":", 1)[0])
    terminal_target = (agent or {}).get("pane_ref") or (agent or {}).get("terminal_ref") or args.name
    terminal_alive = _target_exists(terminal_target)
    target_diagnostic = None
    if not terminal_alive and terminal_target != args.name and _target_exists(args.name):
        target_diagnostic = {
            "reason": "registered-target-missing-window-name-alive",
            "registered_target": terminal_target,
            "fallback_target": args.name,
        }
        terminal_target = args.name
        terminal_alive = True

    if not agent and not terminal_alive:
        return {"ok": False, "error": f"agent not found: {args.name}", "status": "stopped"}

    status = registry.infer_status(args.name, terminal, (agent or {}).get("status", "unknown"), target=terminal_target) if terminal_alive else (agent or {}).get("status", "dead")
    if reg_agent and status != reg_agent.get("status"):
        registry.mark_status(args.name, status, fleet=reg_agent.get("fleet"))

    from lib import runtime_session

    session_info = runtime_session.discover_for_target(
        (agent or {}).get("runtime"),
        terminal,
        terminal_target,
        seat_name=args.name,
        launch_id=(agent or {}).get("aura_launch_id"),
    ) if terminal_alive else {}
    if reg_agent and session_info:
        merged_agent = registry.upsert_agent(runtime_session.merge(dict(reg_agent), session_info))
        reg_agent = merged_agent
        agent = {**(agent or {}), **merged_agent}

    display_name = (agent or {}).get("name") or (args.name.split(":", 1)[1] if ":" in args.name and not args.name.startswith("tmux:") else args.name)
    display_fleet = (agent or {}).get("fleet") or (args.name.split(":", 1)[0] if ":" in args.name and not args.name.startswith("tmux:") else registry.current_fleet())

    session_record = {
        key: (agent or {}).get(key)
        for key in (
            "session_id",
            "runtime_session_id",
            "runtime_session_source",
            "runtime_session_binding",
            "runtime_session_bind_method",
            "runtime_session_bind_source",
            "runtime_session_bound_at",
            "runtime_session_confidence",
            "runtime_session_evidence",
            "runtime_session_env",
            "runtime_session_cwd",
            "runtime_session_created_at_ms",
            "runtime_session_updated_at_ms",
        )
        if (agent or {}).get(key) is not None
    }
    response = runtime_session.merge({
        **session_record,
        "ok": True,
        "name": display_name,
        "fleet": display_fleet,
        "runtime": (agent or {}).get("runtime"),
        "aura_launch_id": (agent or {}).get("aura_launch_id"),
        "status": status,
        "mode": (agent or {}).get("delivery_mode", "immediate"),
        "registered": bool((agent or {}).get("socket_path")) or bool((agent or {}).get("registered")),
        "terminal": "alive" if terminal_alive else "missing",
        "backend": "tmux" if terminal_alive or (agent or {}).get("terminal_ref") else None,
        "terminal_ref": (agent or {}).get("terminal_ref") or (f"{display_fleet}:{display_name}" if terminal_alive else None),
        "backend_ref": (agent or {}).get("backend_ref") or ((agent or {}).get("terminal_ref") or "").removeprefix("tmux:"),
        "pane_ref": (agent or {}).get("pane_ref"),
        "target_diagnostic": target_diagnostic,
        "trace_cell": (agent or {}).get("trace_cell"),
        "last_seen": (agent or {}).get("last_seen", "")
    }, session_info)

    capture_format = getattr(args, "format", "text") or "text"
    if args.output and terminal_alive:
        response["output"] = terminal.capture_output(terminal_target, args.lines, ansi=capture_format == "ansi")
        response["output_format"] = capture_format

    from lib import seat_schema
    return seat_schema.enrich({k: v for k, v in response.items() if v is not None})

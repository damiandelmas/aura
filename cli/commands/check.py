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
    elif ":" in args.name and not args.name.startswith("tmux:") and hasattr(terminal, "configure_session"):
        terminal.configure_session(args.name.split(":", 1)[0])
    terminal_target = (agent or {}).get("pane_ref") or (agent or {}).get("terminal_ref") or args.name
    terminal_alive = _target_exists(terminal_target)
    host_status = None
    host_tail = None
    if (agent or {}).get("host_socket"):
        try:
            from lib import host_client

            host_status = host_client.request((agent or {}).get("host_socket"), {
                "op": "status",
                "launch_id": (agent or {}).get("host_launch_id") or (agent or {}).get("aura_launch_id"),
            })
            if getattr(args, "output", False):
                host_tail = host_client.request((agent or {}).get("host_socket"), {
                    "op": "tail",
                    "launch_id": (agent or {}).get("host_launch_id") or (agent or {}).get("aura_launch_id"),
                    "lines": args.lines,
                })
        except Exception as exc:
            host_status = {
                "ok": False,
                "error": str(exc),
                "outcome": "host_request_failed",
            }
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

    if host_status and host_status.get("ok") and host_status.get("child_alive"):
        status = "alive"
    else:
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
        registry.upsert_agent(runtime_session.merge(dict(reg_agent), session_info))

    display_name = (agent or {}).get("name") or (args.name.split(":", 1)[1] if ":" in args.name and not args.name.startswith("tmux:") else args.name)
    display_fleet = (agent or {}).get("fleet") or (args.name.split(":", 1)[0] if ":" in args.name and not args.name.startswith("tmux:") else registry.current_fleet())

    response = runtime_session.merge({
        "ok": True,
        "name": display_name,
        "fleet": display_fleet,
        "runtime": (agent or {}).get("runtime"),
        "aura_launch_id": (agent or {}).get("aura_launch_id"),
        "status": status,
        "mode": (agent or {}).get("delivery_mode", "immediate"),
        "registered": bool((agent or {}).get("socket_path")) or bool((agent or {}).get("registered")),
        "terminal": "alive" if terminal_alive else "missing",
        "host": "alive" if host_status and host_status.get("ok") else ("unavailable" if host_status else None),
        "child": "alive" if host_status and host_status.get("child_alive") else ("dead" if host_status and host_status.get("ok") else None),
        "host_status": host_status,
        "backend": (agent or {}).get("control_backend") or ("tmux" if terminal_alive or (agent or {}).get("terminal_ref") else None),
        "control_backend": (agent or {}).get("control_backend"),
        "delivery_backend": (agent or {}).get("delivery_backend"),
        "viewport_backend": (agent or {}).get("viewport_backend"),
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
    elif args.output and host_tail and host_tail.get("ok"):
        response["output"] = host_tail.get("output", [])
        response["output_format"] = "host-tail"

    from lib import seat_schema
    return seat_schema.enrich({k: v for k, v in response.items() if v is not None})

"""List all agents."""


def run(args):
    """List all agents."""
    from lib import mesh, registry, terminal

    def _target_exists(target: str) -> bool:
        return terminal.target_exists(target) if hasattr(terminal, "target_exists") else terminal.window_exists(target)

    current_fleet = registry.current_fleet(default=getattr(terminal, "SESSION_NAME", "aura"))
    fleet_filter = getattr(args, "fleet", None)
    result = mesh.discover()
    mesh_agents = result.get("agents", []) if result.get("ok") else []
    if fleet_filter:
        mesh_agents = [a for a in mesh_agents if a.get("fleet") == fleet_filter]
    by_name = {a.get("name"): dict(a) for a in mesh_agents if a.get("name")}

    registry_agents = registry.list_agents(fleet_filter) if fleet_filter else registry.list_agents()
    for agent in registry_agents:
        name = agent.get("name")
        if not name:
            continue
        existing = by_name.get(name, {})
        merged = {**agent, **existing}
        merged.setdefault("registered", True)
        by_name[name] = merged

    fleet = fleet_filter or current_fleet
    if hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)
    for window in terminal.list_windows():
        by_name.setdefault(window, {
            "name": window,
            "fleet": fleet,
            "status": "unknown",
            "delivery_mode": "immediate",
            "last_seen": "",
            "registered": False,
        })

    agents = list(by_name.values())

    if args.status:
        agents = [a for a in agents if a.get("status") == args.status]
    if args.mode:
        agents = [a for a in agents if a.get("delivery_mode") == args.mode]

    from lib import runtime_session, seat_schema
    rows = []
    for a in sorted(agents, key=lambda x: x.get("name", "")):
        name = a.get("name")
        agent_fleet = a.get("fleet") or fleet
        if agent_fleet and hasattr(terminal, "configure_session"):
            terminal.configure_session(agent_fleet)
        terminal_target = a.get("pane_ref") or a.get("terminal_ref") or name
        terminal_alive = _target_exists(terminal_target)
        status = registry.infer_status(name, terminal, a.get("status", "unknown"), target=terminal_target) if terminal_alive else a.get("status", "unknown")
        session_info = runtime_session.discover_for_target(a.get("runtime"), terminal, terminal_target) if terminal_alive else {}
        if a.get("registered") and session_info:
            registry.upsert_agent(runtime_session.merge(dict(a), session_info))
        row = runtime_session.merge({
            "name": name,
            "fleet": agent_fleet,
            "runtime": a.get("runtime"),
            "status": status,
            "mode": a.get("delivery_mode", "immediate"),
            "registered": bool(a.get("socket_path")) or bool(a.get("registered")),
            "terminal": "alive" if terminal_alive else "missing",
            "backend": "tmux" if terminal_alive or a.get("terminal_ref") else None,
            "terminal_ref": a.get("terminal_ref") or (f"tmux:{terminal.SESSION_NAME}:{name}" if terminal_alive else ""),
            "backend_ref": a.get("backend_ref") or (a.get("terminal_ref") or "").removeprefix("tmux:"),
            "pane_ref": a.get("pane_ref"),
            "trace_cell": a.get("trace_cell"),
            "last_seen": (a.get("last_seen", "") or "")[:19]
        }, session_info)
        rows.append(seat_schema.enrich(row))
    return rows

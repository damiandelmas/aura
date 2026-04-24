"""List all agents."""


def run(args):
    """List all agents."""
    from lib import mesh, registry, terminal

    result = mesh.discover()
    mesh_agents = result.get("agents", []) if result.get("ok") else []
    by_name = {a.get("name"): dict(a) for a in mesh_agents if a.get("name")}

    fleet = registry.current_fleet(default=getattr(terminal, "SESSION_NAME", "aura"))
    for agent in registry.list_agents(fleet):
        name = agent.get("name")
        if not name:
            continue
        existing = by_name.get(name, {})
        merged = {**agent, **existing}
        merged.setdefault("registered", True)
        by_name[name] = merged

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

    rows = []
    for a in sorted(agents, key=lambda x: x.get("name", "")):
        name = a.get("name")
        window_alive = terminal.window_exists(name)
        status = registry.infer_status(name, terminal, a.get("status", "unknown")) if window_alive else a.get("status", "unknown")
        rows.append({
            "name": name,
            "fleet": a.get("fleet", fleet),
            "runtime": a.get("runtime"),
            "status": status,
            "mode": a.get("delivery_mode", "immediate"),
            "registered": bool(a.get("socket_path")) or bool(a.get("registered")),
            "terminal": "alive" if window_alive else "missing",
            "terminal_ref": f"tmux:{terminal.SESSION_NAME}:{name}" if window_alive else a.get("terminal_ref", ""),
            "trace_cell": a.get("trace_cell"),
            "last_seen": (a.get("last_seen", "") or "")[:19]
        })
    return rows

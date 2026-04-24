"""List all agents."""


def run(args):
    """List all agents."""
    from lib import mesh, terminal

    result = mesh.discover()
    mesh_agents = result.get("agents", []) if result.get("ok") else []
    by_name = {a.get("name"): a for a in mesh_agents if a.get("name")}

    for window in terminal.list_windows():
        by_name.setdefault(window, {
            "name": window,
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

    return [
        {
            "name": a.get("name"),
            "status": a.get("status", "unknown"),
            "mode": a.get("delivery_mode", "immediate"),
            "registered": bool(a.get("socket_path")) or bool(a.get("registered")),
            "terminal": "alive" if terminal.window_exists(a.get("name")) else "missing",
            "terminal_ref": f"tmux:{terminal.SESSION_NAME}:{a.get('name')}" if terminal.window_exists(a.get("name")) else "",
            "last_seen": (a.get("last_seen", "") or "")[:19]
        }
        for a in sorted(agents, key=lambda x: x.get("name", ""))
    ]

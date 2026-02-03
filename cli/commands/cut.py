"""End agent shift."""


def run(args):
    """Cut agent (graceful stop)."""
    from lib import mesh, terminal

    # Unregister from mesh first
    mesh.unregister(args.name)

    # Kill terminal window
    if terminal.window_exists(args.name):
        terminal.kill_window(args.name)
        return {"ok": True, "name": args.name, "cut": True}

    return {"ok": True, "name": args.name, "cut": True, "note": "window not found"}

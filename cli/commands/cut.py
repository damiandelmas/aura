"""End agent shift."""


def run(args):
    """Cut agent (graceful stop)."""
    from lib import mesh, tmux

    # Unregister from mesh first
    mesh.unregister(args.name)

    # Kill tmux window
    if tmux.window_exists(args.name):
        tmux.kill_window(args.name)
        return {"ok": True, "name": args.name, "cut": True}

    return {"ok": True, "name": args.name, "cut": True, "note": "window not found"}

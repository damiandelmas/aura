"""End agent shift."""


def run(args):
    """Cut agent (graceful or forced stop)."""
    from lib import mesh, terminal

    force = getattr(args, 'force', False)

    if not force:
        # Graceful: unregister from mesh, let wrapper clean up
        mesh.unregister(args.name)

    # Kill terminal window (force or graceful both end here)
    if terminal.window_exists(args.name):
        terminal.kill_window(args.name)
        return {"ok": True, "name": args.name, "cut": True, "force": force}

    # Window gone but still registered — clean up mesh
    if force:
        mesh.unregister(args.name)

    return {"ok": True, "name": args.name, "cut": True, "note": "window not found"}

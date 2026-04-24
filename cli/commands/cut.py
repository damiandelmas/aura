"""End agent shift."""

import time


def run(args):
    """Cut agent (graceful or forced stop)."""
    from lib import mesh, registry, terminal

    force = getattr(args, 'force', False)
    graceful_attempted = False

    if terminal.window_exists(args.name) and not force:
        graceful_attempted = True
        # Runtime-agnostic best effort. Most agent CLIs accept /exit; if not,
        # the window is still force-killed below after a short grace period.
        terminal.send_text(args.name, "/exit", submit=True)
        time.sleep(1.0)

    if not force:
        # Mesh unregister is best-effort; tmux remains the source of process truth.
        mesh.unregister(args.name)

    if terminal.window_exists(args.name):
        terminal.kill_window(args.name)
        registry.mark_status(args.name, "dead")
        return {
            "ok": True,
            "name": args.name,
            "cut": True,
            "force": force,
            "graceful_attempted": graceful_attempted,
            "terminal": "killed",
        }

    if force:
        mesh.unregister(args.name)

    return {
        "ok": True,
        "name": args.name,
        "cut": True,
        "force": force,
        "graceful_attempted": graceful_attempted,
        "note": "window not found",
    }

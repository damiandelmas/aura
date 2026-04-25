"""End agent shift."""

import time


def run(args):
    """Cut agent (graceful or forced stop)."""
    from lib import mesh, registry, terminal, runtimes

    force = getattr(args, 'force', False)
    graceful_attempted = False
    reg_agent = registry.get_agent(args.name)
    if (reg_agent or {}).get("fleet") and hasattr(terminal, "configure_session"):
        terminal.configure_session(reg_agent.get("fleet"))

    runtime = (reg_agent or {}).get("runtime")
    graceful_exit = runtimes.graceful_exit(runtime)

    if terminal.window_exists(args.name) and not force:
        graceful_attempted = True
        terminal.send_text(args.name, graceful_exit, submit=True)
        time.sleep(1.0)

    if not force:
        # Mesh unregister is best-effort; tmux remains the source of process truth.
        mesh.unregister(args.name)

    if terminal.window_exists(args.name):
        terminal.kill_window(args.name)
        registry.mark_status(args.name, "dead", fleet=(reg_agent or {}).get("fleet"))
        return {
            "ok": True,
            "name": args.name,
            "cut": True,
            "force": force,
            "graceful_attempted": graceful_attempted,
            "graceful_exit": graceful_exit if graceful_attempted else None,
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
        "graceful_exit": graceful_exit if graceful_attempted else None,
        "note": "window not found",
    }

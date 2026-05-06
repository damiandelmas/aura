"""End agent shift."""

import time


def run(args):
    """Cut agent (graceful or forced stop)."""
    from lib import mesh, registry, terminal, runtimes

    force = getattr(args, 'force', False)
    graceful_attempted = False
    reg_agent = registry.get_agent(args.name)
    agent_name = (reg_agent or {}).get("name")
    agent_fleet = (reg_agent or {}).get("fleet")
    if not agent_name and ":" in str(args.name) and not str(args.name).startswith("tmux:"):
        agent_fleet, agent_name = str(args.name).split(":", 1)
    agent_name = agent_name or args.name
    if (reg_agent or {}).get("fleet") and hasattr(terminal, "configure_session"):
        terminal.configure_session(reg_agent.get("fleet"))
    terminal_target = (reg_agent or {}).get("pane_ref") or (reg_agent or {}).get("terminal_ref") or args.name

    def _target_exists(target: str) -> bool:
        if hasattr(terminal, "target_exists"):
            exists = terminal.target_exists(target)
            if exists or target != args.name:
                return exists
        return terminal.window_exists(target)

    target_exists = _target_exists(terminal_target)

    runtime = (reg_agent or {}).get("runtime")
    graceful_exit = runtimes.graceful_exit(runtime)
    host_stop = None

    if (reg_agent or {}).get("host_socket"):
        try:
            from lib import host_client

            host_stop = host_client.request((reg_agent or {}).get("host_socket"), {
                "op": "stop",
                "launch_id": (reg_agent or {}).get("host_launch_id") or (reg_agent or {}).get("aura_launch_id"),
                "mode": "force" if force else "graceful",
                "graceful_text": graceful_exit,
            })
        except Exception as exc:
            host_stop = {"ok": False, "error": str(exc), "outcome": "host_request_failed"}
        if not host_stop.get("ok") or host_stop.get("child_alive"):
            result = {
                "ok": False,
                "name": args.name,
                "cut": False,
                "force": force,
                "terminal": "alive" if target_exists else "missing",
                "host_stop": host_stop,
                "error": "host stop failed; refusing to mark host-backed seat dead",
            }
            _record_stop(result, reg_agent, terminal_target)
            return result

    if target_exists and not force and not (reg_agent or {}).get("host_socket"):
        graceful_attempted = True
        terminal.send_text(terminal_target, graceful_exit, submit=True)
        time.sleep(1.0)

    if not force:
        # Mesh unregister is best-effort; tmux remains the source of process truth.
        mesh.unregister(args.name)

    target_exists = _target_exists(terminal_target)
    if target_exists:
        terminal.kill_window(terminal_target)
        registry.mark_status(agent_name, "dead", fleet=agent_fleet)
        result = {
            "ok": True,
            "name": args.name,
            "cut": True,
            "force": force,
            "graceful_attempted": graceful_attempted,
            "graceful_exit": graceful_exit if graceful_attempted else None,
            "terminal": "killed",
            "host_stop": host_stop,
        }
        _record_stop(result, reg_agent, terminal_target)
        return result

    if force:
        mesh.unregister(args.name)
        if reg_agent:
            registry.mark_status(agent_name, "dead", fleet=agent_fleet)

    result = {
        "ok": True,
        "name": args.name,
        "cut": True,
        "force": force,
        "graceful_attempted": graceful_attempted,
        "graceful_exit": graceful_exit if graceful_attempted else None,
        "note": "window not found",
        "host_stop": host_stop,
    }
    _record_stop(result, reg_agent, terminal_target)
    return result


def _record_stop(result: dict, reg_agent: dict | None, terminal_target: str) -> None:
    try:
        from lib import session_ledger
        from lib import registry

        after = None
        if reg_agent:
            after = registry.get_agent(
                reg_agent.get("name") or result.get("name"),
                fleet=reg_agent.get("fleet"),
            )

        session_ledger.append_record({
            "event": "stop",
            "seat": result.get("name"),
            "name": result.get("name"),
            "fleet": (reg_agent or {}).get("fleet"),
            "runtime": (reg_agent or {}).get("runtime"),
            "terminal_ref": (reg_agent or {}).get("terminal_ref"),
            "pane_ref": (reg_agent or {}).get("pane_ref"),
            "target": terminal_target,
            "force": result.get("force"),
            "graceful_attempted": result.get("graceful_attempted"),
            "graceful_exit": result.get("graceful_exit"),
            "result": result,
        })
        session_ledger.append_seat_event(
            event="seat_cut",
            before=reg_agent,
            after=after,
            evidence={
                "target": terminal_target,
                "force": result.get("force"),
                "graceful_attempted": result.get("graceful_attempted"),
                "graceful_exit": result.get("graceful_exit"),
                "terminal": result.get("terminal"),
                "note": result.get("note"),
                "host_stop": result.get("host_stop"),
            },
            source_command="aura seat cut",
        )
    except Exception:
        pass

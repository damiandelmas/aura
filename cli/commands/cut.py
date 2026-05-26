"""End agent shift."""

import time


def _candidate_targets(reg_agent: dict | None, requested: str) -> list[str]:
    targets = []
    for key in ("pane_ref", "terminal_ref", "backend_ref"):
        value = (reg_agent or {}).get(key)
        if value and value not in targets:
            targets.append(value)
    if requested and requested not in targets and (not reg_agent or not targets):
        targets.append(requested)
    return targets


def _target_exists(terminal, target: str, requested: str) -> bool:
    if hasattr(terminal, "target_exists"):
        exists = terminal.target_exists(target)
        if exists or target != requested:
            return exists
    return terminal.window_exists(target)


def _select_terminal_target(terminal, reg_agent: dict | None, requested: str) -> tuple[str, bool, list[dict]]:
    candidates = _candidate_targets(reg_agent, requested)
    checks = []
    for target in candidates:
        exists = _target_exists(terminal, target, requested)
        checks.append({"target": target, "exists": exists})
        if exists:
            return target, True, checks
    target = candidates[0] if candidates else requested
    return target, False, checks


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
    requested = str(args.name)
    terminal_target, target_exists, target_checks = _select_terminal_target(terminal, reg_agent, requested)
    terminal_candidates = [check["target"] for check in target_checks]

    runtime = (reg_agent or {}).get("runtime")
    graceful_exit = runtimes.graceful_exit(runtime)

    if target_exists and not force:
        graceful_attempted = True
        terminal.send_text(terminal_target, graceful_exit, submit=True)
        time.sleep(1.0)

    if not force:
        # Mesh unregister is best-effort; tmux remains the source of process truth.
        mesh.unregister(args.name)

    terminal_target, target_exists, target_checks = _select_terminal_target(terminal, reg_agent, requested)
    terminal_candidates = [check["target"] for check in target_checks]
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
            "terminal_target": terminal_target,
            "terminal_target_candidates": terminal_candidates,
            "terminal_target_checks": target_checks,
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
        "terminal_target": terminal_target,
        "terminal_target_candidates": terminal_candidates,
        "terminal_target_checks": target_checks,
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
                "terminal_target_candidates": result.get("terminal_target_candidates"),
                "terminal_target_checks": result.get("terminal_target_checks"),
            },
            source_command="aura seat cut",
        )
    except Exception:
        pass

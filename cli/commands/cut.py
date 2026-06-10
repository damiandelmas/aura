"""End agent shift."""

import time


def _is_pane_ref(ref: str) -> bool:
    """Return True if ref is a pane-id-based tmux ref (contains %N)."""
    if not ref:
        return False
    # tmux:fleet:%N  or  fleet:%N  or  bare %N
    parts = str(ref).split(":")
    return parts[-1].startswith("%")


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


def _select_kill_target(terminal, reg_agent: dict | None, requested: str) -> tuple[str | None, bool, list[dict]]:
    """Select the kill target using pane-id-only policy.

    Safety contract:
    - If the registry record has a pane_ref, we ONLY consider the pane_ref.
      If that pane is dead we return (pane_ref, False, checks) — the caller
      treats this as "already gone" and proceeds to registry cleanup WITHOUT
      issuing a name-based fallback kill.
    - Only when the record has NO pane_ref at all may name-based targets be
      used; even then they go through `=`-exact matching in kill_window.

    Returns: (target, target_exists, checks_list)
    """
    pane_ref = (reg_agent or {}).get("pane_ref")
    checks = []

    if pane_ref:
        # Pane-id-only: check liveness once, never fall back to names.
        exists = _target_exists(terminal, pane_ref, requested)
        checks.append({"target": pane_ref, "exists": exists, "kind": "pane_ref"})
        return pane_ref, exists, checks

    # No pane_ref — try name-based targets (terminal_ref, backend_ref, requested).
    name_candidates = []
    for key in ("terminal_ref", "backend_ref"):
        value = (reg_agent or {}).get(key)
        if value and value not in name_candidates:
            name_candidates.append(value)
    if requested and requested not in name_candidates:
        name_candidates.append(requested)

    for target in name_candidates:
        exists = _target_exists(terminal, target, requested)
        checks.append({"target": target, "exists": exists, "kind": "name_ref"})
        if exists:
            return target, True, checks

    # Nothing live — report first candidate (or requested) as the dead target.
    dead_target = name_candidates[0] if name_candidates else requested
    return dead_target, False, checks


def _select_terminal_target(terminal, reg_agent: dict | None, requested: str) -> tuple[str, bool, list[dict]]:
    """Legacy shim used for the graceful-send phase only (not for kill)."""
    pane_ref = (reg_agent or {}).get("pane_ref")
    checks = []

    if pane_ref:
        exists = _target_exists(terminal, pane_ref, requested)
        checks.append({"target": pane_ref, "exists": exists})
        return pane_ref, exists, checks

    candidates = _candidate_targets(reg_agent, requested)
    for target in candidates:
        exists = _target_exists(terminal, target, requested)
        checks.append({"target": target, "exists": exists})
        if exists:
            return target, True, checks
    target = candidates[0] if candidates else requested
    return target, False, checks


def _clear_pane_ref(registry, agent_name: str, agent_fleet: str | None) -> None:
    """Null out pane_ref in the registry so no future op can re-use a dead %N."""
    try:
        def _remove_pane_ref(current):
            stored = dict(current or {})
            stored.pop("pane_ref", None)
            return stored
        registry.update_agent_record(agent_name, agent_fleet, _remove_pane_ref)
    except Exception:
        pass


def run(args):
    """Cut agent (graceful or forced stop)."""
    from lib import mesh, registry, terminal, runtimes

    force = getattr(args, 'force', False)
    graceful_attempted = False
    reg_agent = registry.resolve_live(args.name)
    agent_name = (reg_agent or {}).get("name")
    agent_fleet = (reg_agent or {}).get("fleet")
    if not agent_name and ":" in str(args.name) and not str(args.name).startswith("tmux:"):
        agent_fleet, agent_name = str(args.name).split(":", 1)
    agent_name = agent_name or args.name
    if (reg_agent or {}).get("fleet") and hasattr(terminal, "configure_session"):
        terminal.configure_session(reg_agent.get("fleet"))
    requested = str(args.name)

    # Graceful-exit phase: use existing target resolution (pane-preferred).
    terminal_target_for_send, target_exists_send, _ = _select_terminal_target(terminal, reg_agent, requested)

    runtime = (reg_agent or {}).get("runtime")
    graceful_exit = runtimes.graceful_exit(runtime)

    if target_exists_send and not force:
        graceful_attempted = True
        terminal.send_text(terminal_target_for_send, graceful_exit, submit=True)
        time.sleep(1.0)

    if not force:
        # Mesh unregister is best-effort; tmux remains the source of process truth.
        mesh.unregister(args.name)

    # Kill phase: pane-id-only policy — never name-fallback-kill.
    terminal_target, target_exists, target_checks = _select_kill_target(terminal, reg_agent, requested)
    terminal_candidates = [check["target"] for check in target_checks]

    if target_exists:
        terminal.kill_window(terminal_target)
        registry.mark_status(agent_name, "dead", fleet=agent_fleet)
        _clear_pane_ref(registry, agent_name, agent_fleet)
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

    # Target not live — seat is already gone (pane_ref dead, or no window).
    # Mark dead and clear pane_ref; do NOT attempt a name-fallback kill.
    if reg_agent:
        registry.mark_status(agent_name, "dead", fleet=agent_fleet)
        _clear_pane_ref(registry, agent_name, agent_fleet)

    if force:
        mesh.unregister(args.name)
        if reg_agent and not registry.resolve_live(agent_name, fleet=agent_fleet):
            registry.mark_status(agent_name, "dead", fleet=agent_fleet)

    # Determine whether the pane was already absent (not just name-not-found).
    pane_ref = (reg_agent or {}).get("pane_ref")
    note = "pane already gone" if pane_ref and _is_pane_ref(pane_ref) else "window not found"

    result = {
        "ok": True,
        "name": args.name,
        "cut": True,
        "force": force,
        "graceful_attempted": graceful_attempted,
        "graceful_exit": graceful_exit if graceful_attempted else None,
        "note": note,
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
        from lib import diagnostic_cache

        after = None
        if reg_agent:
            after = registry.resolve_live(
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
        target = result.get("name")
        if reg_agent:
            target = (
                reg_agent.get("seat_ref")
                or registry.seat_ref(reg_agent.get("fleet"), reg_agent.get("name") or result.get("name"))
            )
        result["diagnostic_cache_invalidation"] = diagnostic_cache.invalidate(
            target,
            reason="seat-cut",
            source_command="aura seat cut",
            evidence={
                "terminal_target": terminal_target,
                "terminal": result.get("terminal"),
                "note": result.get("note"),
            },
        )
    except Exception:
        pass

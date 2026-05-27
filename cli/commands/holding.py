"""Discover and manage unresolved runtime bodies."""

from __future__ import annotations


def _pane_ref(pane: dict) -> str:
    return f"tmux:{pane.get('session')}:{pane.get('pane_id')}"


def _managed_refs(registry) -> set[str]:
    from commands import seat as seat_cmd

    def live_pane_ref(value: str | None) -> str | None:
        if not value:
            return None
        target = seat_cmd._tmux_target(str(value))
        result = seat_cmd._run_tmux([
            "display-message",
            "-p",
            "-t",
            target,
            "#{session_name}\t#{pane_id}",
        ])
        if result.returncode != 0:
            return None
        parts = result.stdout.strip().split("\t")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            return None
        return f"tmux:{parts[0]}:{parts[1]}"

    refs: set[str] = set()
    for record in registry.list_agents(include_hidden=True):
        for key in ("pane_ref", "terminal_ref", "backend_ref"):
            value = record.get(key)
            if value and key == "pane_ref":
                refs.add(str(value))
            if value:
                resolved = live_pane_ref(str(value))
                if resolved:
                    refs.add(resolved)
    return refs


def _candidate_from_pane(pane: dict, *, registry, managed_refs: set[str]) -> dict:
    from commands import seat as seat_cmd

    pane_ref = _pane_ref(pane)
    window_target = f"{pane.get('session')}:{pane.get('window_name')}"
    already_registered = pane_ref in managed_refs or window_target in managed_refs
    command = pane.get("pane_current_command") or ""
    return {
        "source": "tmux",
        "pane_ref": pane_ref,
        "tmux_session": pane.get("session"),
        "window_index": pane.get("window_index"),
        "pane_index": pane.get("pane_index"),
        "window_name": pane.get("window_name"),
        "pane_id": pane.get("pane_id"),
        "pane_pid": pane.get("pane_pid"),
        "active_command": command,
        "cwd": pane.get("pane_current_path"),
        "runtime_hint": seat_cmd._infer_adoption_runtime(command),
        "already_registered": already_registered,
    }


def _discover(args) -> dict:
    from commands import seat as seat_cmd
    from lib import holding, registry

    fleet = getattr(args, "fleet", None)
    all_fleets = bool(getattr(args, "all_fleets", False))
    if not all_fleets and not fleet:
        fleet = registry.current_fleet()
    panes = seat_cmd._list_tmux_panes()
    if not all_fleets:
        panes = [pane for pane in panes if pane.get("session") == fleet]
    refs = _managed_refs(registry)
    candidates = [_candidate_from_pane(pane, registry=registry, managed_refs=refs) for pane in panes]
    managed = [candidate for candidate in candidates if candidate.get("already_registered")]
    unmanaged = [candidate for candidate in candidates if not candidate.get("already_registered")]

    created = []
    if getattr(args, "create", False):
        for candidate in unmanaged:
            created.append(holding.create_from_candidate(candidate))

    response = {
        "ok": True,
        "schema": "aura.holding.discover.v1",
        "read_only": not getattr(args, "create", False),
        "source": "tmux",
        "fleet": None if all_fleets else fleet,
        "all_fleets": all_fleets,
        "unmanaged": unmanaged,
        "unmanaged_count": len(unmanaged),
        "created": created,
        "created_count": len(created),
    }
    if getattr(args, "all", False):
        response["managed"] = managed
        response["managed_count"] = len(managed)
    return response


def _list(args) -> dict:
    from lib import holding

    records = holding.list_records(
        state_filter=getattr(args, "status", None),
        fleet=getattr(args, "fleet", None),
        include_resolved=bool(getattr(args, "include_resolved", False)),
    )
    return {
        "ok": True,
        "schema": "aura.holding.list.v1",
        "records": records,
        "count": len(records),
    }


def _adopt(args) -> dict:
    from commands import seat as seat_cmd
    from lib import holding, registry

    record = holding.load(args.holding_id)
    if not record:
        return {"ok": False, "error": "holding-not-found", "holding_id": args.holding_id}
    if record.get("state") != "holding":
        return {
            "ok": False,
            "error": "holding-not-active",
            "holding_id": args.holding_id,
            "state": record.get("state"),
            "resolution": record.get("resolution"),
        }
    target = getattr(args, "target", None)
    fleet, _, error = seat_cmd._normalize_adoption_target(target)
    if error:
        return error
    pane_ref = record.get("pane_ref")
    if not pane_ref:
        return {"ok": False, "error": "holding-missing-pane-ref", "holding_id": args.holding_id}
    discovery = seat_cmd._validate_explicit_adoption_pane(pane_ref, fleet)
    if not discovery.get("ok"):
        return {"ok": False, **discovery, "holding_id": args.holding_id, "target": target}

    result = seat_cmd._adopt_pane_as_seat(
        target=target,
        pane=discovery["pane"],
        registry=registry,
        runtime_arg=getattr(args, "runtime", None) or record.get("runtime_hint"),
        cwd_arg=getattr(args, "cwd", None),
        discovered_by=f"holding:{args.holding_id}",
        source_command="aura holding adopt",
        registered_via="holding-adopt",
        rename_window=bool(getattr(args, "rename_window", False)),
        adoption_source=args.holding_id,
    )
    if result.get("ok"):
        resolved = holding.resolve(
            args.holding_id,
            state="adopted",
            target=target,
            reason="adopted-into-aura-seat",
            evidence={
                "pane_ref": result.get("pane_ref"),
                "seat_instance_id": result.get("seat_instance_id"),
                "runtime_session_binding": result.get("runtime_session_binding"),
            },
        )
        result["holding"] = resolved
    return result


def run(args):
    action = args.holding_action
    if action == "discover":
        return _discover(args)
    if action == "list":
        return _list(args)
    if action == "adopt":
        return _adopt(args)
    return {"ok": False, "error": f"unknown holding action: {action}"}

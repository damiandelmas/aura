"""Broadcast a message to every agent in a fleet or live scope."""

import argparse

_registry = None
_terminal = None
_send = None


def _registry_mod():
    global _registry
    if _registry is None:
        from lib import registry as _loaded
        _registry = _loaded
    return _registry


def _terminal_mod():
    global _terminal
    if _terminal is None:
        from lib import terminal as _loaded
        _terminal = _loaded
    return _terminal


def _send_mod():
    global _send
    if _send is None:
        from commands import send as _loaded
        _send = _loaded
    return _send


def _fleet_and_message_from_args(args):
    parts = list(getattr(args, "parts", []) or [])
    explicit_fleet = getattr(args, "fleet", None)
    registry = _registry_mod()
    if hasattr(args, "message"):
        return (explicit_fleet or getattr(args, "fleet_arg", None) or registry.current_fleet(), getattr(args, "message", "") or "")
    if explicit_fleet:
        return explicit_fleet, " ".join(parts)
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    if len(parts) == 1:
        return registry.current_fleet(), parts[0]
    return registry.current_fleet(), ""


def _targets_for_fleet(fleet: str, include_shell: bool = False, allow_hidden: bool = False) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    registry = _registry_mod()
    terminal = _terminal_mod()

    if registry.is_hidden_fleet(fleet) and not allow_hidden:
        return []

    for agent in registry.list_agents(fleet, include_hidden=allow_hidden):
        if registry.is_hidden_agent(agent) and not allow_hidden:
            continue
        name = agent.get("name")
        if name and name not in seen:
            names.append(name)
            seen.add(name)

    # If the command is running inside this fleet's tmux session, include live
    # windows that are not yet registered. This keeps sidecar control useful
    # while the registry is catching up. Shell windows are excluded by default.
    if hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)
    if getattr(terminal, "SESSION_NAME", fleet) == fleet and (allow_hidden or not registry.is_hidden_fleet(fleet)):
        for name in terminal.list_windows():
            if not include_shell and name in ("bash", "sh", "shell"):
                continue
            if name not in seen:
                names.append(name)
                seen.add(name)

    return names


def _live_targets(*, runtime: str | None = None, allow_hidden: bool = False) -> list[dict]:
    """Return registered live targets across fleets.

    This is registry-first: global broadcast is for Aura seats, not raw
    unregistered tmux panes. Fleet broadcast with --include-shell remains the
    local recovery path for intentionally including unregistered windows.
    """
    registry = _registry_mod()
    terminal = _terminal_mod()
    rows = []
    seen: set[str] = set()
    for agent in registry.list_agents(include_hidden=allow_hidden):
        if registry.is_hidden_agent(agent) and not allow_hidden:
            continue
        if runtime and agent.get("runtime") != runtime:
            continue
        fleet = agent.get("fleet")
        name = agent.get("seat") or agent.get("name")
        if not fleet or not name:
            continue
        if registry.is_hidden_fleet(fleet) and not allow_hidden:
            continue
        target = f"{fleet}:{name}"
        if target in seen:
            continue
        terminal_ref = agent.get("pane_ref") or agent.get("terminal_ref") or target
        if not terminal.target_exists(terminal_ref):
            continue
        seen.add(target)
        rows.append({
            "target": target,
            "fleet": fleet,
            "seat": name,
            "runtime": agent.get("runtime"),
            "terminal_ref": terminal_ref,
        })
    return sorted(rows, key=lambda row: (row["fleet"], row["seat"]))


def _message_for_scope(args) -> str:
    parts = list(getattr(args, "parts", []) or [])
    if hasattr(args, "message"):
        return getattr(args, "message", "") or ""
    return " ".join(parts)


def _broadcast_to_targets(args, target_rows: list[dict], message: str) -> dict:
    results = []
    send = _send_mod()
    for row in target_rows:
        target = row["target"]
        dedupe_key = getattr(args, "dedupe_key", None)
        if dedupe_key:
            dedupe_key = f"{dedupe_key}:{target}"
        send_args = argparse.Namespace(
            target=target,
            message=message,
            sender=getattr(args, "sender", None),
            service_sender=getattr(args, "service_sender", None),
            mode=None,
            nudge=False,
            transport=getattr(args, "transport", "auto") or "auto",
            dedupe_key=dedupe_key,
            force=getattr(args, "force", False),
            allow_hidden=bool(getattr(args, "allow_hidden", False)),
        )
        result = send.run(send_args)
        results.append({**row, "result": result})
    sent = [row for row in results if (row.get("result") or {}).get("ok")]
    failed = [row for row in results if not (row.get("result") or {}).get("ok")]
    return {
        "count": len(results),
        "sent_count": len(sent),
        "failed_count": len(failed),
        "targets": [row["target"] for row in target_rows],
        "results": results,
    }


def run(args):
    scope = getattr(args, "scope", None) or "fleet"
    if scope in {"live", "all-live"}:
        message = _message_for_scope(args)
        runtime = getattr(args, "runtime", None)
        targets = _live_targets(runtime=runtime, allow_hidden=bool(getattr(args, "allow_hidden", False)))
        fanout = _broadcast_to_targets(args, targets, message)
        fleets = sorted({row["fleet"] for row in targets})
        return {
            "ok": fanout["failed_count"] == 0,
            "schema": "aura.broadcast_live.v1",
            "scope": "live",
            "runtime": runtime,
            "fleet_count": len(fleets),
            "fleets": fleets,
            **fanout,
        }

    fleet, message = _fleet_and_message_from_args(args)
    include_shell = getattr(args, "include_shell", False)
    allow_hidden = bool(getattr(args, "allow_hidden", False))
    registry = _registry_mod()
    if registry.is_hidden_fleet(fleet) and not allow_hidden:
        return {
            "ok": False,
            "blocked": True,
            "reason": "target-hidden",
            "fleet": fleet,
            "hint": "use --allow-hidden for explicit operator access to hidden/internal fleets",
        }
    targets = _targets_for_fleet(fleet, include_shell=include_shell, allow_hidden=allow_hidden)

    results = []
    send = _send_mod()
    for target in targets:
        dedupe_key = getattr(args, "dedupe_key", None)
        if dedupe_key:
            dedupe_key = f"{dedupe_key}:{target}"
        send_args = argparse.Namespace(
            target=target,
            message=message,
            sender=getattr(args, "sender", None),
            service_sender=getattr(args, "service_sender", None),
            mode=None,
            nudge=False,
            transport=getattr(args, "transport", "auto") or "auto",
            dedupe_key=dedupe_key,
            force=getattr(args, "force", False),
            allow_hidden=allow_hidden,
        )
        result = send.run(send_args)
        results.append({"target": target, "result": result})

    return {
        "ok": True,
        "fleet": fleet,
        "count": len(results),
        "targets": targets,
        "results": results,
    }

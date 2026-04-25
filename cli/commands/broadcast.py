"""Broadcast a message to every agent in a fleet."""

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


def _targets_for_fleet(fleet: str, include_shell: bool = False) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    registry = _registry_mod()
    terminal = _terminal_mod()

    for agent in registry.list_agents(fleet):
        name = agent.get("name")
        if name and name not in seen:
            names.append(name)
            seen.add(name)

    # If the command is running inside this fleet's tmux session, include live
    # windows that are not yet registered. This keeps sidecar control useful
    # while the registry is catching up. Shell windows are excluded by default.
    if hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)
    if getattr(terminal, "SESSION_NAME", fleet) == fleet:
        for name in terminal.list_windows():
            if not include_shell and name in ("bash", "sh", "shell"):
                continue
            if name not in seen:
                names.append(name)
                seen.add(name)

    return names


def run(args):
    fleet, message = _fleet_and_message_from_args(args)
    include_shell = getattr(args, "include_shell", False)
    targets = _targets_for_fleet(fleet, include_shell=include_shell)

    results = []
    send = _send_mod()
    for target in targets:
        dedupe_key = getattr(args, "dedupe_key", None)
        if dedupe_key:
            dedupe_key = f"{dedupe_key}:{target}"
        send_args = argparse.Namespace(
            target=target,
            message=message,
            sender=getattr(args, "sender", "cli") or "cli",
            mode=None,
            nudge=False,
            transport=getattr(args, "transport", "auto") or "auto",
            dedupe_key=dedupe_key,
            force=getattr(args, "force", False),
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

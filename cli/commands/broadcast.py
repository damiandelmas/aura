"""Broadcast a message to every agent in a fleet."""

import argparse

from lib import registry as _registry
from lib import terminal as _terminal
from commands import send as _send


def _fleet_and_message_from_args(args):
    parts = list(getattr(args, "parts", []) or [])
    explicit_fleet = getattr(args, "fleet", None)
    if hasattr(args, "message"):
        return (explicit_fleet or getattr(args, "fleet_arg", None) or _registry.current_fleet(), getattr(args, "message", "") or "")
    if explicit_fleet:
        return explicit_fleet, " ".join(parts)
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    if len(parts) == 1:
        return _registry.current_fleet(), parts[0]
    return _registry.current_fleet(), ""


def _targets_for_fleet(fleet: str, include_shell: bool = False) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for agent in _registry.list_agents(fleet):
        name = agent.get("name")
        if name and name not in seen:
            names.append(name)
            seen.add(name)

    # If the command is running inside this fleet's tmux session, include live
    # windows that are not yet registered. This keeps sidecar control useful
    # while the registry is catching up. Shell windows are excluded by default.
    if getattr(_terminal, "SESSION_NAME", fleet) == fleet:
        for name in _terminal.list_windows():
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
        result = _send.run(send_args)
        results.append({"target": target, "result": result})

    return {
        "ok": True,
        "fleet": fleet,
        "count": len(results),
        "targets": targets,
        "results": results,
    }

"""Broadcast a message to every agent in a fleet or live scope."""

import argparse
import os

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


def _target_exists(terminal, target: str | None) -> bool:
    if not target:
        return False
    if hasattr(terminal, "target_exists"):
        return bool(terminal.target_exists(target))
    if hasattr(terminal, "window_exists"):
        return bool(terminal.window_exists(target))
    return False


def _seat_name(agent: dict) -> str | None:
    return agent.get("seat") or agent.get("name")


def _logical_target(agent: dict, fallback_fleet: str | None = None) -> str | None:
    seat = _seat_name(agent)
    fleet = agent.get("fleet") or fallback_fleet
    if not seat:
        return None
    return f"{fleet}:{seat}" if fleet else seat


def _live_terminal_target(agent: dict, terminal, fallback_fleet: str | None = None) -> str | None:
    for key in ("pane_ref", "terminal_ref", "backend_ref"):
        target = agent.get(key)
        if _target_exists(terminal, target):
            return str(target)
    logical = _logical_target(agent, fallback_fleet)
    if _target_exists(terminal, logical):
        return logical
    return None


def _is_current_target(target: str) -> bool:
    fleet = os.environ.get("AURA_FLEET")
    seat = os.environ.get("AURA_SEAT") or os.environ.get("AURA_AGENT_NAME")
    return bool(seat and target in {seat, f"{fleet}:{seat}" if fleet else ""})


def _targets_for_fleet(
    fleet: str,
    include_shell: bool = False,
    allow_hidden: bool = False,
    include_self: bool = False,
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    registry = _registry_mod()
    terminal = _terminal_mod()

    if registry.is_hidden_fleet(fleet) and not allow_hidden:
        return []

    if hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)

    for agent in registry.list_agents(fleet, include_hidden=allow_hidden):
        if registry.is_hidden_agent(agent) and not allow_hidden:
            continue
        target = _logical_target(agent, fleet)
        if not target or target in seen:
            continue
        if not include_self and _is_current_target(target):
            continue
        if not _live_terminal_target(agent, terminal, fleet):
            continue
        names.append(target)
        seen.add(target)
        seen.add(_seat_name(agent) or target)

    # If the command is running inside this fleet's tmux session, include live
    # windows that are not yet registered. This keeps sidecar control useful
    # while the registry is catching up. Shell windows are excluded by default.
    if include_shell and getattr(terminal, "SESSION_NAME", fleet) == fleet and (allow_hidden or not registry.is_hidden_fleet(fleet)):
        for name in terminal.list_windows():
            if name in ("bash", "sh", "shell"):
                continue
            if name not in seen and (include_self or not _is_current_target(f"{fleet}:{name}")):
                names.append(name)
                seen.add(name)

    return names


def _live_targets(*, runtime: str | None = None, allow_hidden: bool = False, include_self: bool = False) -> list[dict]:
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
        if hasattr(terminal, "configure_session"):
            terminal.configure_session(fleet)
        target = f"{fleet}:{name}"
        if target in seen:
            continue
        terminal_ref = _live_terminal_target(agent, terminal, fleet)
        if not terminal_ref:
            continue
        if _is_current_target(target) and not include_self:
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
        "failed_targets": [row["target"] for row in failed],
        "results": results,
    }


def _fleet_target_rows(fleet: str, targets: list[str]) -> list[dict]:
    rows = []
    for target in targets:
        seat = target.split(":", 1)[1] if target.startswith(f"{fleet}:") else target
        rows.append({"target": target, "fleet": fleet, "seat": seat})
    return rows


def run(args):
    scope = getattr(args, "scope", None) or "fleet"
    if scope in {"live", "all-live"}:
        message = _message_for_scope(args)
        runtime = getattr(args, "runtime", None)
        targets = _live_targets(
            runtime=runtime,
            allow_hidden=bool(getattr(args, "allow_hidden", False)),
            include_self=bool(getattr(args, "force", False)),
        )
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
            "_aura_cli_omit": ["results"],
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
    targets = _targets_for_fleet(
        fleet,
        include_shell=include_shell,
        allow_hidden=allow_hidden,
        include_self=bool(getattr(args, "force", False)),
    )

    fanout = _broadcast_to_targets(args, _fleet_target_rows(fleet, targets), message)
    return {
        "ok": fanout["failed_count"] == 0,
        "schema": "aura.broadcast_fleet.v1",
        "fleet": fleet,
        **fanout,
        "_aura_cli_omit": ["results"],
    }

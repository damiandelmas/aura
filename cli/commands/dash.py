"""Dashboard layout commands for tmux-backed Aura seats."""

from __future__ import annotations

import subprocess


def _tmux(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["tmux", *args], capture_output=True, text=True)


def _target(ref: str) -> str:
    value = str(ref or "")
    if value.startswith("tmux:"):
        value = value[len("tmux:"):]
    if ":" in value:
        fleet, subject = value.split(":", 1)
        if subject.startswith("%"):
            return subject
        return f"{fleet}:{subject}"
    return value


def _window_exists(fleet: str, window: str) -> bool:
    result = _tmux(["list-windows", "-t", fleet, "-F", "#{window_name}"])
    if result.returncode != 0:
        return False
    return window in result.stdout.splitlines()


def _pane_window(pane_ref: str) -> str | None:
    result = _tmux(["display-message", "-p", "-t", _target(pane_ref), "#{window_name}"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _pane_id(target: str) -> str | None:
    result = _tmux(["display-message", "-p", "-t", target, "#{pane_id}"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _pane_count(fleet: str, window: str) -> int:
    result = _tmux(["list-panes", "-t", f"{fleet}:{window}", "-F", "#{pane_id}"])
    if result.returncode != 0:
        return 0
    return len([line for line in result.stdout.splitlines() if line.strip()])


def _set_dashboard_options(fleet: str, dashboard: str, layout: str) -> None:
    _tmux(["select-layout", "-t", f"{fleet}:{dashboard}", layout])
    _tmux(["select-window", "-t", f"{fleet}:{dashboard}"])
    _tmux(["set-option", "-t", fleet, "-g", "monitor-activity", "off"])
    _tmux(["set-option", "-t", fleet, "-g", "visual-activity", "off"])


def _update_agent_pane(registry, terminal, agent: dict, pane_id: str, window: str, *, terminal_ref: str | None = None) -> dict:
    fleet = agent.get("fleet")
    name = agent.get("name")
    record = dict(agent)
    record["pane_ref"] = f"tmux:{fleet}:{pane_id}"
    record["backend_ref"] = f"{fleet}:{pane_id}"
    record["current_window"] = window
    if terminal_ref is not None:
        record["terminal_ref"] = terminal_ref
    registry.upsert_agent(record)
    if hasattr(terminal, "set_pane_title"):
        terminal.set_pane_title(record["pane_ref"], name)
    return record


def _registered_agents(registry, fleet: str) -> list[dict]:
    return [a for a in registry.list_agents(fleet) if a.get("registered") and a.get("name")]


def run(args):
    action = getattr(args, "dash_action", None)
    if action == "tile":
        return tile(args)
    if action == "untile":
        return untile(args)
    if action == "layout":
        return layout(args)
    return {"ok": False, "error": "dash requires an action: tile, untile, or layout"}


def tile(args):
    from lib import registry, terminal

    fleet = getattr(args, "fleet", None) or registry.current_fleet(default=getattr(terminal, "SESSION_NAME", "aura"))
    dashboard = getattr(args, "dashboard", None) or "dashboard"
    layout_name = getattr(args, "layout", None) or "tiled"
    limit = int(getattr(args, "max_panes", 20) or 20)
    if hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)

    agents = _registered_agents(registry, fleet)
    window_agents = [a for a in agents if terminal.window_exists(a["name"])]
    if not window_agents:
        return {"ok": False, "error": f"no registered seat windows to tile in fleet {fleet}", "fleet": fleet}
    window_agents = window_agents[:limit]

    moved = []
    first = window_agents[0]
    renamed_first = False
    placeholder_pane = None
    if _window_exists(fleet, dashboard):
        target_ref = f"{fleet}:{dashboard}"
    else:
        first_target = f"{fleet}:{first['name']}"
        pane = (terminal.pane_id(f"tmux:{first_target}") if hasattr(terminal, "pane_id") else None) or _pane_id(first_target)
        _tmux(["set-window-option", "-t", first_target, "automatic-rename", "off"])
        result = _tmux(["rename-window", "-t", first_target, dashboard])
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or "tmux rename-window failed", "fleet": fleet}
        target_ref = f"{fleet}:{dashboard}"
        renamed_first = True
        if pane:
            moved.append(_update_agent_pane(registry, terminal, first, pane, dashboard))

    join_agents = window_agents[1:] if renamed_first else window_agents
    for agent in join_agents:
        name = agent["name"]
        pane = (terminal.pane_id(f"tmux:{fleet}:{name}") if hasattr(terminal, "pane_id") else None) or _pane_id(f"{fleet}:{name}")
        result = _tmux(["join-pane", "-s", f"{fleet}:{name}", "-t", target_ref])
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or f"failed to join {name}", "fleet": fleet, "source": f"{fleet}:{name}", "target": target_ref, "moved": moved}
        if pane:
            moved.append(_update_agent_pane(registry, terminal, agent, pane, dashboard))
        _tmux(["select-layout", "-t", target_ref, "tiled"])

    if placeholder_pane and _pane_count(fleet, dashboard) > len(moved):
        _tmux(["kill-pane", "-t", placeholder_pane])

    _set_dashboard_options(fleet, dashboard, layout_name)
    return {
        "ok": True,
        "schema": "aura.dash.v1",
        "type": "dash",
        "action": "tile",
        "fleet": fleet,
        "dashboard": dashboard,
        "layout": layout_name,
        "count": len(moved),
        "seats": [record.get("name") for record in moved],
        "pane_refs": {record.get("name"): record.get("pane_ref") for record in moved},
    }


def untile(args):
    from lib import registry, terminal

    fleet = getattr(args, "fleet", None) or registry.current_fleet(default=getattr(terminal, "SESSION_NAME", "aura"))
    dashboard = getattr(args, "dashboard", None) or "dashboard"
    if hasattr(terminal, "configure_session"):
        terminal.configure_session(fleet)
    if not _window_exists(fleet, dashboard):
        return {"ok": False, "error": f"dashboard window not found: {fleet}:{dashboard}", "fleet": fleet}

    agents = _registered_agents(registry, fleet)
    in_dashboard = []
    for agent in agents:
        pane_ref = agent.get("pane_ref")
        if not pane_ref or not (terminal.target_exists(pane_ref) if hasattr(terminal, "target_exists") else False):
            continue
        if _pane_window(pane_ref) == dashboard:
            in_dashboard.append(agent)

    if not in_dashboard:
        return {"ok": False, "error": f"no registered panes in dashboard {fleet}:{dashboard}", "fleet": fleet}

    total_panes = _pane_count(fleet, dashboard)
    leave_one = total_panes == len(in_dashboard)
    remaining = in_dashboard[0] if leave_one else None
    broken = []

    break_agents = in_dashboard[1:] if leave_one else in_dashboard
    for agent in break_agents:
        name = agent["name"]
        pane_ref = agent["pane_ref"]
        result = _tmux(["break-pane", "-s", _target(pane_ref), "-t", f"{fleet}:", "-n", name])
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or f"failed to break pane for {name}", "fleet": fleet, "broken": broken}
        record = dict(agent)
        record["terminal_ref"] = f"tmux:{fleet}:{name}"
        record["backend_ref"] = f"{fleet}:{record.get('pane_ref', '').split(':')[-1]}"
        record["current_window"] = name
        registry.upsert_agent(record)
        broken.append(name)

    if remaining:
        result = _tmux(["rename-window", "-t", f"{fleet}:{dashboard}", remaining["name"]])
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr.strip() or "failed to rename remaining dashboard pane", "fleet": fleet}
        record = dict(remaining)
        record["terminal_ref"] = f"tmux:{fleet}:{remaining['name']}"
        record["backend_ref"] = f"{fleet}:{record.get('pane_ref', '').split(':')[-1]}"
        record["current_window"] = remaining["name"]
        registry.upsert_agent(record)
        broken.append(remaining["name"])

    return {
        "ok": True,
        "schema": "aura.dash.v1",
        "type": "dash",
        "action": "untile",
        "fleet": fleet,
        "dashboard": dashboard,
        "count": len(broken),
        "seats": sorted(broken),
    }


def layout(args):
    from lib import registry, terminal

    fleet = getattr(args, "fleet", None) or registry.current_fleet(default=getattr(terminal, "SESSION_NAME", "aura"))
    dashboard = getattr(args, "dashboard", None) or "dashboard"
    layout_name = getattr(args, "layout", None) or "tiled"
    if not _window_exists(fleet, dashboard):
        return {"ok": False, "error": f"dashboard window not found: {fleet}:{dashboard}", "fleet": fleet}
    _set_dashboard_options(fleet, dashboard, layout_name)
    return {
        "ok": True,
        "schema": "aura.dash.v1",
        "type": "dash",
        "action": "layout",
        "fleet": fleet,
        "dashboard": dashboard,
        "layout": layout_name,
    }

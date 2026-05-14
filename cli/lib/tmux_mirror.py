"""Read-only tmux physical mirror for Aura.

The mirror reports what tmux physically has: sessions, windows, and panes. It is
not a routing authority and it does not mutate terminal state.
"""

from __future__ import annotations

import subprocess
from typing import Any, Callable

from lib import registry

_FIELD_SEP = "\t"
_FORMAT_FIELDS = [
    "#{session_name}",
    "#{window_id}",
    "#{window_index}",
    "#{window_name}",
    "#{pane_id}",
    "#{pane_index}",
    "#{pane_pid}",
    "#{pane_current_path}",
    "#{pane_current_command}",
    "#{pane_active}",
]


def _logical_ref(record: dict[str, Any]) -> str | None:
    seat = record.get("seat") or record.get("name")
    fleet = record.get("fleet")
    if not seat:
        return None
    return f"{fleet}:{seat}" if fleet else str(seat)


def _pane_id_from_ref(value: str | None) -> str | None:
    if not value:
        return None
    subject = str(value)
    if subject.startswith("tmux:"):
        subject = subject[len("tmux:"):]
    if ":" in subject:
        subject = subject.rsplit(":", 1)[1]
    return subject if subject.startswith("%") else None


def _physical_fleet_from_ref(value: str | None) -> str | None:
    if not value:
        return None
    subject = str(value)
    if subject.startswith("tmux:"):
        subject = subject[len("tmux:"):]
    if ":" in subject:
        fleet, _ = subject.split(":", 1)
        return fleet or None
    return None


def parse_panes(output: str) -> list[dict[str, Any]]:
    """Parse `tmux list-panes -a` output produced by this module's format."""
    panes: list[dict[str, Any]] = []
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split(_FIELD_SEP)
        if len(parts) < 10:
            continue
        session, window_id, window_index, window_name, pane_id, pane_index, pane_pid, cwd, command, active = parts[:10]
        pane_ref = f"tmux:{session}:{pane_id}" if session and pane_id else None
        panes.append({
            "physical_fleet": session,
            "tmux_session": session,
            "window_id": window_id,
            "window_index": window_index,
            "window_name": window_name,
            "pane_id": pane_id,
            "pane_index": pane_index,
            "pane_pid": pane_pid,
            "pane_current_path": cwd,
            "pane_current_command": command,
            "pane_active": active == "1",
            "pane_ref": pane_ref,
            "terminal_ref": f"tmux:{session}:{window_name}" if session and window_name else None,
        })
    return panes


def list_physical_panes(*, runner: Callable[..., subprocess.CompletedProcess] | None = None) -> dict[str, Any]:
    """Return exact physical tmux panes without consulting Aura registry."""
    run = runner or subprocess.run
    fmt = _FIELD_SEP.join(_FORMAT_FIELDS)
    result = run(["tmux", "list-panes", "-a", "-F", fmt], capture_output=True, text=True)
    if result.returncode != 0:
        return {
            "ok": False,
            "schema": "aura.tmux_mirror.v1",
            "error": (result.stderr or "tmux list-panes failed").strip(),
            "panes": [],
        }
    panes = parse_panes(result.stdout)
    sessions = sorted({row["physical_fleet"] for row in panes if row.get("physical_fleet")})
    return {
        "ok": True,
        "schema": "aura.tmux_mirror.v1",
        "counts": {"sessions": len(sessions), "panes": len(panes)},
        "sessions": sessions,
        "panes": panes,
    }


def join_managed(panes: list[dict[str, Any]], records: list[dict[str, Any]]) -> dict[str, Any]:
    """Join physical panes to managed Aura registry rows by pane id/ref."""
    by_pane_id: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        pane_id = _pane_id_from_ref(record.get("pane_ref"))
        if pane_id:
            by_pane_id.setdefault(pane_id, []).append(record)

    joined = []
    seen_refs: set[str] = set()
    for pane in panes:
        matches = by_pane_id.get(str(pane.get("pane_id") or ""), [])
        managed = []
        for record in matches:
            logical_ref = _logical_ref(record)
            if logical_ref:
                seen_refs.add(logical_ref)
            managed.append({
                "logical_ref": logical_ref,
                "logical_fleet": record.get("logical_fleet") or record.get("fleet"),
                "logical_seat": record.get("logical_name") or record.get("seat") or record.get("name"),
                "runtime": record.get("runtime"),
                "seat_instance_id": record.get("seat_instance_id"),
                "status": record.get("status"),
            })
        joined.append({
            **pane,
            "managed": managed,
            "managed_state": "managed" if managed else "unmanaged",
        })

    stale = []
    for record in records:
        logical_ref = _logical_ref(record)
        if logical_ref in seen_refs:
            continue
        stale.append({
            "logical_ref": logical_ref,
            "logical_fleet": record.get("logical_fleet") or record.get("fleet"),
            "logical_seat": record.get("logical_name") or record.get("seat") or record.get("name"),
            "physical_fleet": record.get("physical_fleet") or _physical_fleet_from_ref(record.get("pane_ref")),
            "pane_ref": record.get("pane_ref"),
            "runtime": record.get("runtime"),
            "seat_instance_id": record.get("seat_instance_id"),
            "status": record.get("status"),
            "managed_state": "missing_pane",
        })

    return {
        "ok": True,
        "schema": "aura.tmux_mirror.joined.v1",
        "counts": {
            "physical_panes": len(panes),
            "managed_records": len(records),
            "unmanaged_panes": sum(1 for row in joined if row["managed_state"] == "unmanaged"),
            "missing_managed_panes": len(stale),
        },
        "panes": joined,
        "missing_managed": stale,
    }


def view_physical(*, include_hidden: bool = False, runner: Callable[..., subprocess.CompletedProcess] | None = None) -> dict[str, Any]:
    mirror = list_physical_panes(runner=runner)
    if not mirror.get("ok"):
        return mirror
    records = registry.list_agents(include_hidden=include_hidden)
    joined = join_managed(mirror.get("panes") or [], records)
    return {
        **joined,
        "physical": mirror,
    }

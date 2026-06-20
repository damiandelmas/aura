"""Society event source — the world-substrate layer above fleet/placement.

A *society* event fires when the member SET of a group (a fleet or a placement)
changes: join / leave / rename — "society changed, a new member entered". It is NOT
a member's self-state change (that is `reports`), nor a pane move or binding repair.
It drives ambient topology refresh.

Shape mirrors the report-boundary machinery (`reports.schedule_report_subscriptions`
+ `report_subscriptions`):

    member-set write  ──►  emit_society_change(group, kind, member)
                      ──►  schedule_society_subscriptions(group)
                              · explicit watchers (society_subscription rows)
                              · implicit: every LIVE seat IN the changed group
                      ──►  set_ambient_pending(targets, reason)   [the ambient layer's flag]

The ambient-pending flag belongs to the ambient layer (the hook reads it); society
only SETS it. It lives under AURA_STATE_DIR keyed by seat identity — the same path
`cli/hooks/claude_ambient_hook.py:pending_path()` reads — so neither side needs the
box layout. No registry write per society change (seam v2 §3 intent).
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from lib import state

SCHEMA_SUB = "aura.society_subscription.v1"
KINDS = {"join", "leave", "rename"}


# --------------------------------------------------------------------------- paths


def _state_root() -> Path:
    try:
        return Path(state.state_root())
    except Exception:  # noqa: BLE001
        return Path(os.environ.get("AURA_STATE_DIR") or (Path.home() / ".aura"))


def _pending_key(fleet: str, seat: str) -> str:
    return f"{fleet}__{seat}".replace("/", "_")


def pending_path(target: str) -> Path:
    """Per-seat ambient pending-refresh flag path; mirrors the hook's resolution.

    This flag is the ambient layer's mechanism — society only sets it; the hook owns
    reading/clearing it. Path is intentionally identical on both sides."""
    fleet, _, seat = target.partition(":")
    return _state_root() / "ambient-pending" / f"{_pending_key(fleet, seat or 'unknown')}.json"


def subscriptions_root() -> Path:
    return _state_root() / "society-subscriptions"


def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------- pending-flag write


def set_ambient_pending(targets: Iterable[str], reason: str) -> list[str]:
    """Write the ambient pending-refresh flag for each target seat. Best-effort;
    returns the targets actually flagged. Caller resolves live-only targets."""
    written: list[str] = []
    for target in targets:
        if not target or ":" not in target:
            continue
        try:
            _atomic_write(pending_path(target),
                          {"schema": "aura.ambient_pending.v1", "reason": reason, "set_at": _now()})
            written.append(target)
        except OSError:
            continue
    return written


# ------------------------------------------------------------------- subscriptions


def create_subscription(scope: dict[str, str], to: str, *, as_sender: str = "service:aura-society",
                        kinds: list[str] | None = None) -> dict[str, Any]:
    sub_id = f"ssub_{os.urandom(6).hex()}"
    record = {
        "schema": SCHEMA_SUB, "id": sub_id, "scope": scope, "to": to,
        "as": as_sender, "kinds": kinds or sorted(KINDS), "status": "active",
        "created_at": _now(),
    }
    _atomic_write(subscriptions_root() / f"{sub_id}.json", record)
    return record


def list_subscriptions(*, status: str | None = None) -> list[dict[str, Any]]:
    root = subscriptions_root()
    if not root.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("ssub_*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if status and rec.get("status") != status:
            continue
        out.append(rec)
    return out


def set_status(sub_id: str, status: str) -> bool:
    path = subscriptions_root() / f"{sub_id}.json"
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    rec["status"] = status
    _atomic_write(path, rec)
    return True


def _scope_matches(scope: dict[str, str], group: str) -> bool:
    if not isinstance(scope, dict):
        return False
    if scope.get("fleet") and group == f"fleet:{scope['fleet']}":
        return True
    if scope.get("placement") and group == f"placement:{scope['placement']}":
        return True
    return False


# -------------------------------------------------------------- live-in-group fanout


def _live_targets_in_group(group: str) -> list[str]:
    """LIVE seats inside the changed group (implicit-self convention, no rows)."""
    kind, _, name = group.partition(":")
    try:
        from lib import seat_status
        if kind == "fleet":
            rows = seat_status.list_seat_statuses(fleet=name, include_hidden=False)
        elif kind == "placement":
            from lib import placements
            refs = {m.get("target") or m.get("seat_ref")
                    for m in placements.get_placement(name).get("members", [])}
            rows = [r for r in seat_status.list_seat_statuses(include_hidden=False)
                    if (r.get("target") or r.get("seat_ref")) in refs]
        else:
            return []
    except Exception:  # noqa: BLE001 - fanout is best-effort
        return []
    live = []
    for r in rows:
        if r.get("liveness") == "alive" and r.get("managed_state") not in {"stopped", "missing_pane"}:
            t = r.get("target") or r.get("seat_ref")
            if t:
                live.append(t)
    return live


# --------------------------------------------------------------------- the boundary


def schedule_society_subscriptions(group: str, *, kind: str = "join",
                                   member: str | None = None) -> dict[str, Any]:
    """Route a society change: flag implicit live-in-group seats + deliver to any
    explicit watcher subscriptions. Mirror of report-boundary subscription firing.
    Best-effort and non-fatal — a control-plane write must never break on this."""
    reason = f"{kind}:{group}" + (f":{member}" if member else "")
    flagged = set_ambient_pending(_live_targets_in_group(group), reason)

    delivered: list[str] = []
    for sub in list_subscriptions(status="active"):
        if kind not in (sub.get("kinds") or []):
            continue
        if not _scope_matches(sub.get("scope") or {}, group):
            continue
        to = sub.get("to")
        if to:
            set_ambient_pending([to], reason)
            delivered.append(to)
    return {"group": group, "kind": kind, "flagged": flagged, "delivered": delivered}


def emit_society_change(group: str, kind: str, member: str | None = None) -> None:
    """Emit point — call POST-COMMIT from the member-set writes. Swallows errors so a
    registry/placement/fleet write is never broken by society routing."""
    if kind not in KINDS:
        return
    try:
        schedule_society_subscriptions(group, kind=kind, member=member)
    except Exception:  # noqa: BLE001 - never fatal to the originating write
        return

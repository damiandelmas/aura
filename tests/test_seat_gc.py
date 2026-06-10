"""Tests for `aura seat gc` — TTL-based auto-archival of CRUFT registry rows."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(days_ago: int = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return dt.isoformat()


def _make_args(
    *,
    ttl: int = 7,
    fleet: str | None = None,
    dry_run: bool = False,
    confirm: bool = False,
) -> argparse.Namespace:
    return argparse.Namespace(ttl=ttl, fleet=fleet, dry_run=dry_run, confirm=confirm)


def _mirror_with_panes(pane_refs: list[str]) -> dict:
    """Return a fake mirror containing the given pane_refs as live panes."""
    panes = []
    for ref in pane_refs:
        # ref format: tmux:<session>:<pane_id>
        parts = ref.replace("tmux:", "").split(":")
        session = parts[0] if len(parts) >= 2 else "fleet"
        pane_id = parts[1] if len(parts) >= 2 else parts[0]
        panes.append({
            "physical_fleet": session,
            "tmux_session": session,
            "window_id": "@1",
            "window_index": "1",
            "window_name": "worker",
            "pane_id": pane_id,
            "pane_index": "0",
            "pane_pid": "1234",
            "pane_current_path": "/tmp",
            "pane_current_command": "bash",
            "pane_active": True,
            "pane_ref": ref,
            "terminal_ref": f"tmux:{session}:worker",
        })
    return {"ok": True, "schema": "aura.tmux_mirror.v1", "panes": panes}


def _read_ledger(state_root: Path) -> list[dict]:
    ledger_path = state_root / "registry" / "session-ledger.jsonl"
    if not ledger_path.exists():
        return []
    events = []
    for line in ledger_path.read_text().splitlines():
        line = line.strip()
        if line:
            events.append(json.loads(line))
    return events


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def gc_state(monkeypatch, tmp_path):
    """Isolated AURA_STATE_DIR with a clean registry, no live tmux."""
    state_root = tmp_path / ".aura"
    state_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AURA_STATE_DIR", str(state_root))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(state_root / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "test-fleet")
    return state_root


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_gc_archives_old_cruft_row_with_confirm(gc_state, monkeypatch):
    """An unbound row with no session_id, created 30 days ago, pane absent → archived."""
    from lib import registry, tmux_mirror
    from commands.seat import _gc

    # Insert a stale cruft row (no pane_ref → will always be missing_managed)
    registry.upsert_agent({
        "name": "old-cruft",
        "fleet": "test-fleet",
        "runtime": "codex",
        "created_at": _iso(30),
        "runtime_session_binding": "unbound",
    })

    # Mirror: no live panes
    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: _mirror_with_panes([]))

    result = _gc(_make_args(ttl=7, confirm=True))

    assert result["ok"] is True
    assert result["dry_run"] is False
    assert len(result["archived"]) == 1
    assert result["archived"][0]["ref"] == "test-fleet:old-cruft"
    assert len(result["removed"]) == 1

    # Row must be gone from registry
    assert registry.get_agent("old-cruft", fleet="test-fleet") is None

    # seat_auto_archived ledger event must be written
    events = _read_ledger(gc_state)
    auto_archived = [e for e in events if e.get("event") == "seat_auto_archived"]
    assert auto_archived, "expected a seat_auto_archived ledger event"


def test_gc_keeps_resumable_row(gc_state, monkeypatch):
    """A row with runtime_session_binding=bound + session id is KEPT even if old and pane gone."""
    from lib import registry, tmux_mirror
    from commands.seat import _gc

    registry.upsert_agent({
        "name": "resumable",
        "fleet": "test-fleet",
        "runtime": "codex",
        "created_at": _iso(60),
        "runtime_session_binding": "bound",
        "runtime_session_id": "sess-abc-123",
    })

    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: _mirror_with_panes([]))

    result = _gc(_make_args(ttl=7, confirm=True))

    assert result["ok"] is True
    kept_refs = [k["ref"] for k in result["kept"]]
    assert "test-fleet:resumable" in kept_refs
    kept_reasons = {k["ref"]: k["reason"] for k in result["kept"]}
    assert kept_reasons["test-fleet:resumable"] == "resumable"

    # Row must still be in registry
    assert registry.get_agent("resumable", fleet="test-fleet") is not None


def test_gc_archives_bound_row_for_removed_runtime(gc_state, monkeypatch):
    """A row bound to a runtime no longer in RUNTIMES (e.g. legacy omx) is false
    lineage — you cannot resume into a deleted runtime — so it is ARCHIVED as
    cruft despite being bound, not kept as resumable."""
    from lib import registry, tmux_mirror, runtimes
    from commands.seat import _gc

    assert "omx" not in runtimes.RUNTIMES  # precondition: runtime was removed

    registry.upsert_agent({
        "name": "legacy-omx",
        "fleet": "test-fleet",
        "runtime": "omx",
        "created_at": _iso(60),
        "runtime_session_binding": "bound",
        "runtime_session_id": "sess-omx-zombie",
    })

    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: _mirror_with_panes([]))

    result = _gc(_make_args(ttl=7, confirm=True))

    assert result["ok"] is True
    archived_refs = {a["ref"]: a for a in result["archived"]}
    assert "test-fleet:legacy-omx" in archived_refs
    assert archived_refs["test-fleet:legacy-omx"]["reason"] == "removed-runtime"
    assert "test-fleet:legacy-omx" in result["removed"]

    # Row must be gone from the registry
    assert registry.get_agent("legacy-omx", fleet="test-fleet") is None


def test_gc_archives_removed_runtime_row_regardless_of_age(gc_state, monkeypatch):
    """A removed-runtime row is TTL-EXEMPT: it can never resume, so no age grace
    serves it — even a 1-day-old bound omx row is archived on the first gc."""
    from lib import registry, tmux_mirror
    from commands.seat import _gc

    registry.upsert_agent({
        "name": "recent-omx",
        "fleet": "test-fleet",
        "runtime": "omx",
        "created_at": _iso(1),
        "runtime_session_binding": "bound",
        "runtime_session_id": "sess-omx-recent",
    })

    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: _mirror_with_panes([]))

    result = _gc(_make_args(ttl=7, confirm=True))

    assert result["ok"] is True
    archived_refs = {a["ref"]: a for a in result["archived"]}
    assert "test-fleet:recent-omx" in archived_refs
    assert archived_refs["test-fleet:recent-omx"]["reason"] == "removed-runtime"
    assert "test-fleet:recent-omx" in result["removed"]
    assert registry.get_agent("recent-omx", fleet="test-fleet") is None


def test_gc_keeps_fork_in_progress_row(gc_state, monkeypatch):
    """A pending-fork-child row carries fork lineage (source_session_id) and is KEPT even if old."""
    from lib import registry, tmux_mirror
    from commands.seat import _gc

    registry.upsert_agent({
        "name": "forkchild",
        "fleet": "test-fleet",
        "runtime": "codex",
        "created_at": _iso(60),
        "runtime_session_binding": "pending-fork-child",
        "source_session_id": "sess-parent-999",
    })

    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: _mirror_with_panes([]))

    result = _gc(_make_args(ttl=7, confirm=True))

    assert result["ok"] is True
    kept_reasons = {k["ref"]: k["reason"] for k in result["kept"]}
    assert kept_reasons.get("test-fleet:forkchild") == "fork-lineage"
    assert registry.get_agent("forkchild", fleet="test-fleet") is not None


def test_gc_keeps_within_ttl_row(gc_state, monkeypatch):
    """A cruft row created today is KEPT (within TTL)."""
    from lib import registry, tmux_mirror
    from commands.seat import _gc

    registry.upsert_agent({
        "name": "fresh-cruft",
        "fleet": "test-fleet",
        "runtime": "codex",
        "created_at": _iso(0),
        "runtime_session_binding": "unbound",
    })

    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: _mirror_with_panes([]))

    result = _gc(_make_args(ttl=7, confirm=True))

    assert result["ok"] is True
    kept_refs = [k["ref"] for k in result["kept"]]
    assert "test-fleet:fresh-cruft" in kept_refs
    kept_reasons = {k["ref"]: k["reason"] for k in result["kept"]}
    assert kept_reasons["test-fleet:fresh-cruft"] == "within-ttl"

    # Row must still be present
    assert registry.get_agent("fresh-cruft", fleet="test-fleet") is not None


def test_gc_dry_run_does_not_write(gc_state, monkeypatch):
    """--dry-run on a cruft row: row is listed as a candidate but no removal happens."""
    from lib import registry, tmux_mirror
    from commands.seat import _gc

    registry.upsert_agent({
        "name": "will-not-die",
        "fleet": "test-fleet",
        "runtime": "codex",
        "created_at": _iso(30),
        "runtime_session_binding": "unbound",
    })

    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: _mirror_with_panes([]))

    result = _gc(_make_args(ttl=7, dry_run=True, confirm=False))

    assert result["ok"] is True
    assert result["dry_run"] is True
    # Candidate is listed in archived
    assert len(result["archived"]) == 1
    # But nothing was removed
    assert result["removed"] == []
    assert len(result["counts"]["removed"]) == 0 if isinstance(result["counts"]["removed"], list) else result["counts"]["removed"] == 0

    # Row still in registry
    assert registry.get_agent("will-not-die", fleet="test-fleet") is not None

    # No ledger events
    events = _read_ledger(gc_state)
    auto_archived = [e for e in events if e.get("event") == "seat_auto_archived"]
    assert auto_archived == []


def test_gc_no_confirm_defaults_to_dry_run(gc_state, monkeypatch):
    """Omitting --confirm behaves like dry-run: candidate listed but not removed."""
    from lib import registry, tmux_mirror
    from commands.seat import _gc

    registry.upsert_agent({
        "name": "safe-row",
        "fleet": "test-fleet",
        "runtime": "codex",
        "created_at": _iso(30),
        "runtime_session_binding": "unbound",
    })

    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: _mirror_with_panes([]))

    result = _gc(_make_args(ttl=7))  # no confirm, no dry_run

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert len(result["archived"]) == 1
    assert result["removed"] == []
    assert registry.get_agent("safe-row", fleet="test-fleet") is not None


def test_gc_mirror_unavailable_archives_nothing(gc_state, monkeypatch):
    """When tmux mirror is unavailable, return error and archive nothing."""
    from lib import registry, tmux_mirror
    from commands.seat import _gc

    registry.upsert_agent({
        "name": "victim",
        "fleet": "test-fleet",
        "runtime": "codex",
        "created_at": _iso(30),
        "runtime_session_binding": "unbound",
    })

    monkeypatch.setattr(
        tmux_mirror,
        "list_physical_panes",
        lambda **_kw: {"ok": False, "error": "tmux not running", "panes": []},
    )

    result = _gc(_make_args(ttl=7, confirm=True))

    assert result["ok"] is False
    assert result["error"] == "tmux-mirror-unavailable"

    # Row still in registry — nothing was touched
    assert registry.get_agent("victim", fleet="test-fleet") is not None

    # No ledger events
    events = _read_ledger(gc_state)
    assert [e for e in events if e.get("event") == "seat_auto_archived"] == []


def test_gc_live_row_not_a_candidate(gc_state, monkeypatch):
    """A row whose pane is live in the mirror is never even a candidate."""
    from lib import registry, tmux_mirror
    from commands.seat import _gc

    pane_ref = "tmux:test-fleet:%55"
    registry.upsert_agent({
        "name": "live-agent",
        "fleet": "test-fleet",
        "runtime": "codex",
        "created_at": _iso(30),
        "pane_ref": pane_ref,
        "runtime_session_binding": "unbound",
    })

    # Mirror contains that pane → join_managed will NOT put it in missing_managed
    monkeypatch.setattr(
        tmux_mirror,
        "list_physical_panes",
        lambda **_kw: _mirror_with_panes([pane_ref]),
    )

    result = _gc(_make_args(ttl=7, confirm=True))

    assert result["ok"] is True
    assert result["archived"] == []
    assert result["removed"] == []

    # Row still in registry
    assert registry.get_agent("live-agent", fleet="test-fleet") is not None

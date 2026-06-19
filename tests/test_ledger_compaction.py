"""Ledger compaction must bound the file WITHOUT changing what resume sees.

The continuity/resume consumer is ``project_latest_from_ledger``. These tests
prove compaction is projection-equivalent (identical fold over seat_ref, alias
chains, and terminal flags) so a bound, resumable session still resolves after
the 459 MB ledger is folded down — plus the write-path cap, atomicity, and
archival behaviour.
"""

from __future__ import annotations

import gzip
import os
import sys
from pathlib import Path

import pytest  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))

from lib import session_ledger  # noqa: E402


def _seed_realistic_ledger() -> None:
    """A ledger with repeated state rows, a rename, an alias, and a terminal."""
    # Many repeated observation/bind rows per seat (the compactible bulk).
    for i in range(50):
        session_ledger.append_seat_event(
            event="session_observed",
            seat="alpha",
            fleet="f1",
            runtime="claude-code",
            after={
                "seat": "alpha",
                "fleet": "f1",
                "runtime": "claude-code",
                "runtime_session_id": f"sess-alpha-{i}",
                "runtime_session_binding": "bound",
                "cwd": "/work/alpha",
            },
        )
    for i in range(30):
        session_ledger.append_seat_event(
            event="session_observed",
            seat="beta",
            fleet="f1",
            runtime="codex",
            after={
                "seat": "beta",
                "fleet": "f1",
                "runtime": "codex",
                "runtime_session_id": "sess-beta-final" if i == 29 else f"sess-beta-{i}",
                "runtime_session_binding": "bound",
                "cwd": "/work/beta",
            },
        )
    # A rename (lineage event — must survive verbatim to drive the alias map).
    session_ledger.append_seat_event(
        event="seat_renamed",
        seat="gamma2",
        fleet="f1",
        before={"seat": "gamma", "fleet": "f1", "seat_ref": "f1:gamma"},
        after={"seat": "gamma2", "fleet": "f1", "seat_ref": "f1:gamma2",
               "runtime_session_id": "sess-gamma", "runtime_session_binding": "bound"},
    )
    for i in range(20):
        session_ledger.append_seat_event(
            event="session_observed",
            seat="gamma2",
            fleet="f1",
            runtime="claude-code",
            after={"seat": "gamma2", "fleet": "f1",
                   "runtime_session_id": "sess-gamma", "runtime_session_binding": "bound"},
        )
    # A terminal event (must survive to suppress restore).
    for i in range(10):
        session_ledger.append_seat_event(
            event="session_observed", seat="delta", fleet="f1", runtime="codex",
            after={"seat": "delta", "fleet": "f1", "runtime_session_id": "sess-delta"},
        )
    session_ledger.append_seat_event(
        event="seat_cut", seat="delta", fleet="f1",
        after={"seat": "delta", "fleet": "f1"},
    )
    # Compatibility v1 rows + a fleet event.
    for i in range(15):
        session_ledger.append_record({
            "event": "session_bound_current", "seat": "epsilon", "fleet": "f2",
            "runtime": "claude-code", "runtime_session_id": f"sess-eps-{i}",
            "runtime_session_binding": "bound",
        })
    session_ledger.append_fleet_event(event="fleet_renamed", fleet="f2",
                                      before={"current_name": "f2old"}, after={"current_name": "f2"})


def test_compaction_is_projection_equivalent(monkeypatch):
    # KEEP_TAIL=0 forces the pure latest-per-key fold (no tail safety net),
    # so equivalence proves the fold itself, not just tail retention.
    monkeypatch.setenv("AURA_LEDGER_KEEP_TAIL", "0")
    _seed_realistic_ledger()

    before = session_ledger.project_latest_from_ledger()
    lines_before = sum(1 for _ in session_ledger.ledger_path().open())

    result = session_ledger.compact_ledger(force=True)
    assert result["compacted"] is True
    assert result["lines_after"] < lines_before

    after = session_ledger.project_latest_from_ledger()
    assert after == before, "compaction changed the resume projection"


def test_restore_plan_identical_after_compaction(monkeypatch):
    monkeypatch.setenv("AURA_LEDGER_KEEP_TAIL", "0")
    _seed_realistic_ledger()
    caps = {"claude-code": {"supports_resume": True}, "codex": {"supports_resume": True}}

    rows_before = session_ledger.project_latest_from_ledger()
    plan_before = session_ledger.restore_plan_from_rows(rows_before, caps)

    session_ledger.compact_ledger(force=True)

    rows_after = session_ledger.project_latest_from_ledger()
    plan_after = session_ledger.restore_plan_from_rows(rows_after, caps)
    assert plan_after["rows"] == plan_before["rows"]
    assert plan_after["restore_ready"] == plan_before["restore_ready"]


def test_write_path_cap_triggers_compaction(monkeypatch):
    monkeypatch.setenv("AURA_LEDGER_MAX_BYTES", "20000")  # ~20 KB cap
    monkeypatch.setenv("AURA_LEDGER_KEEP_TAIL", "10")
    for i in range(400):
        session_ledger.append_seat_event(
            event="session_observed", seat="alpha", fleet="f1", runtime="codex",
            after={"seat": "alpha", "fleet": "f1", "runtime_session_id": f"s{i}",
                   "runtime_session_binding": "bound"},
        )
    size = session_ledger.ledger_path().stat().st_size
    # Without the cap this would be far larger; the cap holds it bounded.
    assert size <= 20000 * 3, f"cap did not bound the ledger: {size} bytes"
    # The latest row is still resolvable (resume intact).
    rows = session_ledger.project_latest_from_ledger()
    alpha = [r for r in rows if r.get("seat") == "alpha"]
    assert alpha and alpha[0]["runtime_session_id"] == "s399"


def test_compaction_archives_original(monkeypatch):
    monkeypatch.setenv("AURA_LEDGER_KEEP_TAIL", "0")
    _seed_realistic_ledger()
    lines_before = sum(1 for _ in session_ledger.ledger_path().open())

    result = session_ledger.compact_ledger(force=True)
    archive = result["archive"]
    assert archive and os.path.exists(archive)
    # The archive holds the full original, recoverable line-for-line.
    with gzip.open(archive, "rt", encoding="utf-8") as f:
        archived = sum(1 for line in f if line.strip())
    assert archived == lines_before


def test_compaction_noop_under_cap(monkeypatch):
    session_ledger.append_seat_event(
        event="session_observed", seat="alpha", fleet="f1", runtime="codex",
        after={"seat": "alpha", "fleet": "f1"},
    )
    result = session_ledger.compact_ledger()  # no force, tiny file
    assert result["compacted"] is False
    assert result["reason"] == "under-cap"


def test_compaction_missing_ledger_safe():
    result = session_ledger.compact_ledger()
    assert result["compacted"] is False
    assert result["reason"] == "no-ledger"

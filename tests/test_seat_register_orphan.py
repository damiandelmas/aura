"""Tests for `aura seat register-orphan` (plan 011 phase 0)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


@pytest.fixture
def aura_state(monkeypatch, tmp_path):
    state_root = tmp_path / ".aura"
    state_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AURA_STATE_DIR", str(state_root))
    monkeypatch.setenv("AURA_FLEET", "test-fleet")
    return state_root


def _make_pane(session, window_name, pane_id="%42", pid=12345,
               command="node", cwd="/tmp/work"):
    return {
        "session": session,
        "window_index": "0",
        "window_name": window_name,
        "pane_id": pane_id,
        "pane_pid": pid,
        "pane_current_command": command,
        "pane_current_path": cwd,
    }


def test_register_orphan_inserts_record_for_existing_pane(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    panes = [_make_pane("flex-leaders-2", "engineer", pane_id="%48", pid=1848341,
                        command="node", cwd="/home/axp/projects/flexsearch")]
    monkeypatch.setattr(seat_cmd, "_list_tmux_panes", lambda: panes)

    args = argparse.Namespace(
        seat_action="register-orphan",
        target="flex-leaders-2:engineer",
        pane=None,
        runtime="codex",
        cwd=None,
    )
    result = seat_cmd._register_orphan(args, registry)

    assert result["ok"] is True
    assert result["target"] == "flex-leaders-2:engineer"
    record = result["record"]
    assert record["seat"] == "engineer"
    assert record["fleet"] == "flex-leaders-2"
    assert record["runtime"] == "codex"
    assert record["pane_ref"] == "tmux:flex-leaders-2:%48"
    assert record["registered_via"] == "register-orphan"
    assert record["registered_pane_pid"] == 1848341
    assert record["runtime_session_binding"] == "unbound"
    assert record["aura_launch_id"] is None
    assert record["cwd"] == "/home/axp/projects/flexsearch"

    # Provenance reflects the discovery path.
    assert result["provenance"]["discovered_by"] == "scan"
    assert result["provenance"]["runtime_inferred"] is False


def test_register_orphan_rejects_target_with_existing_registry_row(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    panes = [_make_pane("flex-leaders-2", "engineer", pane_id="%48")]
    monkeypatch.setattr(seat_cmd, "_list_tmux_panes", lambda: panes)

    args = argparse.Namespace(
        seat_action="register-orphan",
        target="flex-leaders-2:engineer",
        pane=None,
        runtime="codex",
        cwd=None,
    )
    first = seat_cmd._register_orphan(args, registry)
    assert first["ok"] is True

    second = seat_cmd._register_orphan(args, registry)
    assert second["ok"] is False
    assert second["error"] == "already-registered"
    assert second["record"]["seat"] == "engineer"


def test_register_orphan_rejects_when_no_pane_found(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    monkeypatch.setattr(seat_cmd, "_list_tmux_panes", lambda: [])

    args = argparse.Namespace(
        seat_action="register-orphan",
        target="flex-leaders-2:engineer",
        pane=None,
        runtime=None,
        cwd=None,
    )
    result = seat_cmd._register_orphan(args, registry)

    assert result["ok"] is False
    assert result["error"] == "no-pane"
    assert result["target"] == "flex-leaders-2:engineer"


def test_register_orphan_rejects_ambiguous_panes_without_explicit_ref(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    panes = [
        _make_pane("flex-leaders-2", "engineer", pane_id="%48"),
        _make_pane("flex-leaders-2", "engineer", pane_id="%52"),
    ]
    monkeypatch.setattr(seat_cmd, "_list_tmux_panes", lambda: panes)

    args = argparse.Namespace(
        seat_action="register-orphan",
        target="flex-leaders-2:engineer",
        pane=None,
        runtime="codex",
        cwd=None,
    )
    result = seat_cmd._register_orphan(args, registry)

    assert result["ok"] is False
    assert result["error"] == "ambiguous-pane"
    assert len(result["candidates"]) == 2
    # candidates contain pane_ref strings the operator can reuse with --pane.
    assert "tmux:flex-leaders-2:%48" in {c["pane_ref"] for c in result["candidates"]}


def test_register_orphan_infers_codex_from_node_argv(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    panes = [_make_pane("flex-leaders-2", "engineer", pane_id="%48",
                        command="node")]
    monkeypatch.setattr(seat_cmd, "_list_tmux_panes", lambda: panes)

    args = argparse.Namespace(
        seat_action="register-orphan",
        target="flex-leaders-2:engineer",
        pane=None,
        runtime=None,
        cwd=None,
    )
    result = seat_cmd._register_orphan(args, registry)

    assert result["ok"] is True
    # bare `node` with no other signal defaults to codex per inference table.
    assert result["record"]["runtime"] == "codex"
    assert result["provenance"]["runtime_inferred"] is True


def test_register_orphan_writes_session_ledger_event(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry, session_ledger

    panes = [_make_pane("flex-leaders-2", "engineer", pane_id="%48",
                        command="node", cwd="/home/axp/projects/flexsearch")]
    monkeypatch.setattr(seat_cmd, "_list_tmux_panes", lambda: panes)

    args = argparse.Namespace(
        seat_action="register-orphan",
        target="flex-leaders-2:engineer",
        pane=None,
        runtime="codex",
        cwd=None,
    )
    result = seat_cmd._register_orphan(args, registry)
    assert result["ok"] is True

    rows = session_ledger.iter_records()
    matching = [r for r in rows if r.get("event") == "seat_registered_orphan"]
    assert matching, "expected a seat_registered_orphan ledger event"
    row = matching[-1]
    assert row["seat_ref"] == "flex-leaders-2:engineer"
    assert row["evidence"]["pane_ref"] == "tmux:flex-leaders-2:%48"
    assert row["evidence"]["runtime"] == "codex"
    # before is null because no prior row existed; ledger snapshot omits None.
    assert row.get("before") in (None, {}, "")


def test_register_orphan_does_not_paste_or_bind_session(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    panes = [_make_pane("flex-leaders-2", "engineer", pane_id="%48")]
    monkeypatch.setattr(seat_cmd, "_list_tmux_panes", lambda: panes)

    sentinel = {"send_text_called": False}

    class BannedTerminal:
        @staticmethod
        def send_text(*a, **kw):
            sentinel["send_text_called"] = True
            return {"ok": True}

    args = argparse.Namespace(
        seat_action="register-orphan",
        target="flex-leaders-2:engineer",
        pane=None,
        runtime="codex",
        cwd=None,
    )
    result = seat_cmd._register_orphan(args, registry, terminal=BannedTerminal)

    assert result["ok"] is True
    assert sentinel["send_text_called"] is False
    assert result["record"]["runtime_session_id"] is None
    assert result["record"]["runtime_session_binding"] == "unbound"


def test_register_orphan_rejects_empty_or_malformed_target(aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    for bad in ("", ":", "no-colon", "flex:", ":seat"):
        args = argparse.Namespace(
            seat_action="register-orphan",
            target=bad,
            pane=None,
            runtime=None,
            cwd=None,
        )
        result = seat_cmd._register_orphan(args, registry)
        assert result["ok"] is False, f"target {bad!r} should fail"
        assert result["error"] == "empty-target"

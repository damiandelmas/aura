from __future__ import annotations

import argparse
import json
import subprocess
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
    monkeypatch.setenv("AURA_FLEET", "runway-engineering")
    return state_root


def _pane(session="runway-engineering", window_name="bash", pane_id="%191", pid=12345, command="codex", cwd="/tmp/work"):
    return {
        "session": session,
        "window_index": "2",
        "window_name": window_name,
        "pane_index": "0",
        "pane_id": pane_id,
        "pane_pid": pid,
        "pane_current_command": command,
        "pane_current_path": cwd,
    }


def test_holding_discover_lists_duplicate_window_names_by_pane_id(monkeypatch, aura_state):
    from commands import holding as holding_cmd
    from commands import seat as seat_cmd
    from lib import holding

    panes = [
        _pane(pane_id="%191", pid=111),
        _pane(pane_id="%192", pid=222),
    ]
    monkeypatch.setattr(seat_cmd, "_list_tmux_panes", lambda: panes)

    args = argparse.Namespace(
        holding_action="discover",
        tmux=True,
        fleet="runway-engineering",
        all_fleets=False,
        all=False,
        create=True,
    )
    result = holding_cmd.run(args)

    assert result["ok"] is True
    assert result["unmanaged_count"] == 2
    assert {row["pane_ref"] for row in result["unmanaged"]} == {
        "tmux:runway-engineering:%191",
        "tmux:runway-engineering:%192",
    }
    assert result["created_count"] == 2
    records = holding.list_records(fleet="runway-engineering")
    assert len(records) == 2
    assert {row["pane_ref"] for row in records} == {
        "tmux:runway-engineering:%191",
        "tmux:runway-engineering:%192",
    }


def test_holding_discover_does_not_hide_duplicate_window_name_by_managed_target(monkeypatch, aura_state):
    from commands import holding as holding_cmd
    from commands import seat as seat_cmd
    from lib import registry

    registry.upsert_agent({
        "name": "lead",
        "seat": "lead",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "pane_ref": "tmux:runway-engineering:%200",
        "terminal_ref": "runway-engineering:lead",
        "backend_ref": "runway-engineering:lead",
        "registered": True,
    })
    panes = [
        _pane(window_name="lead", pane_id="%200", pid=200),
        _pane(window_name="lead", pane_id="%201", pid=201),
    ]
    monkeypatch.setattr(seat_cmd, "_list_tmux_panes", lambda: panes)

    args = argparse.Namespace(
        holding_action="discover",
        tmux=True,
        fleet="runway-engineering",
        all_fleets=False,
        all=True,
        create=False,
    )
    result = holding_cmd.run(args)

    assert result["ok"] is True
    assert {row["pane_ref"] for row in result["managed"]} == {"tmux:runway-engineering:%200"}
    assert {row["pane_ref"] for row in result["unmanaged"]} == {"tmux:runway-engineering:%201"}


def test_holding_list_explicit_resolved_status_includes_resolved_records(aura_state):
    from lib import holding

    record = holding.create_from_candidate({
        "source": "tmux",
        "pane_ref": "tmux:runway-engineering:%191",
        "tmux_session": "runway-engineering",
        "window_name": "bash",
        "pane_id": "%191",
    })
    holding.resolve(record["holding_id"], state="adopted", target="runway-engineering:research-2")

    assert holding.list_records(state_filter="holding") == []
    adopted = holding.list_records(state_filter="adopted")
    assert len(adopted) == 1
    assert adopted[0]["holding_id"] == record["holding_id"]


def test_seat_adopt_accepts_documented_tmux_pane_ref_and_records_unbound(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry, session_ledger

    calls = []

    def fake_run_tmux(args):
        calls.append(args)
        if args[:4] == ["display-message", "-p", "-t", "%191"]:
            fmt = args[-1]
            if "pane_current_path" in fmt:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout="runway-engineering\t2\tbash\t0\t%191\t12345\tcodex\t/tmp/work\n",
                    stderr="",
                )
        if args[:4] == ["display-message", "-p", "-t", "runway-engineering:research-2"]:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="can't find window")
        if args[:2] == ["rename-window", "-t"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected")

    monkeypatch.setattr(seat_cmd, "_run_tmux", fake_run_tmux)

    args = argparse.Namespace(
        seat_action="adopt",
        pane="tmux:runway-engineering:%191",
        target="runway-engineering:research-2",
        rename_window=True,
        runtime="codex",
        cwd="auto",
        identity_provider=None,
        identity_id=None,
        identity_label=None,
    )
    result = seat_cmd.run(args)

    assert result["ok"] is True
    assert result["action"] == "adopt"
    assert result["target"] == "runway-engineering:research-2"
    assert result["pane_ref"] == "tmux:runway-engineering:%191"
    assert result["managed_state"] == "adopted_unbound"
    assert result["runtime_session_binding"] == "unbound"
    assert result["runtime_session_id"] is None
    assert result["next_command"] == "aura sessions bind-current --target runway-engineering:research-2 --runtime codex"

    record = registry.get_agent("runway-engineering:research-2")
    assert record["registered_via"] == "adopt"
    assert record["seat_instance_id"].startswith("si_")
    assert record["terminal_ref"] == "runway-engineering:research-2"
    assert record["runtime_session_binding"] == "unbound"
    assert record.get("runtime_session_id") is None

    events = [row for row in session_ledger.iter_records() if row.get("event") == "seat_adopted"]
    assert events
    assert events[-1]["seat_ref"] == "runway-engineering:research-2"
    assert events[-1]["evidence"]["pane_ref"] == "tmux:runway-engineering:%191"
    assert any(call[:2] == ["rename-window", "-t"] for call in calls)


def test_seat_adopt_preserves_exact_runtime_binding(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    def fake_run_tmux(args):
        if args[:4] == ["display-message", "-p", "-t", "%191"]:
            fmt = args[-1]
            if "pane_current_path" in fmt:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    stdout="runway-engineering\t2\tbash\t0\t%191\t12345\tcodex\t/tmp/work\n",
                    stderr="",
                )
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected")

    monkeypatch.setattr(seat_cmd, "_run_tmux", fake_run_tmux)
    monkeypatch.setattr(
        seat_cmd,
        "_runtime_session_fields",
        lambda runtime, pane, seat: {
            "runtime_session_id": "019dd797-1169-7931-b2f7-17824b3b7134",
            "session_id": "019dd797-1169-7931-b2f7-17824b3b7134",
            "runtime_session_binding": "bound",
            "runtime_session_bind_method": "argv-resume",
            "runtime_session_source": "argv:codex-resume",
            "runtime_session_confidence": "exact",
        },
    )

    args = argparse.Namespace(
        seat_action="adopt",
        pane="tmux:runway-engineering:%191",
        target="runway-engineering:research-bound",
        rename_window=False,
        runtime="codex",
        cwd="auto",
        identity_provider=None,
        identity_id=None,
        identity_label=None,
    )
    result = seat_cmd.run(args)

    assert result["ok"] is True
    assert result["managed_state"] == "adopted_bound"
    assert result["runtime_session_binding"] == "bound"
    assert result["runtime_session_id"] == "019dd797-1169-7931-b2f7-17824b3b7134"
    record = registry.get_agent("runway-engineering:research-bound")
    assert record["managed_state"] == "adopted_bound"
    assert record["runtime_session_binding"] == "bound"
    assert record["runtime_session_id"] == "019dd797-1169-7931-b2f7-17824b3b7134"


def test_holding_adopt_resolves_holding_record(monkeypatch, aura_state):
    from commands import holding as holding_cmd
    from commands import seat as seat_cmd
    from lib import holding, registry

    candidate = {
        "source": "tmux",
        "pane_ref": "tmux:runway-engineering:%191",
        "tmux_session": "runway-engineering",
        "window_index": "2",
        "pane_index": "0",
        "window_name": "bash",
        "pane_id": "%191",
        "pane_pid": 12345,
        "active_command": "codex",
        "cwd": "/tmp/work",
        "runtime_hint": "codex",
    }
    hold = holding.create_from_candidate(candidate)

    def fake_run_tmux(args):
        if args[:4] == ["display-message", "-p", "-t", "%191"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout="runway-engineering\t2\tbash\t0\t%191\t12345\tcodex\t/tmp/work\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected")

    monkeypatch.setattr(seat_cmd, "_run_tmux", fake_run_tmux)

    args = argparse.Namespace(
        holding_action="adopt",
        holding_id=hold["holding_id"],
        target="runway-engineering:research-3",
        rename_window=False,
        runtime=None,
        cwd="auto",
    )
    result = holding_cmd.run(args)

    assert result["ok"] is True
    assert result["target"] == "runway-engineering:research-3"
    assert result["holding"]["state"] == "adopted"
    assert result["holding"]["resolution"]["target"] == "runway-engineering:research-3"
    record = registry.get_agent("runway-engineering:research-3")
    assert record["pane_ref"] == "tmux:runway-engineering:%191"
    assert record["terminal_ref"] == "tmux:runway-engineering:%191"


def test_register_orphan_explicit_pane_uses_shared_adoption_core(monkeypatch, aura_state):
    from commands import seat as seat_cmd
    from lib import registry

    def fake_run_tmux(args):
        if args[:4] == ["display-message", "-p", "-t", "%191"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout="runway-engineering\t2\tengineer\t0\t%191\t12345\tcodex\t/tmp/work\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected")

    monkeypatch.setattr(seat_cmd, "_run_tmux", fake_run_tmux)

    args = argparse.Namespace(
        seat_action="register-orphan",
        target="runway-engineering:engineer",
        pane="tmux:runway-engineering:%191",
        runtime="codex",
        cwd=None,
    )
    result = seat_cmd._register_orphan(args, registry)

    assert result["ok"] is True
    assert result["action"] == "register-orphan"
    assert result["record"]["registered_via"] == "register-orphan"
    assert result["record"]["pane_ref"] == "tmux:runway-engineering:%191"

import argparse
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_parse_tmux_panes_reports_physical_truth():
    from lib import tmux_mirror

    output = "fleet-a\t@1\t1\tworker\t%12\t0\t1234\t/tmp/project\tcodex\t1\n"
    rows = tmux_mirror.parse_panes(output)

    assert rows == [{
        "physical_fleet": "fleet-a",
        "tmux_session": "fleet-a",
        "window_id": "@1",
        "window_index": "1",
        "window_name": "worker",
        "pane_id": "%12",
        "pane_index": "0",
        "pane_pid": "1234",
        "pane_current_path": "/tmp/project",
        "pane_current_command": "codex",
        "pane_active": True,
        "pane_ref": "tmux:fleet-a:%12",
        "terminal_ref": "tmux:fleet-a:worker",
    }]


def test_join_managed_marks_managed_unmanaged_and_missing():
    from lib import tmux_mirror

    panes = tmux_mirror.parse_panes(
        "fleet-a\t@1\t1\tworker\t%12\t0\t1234\t/tmp/project\tcodex\t1\n"
        "fleet-b\t@2\t1\tloose\t%13\t0\t1235\t/tmp\tbash\t0\n"
    )
    records = [
        {"fleet": "logical", "name": "worker", "runtime": "codex", "pane_ref": "tmux:fleet-a:%12", "seat_instance_id": "si_1"},
        {"fleet": "logical", "name": "stale", "runtime": "codex", "pane_ref": "tmux:fleet-a:%99", "seat_instance_id": "si_2"},
    ]

    result = tmux_mirror.join_managed(panes, records)

    assert result["counts"] == {
        "physical_panes": 2,
        "managed_records": 2,
        "unmanaged_panes": 1,
        "missing_managed_panes": 1,
    }
    managed = next(row for row in result["panes"] if row["pane_id"] == "%12")
    assert managed["managed_state"] == "managed"
    assert managed["managed"][0]["logical_ref"] == "logical:worker"
    unmanaged = next(row for row in result["panes"] if row["pane_id"] == "%13")
    assert unmanaged["managed_state"] == "unmanaged"
    assert result["missing_managed"][0]["logical_ref"] == "logical:stale"


def test_join_managed_requires_session_for_session_qualified_pane_ref():
    from lib import tmux_mirror

    panes = tmux_mirror.parse_panes(
        "live-fleet\t@1\t1\tworker\t%12\t0\t1234\t/tmp/project\tcodex\t1\n"
    )
    records = [
        {"fleet": "old-fleet", "name": "stale", "runtime": "codex", "pane_ref": "tmux:old-fleet:%12", "seat_instance_id": "si_old"},
        {"fleet": "live-fleet", "name": "worker", "runtime": "codex", "pane_ref": "tmux:live-fleet:%12", "seat_instance_id": "si_live"},
    ]

    result = tmux_mirror.join_managed(panes, records)

    managed = result["panes"][0]["managed"]
    assert [row["logical_ref"] for row in managed] == ["live-fleet:worker"]
    assert result["missing_managed"][0]["logical_ref"] == "old-fleet:stale"


def test_join_managed_reports_topology_hygiene_audits():
    from lib import tmux_mirror

    panes = tmux_mirror.parse_panes(
        "physical\t@1\t1\tworker\t%12\t0\t1234\t/tmp/project\tcodex\t1\n"
    )
    records = [
        {
            "fleet": "logical",
            "name": "worker",
            "runtime": "codex",
            "pane_ref": "tmux:physical:%12",
            "runtime_session_id": "same-session",
            "seat_instance_id": "si_1",
            "status": "idle",
        },
        {
            "fleet": "logical",
            "name": "duplicate",
            "runtime": "codex",
            "pane_ref": "tmux:physical:%12",
            "runtime_session_id": "same-session",
            "seat_instance_id": "si_2",
            "status": "idle",
        },
        {
            "fleet": "logical",
            "name": "stale",
            "runtime": "codex",
            "pane_ref": "tmux:physical:%99",
            "runtime_session_id": "stale-session",
            "seat_instance_id": "si_3",
            "status": "idle",
        },
    ]

    audits = tmux_mirror.join_managed(panes, records)["audits"]

    assert audits["counts"] == {
        "duplicate_runtime_sessions": 1,
        "duplicate_pane_refs": 1,
        "logical_physical_drift": 3,
        "stale_rows": 1,
    }
    assert audits["duplicate_runtime_sessions"][0]["key"] == "same-session"
    assert audits["duplicate_pane_refs"][0]["key"] == "tmux:physical:%12"
    assert audits["stale_rows"][0]["logical_ref"] == "logical:stale"


def test_view_physical_uses_fake_tmux_and_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry
    from commands import view

    registry.upsert_agent({
        "fleet": "logical-fleet",
        "name": "managed-seat",
        "runtime": "codex",
        "pane_ref": "tmux:physical-fleet:%42",
        "seat_instance_id": "si_managed",
    })

    def fake_runner(cmd, capture_output=True, text=True):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="physical-fleet\t@1\t1\tmanaged-seat\t%42\t0\t4321\t/tmp\tcodex\t1\n",
            stderr="",
        )

    monkeypatch.setattr(view.tmux_mirror, "list_physical_panes", lambda runner=None: {
        "ok": True,
        "schema": "aura.tmux_mirror.v1",
        "counts": {"sessions": 1, "panes": 1},
        "sessions": ["physical-fleet"],
        "panes": __import__("lib.tmux_mirror", fromlist=["parse_panes"]).parse_panes(fake_runner([]).stdout),
    })

    result = view.run(argparse.Namespace(view_action="physical", view_target=None, scope=None, limit=10, include_hidden=False))

    assert result["schema"] == "aura.tmux_mirror.joined.v1"
    assert result["counts"]["physical_panes"] == 1
    assert result["panes"][0]["managed"][0]["logical_ref"] == "logical-fleet:managed-seat"

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_posture_delta_first_snapshot_is_unknown():
    from lib import terminal_posture

    result = terminal_posture.classify_delta(previous_hash=None, output_hash="a")

    assert result == {
        "state": "unknown",
        "confidence": 0.5,
        "explanation": "No previous terminal snapshot exists.",
    }


def test_posture_delta_changed_snapshot_is_working():
    from lib import terminal_posture

    result = terminal_posture.classify_delta(previous_hash="a", output_hash="b")

    assert result["state"] == "working"
    assert result["confidence"] == 0.9


def test_posture_delta_unchanged_snapshot_is_idle():
    from lib import terminal_posture

    result = terminal_posture.classify_delta(previous_hash="a", output_hash="a")

    assert result["state"] == "idle"
    assert result["confidence"] == 0.85


def test_posture_sample_writes_unknown_on_first_snapshot(monkeypatch, tmp_path):
    from commands import posture

    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    monkeypatch.setattr(posture.check, "run", lambda args: {
        "ok": True,
        "name": "engineer",
        "fleet": "unit-fleet",
        "runtime": "codex",
        "status": "alive",
        "terminal": "alive",
        "output": ["first snapshot"],
    })

    result = posture.run(argparse.Namespace(name="unit-fleet:engineer", fleet=None, lines=40))

    assert result["ok"] is True
    assert result["state"] == "unknown"
    assert result["source"]["previous_output_hash"] is None
    assert result["source"]["provider"] == "snapshot_delta"

    seat_latest = tmp_path / ".aura" / "seats" / "unit-fleet:engineer" / "posture" / "latest.json"
    assert json.loads(seat_latest.read_text(encoding="utf-8"))["state"] == "unknown"
    global_latest = tmp_path / ".aura" / "terminal-posture" / "latest.json"
    global_record = json.loads(global_latest.read_text(encoding="utf-8"))
    assert global_record["targets"]["unit-fleet:engineer"]["state"] == "unknown"


def test_posture_sample_changed_output_is_working(monkeypatch, tmp_path):
    from commands import posture

    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    outputs = [["snapshot one"], ["snapshot two"]]

    def fake_check(args):
        return {
            "ok": True,
            "name": "engineer",
            "fleet": "unit-fleet",
            "runtime": "codex",
            "status": "alive",
            "terminal": "alive",
            "output": outputs.pop(0),
        }

    monkeypatch.setattr(posture.check, "run", fake_check)
    args = argparse.Namespace(name="unit-fleet:engineer", fleet=None, lines=20)

    first = posture.run(args)
    second = posture.run(args)

    assert first["state"] == "unknown"
    assert second["state"] == "working"
    assert second["source"]["output_changed"] is True


def test_posture_sample_unchanged_output_is_idle(monkeypatch, tmp_path):
    from commands import posture

    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    monkeypatch.setattr(posture.check, "run", lambda args: {
        "ok": True,
        "name": "engineer",
        "fleet": "unit-fleet",
        "runtime": "codex",
        "status": "alive",
        "terminal": "alive",
        "output": ["same snapshot"],
    })
    args = argparse.Namespace(name="unit-fleet:engineer", fleet=None, lines=20)

    first = posture.run(args)
    second = posture.run(args)

    assert first["state"] == "unknown"
    assert second["state"] == "idle"
    assert second["source"]["output_changed"] is False
    assert second["reused"] is False

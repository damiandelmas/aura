import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_inspect_default_uses_check_status_without_output(monkeypatch):
    from commands import inspect

    seen = {}

    def fake_check(args):
        seen["args"] = args
        return {"ok": True, "name": "worker", "status": "idle", "output": ["ready"]}

    monkeypatch.setattr(inspect.check, "run", fake_check)
    result = inspect.run(argparse.Namespace(
        name="worker",
        raw=False,
        sense=False,
        lines=12,
        format="text",
    ))

    assert seen["args"].name == "worker"
    assert seen["args"].output is False
    assert seen["args"].lines == 12
    assert result["ok"] is True
    assert result["inspect"] is True
    assert result["inspect_mode"] == "status"
    assert result["seat"] == "worker"


def test_inspect_bounds_output_to_requested_lines(monkeypatch):
    from commands import inspect

    monkeypatch.setattr(inspect.check, "run", lambda args: {
        "ok": True,
        "name": "worker",
        "status": "idle",
        "output": ["one", "two", "three"],
    })

    result = inspect.run(argparse.Namespace(
        name="worker",
        raw=False,
        sense=False,
        lines=2,
        format="text",
    ))

    assert result["output"] == ["two", "three"]


def test_inspect_raw_labels_raw_mode(monkeypatch):
    from commands import inspect

    seen = {}

    def fake_check(args):
        seen["args"] = args
        return {
            "ok": True,
            "name": "worker",
            "status": "idle",
            "output": ["raw"],
        }

    monkeypatch.setattr(inspect.check, "run", fake_check)

    result = inspect.run(argparse.Namespace(
        name="worker",
        raw=True,
        sense=False,
        lines=20,
        format="ansi",
    ))

    assert seen["args"].output is True
    assert result["inspect_mode"] == "raw"
    assert result["output"] == ["raw"]


def test_inspect_sense_uses_sense_command(monkeypatch):
    from commands import inspect

    seen = {}

    def fake_sense(args):
        seen["args"] = args
        return {"ok": True, "schema": "aura.sense.v1", "name": "worker", "state": "busy"}

    monkeypatch.setattr(inspect.sense, "run", fake_sense)
    result = inspect.run(argparse.Namespace(
        name="worker",
        raw=False,
        sense=True,
        lines=80,
        question="blocked?",
        features="state,next_action",
        contract="blocked",
        sense_mode="heuristic",
        model=None,
        ollama_host=None,
        llm_timeout=1.0,
    ))

    assert seen["args"].name == "worker"
    assert seen["args"].question == "blocked?"
    assert seen["args"].contract == "blocked"
    assert result["inspect"] is True
    assert result["inspect_mode"] == "sense"
    assert result["state"] == "busy"

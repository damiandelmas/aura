"""H2 — claude_keeper_hook: message-count cadence, PreCompact, dedup, loop guard."""

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


@pytest.fixture
def hook(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("AURA_FLEET", "F")
    monkeypatch.setenv("AURA_SEAT", "a")
    from hooks import claude_keeper_hook as mod
    return mod


def _transcript(tmp_path, n):
    path = tmp_path / "t.jsonl"
    path.write_text("".join(json.dumps({"role": "user" if i % 2 else "assistant"}) + "\n"
                            for i in range(n)), encoding="utf-8")
    return str(path)


def _drive(mod, monkeypatch, event, spy):
    monkeypatch.setattr(mod, "load_event", lambda: event)
    monkeypatch.setattr(mod, "detach_keeper", lambda target, boundary: spy.append((target, boundary)))
    return mod.main()


def test_due_boundary_math(hook):
    assert hook.due_boundary(10) is None
    assert hook.due_boundary(15) == "m15"
    assert hook.due_boundary(29) == "m15"
    assert hook.due_boundary(30) == "m30"
    assert hook.due_boundary(45) == "m45"


def test_stop_below_cadence_no_detach(hook, monkeypatch, tmp_path):
    spy = []
    _drive(hook, monkeypatch,
           {"hook_event_name": "Stop", "session_id": "s1",
            "transcript_path": _transcript(tmp_path, 10)}, spy)
    assert spy == []


def test_stop_at_cadence_detaches(hook, monkeypatch, tmp_path):
    spy = []
    _drive(hook, monkeypatch,
           {"hook_event_name": "Stop", "session_id": "s1",
            "transcript_path": _transcript(tmp_path, 15)}, spy)
    assert spy == [("F:a", "m15")]


def test_stop_hook_active_is_noop(hook, monkeypatch, tmp_path):
    spy = []
    _drive(hook, monkeypatch,
           {"hook_event_name": "Stop", "session_id": "s1", "stop_hook_active": True,
            "transcript_path": _transcript(tmp_path, 30)}, spy)
    assert spy == []


def test_precompact_detaches(hook, monkeypatch):
    spy = []
    _drive(hook, monkeypatch, {"hook_event_name": "PreCompact", "session_id": "s1"}, spy)
    assert spy == [("F:a", "precompact")]


def test_fired_boundary_deduped(hook, monkeypatch, tmp_path):
    spy = []
    ev = {"hook_event_name": "Stop", "session_id": "s1",
          "transcript_path": _transcript(tmp_path, 15)}
    _drive(hook, monkeypatch, ev, spy)   # fires m15
    _drive(hook, monkeypatch, ev, spy)   # same boundary, same session → skip
    assert spy == [("F:a", "m15")]

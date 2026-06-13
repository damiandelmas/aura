"""Tests for `aura event` ensure-alive respawn and no_agent script mode.

Covers the build-spec acceptance checks: a dead ensure-alive target respawns
(not window-not-found), a busy target still skips, an alive target sends; a
no_agent script delivers nothing on empty stdout, writes a report on non-empty
stdout, fails (with backoff) on non-zero exit; the report it writes matches an
existing report subscription (the pub/sub path); and script resolution is
traversal-guarded.
"""

import argparse
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))

from commands import event  # noqa: E402
from lib import events, reports, report_subscriptions  # noqa: E402


@pytest.fixture
def aura_state(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AURA_EVENT_SCRIPTS_DIR", str(tmp_path / "event-scripts"))
    return tmp_path


def _start_args(**over):
    base = dict(
        name="t", target="flex:scout", sender=None, every=120.0, ticks=None,
        template=None, run_id=None, start_delay=0, no_daemon=True,
        no_agent=False, script=None, report_state=None,
        respawn_runtime=None, respawn_cwd=None, respawn_prompt=None,
    )
    base.update(over)
    return argparse.Namespace(**base)


def _write_script(state_dir: Path, name: str, body: str) -> str:
    root = state_dir / "event-scripts"
    root.mkdir(parents=True, exist_ok=True)
    p = root / name
    p.write_text(body, encoding="utf-8")
    return name


# --------------------------------------------------------------------------
# _make_job validation
# --------------------------------------------------------------------------

def test_make_job_no_agent_requires_script():
    with pytest.raises(ValueError, match="requires --script"):
        event._make_job(_start_args(no_agent=True))


def test_make_job_no_agent_rejects_respawn():
    with pytest.raises(ValueError, match="cannot use --respawn"):
        event._make_job(_start_args(no_agent=True, script="w.py", respawn_runtime="codex"))


def test_make_job_records_respawn_recipe():
    job = event._make_job(_start_args(respawn_runtime="codex", respawn_cwd="/x", respawn_prompt="boot"))
    assert job["respawn"] == {"runtime": "codex", "cwd": "/x", "prompt": "boot"}
    assert job["no_agent"] is False


# --------------------------------------------------------------------------
# ensure-alive (respawn-if-dead / skip-if-busy / send-if-alive)
# --------------------------------------------------------------------------

def test_ensure_alive_dead_target_respawns(monkeypatch):
    job = event._make_job(_start_args(respawn_runtime="codex", respawn_cwd="/x", respawn_prompt="boot"))
    monkeypatch.setattr(event, "_target_is_busy", lambda t: {"ok": True, "busy": False, "terminal": "missing"})
    calls = {}

    def fake_respawn(j, r, tick):
        calls["r"] = (j, r, tick)
        return {"ok": True, "respawned": True, "state": "respawned"}

    monkeypatch.setattr(event, "_respawn", fake_respawn)
    result = event._deliver(job, 1)
    assert result.get("respawned") is True
    assert calls["r"][1] == {"runtime": "codex", "cwd": "/x", "prompt": "boot"}


def test_ensure_alive_busy_target_skips_no_respawn(monkeypatch):
    job = event._make_job(_start_args(respawn_runtime="codex"))
    monkeypatch.setattr(event, "_target_is_busy", lambda t: {"ok": True, "busy": True, "blocker": "target-busy", "terminal": "alive"})
    monkeypatch.setattr(event, "_respawn", lambda *a, **k: pytest.fail("must not respawn a live busy seat"))
    result = event._deliver(job, 1)
    assert result.get("skipped") is True
    assert result.get("reason") == "target-busy"


def test_ensure_alive_alive_idle_sends(monkeypatch):
    job = event._make_job(_start_args(respawn_runtime="codex"))
    monkeypatch.setattr(event, "_target_is_busy", lambda t: {"ok": True, "busy": False, "blocker": None, "terminal": "alive"})
    monkeypatch.setattr(event, "_respawn", lambda *a, **k: pytest.fail("must not respawn a live seat"))

    class _R:
        returncode = 0
        stdout = '{"ok": true, "state": "attempted", "submitted_verified": true}'
        stderr = ""

    monkeypatch.setattr(event.subprocess, "run", lambda *a, **k: _R())
    result = event._deliver(job, 1)
    assert result["ok"] is True
    assert result.get("respawned") is not True
    assert result["message_id"]


def test_respawn_builds_fleet_seat_spawn_command(monkeypatch):
    job = event._make_job(_start_args(target="flex-community:recovery-pain-scout"))
    captured = {}

    class _R:
        returncode = 0
        stdout = '{"ok": true, "spawned": true}'
        stderr = ""

    def fake_run(cmd, *a, **k):
        captured["cmd"] = cmd
        return _R()

    monkeypatch.setattr(event.subprocess, "run", fake_run)
    recipe = {"runtime": "codex", "cwd": "/work", "prompt": "bootstrap here"}
    result = event._respawn(job, recipe, 1)
    cmd = captured["cmd"]
    assert cmd[:3] == [event._aura_bin(), "spawn", "recovery-pain-scout"]
    assert "--fleet" in cmd and cmd[cmd.index("--fleet") + 1] == "flex-community"
    assert cmd[cmd.index("--runtime") + 1] == "codex"
    assert cmd[cmd.index("--cwd") + 1] == "/work"
    assert cmd[cmd.index("--prompt") + 1] == "bootstrap here"
    assert result["respawned"] is True and result["state"] == "respawned"


# --------------------------------------------------------------------------
# no_agent script mode
# --------------------------------------------------------------------------

def test_no_agent_empty_stdout_is_silent(aura_state, monkeypatch):
    job = event._make_job(_start_args(no_agent=True, script="w.py"))
    monkeypatch.setattr(events, "run_script", lambda s: (True, ""))
    result = event._deliver(job, 1)
    assert result["ok"] is True and result.get("skipped") is True
    assert result["state"] == "silent"
    assert reports.latest_report() is None  # nothing delivered


def test_no_agent_nonempty_stdout_writes_report(aura_state, monkeypatch):
    job = event._make_job(_start_args(no_agent=True, script="w.py", target="flex:reply-watch", report_state="needs_decision"))
    monkeypatch.setattr(events, "run_script", lambda s: (True, "📬 reply from acme"))
    monkeypatch.setattr(reports, "infer_context", lambda: {})
    monkeypatch.setattr(reports, "schedule_report_subscriptions", lambda r, **k: [])
    result = event._deliver(job, 1)
    assert result["ok"] is True and result.get("delivered") is True
    latest = reports.latest_report()
    assert latest is not None
    assert latest["work"] == "📬 reply from acme"
    assert latest["state"] == "needs_decision"
    assert latest["seat"] == "reply-watch" and latest["fleet"] == "flex"
    assert latest["source"] == "aura-event:no-agent"


def test_no_agent_nonzero_exit_is_failure_with_backoff(aura_state, monkeypatch):
    job = event._make_job(_start_args(no_agent=True, script="w.py"))
    events.save_state(job)
    monkeypatch.setattr(events, "run_script", lambda s: (False, "boom: exit 1"))
    tick_result = event._tick(events.load_state(job["job_id"]), force=True)
    assert tick_result["ok"] is False
    saved = events.load_state(job["job_id"])
    assert saved["consecutive_errors"] == 1
    assert saved["last_error"]
    # failure reschedules with backoff, not the normal interval
    assert saved["next_tick_at"] is not None


def test_no_agent_report_matches_subscription(aura_state, monkeypatch):
    """#4 pub/sub: a no_agent report is shaped to match an existing subscription."""
    sub = report_subscriptions.create(
        name="reply-watch-sub", to="flex:operator", fleet="flex", states=[],
    )
    job = event._make_job(_start_args(no_agent=True, script="w.py", target="flex:reply-watch"))
    monkeypatch.setattr(events, "run_script", lambda s: (True, "new prospect reply"))
    monkeypatch.setattr(reports, "infer_context", lambda: {})
    monkeypatch.setattr(reports, "schedule_report_subscriptions", lambda r, **k: [])
    event._deliver(job, 1)
    report = reports.latest_report()
    assert report_subscriptions.matches_report(sub, report) is True


# --------------------------------------------------------------------------
# script resolution guard
# --------------------------------------------------------------------------

def test_run_script_blocks_path_traversal(aura_state):
    ok, msg = events.run_script("../../etc/passwd")
    assert ok is False
    assert "outside" in msg


def test_run_script_runs_python_and_captures_stdout(aura_state):
    _write_script(aura_state, "hello.py", "print('hi there')\n")
    ok, out = events.run_script("hello.py")
    assert ok is True and out == "hi there"


def test_run_script_nonzero_exit_reports_failure(aura_state):
    _write_script(aura_state, "boom.py", "import sys; sys.stderr.write('nope'); sys.exit(3)\n")
    ok, msg = events.run_script("boom.py")
    assert ok is False
    assert "code 3" in msg and "nope" in msg

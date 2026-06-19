"""Daemon supervision: computed liveness + respawn-the-dead, no double-spawn.

These prove the two-laws read discipline for event daemons (liveness computed
from the pid, never trusted from the stored record) and the ensure-daemons
supervisor that a systemd --user timer drives.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))

from lib import events  # noqa: E402
from commands import event as event_cmd  # noqa: E402


def _running_job(job_id: str, name: str, pid):
    return {
        "schema": "aura.event.job.v1",
        "job_id": job_id,
        "name": name,
        "kind": "interval",
        "status": "running",
        "interval_seconds": 60.0,
        "tick": 0,
        "daemon": {"pid": pid} if pid is not None else None,
    }


def test_pid_is_daemon_dead_pid_reads_false():
    # A pid that cannot exist reads not-alive (computed, not trusted).
    assert events.pid_is_daemon(2_000_000_000, "evt_x") is False
    assert events.pid_is_daemon(None, "evt_x") is False


def test_pid_is_daemon_wrong_process_reads_false():
    # This test process IS alive, but it is not an "event daemon" for the job —
    # the cmdline guard rejects it (guards against pid reuse).
    assert events.pid_is_daemon(os.getpid(), "evt_x") is False


def test_daemon_alive_requires_daemon_record():
    assert events.daemon_alive({"job_id": "evt_x"}) is False
    assert events.daemon_alive({"job_id": "evt_x", "daemon": {"pid": 2_000_000_000}}) is False


def test_ensure_daemons_respawns_dead_running_job(monkeypatch):
    job = _running_job("evt_dead_1", "heal-sweep", 2_000_000_000)  # dead pid
    events.save_state(job)

    spawned = []

    def fake_spawn(job_id):
        spawned.append(job_id)
        return {"pid": 424242, "log": "x", "cmd": ["aura", "event", "daemon", job_id]}

    monkeypatch.setattr(event_cmd, "_spawn_daemon", fake_spawn)

    result = event_cmd._ensure_daemons()
    assert result["respawned"] == 1
    assert result["alive"] == 0
    assert spawned == ["evt_dead_1"]
    # The job's daemon record was refreshed to the new pid.
    reloaded = events.load_state("evt_dead_1")
    assert reloaded["daemon"]["pid"] == 424242


def test_ensure_daemons_skips_alive_and_non_running(monkeypatch):
    events.save_state(_running_job("evt_alive_1", "reply-watch", 111))
    events.save_state({**_running_job("evt_stopped_1", "old", 222), "status": "stopped"})
    events.save_state({**_running_job("evt_paused_1", "paused-job", 333), "status": "paused"})

    # evt_alive_1 reads alive; nothing else is running.
    monkeypatch.setattr(events, "daemon_alive",
                        lambda job: job.get("job_id") == "evt_alive_1")

    def boom(job_id):
        raise AssertionError(f"must not respawn {job_id}")

    monkeypatch.setattr(event_cmd, "_spawn_daemon", boom)

    result = event_cmd._ensure_daemons()
    assert result["alive"] == 1
    assert result["respawned"] == 0
    assert result["checked"] == 1  # only the one running job is counted


def test_job_summary_reports_computed_liveness():
    job = _running_job("evt_corpse_1", "scout", 2_000_000_000)
    summary = event_cmd._job_summary(job)
    # The record says daemon={pid}, but computed liveness is honest: dead.
    assert summary["daemon"] == {"pid": 2_000_000_000}
    assert summary["daemon_alive"] is False

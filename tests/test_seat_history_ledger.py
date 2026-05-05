import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_append_seat_event_normalizes_before_after(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import session_ledger

    before = {
        "name": "engineer",
        "fleet": "flex-leaders",
        "runtime": "codex",
        "runtime_session_id": "old-session",
        "cwd": "/repo",
        "ignored_noise": "nope",
    }
    after = {
        **before,
        "fleet": "flex-leaders-2",
        "runtime_session_id": "new-session",
        "desks_role_id": "leader-engineer",
    }

    event = session_ledger.append_seat_event(
        event="seat_rehomed",
        before=before,
        after=after,
        evidence={"reason": "unit-test"},
        source_command="aura seat rehome",
    )

    assert event["schema"] == "aura.seat_history.v1"
    assert event["event_id"].startswith("aura-seat-history-")
    assert event["seat_ref"] == "flex-leaders-2:engineer"
    assert event["runtime_session_id"] == "new-session"
    assert event["before"]["seat_ref"] == "flex-leaders:engineer"
    assert event["after"]["seat_ref"] == "flex-leaders-2:engineer"
    assert "ignored_noise" not in event["before"]
    assert "desks_role_id" not in event
    assert "desks_role_id" not in event["after"]


def test_seat_history_for_target_follows_rehome_alias(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import session_ledger

    old = {"name": "engineer", "fleet": "old", "runtime": "codex", "runtime_session_id": "s1"}
    new = {"name": "engineer", "fleet": "new", "runtime": "codex", "runtime_session_id": "s1"}
    session_ledger.append_seat_event(event="seat_spawned", after=old)
    session_ledger.append_seat_event(
        event="seat_rehomed",
        before=old,
        after=new,
        source_ref="old:engineer",
        target_ref="new:engineer",
    )
    session_ledger.append_seat_event(
        event="seat_alias_created",
        before=old,
        after=new,
        source_ref="old:engineer",
        target_ref="new:engineer",
    )

    rows = session_ledger.seat_history_for_target("new:engineer")
    assert [row["event"] for row in rows] == ["seat_spawned", "seat_rehomed", "seat_alias_created"]


def test_restore_plan_from_ledger_uses_latest_active_state(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import runtimes, session_ledger

    old = {
        "name": "engineer",
        "fleet": "old",
        "runtime": "codex",
        "runtime_session_id": "old-session",
        "runtime_session_source": "codex-jsonl:nonce",
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": "nonce-jsonl",
        "runtime_session_bind_source": "codex-jsonl:nonce",
        "runtime_session_confidence": "exact",
        "cwd": "/repo",
    }
    new = {
        **old,
        "fleet": "new",
        "runtime_session_id": "new-session",
    }
    dead = {
        "name": "dead",
        "fleet": "new",
        "runtime": "codex",
        "runtime_session_id": "dead-session",
        "runtime_session_confidence": "exact",
        "cwd": "/repo",
    }
    session_ledger.append_seat_event(event="seat_spawned", after=old)
    session_ledger.append_seat_event(event="seat_rehomed", before=old, after=new)
    session_ledger.append_seat_event(event="seat_spawned", after=dead)
    session_ledger.append_seat_event(event="seat_cut", before=dead, after={**dead, "status": "dead"})

    latest = session_ledger.project_latest_from_ledger()
    by_ref = {row["seat_ref"]: row for row in latest}
    assert "new:engineer" in by_ref
    assert "old:engineer" not in by_ref
    assert by_ref["new:dead"]["restore_suppressed"] is True

    plan = session_ledger.restore_plan_from_rows(latest, runtimes.capability_map())
    rows = {f"{row['fleet']}:{row['seat']}": row for row in plan["rows"]}
    assert rows["new:engineer"]["restore_ready"] is True
    assert "resume new-session" in rows["new:engineer"]["restore_command"]
    assert rows["new:dead"]["restore_ready"] is False
    assert rows["new:dead"]["restore_reason"] == "latest-seat-state-is-terminal"


def test_sessions_seat_history_command_reads_target(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import sessions
    from lib import session_ledger

    session_ledger.append_seat_event(
        event="seat_spawned",
        after={"name": "engineer", "fleet": "fleet", "runtime": "codex", "runtime_session_id": "s1"},
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="seat-history",
        target=None,
        nonce="fleet:engineer",
        limit=None,
        no_follow_aliases=False,
    ))

    assert result["ok"] is True
    assert result["target"] == "fleet:engineer"
    assert result["rows"][0]["event"] == "seat_spawned"

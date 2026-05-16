import json
import os
from pathlib import Path
import subprocess
import sys
import argparse


ROOT = Path(__file__).resolve().parents[1]
AURA = ROOT / "cli" / "aura"
sys.path.insert(0, str(ROOT / "cli"))


def run_aura(args, env, cwd=None):
    result = subprocess.run(
        [sys.executable, str(AURA), *args],
        cwd=cwd or ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def run_aura_raw(args, env, cwd=None):
    return subprocess.run(
        [sys.executable, str(AURA), *args],
        cwd=cwd or ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )


def write_registry(env, rows):
    path = Path(env["AURA_STATE_DIR"]) / "registry" / "seats.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        f"{row['fleet']}:{row['name']}": {
            "seat": row["name"],
            "seat_ref": f"{row['fleet']}:{row['name']}",
            "registered": True,
            **row,
        }
        for row in rows
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_report_appends_semantic_delta_with_inferred_context(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "AURA_FLEET": "unitfleet",
        "AURA_SEAT": "engineer",
        "AURA_RUNTIME": "codex",
        "CODEX_THREAD_ID": "019ddf5f-b386-7ef0-9f43-8329ab2019c7",
        "DESKS_ROLE_ID": "leader-engine",
        "DESKS_PRODUCT": "flex",
        "DESKS_UNIT": "engine",
        "DESKS_ROLE_HOME": "/tmp/roles/leader-engine",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    result = run_aura_raw(
        [
            "report",
            "complete",
            "--work",
            "Simplified Aura report primitive",
            "--done",
            "Added global report ledger",
            "--done",
            "Kept agent-facing fields tiny",
            "--receipt",
            "focused tests passed",
            "--next",
            "Document report-first UX",
        ],
        env,
        cwd=tmp_path,
    )

    assert result.stdout == ""

    latest = run_aura(["report", "latest"], env)
    record = latest["record"]
    assert record["schema"] == "aura.report.v1"
    assert record["state"] == "complete"
    assert record["work"] == "Simplified Aura report primitive"
    assert record["done"] == ["Added global report ledger", "Kept agent-facing fields tiny"]
    assert record["receipts"] == ["focused tests passed"]
    assert record["next"] == "Document report-first UX"
    assert record["seat"] == "engineer"
    assert record["fleet"] == "unitfleet"
    assert record["runtime"] == "codex"
    assert record["session_id"] == "019ddf5f-b386-7ef0-9f43-8329ab2019c7"
    assert record["role"]["desks_role_id"] == "leader-engine"
    assert record["role"]["desks_product"] == "flex"
    assert record["role"]["desks_unit"] == "engine"
    assert record["role"]["desks_role_home"] == "/tmp/roles/leader-engine"

    ledger = tmp_path / ".aura" / "reports" / "reports.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["report_id"] == record["report_id"]


def test_report_ack_prints_compact_receipt(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "AURA_FLEET": "unitfleet",
        "AURA_SEAT": "engineer",
        "AURA_RUNTIME": "codex",
        "CODEX_THREAD_ID": "019ddf5f-b386-7ef0-9f43-8329ab2019c7",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    result = run_aura(["report", "complete", "--work", "Ack mode", "--ack"], env)

    assert result["ok"] is True
    assert result["schema"] == "aura.report_ack.v1"
    assert result["state"] == "complete"
    assert result["work"] == "Ack mode"
    assert result["seat"] == "engineer"
    assert result["fleet"] == "unitfleet"
    assert result["warnings"] == []


def test_report_list_and_latest_read_global_ledger(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "AURA_FLEET": "unitfleet",
        "AURA_SEAT": "worker",
        "AURA_RUNTIME": "codex",
        "CODEX_THREAD_ID": "019ddf5f-b386-7ef0-9f43-8329ab2019c7",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    run_aura_raw(["report", "working", "--work", "First"], env)
    run_aura_raw(["report", "blocked", "--work", "Second", "--blocker", "needs decision"], env)

    listed = run_aura(["report", "list", "--limit", "1"], env)
    assert listed["ok"] is True
    assert listed["count"] == 1
    second_id = listed["rows"][0]["report_id"]

    latest = run_aura(["report", "latest"], env)
    assert latest["ok"] is True
    assert latest["record"]["report_id"] == second_id
    assert latest["record"]["state"] == "blocked"
    assert latest["record"]["blockers"] == ["needs decision"]


def test_report_list_and_latest_can_filter_by_target_state_and_cwd(tmp_path):
    base_env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "AURA_RUNTIME": "codex",
        "CODEX_THREAD_ID": "019ddf5f-b386-7ef0-9f43-8329ab2019c7",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    env_a = {**base_env, "AURA_FLEET": "fleet-a", "AURA_SEAT": "worker-a"}
    env_b = {**base_env, "AURA_FLEET": "fleet-b", "AURA_SEAT": "worker-b"}
    repo_a = tmp_path / "repo-a"
    repo_b = tmp_path / "repo-b"
    repo_a.mkdir()
    repo_b.mkdir()

    run_aura_raw(["report", "working", "--work", "A first"], env_a, cwd=repo_a)
    run_aura_raw(["report", "complete", "--work", "B done"], env_b, cwd=repo_b)
    run_aura_raw(["report", "complete", "--work", "A done"], env_a, cwd=repo_a)

    listed = run_aura([
        "report",
        "list",
        "--target",
        "fleet-a:worker-a",
        "--state",
        "complete",
        "--cwd-prefix",
        str(repo_a),
    ], base_env)
    assert listed["ok"] is True
    assert listed["count"] == 1
    assert listed["rows"][0]["work"] == "A done"
    assert listed["rows"][0]["fleet"] == "fleet-a"
    assert listed["rows"][0]["seat"] == "worker-a"

    latest = run_aura(["report", "latest", "--fleet", "fleet-b"], base_env)
    assert latest["ok"] is True
    assert latest["record"]["work"] == "B done"


def test_report_releases_queued_messages_for_reporting_seat(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")

    from commands import send
    from lib import queued_messages, reports

    sent = []

    def fake_send(args):
        sent.append((args.target, args.message, args.sender, args.dedupe_key, args.force))
        return {"ok": True, "message_id": "aura-msg-test"}

    monkeypatch.setattr(send, "run", fake_send)

    queued = queued_messages.create(
        target="unitfleet:worker",
        message="continue after report",
        sender="tester",
    )
    report = reports.append_report({"state": "complete", "work": "done"})
    released = reports.release_queued_messages(report)

    assert sent == [("unitfleet:worker", "continue after report", "tester", f"queue:{queued['queue_id']}", True)]
    assert released[0]["status"] == "released"
    saved = queued_messages.load(queued["queue_id"])
    assert saved["release_report_id"] == report["report_id"]
    assert saved["release_message_id"] == "aura-msg-test"


def test_report_command_schedules_queued_release_after_ack(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")

    from commands import report as report_cmd, send
    from lib import queued_messages

    def fail_send(_args):
        raise AssertionError("report should schedule queue release, not send inline")

    started = []
    monkeypatch.setattr(send, "run", fail_send)
    monkeypatch.setattr(report_cmd, "_start_queued_release_worker", lambda report_id: started.append(report_id))

    queued = queued_messages.create(
        target="unitfleet:worker",
        message="continue after report",
        sender="tester",
    )
    args = argparse.Namespace(
        report_action="complete",
        work="done",
        done=[],
        receipt=[],
        next_action=None,
        blocker=[],
        ack=True,
    )
    result = report_cmd.run(args)

    assert result["ok"] is True
    assert result["scheduled_queued"] == 1
    assert result["queue_release_delay_seconds"] == 1.5
    assert started == [result["report_id"]]
    saved = queued_messages.load(queued["queue_id"])
    assert saved["status"] == "scheduled"
    assert saved["release_report_id"] == result["report_id"]


def test_queue_release_report_command_releases_scheduled_message(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")

    from commands import queue as queue_cmd, send
    from lib import queued_messages, reports

    sent = []

    def fake_send(args):
        sent.append((args.target, args.message, args.dedupe_key))
        return {"ok": True, "message_id": "aura-msg-delayed"}

    monkeypatch.setattr(send, "run", fake_send)

    queued = queued_messages.create(
        target="unitfleet:worker",
        message="continue after report",
        sender="tester",
    )
    report = reports.append_report({"state": "complete", "work": "done"})
    scheduled = reports.schedule_queued_messages(report, delay_seconds=1.5)
    assert scheduled[0]["status"] == "scheduled"

    result = queue_cmd.run(argparse.Namespace(release_report=report["report_id"], delay="0"))

    assert result["ok"] is True
    assert result["released"] == 1
    assert sent == [("unitfleet:worker", "continue after report", f"queue:{queued['queue_id']}")]
    saved = queued_messages.load(queued["queue_id"])
    assert saved["status"] == "released"
    assert saved["release_message_id"] == "aura-msg-delayed"


def test_report_release_failure_is_inspectable_and_not_retried(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")

    from commands import send
    from lib import queued_messages, reports

    calls = []

    def fake_send(args):
        calls.append((args.target, args.dedupe_key, args.force))
        return {"ok": False, "error": "target missing"}

    monkeypatch.setattr(send, "run", fake_send)

    queued = queued_messages.create(
        target="unitfleet:worker",
        message="continue after report",
        sender="tester",
    )
    first_report = reports.append_report({"state": "complete", "work": "first"})
    first_release = reports.release_queued_messages(first_report)
    second_report = reports.append_report({"state": "complete", "work": "second"})
    second_release = reports.release_queued_messages(second_report)

    assert len(calls) == 1
    assert calls == [("unitfleet:worker", f"queue:{queued['queue_id']}", True)]
    assert first_release[0]["status"] == "release_failed"
    assert first_release[0]["release_report_id"] == first_report["report_id"]
    assert first_release[0]["error"] == "target missing"
    assert second_release == []
    saved = queued_messages.load(queued["queue_id"])
    assert saved["status"] == "release_failed"
    assert saved["attempts"][0]["report_id"] == first_report["report_id"]


def test_report_release_records_send_exception_without_breaking_report(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")

    from commands import send
    from lib import queued_messages, reports

    def broken_send(args):
        raise RuntimeError("boom")

    monkeypatch.setattr(send, "run", broken_send)

    queued = queued_messages.create(
        target="unitfleet:worker",
        message="continue after report",
        sender="tester",
    )
    report = reports.append_report({"state": "complete", "work": "done"})
    released = reports.release_queued_messages(report)

    assert released[0]["status"] == "release_failed"
    assert released[0]["error"] == "queue release send failed: boom"
    saved = queued_messages.load(queued["queue_id"])
    assert saved["attempts"][0]["ok"] is False
    assert saved["attempts"][0]["result"]["error"] == "queue release send failed: boom"


def test_report_release_matches_rehomed_seat_alias(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "newfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")

    from commands import send
    from lib import queued_messages, registry, reports

    sent = []

    def fake_send(args):
        sent.append(args.target)
        return {"ok": True, "message_id": "aura-msg-test"}

    monkeypatch.setattr(send, "run", fake_send)
    registry.add_alias("oldfleet:worker", "newfleet:worker", reason="test")

    queued = queued_messages.create(
        target="oldfleet:worker",
        message="continue after report",
        sender="tester",
    )
    report = reports.append_report({"state": "complete", "work": "done"})
    released = reports.release_queued_messages(report)

    assert sent == ["oldfleet:worker"]
    assert released[0]["status"] == "released"
    assert queued_messages.load(queued["queue_id"])["release_report_id"] == report["report_id"]


def test_queue_command_records_pending_message(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    write_registry(env, [{
        "name": "lead",
        "fleet": "unitfleet",
        "runtime": "codex",
        "seat_instance_id": "si_lead",
        "pane_ref": "tmux:unitfleet:%1",
    }])

    result = run_aura(["queue", "unitfleet:worker", "after your next report", "--as", "unitfleet:lead"], env)

    assert result["ok"] is True
    assert result["schema"] == "aura.queue_ack.v1"
    assert result["target"] == "unitfleet:worker"
    assert result["after"] == "next-report"

    listed = run_aura(["queue", "--list", "--status", "pending"], env)
    assert listed["ok"] is True
    assert listed["records"][0]["message"] == "after your next report"
    assert listed["records"][0]["sender"] == "unitfleet:lead"


def test_queue_command_infers_current_seat_sender(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "AURA_FLEET": "unitfleet",
        "AURA_SEAT": "lead",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    write_registry(env, [{
        "name": "lead",
        "fleet": "unitfleet",
        "runtime": "codex",
        "seat_instance_id": "si_lead",
        "pane_ref": "tmux:unitfleet:%1",
    }])

    result = run_aura(["queue", "unitfleet:worker", "after your next report"], env)

    assert result["ok"] is True
    listed = run_aura(["queue", "--list", "--status", "pending"], env)
    assert listed["records"][0]["sender"] == "unitfleet:lead"


def test_queue_command_accepts_service_sender(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    result = run_aura(["queue", "unitfleet:worker", "after your next report", "--as-service", "chatbot-pipeline"], env)

    assert result["ok"] is True
    listed = run_aura(["queue", "--list", "--status", "pending"], env)
    assert listed["records"][0]["sender"] == "service:chatbot-pipeline"
    assert listed["records"][0]["sender_kind"] == "service"


def test_event_subscribe_reports_creates_named_subscription(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    result = run_aura(
        [
            "event",
            "subscribe",
            "reports",
            "--name",
            "unit-checkins",
            "--fleet",
            "unitfleet",
            "--state",
            "blocked",
            "--state",
            "complete",
            "--to",
            "unitfleet:lead",
        ],
        env,
    )

    subscription = result["subscription"]
    assert result["ok"] is True
    assert result["schema"] == "aura.event.report_subscription_ack.v1"
    assert subscription["name"] == "unit-checkins"
    assert subscription["fleet"] == "unitfleet"
    assert subscription["states"] == ["blocked", "complete"]
    assert subscription["to"] == "unitfleet:lead"

    listed = run_aura(["event", "subscriptions"], env)
    assert listed["subscriptions"][0]["subscription_id"] == subscription["subscription_id"]

    shown = run_aura(["event", "subscription", "show", "unit-checkins"], env)
    assert shown["subscription"]["subscription_id"] == subscription["subscription_id"]


def test_event_subscribe_reports_requires_source_filter(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    raw = subprocess.run(
        [
            sys.executable,
            str(AURA),
            "event",
            "subscribe",
            "reports",
            "--name",
            "too-broad",
            "--to",
            "unitfleet:lead",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    result = json.loads(raw.stdout)

    assert raw.returncode == 1
    assert result["ok"] is False
    assert result["error"] == "report subscriptions require --fleet or --target"


def test_event_subscribe_reports_rejects_duplicate_active_name(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    args = [
        "event",
        "subscribe",
        "reports",
        "--name",
        "unit-checkins",
        "--fleet",
        "unitfleet",
        "--to",
        "unitfleet:lead",
    ]
    first = run_aura(args, env)
    raw = subprocess.run(
        [sys.executable, str(AURA), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    second = json.loads(raw.stdout)

    assert first["ok"] is True
    assert raw.returncode == 1
    assert second["error"] == "report subscription already exists: unit-checkins"


def test_report_command_schedules_report_subscription_after_ack(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")

    from commands import report as report_cmd
    from lib import report_subscriptions

    started = []
    monkeypatch.setattr(report_cmd, "_start_report_subscription_worker", lambda report_id: started.append(report_id))

    report_subscriptions.create(
        name="unit-checkins",
        to="unitfleet:lead",
        fleet="unitfleet",
        states=["complete"],
    )
    args = argparse.Namespace(
        report_action="complete",
        work="done",
        done=[],
        receipt=[],
        next_action=None,
        blocker=[],
        ack=True,
    )
    result = report_cmd.run(args)

    assert result["ok"] is True
    assert result["scheduled_report_subscriptions"] == 1
    assert result["report_subscription_delay_seconds"] == 1.5
    assert started == [result["report_id"]]
    subscription = report_subscriptions.load("unit-checkins")
    scheduled = subscription["reports"][result["report_id"]]
    assert scheduled["status"] == "scheduled"
    assert scheduled["release_delay_seconds"] == 1.5


def test_paused_report_subscription_does_not_schedule(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")

    from lib import report_subscriptions, reports

    report_subscriptions.create(
        name="unit-checkins",
        to="unitfleet:lead",
        fleet="unitfleet",
        states=["complete"],
    )
    report_subscriptions.set_status("unit-checkins", "paused")
    report = reports.append_report({"state": "complete", "work": "done"})

    assert reports.schedule_report_subscriptions(report) == []


def test_event_release_report_subscriptions_sends_scheduled_notification(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")

    from commands import event as event_cmd, send
    from lib import report_subscriptions, reports

    sent = []

    def fake_send(args):
        sent.append((args.target, args.message, args.sender, args.dedupe_key))
        return {"ok": True, "message_id": "aura-msg-report-sub"}

    monkeypatch.setattr(send, "run", fake_send)

    subscription = report_subscriptions.create(
        name="unit-checkins",
        to="unitfleet:lead",
        fleet="unitfleet",
        states=["complete"],
    )
    report = reports.append_report({
        "state": "complete",
        "work": "done",
        "receipts": ["tests passed"],
        "next": "move on",
    })
    scheduled = reports.schedule_report_subscriptions(report, delay_seconds=1.5)
    assert scheduled[0]["reports"][report["report_id"]]["status"] == "scheduled"

    result = event_cmd.run(argparse.Namespace(
        event_action="release-report-subscriptions",
        ref=report["report_id"],
        delay="0",
    ))

    assert result["ok"] is True
    assert result["released"] == 1
    assert sent[0][0] == "unitfleet:lead"
    assert sent[0][2] == "aura-event"
    assert sent[0][3] == f"report-sub:unitfleet:lead:{report['report_id']}"
    assert "[AURA REPORT state=complete from=unitfleet:worker]" in sent[0][1]
    assert "work: done" in sent[0][1]
    assert "report_id: " + report["report_id"] in sent[0][1]
    saved = report_subscriptions.load("unit-checkins")
    state = saved["reports"][report["report_id"]]
    assert state["status"] == "notified"
    assert state["message_id"] == "aura-msg-report-sub"


def test_report_subscription_skips_self_echo(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")

    from lib import report_subscriptions, reports

    report_subscriptions.create(
        name="worker-self",
        to="unitfleet:worker",
        fleet="unitfleet",
        states=["complete"],
    )
    report = reports.append_report({"state": "complete", "work": "done"})
    scheduled = reports.schedule_report_subscriptions(report)

    assert scheduled == []
    saved = report_subscriptions.load("worker-self")
    state = saved["reports"][report["report_id"]]
    assert state["status"] == "skipped_self"
    assert state["reason"] == "report-source-is-notification-target"


def test_report_subscription_dedupes_overlapping_recipients(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")

    from commands import send
    from lib import report_subscriptions, reports

    sent = []

    def fake_send(args):
        sent.append((args.target, args.dedupe_key, args.force))
        return {"ok": True, "message_id": f"aura-msg-{len(sent)}"}

    monkeypatch.setattr(send, "run", fake_send)

    first = report_subscriptions.create(
        name="lead-all",
        to="unitfleet:lead",
        fleet="unitfleet",
        states=["complete"],
    )
    second = report_subscriptions.create(
        name="lead-worker",
        to="unitfleet:lead",
        target="unitfleet:worker",
        states=["complete"],
    )
    report = reports.append_report({"state": "complete", "work": "done"})
    scheduled = reports.schedule_report_subscriptions(report)
    assert {row["subscription_id"] for row in scheduled} == {first["subscription_id"], second["subscription_id"]}

    released = report_subscriptions.release_for_report(report)

    assert sent == [("unitfleet:lead", f"report-sub:unitfleet:lead:{report['report_id']}", False)]
    states = {
        row["subscription_id"]: row["reports"][report["report_id"]]["status"]
        for row in released
    }
    assert set(states.values()) == {"notified", "deduped"}

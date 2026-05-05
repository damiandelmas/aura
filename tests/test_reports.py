import json
import os
from pathlib import Path
import subprocess
import sys


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

    result = run_aura(["queue", "unitfleet:worker", "after your next report", "--as", "tester"], env)

    assert result["ok"] is True
    assert result["schema"] == "aura.queue_ack.v1"
    assert result["target"] == "unitfleet:worker"
    assert result["after"] == "next-report"

    listed = run_aura(["queue", "--list", "--status", "pending"], env)
    assert listed["ok"] is True
    assert listed["records"][0]["message"] == "after your next report"
    assert listed["records"][0]["sender"] == "tester"


def test_queue_command_infers_current_seat_sender(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "AURA_FLEET": "unitfleet",
        "AURA_SEAT": "lead",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    result = run_aura(["queue", "unitfleet:worker", "after your next report"], env)

    assert result["ok"] is True
    listed = run_aura(["queue", "--list", "--status", "pending"], env)
    assert listed["records"][0]["sender"] == "unitfleet:lead"

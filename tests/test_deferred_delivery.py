import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_send_defer_if_busy_creates_outbox_without_daemon(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))

    from commands import send
    from lib import delivery

    class FakeTerminal:
        @staticmethod
        def capture_output(name, lines=80):
            return ["• Working (1s)", "Running tool call"]

        @staticmethod
        def send_text(name, text, submit=True):
            raise AssertionError("send_text should not run for blocked target")

    args = argparse.Namespace(
        target="worker",
        message="important result",
        sender="tester",
        dedupe_key="defer-key",
        force=False,
        defer_if_busy=True,
        defer_ttl="30s",
        defer_retry_every="5s",
        no_deferred_daemon=True,
    )

    result = send._send_tmux(args, FakeTerminal, delivery, terminal_target="tmux:fleet:%1")

    assert result["ok"] is True
    assert result["blocked"] is True
    assert result["deferred"] is True
    deferred_record = result["deferred_record"]
    assert deferred_record["status"] == "pending"
    assert deferred_record["target"] == "worker"
    assert deferred_record["message"] == "important result"
    assert deferred_record["blocked_reason"] == "target-busy"


def test_send_defer_if_composer_active_creates_outbox_without_paste(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))

    from commands import send
    from lib import delivery

    class FakeTerminal:
        sent = False

        @staticmethod
        def capture_output(name, lines=80):
            return ["› human draft in progress", "", "gpt-5.5 high"]

        @classmethod
        def send_text(cls, name, text, submit=True):
            cls.sent = True
            return {"ok": True}

    args = argparse.Namespace(
        target="worker",
        message="important result",
        sender="tester",
        dedupe_key="defer-active-input",
        force=False,
        defer_if_busy=True,
        defer_ttl="30s",
        defer_retry_every="5s",
        no_deferred_daemon=True,
    )

    result = send._send_tmux(args, FakeTerminal, delivery, terminal_target="tmux:fleet:%1")

    assert result["ok"] is True
    assert result["blocked"] is True
    assert result["deferred"] is True
    assert result["reason"] == "target-input-active"
    assert FakeTerminal.sent is False
    assert result["deferred_record"]["blocked_reason"] == "target-input-active"


def test_send_defer_if_submit_unverified_creates_outbox(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))

    from commands import send
    from lib import delivery

    class FakeTerminal:
        captures = [
            ["› Explain this codebase", "", "gpt-5.5 high"],
            ["› Explain this codebase", "", "gpt-5.5 high"],
        ]
        keys = []

        @staticmethod
        def send_text(name, text, submit=True):
            return {"ok": True, "target": "tmux:fleet:%1", "bytes": len(text), "submitted": submit}

        @classmethod
        def capture_output(cls, name, lines=80):
            if cls.captures:
                return cls.captures.pop(0)
            return ["› Explain this codebase", "", "gpt-5.5 high"]

        @classmethod
        def send_keys(cls, name, text, enter=True):
            cls.keys.append((name, text, enter))
            return {"ok": True, "target": "tmux:fleet:%1"}

    args = argparse.Namespace(
        target="worker",
        message="important result",
        sender="tester",
        dedupe_key="defer-unverified",
        force=False,
        defer_if_busy=True,
        defer_ttl="30s",
        defer_retry_every="5s",
        no_deferred_daemon=True,
    )

    result = send._send_tmux(args, FakeTerminal, delivery, terminal_target="tmux:fleet:%1")

    assert result["ok"] is True
    assert result["blocked"] is True
    assert result["deferred"] is True
    assert result["reason"] == "submit-unverified"
    assert result["submitted_verified"] is False
    assert result["deferred_record"]["blocked_reason"] == "submit-unverified:missing-positive-submit-evidence"
    assert FakeTerminal.keys


def test_deferred_run_once_marks_delivered(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import deferred

    record = deferred.create(
        target="worker",
        message="hello",
        sender="tester",
        dedupe_key="defer-key",
        retry_every_seconds=1,
        ttl_seconds=30,
    )

    def fake_run(cmd, text=True, capture_output=True, env=None):
        assert cmd[:3] == [deferred._aura_bin(), "--json", "send"]
        return type("Result", (), {
            "returncode": 0,
            "stdout": json.dumps({"ok": True, "message_id": "aura-msg-delivered", "submitted_verified": True}),
            "stderr": "",
        })()

    monkeypatch.setattr(deferred.subprocess, "run", fake_run)

    result = deferred.run_once(record["deferred_id"])

    assert result["ok"] is True
    assert result["state"] == "delivered"
    saved = deferred.load(record["deferred_id"])
    assert saved["status"] == "delivered"
    assert saved["delivery_result"]["message_id"] == "aura-msg-delivered"


def test_deferred_run_once_keeps_retrying_on_busy(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import deferred

    record = deferred.create(
        target="worker",
        message="hello",
        sender="tester",
        dedupe_key="defer-key",
        retry_every_seconds=1,
        ttl_seconds=30,
    )

    def fake_run(cmd, text=True, capture_output=True, env=None):
        return type("Result", (), {
            "returncode": 1,
            "stdout": json.dumps({"ok": False, "blocked": True, "reason": "target-busy"}),
            "stderr": "",
        })()

    monkeypatch.setattr(deferred.subprocess, "run", fake_run)

    result = deferred.run_once(record["deferred_id"])

    assert result["ok"] is True
    assert result["state"] == "blocked"
    saved = deferred.load(record["deferred_id"])
    assert saved["status"] == "retrying"
    assert saved["attempts"][0]["result"]["reason"] == "target-busy"


def test_deferred_run_once_keeps_retrying_on_active_input_without_nudge(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import deferred

    record = deferred.create(
        target="worker",
        message="hello",
        sender="tester",
        dedupe_key="defer-key",
        retry_every_seconds=1,
        ttl_seconds=30,
    )

    calls = []

    def fake_run(cmd, text=True, capture_output=True, env=None):
        calls.append(cmd)
        return type("Result", (), {
            "returncode": 1,
            "stdout": json.dumps({"ok": False, "blocked": True, "reason": "target-input-active"}),
            "stderr": "",
        })()

    monkeypatch.setattr(deferred.subprocess, "run", fake_run)

    result = deferred.run_once(record["deferred_id"])

    assert result["ok"] is True
    assert result["state"] == "blocked"
    assert result["recovery"] is None
    assert not any("--nudge" in cmd for cmd in calls)
    saved = deferred.load(record["deferred_id"])
    assert saved["status"] == "retrying"
    assert saved["attempts"][0]["result"]["reason"] == "target-input-active"


def test_deferred_run_once_does_not_mark_unverified_ok_as_delivered(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import deferred

    record = deferred.create(
        target="worker",
        message="hello",
        sender="tester",
        dedupe_key="defer-key",
        retry_every_seconds=1,
        ttl_seconds=30,
    )

    def fake_run(cmd, text=True, capture_output=True, env=None):
        return type("Result", (), {
            "returncode": 0,
            "stdout": json.dumps({
                "ok": True,
                "state": "failed",
                "message_id": "aura-msg-unverified",
                "submitted_verified": False,
                "submit_verify_reason": "missing-positive-submit-evidence",
            }),
            "stderr": "",
        })()

    monkeypatch.setattr(deferred.subprocess, "run", fake_run)

    result = deferred.run_once(record["deferred_id"])

    assert result["ok"] is False
    assert result["state"] == "failed"
    saved = deferred.load(record["deferred_id"])
    assert saved["status"] == "failed"
    assert saved["failure_result"]["submitted_verified"] is False


def test_deferred_run_once_nudges_once_on_queued_input(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import deferred

    record = deferred.create(
        target="worker",
        message="hello",
        sender="tester",
        dedupe_key="defer-key",
        retry_every_seconds=1,
        ttl_seconds=30,
    )

    calls = []

    def fake_run(cmd, text=True, capture_output=True, env=None):
        calls.append(cmd)
        if "--nudge" in cmd:
            return type("Result", (), {
                "returncode": 0,
                "stdout": json.dumps({"ok": True, "nudged": True}),
                "stderr": "",
            })()
        return type("Result", (), {
            "returncode": 1,
            "stdout": json.dumps({"ok": False, "blocked": True, "reason": "target-input-queued"}),
            "stderr": "",
        })()

    monkeypatch.setattr(deferred.subprocess, "run", fake_run)

    result = deferred.run_once(record["deferred_id"])

    assert result["ok"] is True
    assert result["state"] == "blocked"
    assert result["recovery"]["action"] == "nudge-queued-input"
    assert any("--nudge" in cmd for cmd in calls)
    saved = deferred.load(record["deferred_id"])
    assert saved["status"] == "retrying"
    assert saved["recovery_attempts"][0]["result"]["nudged"] is True


def test_deferred_run_once_does_not_repeat_queued_input_nudge(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import deferred

    record = deferred.create(
        target="worker",
        message="hello",
        sender="tester",
        dedupe_key="defer-key",
        retry_every_seconds=1,
        ttl_seconds=30,
    )
    record["recovery_attempts"] = [
        {"action": "nudge-queued-input", "result": {"ok": True, "nudged": True}},
    ]
    deferred.save(record)

    calls = []

    def fake_run(cmd, text=True, capture_output=True, env=None):
        calls.append(cmd)
        return type("Result", (), {
            "returncode": 1,
            "stdout": json.dumps({"ok": False, "blocked": True, "reason": "target-input-queued"}),
            "stderr": "",
        })()

    monkeypatch.setattr(deferred.subprocess, "run", fake_run)

    result = deferred.run_once(record["deferred_id"])

    assert result["ok"] is True
    assert result["state"] == "blocked"
    assert result["recovery"]["skipped"] is True
    assert not any("--nudge" in cmd for cmd in calls)


def test_deferred_drain_runs_due_records(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import deferred

    due = deferred.create(
        target="worker",
        message="hello",
        sender="tester",
        dedupe_key="due",
        retry_every_seconds=1,
        ttl_seconds=30,
    )
    future = deferred.create(
        target="worker",
        message="later",
        sender="tester",
        dedupe_key="future",
        retry_every_seconds=1,
        ttl_seconds=30,
    )
    future["next_run_epoch"] = future["next_run_epoch"] + 600
    deferred.save(future)

    def fake_run(cmd, text=True, capture_output=True, env=None):
        return type("Result", (), {
            "returncode": 0,
            "stdout": json.dumps({"ok": True, "message_id": "aura-msg-delivered", "submitted_verified": True}),
            "stderr": "",
        })()

    monkeypatch.setattr(deferred.subprocess, "run", fake_run)

    result = deferred.run_due()

    assert result["ok"] is True
    assert result["count"] == 1
    assert result["delivered"] == 1
    assert deferred.load(due["deferred_id"])["status"] == "delivered"
    assert deferred.load(future["deferred_id"])["status"] == "pending"

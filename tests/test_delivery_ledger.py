import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_delivery_v2_helpers_tolerate_mixed_records(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))

    from lib import delivery

    delivery.append_record({
        "schema": "aura.delivery.v1",
        "message_id": "old-msg",
        "target": "worker",
        "dedupe_key": "old-key",
        "state": "delivered",
    })
    record = delivery.new_delivery_record(
        delivery_type="semantic_send",
        sender="tester",
        target="worker",
        payload_hash="abc123",
        backend="tmux",
        backend_ref="tmux:fleet:%1",
        dedupe_key="new-key",
    )
    delivery.append_attempt(record, state="attempting", evidence={"paste_ok": True})
    delivery.append_final_record(record, state="delivered", submitted_verified=True)

    recent = delivery.recent_records(target="worker", limit=10)
    assert len(recent) == 2
    assert recent[-1]["schema"] == "aura.delivery.v2"
    assert recent[-1]["delivery_id"].startswith("aura-delivery-")
    assert recent[-1]["attempts"][0]["state"] == "attempting"
    assert delivery.last_state_for_target("worker")["dedupe_key"] == "new-key"
    assert delivery.find_by_dedupe_key("old-key")["message_id"] == "old-msg"
    assert delivery.has_successful_dedupe("worker", "new-key") == recent[-1]["message_id"]


def test_standard_send_tmux_does_not_preflight_block_busy_target(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))

    from commands import send
    from lib import delivery

    class FakeTerminal:
        @staticmethod
        def capture_output(name, lines=80):
            return ["• Working (1s)", "Running tool call"]

        @staticmethod
        def send_text(name, text, submit=True):
            return {"ok": True, "target": "tmux:fleet:%1", "bytes": len(text), "submitted": submit}

    args = argparse.Namespace(
        target="worker",
        message="do not append",
        sender="tester",
        dedupe_key="unit-block",
        force=False,
    )

    result = send._send_tmux(args, FakeTerminal, delivery, terminal_target="tmux:fleet:%1")

    assert result["ok"] is True
    record = result["record"]
    assert record["schema"] == "aura.delivery.v2"
    assert record["state"] == "delivered"
    assert record["attempts"][-1]["evidence"]["paste_ok"] is True


def test_send_refuses_current_seat_without_force(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "worker")
    monkeypatch.setenv("CODEX_THREAD_ID", "session-self")

    from commands import send
    from lib import registry

    registry.upsert_agent({
        "name": "worker",
        "fleet": "unitfleet",
        "runtime": "codex",
        "runtime_session_id": "session-self",
        "pane_ref": "tmux:unitfleet:%1",
    })

    args = argparse.Namespace(
        target="unitfleet:worker",
        message="do not paste into self",
        sender="tester",
        transport="tmux",
        mode="auto",
        force=False,
        nudge=False,
        allow_hidden=False,
    )

    result = send.run(args)

    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "target-is-current-seat"


def test_send_tmux_delivered_record_has_attempt_evidence(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))

    from commands import send
    from lib import delivery

    class FakeTerminal:
        captures = [
            ["• Working (1s)"],
        ]

        @staticmethod
        def send_text(name, text, submit=True):
            return {"ok": True, "target": "tmux:fleet:%1", "bytes": len(text), "submitted": submit}

        @classmethod
        def capture_output(cls, name, lines=80):
            return cls.captures.pop(0)

    args = argparse.Namespace(
        target="worker",
        message="hello",
        sender="tester",
        dedupe_key="unit-deliver",
        force=False,
    )

    result = send._send_tmux(args, FakeTerminal, delivery, terminal_target="tmux:fleet:%1")

    assert result["ok"] is True
    record = result["record"]
    assert record["schema"] == "aura.delivery.v2"
    assert record["delivery_type"] == "semantic_send"
    assert record["state"] == "delivered"
    assert [attempt["state"] for attempt in record["attempts"]] == ["pending", "attempted"]
    assert record["attempts"][-1]["evidence"]["submitted_verified"] is True

    lines = (tmp_path / "deliveries.jsonl").read_text(encoding="utf-8").splitlines()
    parsed = [json.loads(line) for line in lines]
    assert parsed[-1]["schema"] == "aura.delivery.v2"

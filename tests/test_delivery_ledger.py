import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _register_sender(name: str = "lead", fleet: str = "unitfleet") -> None:
    from lib import registry

    registry.upsert_agent({
        "name": name,
        "fleet": fleet,
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": f"si_{name}",
        "pane_ref": f"tmux:{fleet}:%sender",
    })


def _register_target(name: str = "worker", fleet: str = "unitfleet", pane: str = "%target") -> None:
    from lib import registry

    registry.upsert_agent({
        "name": name,
        "fleet": fleet,
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": f"si_{name}",
        "pane_ref": f"tmux:{fleet}:{pane}",
    })


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
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import send
    from lib import delivery
    _register_sender()

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
        sender="unitfleet:lead",
        dedupe_key="unit-block",
        force=False,
    )

    result = send._send_tmux(args, FakeTerminal, delivery, terminal_target="tmux:fleet:%1")

    assert result["ok"] is True
    record = result["record"]
    assert record["schema"] == "aura.delivery.v2"
    assert record["state"] == "attempted"
    assert record["attempts"][-1]["evidence"]["paste_ok"] is True


def test_cli_output_can_hide_operator_record_for_routine_send(capsys):
    from lib.output import output

    output({
        "ok": True,
        "message_id": "aura-msg-test",
        "target": "unitfleet:worker",
        "record": {"attempts": [{"evidence": {"large": "debug"}}]},
        "_aura_cli_omit": ["record"],
    })

    rendered = json.loads(capsys.readouterr().out)
    assert rendered == {
        "ok": True,
        "message_id": "aura-msg-test",
        "target": "unitfleet:worker",
    }


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
        sender=None,
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


def test_send_retargets_stale_pane_ref_to_live_logical_window(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import send
    from lib import registry, terminal

    registry.upsert_agent({
        "name": "lead",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_lead",
        "pane_ref": "tmux:unitfleet:%1",
    })
    registry.upsert_agent({
        "name": "worker",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:unitfleet:%99",
        "terminal_ref": "unitfleet:worker",
    })

    sent = {}

    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "target_exists", lambda target: target == "unitfleet:worker")

    def fake_send_text(target, text, submit=True):
        sent["target"] = target
        sent["text"] = text
        return {"ok": True, "target": target, "bytes": len(text), "submitted": submit}

    monkeypatch.setattr(terminal, "send_text", fake_send_text)

    args = argparse.Namespace(
        target="unitfleet:worker",
        message="hello stale pane",
        sender="unitfleet:lead",
        transport="auto",
        mode="auto",
        force=False,
        nudge=False,
        allow_hidden=False,
        dedupe_key="unit-stale-pane",
        defer_if_busy=False,
    )

    result = send.run(args)

    assert result["ok"] is True
    assert result["transport"] == "tmux"
    assert sent["target"] == "unitfleet:worker"
    assert result["terminal_ref"] == "unitfleet:worker"
    assert result["target_diagnostic"] == {
        "reason": "registered-target-missing-window-name-alive",
        "registered_target": "tmux:unitfleet:%99",
        "fallback_target": "unitfleet:worker",
    }
    assert result["record"]["backend_ref"] == "unitfleet:worker"
    assert result["record"]["target_diagnostic"] == result["target_diagnostic"]


def test_send_refuses_unmanaged_explicit_fleet_target(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))

    from commands import send
    from lib import terminal

    _register_sender()

    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "target_exists", lambda target: True)

    args = argparse.Namespace(
        target="unitfleet:bash",
        message="do not send to raw window name",
        sender="unitfleet:lead",
        transport="auto",
        mode="auto",
        force=False,
        nudge=False,
        allow_hidden=False,
        dedupe_key="unit-unmanaged-target",
        defer_if_busy=False,
    )

    result = send.run(args)

    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "target-not-managed"


def test_send_refuses_raw_tmux_target(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import send

    _register_sender()

    args = argparse.Namespace(
        target="tmux:unitfleet:%1",
        message="do not send raw",
        sender="unitfleet:lead",
        transport="auto",
        mode="auto",
        force=False,
        nudge=False,
        allow_hidden=False,
        dedupe_key="unit-raw-target",
        defer_if_busy=False,
    )

    result = send.run(args)

    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "raw-terminal-target"


def test_send_accepts_explicit_service_sender_for_managed_target(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))

    from commands import send
    from lib import terminal

    _register_target()
    sent = {}

    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "target_exists", lambda target: target == "tmux:unitfleet:%target")

    def fake_send_text(target, text, submit=True):
        sent["target"] = target
        sent["text"] = text
        return {"ok": True, "target": target, "bytes": len(text), "submitted": submit}

    monkeypatch.setattr(terminal, "send_text", fake_send_text)

    args = argparse.Namespace(
        target="unitfleet:worker",
        message="service ping",
        sender=None,
        service_sender="chatbot-pipeline",
        transport="auto",
        mode="auto",
        force=False,
        nudge=False,
        allow_hidden=False,
        dedupe_key="unit-service-sender",
        defer_if_busy=False,
    )

    result = send.run(args)

    assert result["ok"] is True
    assert result["sender"] == "service:chatbot-pipeline"
    assert result["sender_kind"] == "service"
    assert "from=service:chatbot-pipeline" in sent["text"]
    assert result["record"]["sender"] == "service:chatbot-pipeline"
    assert result["record"]["sender_kind"] == "service"


def test_service_sender_does_not_bypass_managed_target_guard(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import send
    from lib import terminal

    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "target_exists", lambda target: True)

    args = argparse.Namespace(
        target="unitfleet:bash",
        message="service cannot target raw window",
        sender=None,
        service_sender="chatbot-pipeline",
        transport="auto",
        mode="auto",
        force=False,
        nudge=False,
        allow_hidden=False,
        dedupe_key="unit-service-target-guard",
        defer_if_busy=False,
    )

    result = send.run(args)

    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "target-not-managed"


def test_send_rejects_sender_and_service_sender_together(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import send

    args = argparse.Namespace(
        target="unitfleet:worker",
        message="conflicting senders",
        sender="unitfleet:lead",
        service_sender="chatbot-pipeline",
        transport="auto",
        mode="auto",
        force=False,
        nudge=False,
        allow_hidden=False,
        dedupe_key="unit-sender-conflict",
        defer_if_busy=False,
    )

    result = send.run(args)

    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "sender-conflict"


def test_send_infers_current_seat_sender(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "lead")

    from commands import send
    from lib import delivery
    _register_sender()

    sent = {}

    class FakeTerminal:
        @staticmethod
        def send_text(name, text, submit=True):
            sent["text"] = text
            return {"ok": True, "target": "tmux:unitfleet:%1", "bytes": len(text), "submitted": submit}

        @staticmethod
        def capture_output(name, lines=80):
            return [sent["text"]]

    args = argparse.Namespace(
        target="worker",
        message="hello from lead",
        sender=None,
        dedupe_key="unit-sender",
        force=False,
    )

    result = send._send_tmux(args, FakeTerminal, delivery, terminal_target="tmux:unitfleet:%1")

    assert result["ok"] is True
    assert "from=unitfleet:lead" in sent["text"]
    assert result["record"]["sender"] == "unitfleet:lead"


def test_send_infers_sender_from_process_context_without_seat_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.delenv("AURA_SEAT", raising=False)
    monkeypatch.delenv("AURA_AGENT_NAME", raising=False)

    from commands import send
    from lib import delivery, reports
    _register_sender(name="lead-engineer", fleet="runway-engineering")

    monkeypatch.setattr(reports, "infer_context", lambda: {
        "fleet": "runway-engineering",
        "seat": "lead-engineer",
    })
    sent = {}

    class FakeTerminal:
        @staticmethod
        def send_text(name, text, submit=True):
            sent["text"] = text
            return {"ok": True, "target": "tmux:runway-engineering:%1", "bytes": len(text), "submitted": submit}

        @staticmethod
        def capture_output(name, lines=80):
            return [sent["text"]]

    args = argparse.Namespace(
        target="worker",
        message="hello from inferred lead",
        sender=None,
        dedupe_key="unit-inferred-sender",
        force=False,
    )

    result = send._send_tmux(args, FakeTerminal, delivery, terminal_target="tmux:runway-engineering:%1")

    assert result["ok"] is True
    assert "from=runway-engineering:lead-engineer" in sent["text"]
    assert result["record"]["sender"] == "runway-engineering:lead-engineer"


def test_send_refuses_unidentified_sender(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))
    monkeypatch.delenv("AURA_FLEET", raising=False)
    monkeypatch.delenv("AURA_SEAT", raising=False)
    monkeypatch.delenv("AURA_AGENT_NAME", raising=False)

    from commands import send
    from lib import delivery, reports

    monkeypatch.setattr(reports, "infer_context", lambda: {})

    args = argparse.Namespace(
        target="worker",
        message="hello from nowhere",
        sender=None,
        dedupe_key="unit-no-sender",
        force=False,
    )

    result = send._send_tmux(args, object(), delivery, terminal_target="tmux:fleet:%1")

    assert result["ok"] is False
    assert result["reason"] == "sender-not-inferred"


def test_send_refuses_unmanaged_explicit_sender(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import send
    from lib import delivery

    args = argparse.Namespace(
        target="worker",
        message="hello from raw bash",
        sender="runway-engineering:bash",
        dedupe_key="unit-unmanaged-sender",
        force=False,
    )

    result = send._send_tmux(args, object(), delivery, terminal_target="tmux:fleet:%1")

    assert result["ok"] is False
    assert result["reason"] == "sender-not-inferred"


def test_send_tmux_attempted_record_has_attempt_evidence(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import send
    from lib import delivery
    _register_sender()

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
        sender="unitfleet:lead",
        dedupe_key="unit-deliver",
        force=False,
    )

    result = send._send_tmux(args, FakeTerminal, delivery, terminal_target="tmux:fleet:%1")

    assert result["ok"] is True
    record = result["record"]
    assert record["schema"] == "aura.delivery.v2"
    assert record["delivery_type"] == "semantic_send"
    assert record["state"] == "attempted"
    assert [attempt["state"] for attempt in record["attempts"]] == ["pending", "attempted"]
    assert record["attempts"][-1]["evidence"]["submitted_verified"] is None

    lines = (tmp_path / "deliveries.jsonl").read_text(encoding="utf-8").splitlines()
    parsed = [json.loads(line) for line in lines]
    assert parsed[-1]["schema"] == "aura.delivery.v2"

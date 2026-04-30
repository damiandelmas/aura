import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_clawhip_deliver_prepares_canonical_reply_handle(monkeypatch):
    monkeypatch.setenv("AURA_CLAWHIP_BIN", "/missing/clawhip")

    from lib import event_sidecar

    result = event_sidecar.deliver_human_message("flex-leaders-2:engineer", "hello")

    assert result["ok"] is False
    assert result["category"] == "sidecar-unavailable"
    assert result["event"]["kind"] == "human.message.outbound"
    assert result["event"]["payload"]["reply_handle"] == "@{flex-leaders-2:engineer}"
    assert result["rendered"] == "@{flex-leaders-2:engineer} hello"


def test_clawhip_register_runtime_uses_aura_seat_truth(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / ".aura" / "registry" / "seats.json"))
    monkeypatch.setenv("AURA_CLAWHIP_BIN", "/missing/clawhip")

    from commands import clawhip
    from lib import registry

    registry.upsert_agent({
        "name": "engineer",
        "fleet": "flex-leaders-2",
        "runtime": "codex",
        "pane_ref": "tmux:flex-leaders-2:%291",
        "session_id": "codex-thread",
    })

    result = clawhip.run(argparse.Namespace(clawhip_action="register-seat", seat="engineer", channel="discord:aura-ops"))

    assert result["ok"] is False
    assert result["event"]["kind"] == "runtime.register"
    assert result["registration"]["seat_key"] == "flex-leaders-2:engineer"
    assert result["registration"]["reply_handle"] == "@{flex-leaders-2:engineer}"
    assert result["registration"]["pane_ref"] == "tmux:flex-leaders-2:%291"


def test_clawhip_emit_returns_structured_unavailable(monkeypatch):
    monkeypatch.setenv("AURA_CLAWHIP_BIN", "/missing/clawhip")

    from commands import clawhip

    result = clawhip.run(argparse.Namespace(clawhip_action="emit", kind="unit.test", payload_json='{"x": 1}'))

    assert result["ok"] is False
    assert result["category"] == "sidecar-unavailable"
    assert result["event"]["kind"] == "unit.test"
    assert result["event"]["payload"] == {"x": 1}


def test_clawhip_deliver_executes_available_sidecar_and_records_evidence(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))
    fake = tmp_path / "clawhip"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = \"status\" ]; then echo '{\"ok\":true,\"mode\":\"fake\"}'; exit 0; fi\n"
        "if [ \"$1\" = \"send\" ]; then echo '{\"ok\":true,\"message_id\":\"sidecar-1\"}'; exit 0; fi\n"
        "echo '{\"ok\":true}'\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    monkeypatch.setenv("AURA_CLAWHIP_BIN", str(fake))

    from lib import delivery, event_sidecar

    result = event_sidecar.deliver_human_message("flex-leaders-2:engineer", "hello", channel="discord:aura-ops")

    assert result["ok"] is True
    assert result["state"] == "delivered"
    assert result["sidecar_result"]["data"]["message_id"] == "sidecar-1"
    records = delivery.iter_records()
    assert records[-1]["delivery_type"] == "sidecar_delivery"
    assert records[-1]["backend"] == "clawhip"


def test_clawhip_verify_bindings_executes_available_sidecar(monkeypatch, tmp_path):
    fake = tmp_path / "clawhip"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = \"status\" ]; then echo '{\"ok\":true}'; exit 0; fi\n"
        "if [ \"$1\" = \"config\" ]; then echo '{\"missing\":[\"DISCORD_TOKEN\"],\"forbidden\":[]}'; exit 0; fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    monkeypatch.setenv("AURA_CLAWHIP_BIN", str(fake))

    from lib import event_sidecar

    result = event_sidecar.verify_bindings()

    assert result["ok"] is True
    assert result["bindings"]["missing"] == ["DISCORD_TOKEN"]

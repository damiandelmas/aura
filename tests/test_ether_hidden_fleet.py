import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_discord_rejects_explicit_hidden_target(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import discord_bridge
    from lib import registry

    registry.upsert_agent({
        "name": "ether",
        "fleet": "_aura-ether",
        "runtime": "codex",
        "hidden": True,
        "kind": "ether",
        "pane_ref": "tmux:_aura-ether:%1",
    })

    result = discord_bridge._resolve_route_target("_aura-ether:ether")

    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "target-hidden"


def test_discord_ambiguous_candidates_use_braced_handles(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import discord_bridge
    from lib import registry

    registry.upsert_agent({"name": "engineer", "fleet": "one", "pane_ref": "tmux:one:%1"})
    registry.upsert_agent({"name": "engineer", "fleet": "two", "pane_ref": "tmux:two:%2"})
    monkeypatch.setattr(discord_bridge, "_is_live", lambda agent: True)

    result = discord_bridge._resolve_route_target("engineer")

    assert result["ambiguous"] is True
    assert result["candidates"] == ["@{one:engineer}", "@{two:engineer}"]


def test_discord_inbound_route_records_delivery_ledger(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))

    from commands import discord_bridge
    from lib import delivery, registry

    registry.upsert_agent({"name": "engineer", "fleet": "one", "pane_ref": "tmux:one:%1"})
    monkeypatch.setattr(discord_bridge, "_is_live", lambda agent: True)

    def fake_run(cmd, text=True, capture_output=True, env=None):
        return type("Result", (), {
            "returncode": 0,
            "stdout": json.dumps({"ok": True, "message_id": "aura-msg-routed", "submitted_verified": True}),
            "stderr": "",
        })()

    monkeypatch.setattr(discord_bridge.subprocess, "run", fake_run)

    result = discord_bridge._send_to_aura("one:engineer", "hello", "discord:damian")

    assert result["ok"] is True
    record = delivery.iter_records()[-1]
    assert record["delivery_type"] == "human_inbound_route"
    assert record["target"] == "one:engineer"
    assert record["route_result"]["message_id"] == "aura-msg-routed"


def test_discord_ack_names_deferred_delivery_id():
    from commands import discord_bridge

    ack = discord_bridge._ack_for_result(
        "one:engineer",
        {
            "ok": True,
            "blocked": True,
            "deferred": True,
            "reason": "target-busy",
            "deferred_record": {"deferred_id": "aura-defer-123"},
        },
    )

    assert ack == "deferred for `one:engineer`: target-busy; deferred `aura-defer-123`"

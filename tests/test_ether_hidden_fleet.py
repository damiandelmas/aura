import asyncio
import json
import sys
from pathlib import Path
import pytest


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

    observed = {}

    def fake_run(cmd, text=True, capture_output=True, env=None):
        observed["cmd"] = cmd
        return type("Result", (), {
            "returncode": 0,
            "stdout": json.dumps({"ok": True, "message_id": "aura-msg-routed", "submitted_verified": True}),
            "stderr": "",
        })()

    monkeypatch.setattr(discord_bridge.subprocess, "run", fake_run)

    result = discord_bridge._send_to_aura("one:engineer", "hello", "discord:damian")

    assert result["ok"] is True
    assert observed["cmd"][observed["cmd"].index("send") + 1] == "one:engineer"
    assert "--as-service" in observed["cmd"]
    assert observed["cmd"][observed["cmd"].index("--as-service") + 1] == "discord-damian"
    assert "--force" in observed["cmd"]
    record = delivery.iter_records()[-1]
    assert record["delivery_type"] == "human_inbound_route"
    assert record["target"] == "one:engineer"
    assert record["route_result"]["message_id"] == "aura-msg-routed"


def test_discord_plain_reply_uses_last_explicit_target(tmp_path):
    from commands import discord_bridge

    state_path = tmp_path / "routes.json"

    assert discord_bridge._route_for_message("plain hello", "channel-1", "user-1", path=state_path) is None
    assert discord_bridge._route_for_message("@{one:engineer} hello", "channel-1", "user-1", path=state_path) == (
        "one:engineer",
        "hello",
        True,
    )

    discord_bridge._remember_last_target(
        "channel-1",
        "user-1",
        "one:engineer",
        "discord:damian",
        path=state_path,
    )

    assert discord_bridge._route_for_message("plain hello", "channel-1", "user-1", path=state_path) == (
        "one:engineer",
        "plain hello",
        False,
    )
    assert discord_bridge._route_for_message("plain hello", "channel-1", "user-2", path=state_path) is None


def test_discord_channel_binding_routes_plain_messages_and_seat_mentions(tmp_path):
    from commands import discord_bridge

    bindings_path = tmp_path / "channel-bindings.json"
    discord_bridge._write_channel_bindings(
        {
            "schema": "aura.discord.channel_bindings.v1",
            "channels": {
                "channel-1": {
                    "fleet": "one",
                    "default_seat": "manager",
                    "aliases": {"gm": "general-manager", "eyes": "other:eyes"},
                }
            },
        },
        path=bindings_path,
    )

    assert discord_bridge._route_for_message(
        "plain hello",
        "channel-1",
        "user-1",
        bindings_path=bindings_path,
    ) == ("one:manager", "plain hello", False)
    assert discord_bridge._route_for_message(
        "@engineer fix this",
        "channel-1",
        "user-1",
        bindings_path=bindings_path,
    ) == ("one:engineer", "fix this", True)
    assert discord_bridge._route_for_message(
        "@gm status",
        "channel-1",
        "user-1",
        bindings_path=bindings_path,
    ) == ("one:general-manager", "status", True)
    assert discord_bridge._route_for_message(
        "@eyes check",
        "channel-1",
        "user-1",
        bindings_path=bindings_path,
    ) == ("other:eyes", "check", True)


def test_discord_can_send_to_hermes_ingress(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))
    monkeypatch.setenv("HERMES_INGRESS_URL", "http://ingress.local/v1/messages")

    from commands import discord_bridge
    from lib import delivery

    observed = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        observed["url"] = url
        observed["payload"] = json
        observed["timeout"] = timeout

        class Response:
            status_code = 202
            text = ""

            def json(self):
                return {"ok": True, "id": "http-ingress-123", "status": "accepted"}

        return Response()

    monkeypatch.setattr(discord_bridge.requests, "post", fake_post)

    result = discord_bridge._send_to_target("hermes:context-owner", "hello", "discord:damian")

    assert result["ok"] is True
    assert result["message_id"] == "http-ingress-123"
    assert observed["url"] == "http://ingress.local/v1/messages"
    assert observed["timeout"] == 180
    assert observed["payload"]["target"] == "hermes:context-owner"
    assert observed["payload"]["from"] == "service:discord-damian"
    record = delivery.iter_records()[-1]
    assert record["delivery_type"] == "human_inbound_route"
    assert record["target"] == "hermes:context-owner"


def test_discord_listened_channels_include_bindings(tmp_path):
    from commands import discord_bridge

    bindings_path = tmp_path / "channel-bindings.json"
    discord_bridge._write_channel_bindings(
        {
            "schema": "aura.discord.channel_bindings.v1",
            "channels": {
                "bound-channel": {},
                "hermes-channel": {"default_target": "hermes:context-owner"},
            },
        },
        path=bindings_path,
    )

    assert discord_bridge._listened_channel_ids("default-channel", path=bindings_path) == {
        "default-channel",
        "bound-channel",
    }


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


def test_discord_ack_uses_hermes_node_response():
    from commands import discord_bridge

    ack = discord_bridge._ack_for_result(
        "hermes:context-owner",
        {
            "ok": True,
            "message_id": "http-ingress-123",
            "response": "Context answer.",
        },
    )

    assert ack == "Context answer."


@pytest.mark.asyncio
async def test_discord_processing_reactions_swap_eyes_for_result():
    from commands import discord_bridge

    class Message:
        def __init__(self):
            self.reactions = []

        async def add_reaction(self, emoji):
            self.reactions.append(("add", emoji))

        async def remove_reaction(self, emoji, user):
            self.reactions.append(("remove", emoji, user))

    message = Message()
    await discord_bridge._mark_processing_start(message)
    await discord_bridge._mark_processing_complete(message, "bot-user", True)

    assert message.reactions == [
        ("add", "👀"),
        ("remove", "👀", "bot-user"),
        ("add", "✅"),
    ]


@pytest.mark.asyncio
async def test_discord_processing_reactions_mark_failure():
    from commands import discord_bridge

    class Message:
        def __init__(self):
            self.reactions = []

        async def add_reaction(self, emoji):
            self.reactions.append(("add", emoji))

        async def remove_reaction(self, emoji, user):
            self.reactions.append(("remove", emoji, user))

    message = Message()
    await discord_bridge._mark_processing_complete(message, "bot-user", False)

    assert message.reactions == [
        ("remove", "👀", "bot-user"),
        ("add", "❌"),
    ]


@pytest.mark.asyncio
async def test_discord_typing_indicator_runs_until_stopped():
    from commands import discord_bridge

    class Channel:
        def __init__(self):
            self.typing_calls = 0

        async def trigger_typing(self):
            self.typing_calls += 1

    channel = Channel()
    task = discord_bridge._start_typing_indicator(channel)
    await asyncio.sleep(0)
    await discord_bridge._stop_typing_indicator(task)

    assert channel.typing_calls == 1


@pytest.mark.asyncio
async def test_discord_typing_indicator_errors_do_not_escape():
    from commands import discord_bridge

    class Channel:
        async def trigger_typing(self):
            raise RuntimeError("typing denied")

    task = discord_bridge._start_typing_indicator(Channel())
    await asyncio.sleep(0)
    await discord_bridge._stop_typing_indicator(task)

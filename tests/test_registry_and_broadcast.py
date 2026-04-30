import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_registry_round_trip_and_fleet_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    from lib import registry

    registry.upsert_agent({
        "name": "c1",
        "fleet": "testfleet",
        "runtime": "claude-code",
        "terminal_ref": "testfleet:c1",
    })

    agent = registry.get_agent("c1", fleet="testfleet")
    assert agent["registered"] is True
    assert agent["runtime"] == "claude-code"
    assert agent["trace_cell"] == "claude_code"

    assert [a["name"] for a in registry.list_agents("testfleet")] == ["c1"]
    assert registry.list_agents("other") == []


def test_hidden_registry_agents_are_excluded_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    from lib import registry

    registry.upsert_agent({
        "name": "worker",
        "fleet": "visible",
        "runtime": "codex",
    })
    registry.upsert_agent({
        "name": "ether-coordinator",
        "fleet": "_aura-ether",
        "runtime": "codex",
        "hidden": True,
        "kind": "ether",
    })

    assert [a["name"] for a in registry.list_agents()] == ["worker"]
    hidden = registry.list_agents(include_hidden=True)
    assert [a["name"] for a in hidden] == ["ether-coordinator", "worker"]
    assert registry.is_hidden_agent(registry.get_agent("ether-coordinator")) is True


def test_get_agent_prefers_current_fleet_and_accepts_fleet_qualified_name(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "flexgraph-leaders")
    from lib import registry

    registry.upsert_agent({"name": "engineer", "fleet": "flex-leaders-2", "runtime": "codex"})
    registry.upsert_agent({"name": "engineer", "fleet": "flexgraph-leaders", "runtime": "codex"})

    assert registry.get_agent("engineer")["fleet"] == "flexgraph-leaders"
    assert registry.get_agent("flex-leaders-2:engineer")["fleet"] == "flex-leaders-2"


def test_send_blocks_hidden_targets_without_operator_override(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    from commands import send
    from lib import registry

    registry.upsert_agent({
        "name": "ether-coordinator",
        "fleet": "_aura-ether",
        "runtime": "codex",
        "hidden": True,
        "kind": "ether",
        "pane_ref": "tmux:_aura-ether:%1",
    })

    args = argparse.Namespace(
        target="ether-coordinator",
        message="hello",
        sender="tester",
        mode=None,
        nudge=False,
        transport="tmux",
        dedupe_key=None,
        force=False,
        allow_hidden=False,
    )

    result = send.run(args)

    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "target-hidden"


def test_broadcast_targets_registered_fleet_agents_and_excludes_shell(monkeypatch):
    from commands import broadcast

    registry_agents = [
        {"name": "claude1", "fleet": "triad", "registered": True},
        {"name": "hermes1", "fleet": "triad", "registered": True},
    ]

    class FakeRegistry:
        @staticmethod
        def list_agents(fleet=None, include_hidden=False):
            return [a for a in registry_agents if fleet is None or a.get("fleet") == fleet]
        @staticmethod
        def is_hidden_agent(record):
            return bool(record.get("hidden")) or record.get("kind") == "ether" or str(record.get("fleet") or "").startswith("_")
        @staticmethod
        def is_hidden_fleet(fleet):
            return bool(fleet and str(fleet).startswith("_"))

    class FakeTerminal:
        @staticmethod
        def list_windows():
            return ["bash", "codex1"]

    sent = []

    class FakeSend:
        @staticmethod
        def run(args):
            sent.append((args.target, args.message, args.transport))
            return {"ok": True, "target": args.target}

    monkeypatch.setattr(broadcast, "_registry", FakeRegistry)
    monkeypatch.setattr(broadcast, "_terminal", FakeTerminal)
    monkeypatch.setattr(broadcast, "_send", FakeSend)

    args = argparse.Namespace(
        fleet="triad",
        fleet_arg=None,
        message="ping",
        sender="cli",
        transport="tmux",
        dedupe_key=None,
        force=False,
        include_shell=False,
        allow_hidden=False,
    )
    result = broadcast.run(args)

    assert result["ok"] is True
    assert result["count"] == 3
    assert [x[0] for x in sent] == ["claude1", "hermes1", "codex1"]
    assert all(x[1] == "ping" for x in sent)


def test_broadcast_parses_message_when_fleet_flag_is_set(monkeypatch):
    from commands import broadcast

    class FakeRegistry:
        @staticmethod
        def list_agents(fleet=None, include_hidden=False):
            return [{"name": "claude1", "fleet": fleet, "registered": True}]
        @staticmethod
        def is_hidden_agent(record):
            return bool(record.get("hidden")) or record.get("kind") == "ether" or str(record.get("fleet") or "").startswith("_")
        @staticmethod
        def is_hidden_fleet(fleet):
            return bool(fleet and str(fleet).startswith("_"))

    class FakeTerminal:
        SESSION_NAME = "other"
        @staticmethod
        def list_windows():
            return []

    sent = []
    class FakeSend:
        @staticmethod
        def run(args):
            sent.append((args.target, args.message))
            return {"ok": True}

    monkeypatch.setattr(broadcast, "_registry", FakeRegistry)
    monkeypatch.setattr(broadcast, "_terminal", FakeTerminal)
    monkeypatch.setattr(broadcast, "_send", FakeSend)

    args = argparse.Namespace(
        fleet="triad",
        parts=["hello", "world"],
        sender="cli",
        transport="tmux",
        dedupe_key=None,
        force=False,
        include_shell=False,
        allow_hidden=False,
    )
    result = broadcast.run(args)

    assert result["fleet"] == "triad"
    assert sent == [("claude1", "hello world")]


def test_broadcast_blocks_hidden_fleet_without_operator_override(monkeypatch):
    from commands import broadcast

    class FakeRegistry:
        @staticmethod
        def current_fleet():
            return "_aura-ether"
        @staticmethod
        def list_agents(fleet=None, include_hidden=False):
            return [{"name": "ether", "fleet": "_aura-ether", "kind": "ether", "hidden": True}]
        @staticmethod
        def is_hidden_agent(record):
            return bool(record.get("hidden")) or record.get("kind") == "ether" or str(record.get("fleet") or "").startswith("_")
        @staticmethod
        def is_hidden_fleet(fleet):
            return bool(fleet and str(fleet).startswith("_"))

    monkeypatch.setattr(broadcast, "_registry", FakeRegistry)

    result = broadcast.run(argparse.Namespace(
        fleet="_aura-ether",
        parts=["ping"],
        sender="cli",
        transport="tmux",
        dedupe_key=None,
        force=False,
        include_shell=False,
        allow_hidden=False,
    ))

    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "target-hidden"

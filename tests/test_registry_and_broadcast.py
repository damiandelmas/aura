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


def test_broadcast_targets_registered_fleet_agents_and_excludes_shell(monkeypatch):
    from commands import broadcast

    registry_agents = [
        {"name": "claude1", "fleet": "triad", "registered": True},
        {"name": "hermes1", "fleet": "triad", "registered": True},
    ]

    class FakeRegistry:
        @staticmethod
        def list_agents(fleet=None):
            return [a for a in registry_agents if fleet is None or a.get("fleet") == fleet]

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
        def list_agents(fleet=None):
            return [{"name": "claude1", "fleet": fleet, "registered": True}]

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
    )
    result = broadcast.run(args)

    assert result["fleet"] == "triad"
    assert sent == [("claude1", "hello world")]

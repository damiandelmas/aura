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


def test_rehome_preserves_physical_refs_and_adds_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    registry.upsert_agent({
        "name": "old-seat",
        "fleet": "old-fleet",
        "runtime": "codex",
        "session_id": "session-1",
        "runtime_session_id": "session-1",
        "terminal_ref": "old-fleet:old-seat",
        "backend_ref": "old-fleet:old-seat",
        "pane_ref": "tmux:old-fleet:%12",
        "cwd": "/tmp/repo",
    })

    result = registry.rehome_agent(
        "old-fleet:old-seat",
        new_name="leader-engine",
        new_fleet="flex-leaders",
        metadata={"desks_role_id": "leader-engine", "desks_product": "flex"},
    )

    assert result["ok"] is True
    assert result["source"] == "old-fleet:old-seat"
    assert result["target"] == "flex-leaders:leader-engine"
    assert registry.get_agent("old-fleet:old-seat")["name"] == "leader-engine"
    assert registry.get_agent("old-fleet:old-seat")["resolved_from"] == "old-fleet:old-seat"
    moved = registry.get_agent("flex-leaders:leader-engine")
    assert moved["fleet"] == "flex-leaders"
    assert moved["seat_ref"] == "flex-leaders:leader-engine"
    assert moved["pane_ref"] == "tmux:old-fleet:%12"
    assert moved["backend_ref"] == "old-fleet:old-seat"
    assert moved["session_id"] == "session-1"
    assert moved["desks_role_id"] == "leader-engine"
    assert moved["desks_product"] == "flex"
    assert registry.read_aliases()["old-fleet:old-seat"]["target"] == "flex-leaders:leader-engine"


def test_seat_rehome_command_loads_role_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import seat
    from lib import registry

    role_home = tmp_path / "roles" / "leader-engine"
    role_home.mkdir(parents=True)
    for name in ("SOUL.md", "AGENTS.md", "MEMORY.md", "BOOTSTRAP.md", "COMPRESSION.md"):
        (role_home / name).write_text(name, encoding="utf-8")
    (role_home / "role.json").write_text(
        '''{
          "schema": "desks.role.v1",
          "product": "flex",
          "unit": "engine",
          "role_id": "leader-engine",
          "seat": "leader-engine",
          "fleet": "flex-leaders",
          "workspace_root": "/tmp",
          "files": {
            "soul": "SOUL.md",
            "agents": "AGENTS.md",
            "memory": "MEMORY.md",
            "bootstrap": "BOOTSTRAP.md",
            "compression": "COMPRESSION.md"
          }
        }''',
        encoding="utf-8",
    )
    registry.upsert_agent({
        "name": "old-seat",
        "fleet": "old-fleet",
        "runtime": "codex",
        "pane_ref": "tmux:old-fleet:%12",
    })

    result = seat.run(argparse.Namespace(
        seat_action="rehome",
        source="old-fleet:old-seat",
        name="leader-engine",
        fleet="flex-leaders",
        role_home=str(role_home),
        manifest=None,
        no_alias_old=False,
    ))

    assert result["ok"] is True
    moved = registry.get_agent("flex-leaders:leader-engine")
    assert moved["desks_role_home"] == str(role_home)
    assert moved["desks_role_id"] == "leader-engine"
    assert moved["desks_product"] == "flex"
    assert moved["desks_unit"] == "engine"


def test_seat_rehome_move_terminal_updates_physical_refs(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "old-seat",
        "fleet": "old-fleet",
        "runtime": "codex",
        "pane_ref": "tmux:old-fleet:%12",
        "terminal_ref": "old-fleet:old-seat",
        "backend_ref": "old-fleet:old-seat",
    })

    def fake_move_terminal(record, *, fleet, name, index):
        assert record["pane_ref"] == "tmux:old-fleet:%12"
        assert fleet == "new-fleet"
        assert name == "new-seat"
        assert index == "2"
        return {
            "ok": True,
            "terminal_ref": "new-fleet:new-seat",
            "backend_ref": "new-fleet:new-seat",
            "pane_ref": "tmux:new-fleet:%12",
            "physical_fleet": "new-fleet",
        }

    monkeypatch.setattr(seat, "_move_terminal", fake_move_terminal)
    result = seat.run(argparse.Namespace(
        seat_action="rehome",
        source="old-fleet:old-seat",
        name="new-seat",
        fleet="new-fleet",
        role_home=None,
        manifest=None,
        move_terminal=True,
        index="2",
        no_alias_old=False,
    ))

    assert result["ok"] is True
    moved = registry.get_agent("new-fleet:new-seat")
    assert moved["terminal_ref"] == "new-fleet:new-seat"
    assert moved["backend_ref"] == "new-fleet:new-seat"
    assert moved["pane_ref"] == "tmux:new-fleet:%12"
    assert moved["physical_fleet"] == "new-fleet"


def test_seat_rehome_index_requires_move_terminal(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import seat

    result = seat.run(argparse.Namespace(
        seat_action="rehome",
        source="old-fleet:old-seat",
        name="new-seat",
        fleet="new-fleet",
        role_home=None,
        manifest=None,
        move_terminal=False,
        index="2",
        no_alias_old=False,
    ))

    assert result["ok"] is False
    assert "--index requires --move-terminal" in result["error"]


def test_seat_cut_routes_through_cut_command(monkeypatch):
    from commands import seat

    seen = {}

    def fake_cut(args):
        seen["args"] = args
        return {"ok": True, "name": args.name, "cut": True}

    monkeypatch.setattr("commands.cut.run", fake_cut)
    result = seat.run(argparse.Namespace(
        seat_action="cut",
        name="fleet:worker",
        force=True,
    ))

    assert seen["args"].name == "fleet:worker"
    assert seen["args"].force is True
    assert result["ok"] is True
    assert result["seat_cut"] is True
    assert result["seat"] == "fleet:worker"


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

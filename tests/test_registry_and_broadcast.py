import argparse
import os
import subprocess
import sys
from multiprocessing import Process
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _registry_upsert_worker(state_dir: str, name: str):
    os.environ["AURA_STATE_DIR"] = state_dir
    from lib import registry

    registry.upsert_agent({
        "name": name,
        "fleet": "race-fleet",
        "runtime": "codex",
        "pane_ref": f"tmux:race-fleet:%{name.removeprefix('worker')}",
    })


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


def test_registry_strips_transient_projection_and_prompt_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    from lib import registry

    registry.upsert_agent({
        "name": "c1",
        "fleet": "testfleet",
        "runtime": "codex",
        "terminal_ref": "testfleet:c1",
        "prompt_sent": True,
        "agent_map_ready": True,
        "agent_map_injected": True,
        "alias_chain": ["testfleet:old"],
        "prompt_submit_retry": {"ok": True},
        "resolved_from": "testfleet:old",
        "flex_project_packet_delivered": True,
        "flex_project_packet_delivered_at": "2026-05-07T00:00:00+00:00",
        "flex_project_packet_source": "spawn.prompt",
        "flex_project_packet_manifest": "/tmp/project.yaml",
        "flex_project_packet_session_key": "session-1",
        "managed_state": "spawned_bound",
        "restore_ready": True,
        "restore_reason": "bound",
        "risk_flags": ["example"],
        "liveness": "alive",
    })

    agent = registry.get_agent("c1", fleet="testfleet")
    for key in registry.TRANSIENT_AGENT_FIELDS:
        assert key not in agent


def test_registry_upserts_are_safe_across_parallel_processes(tmp_path, monkeypatch):
    state_dir = str(tmp_path / ".aura")
    workers = [
        Process(target=_registry_upsert_worker, args=(state_dir, f"worker{index}"))
        for index in range(8)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(10)
        assert worker.exitcode == 0

    from lib import registry

    monkeypatch.setenv("AURA_STATE_DIR", state_dir)
    names = {row["name"] for row in registry.list_agents("race-fleet")}
    assert names == {f"worker{index}" for index in range(8)}


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


def test_rehome_repairs_same_incarnation_duplicate_target(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    registry.upsert_agent({
        "name": "operator",
        "fleet": "aura-refresh-test",
        "runtime": "codex",
        "seat_instance_id": "si_same",
        "pane_ref": "tmux:aura-refresh-test:%341",
        "runtime_session_id": "session-same",
        "terminal_ref": "aura-refresh-test:operator",
        "backend_ref": "aura-refresh-test:operator",
    })
    registry.upsert_agent({
        "name": "pilot",
        "fleet": "aura-refresh-test",
        "runtime": "codex",
        "seat_instance_id": "si_same",
        "pane_ref": "tmux:aura-refresh-test:%341",
        "runtime_session_id": "session-same",
        "terminal_ref": "aura-refresh-test:pilot",
        "backend_ref": "aura-refresh-test:pilot",
        "rehome_source": "aura-refresh-test:operator",
    })

    result = registry.rehome_agent("aura-refresh-test:operator", new_name="pilot")

    assert result["ok"] is True
    assert result["repair_duplicate"] is True
    assert registry.read_registry().keys() == {"aura-refresh-test:pilot"}
    assert registry.get_agent("aura-refresh-test:pilot")["seat_instance_id"] == "si_same"
    assert registry.get_agent("aura-refresh-test:operator")["resolved_from"] == "aura-refresh-test:operator"
    assert registry.read_aliases()["aura-refresh-test:operator"]["target"] == "aura-refresh-test:pilot"


def test_rehome_rejects_different_incarnation_target(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    registry.upsert_agent({
        "name": "operator",
        "fleet": "aura-refresh-test",
        "runtime": "codex",
        "seat_instance_id": "si_source",
        "pane_ref": "tmux:aura-refresh-test:%341",
    })
    registry.upsert_agent({
        "name": "pilot",
        "fleet": "aura-refresh-test",
        "runtime": "codex",
        "seat_instance_id": "si_dest",
        "pane_ref": "tmux:aura-refresh-test:%342",
    })

    result = registry.rehome_agent("aura-refresh-test:operator", new_name="pilot")

    assert result["ok"] is False
    assert result["reason"] == "target-registry-exists"
    assert set(registry.read_registry().keys()) == {"aura-refresh-test:operator", "aura-refresh-test:pilot"}


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
    monkeypatch.setenv("AURA_ENABLE_UNSAFE_MOVE_TERMINAL", "1")
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


def test_seat_rehome_move_terminal_refreshes_stale_pane_ref(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_ENABLE_UNSAFE_MOVE_TERMINAL", "1")
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "developer",
        "fleet": "flex-desk",
        "runtime": "codex",
        "aura_launch_id": "aura-launch-real",
        "runtime_session_id": "session-real",
        "pane_ref": "tmux:flex-desks:%770",
        "terminal_ref": "flex-desks:developer",
        "backend_ref": "flex-desks:developer",
    })

    monkeypatch.setattr(seat, "_list_tmux_panes", lambda: [
        {"session": "flex-desks", "window_index": "7", "window_name": "developer-stale", "pane_id": "%770", "pane_pid": 770},
        {"session": "flex-desk", "window_index": "1", "window_name": "developer", "pane_id": "%789", "pane_pid": 789},
    ])

    def fake_discover(record, pane):
        if pane["pane_id"] == "%789":
            return {
                "runtime_session_id": "session-real",
                "runtime_session_evidence": {"aura_launch_id": "aura-launch-real"},
            }
        return {}

    monkeypatch.setattr(seat, "_discover_pane", fake_discover)

    calls = []

    def fake_run_tmux(args):
        calls.append(args)
        if args[:3] == ["display-message", "-p", "-t"]:
            target = args[3]
            fmt = args[4]
            if target == "flex-desks:%770" and "pane_pid" in fmt:
                return subprocess.CompletedProcess(args, 0, stdout="flex-desks\t7\tdeveloper-stale\t%770\t770\n", stderr="")
            if target == "flex-desk:%789" and fmt == "#{session_name}:#{window_index}:#{pane_id}":
                return subprocess.CompletedProcess(args, 0, stdout="flex-desk:1:%789\n", stderr="")
            if target == "%789" and fmt == "#{session_name}:#{window_index}:#{window_name}:#{pane_id}":
                return subprocess.CompletedProcess(args, 0, stdout="flex-desks:8:developer:%789\n", stderr="")
        if args[:2] == ["has-session", "-t"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:2] == ["move-window", "-s"]:
            assert args[2] == "flex-desk:1"
            assert args[4] == "flex-desks:"
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:2] == ["rename-window", "-t"]:
            assert args[2] == "%789"
            assert args[3] == "developer"
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected")

    monkeypatch.setattr(seat, "_run_tmux", fake_run_tmux)

    result = seat.run(argparse.Namespace(
        seat_action="rehome",
        source="flex-desk:developer",
        name="developer",
        fleet="flex-desks",
        role_home=None,
        manifest=None,
        move_terminal=True,
        index=None,
        no_alias_old=False,
    ))

    assert result["ok"] is True
    moved = registry.get_agent("flex-desks:developer")
    assert moved["pane_ref"] == "tmux:flex-desks:%789"
    assert moved["rehome_source_refreshed"] is True
    assert moved["rehome_previous_pane_ref"] == "tmux:flex-desks:%770"


def test_seat_rehome_move_terminal_refuses_destination_collision(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_ENABLE_UNSAFE_MOVE_TERMINAL", "1")
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "developer",
        "fleet": "flex-desk",
        "runtime": "codex",
        "aura_launch_id": "aura-launch-real",
        "runtime_session_id": "session-real",
        "pane_ref": "tmux:flex-desk:%789",
        "terminal_ref": "flex-desk:developer",
        "backend_ref": "flex-desk:developer",
    })

    def fake_discover(record, pane):
        if pane["pane_id"] == "%789":
            return {
                "runtime_session_id": "session-real",
                "runtime_session_evidence": {"aura_launch_id": "aura-launch-real"},
            }
        return {}

    monkeypatch.setattr(seat, "_discover_pane", fake_discover)

    def fake_run_tmux(args):
        if args[:3] == ["display-message", "-p", "-t"]:
            target = args[3]
            fmt = args[4]
            if target == "flex-desk:%789" and "pane_pid" in fmt:
                return subprocess.CompletedProcess(args, 0, stdout="flex-desk\t1\tdeveloper\t%789\t789\n", stderr="")
            if target == "flex-desk:%789" and fmt == "#{session_name}:#{window_index}:#{pane_id}":
                return subprocess.CompletedProcess(args, 0, stdout="flex-desk:1:%789\n", stderr="")
            if target == "flex-desks:developer" and "pane_pid" in fmt:
                return subprocess.CompletedProcess(args, 0, stdout="flex-desks\t7\tdeveloper\t%770\t770\n", stderr="")
        if args[:2] == ["has-session", "-t"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:2] == ["move-window", "-s"]:
            raise AssertionError("should refuse before moving a colliding destination")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="unexpected")

    monkeypatch.setattr(seat, "_run_tmux", fake_run_tmux)

    result = seat.run(argparse.Namespace(
        seat_action="rehome",
        source="flex-desk:developer",
        name="developer",
        fleet="flex-desks",
        role_home=None,
        manifest=None,
        move_terminal=True,
        index=None,
        no_alias_old=False,
    ))

    assert result["ok"] is False
    assert result["reason"] == "target-window-exists"
    assert result["existing"]["pane_id"] == "%770"
    assert registry.get_agent("flex-desk:developer")["pane_ref"] == "tmux:flex-desk:%789"
    assert registry.get_agent("flex-desks:developer") is None


def test_seat_rehome_move_terminal_refuses_registry_collision_before_tmux(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_ENABLE_UNSAFE_MOVE_TERMINAL", "1")
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "operator",
        "fleet": "aura-refresh-test",
        "runtime": "codex",
        "seat_instance_id": "si_source",
        "pane_ref": "tmux:aura-refresh-test:%341",
    })
    registry.upsert_agent({
        "name": "pilot",
        "fleet": "aura-refresh-test",
        "runtime": "codex",
        "seat_instance_id": "si_dest",
        "pane_ref": "tmux:aura-refresh-test:%342",
    })

    def fail_move_terminal(record, *, fleet, name, index):
        raise AssertionError("registry collision should be rejected before tmux mutation")

    monkeypatch.setattr(seat, "_move_terminal", fail_move_terminal)

    result = seat.run(argparse.Namespace(
        seat_action="rehome",
        source="aura-refresh-test:operator",
        name="pilot",
        fleet=None,
        role_home=None,
        manifest=None,
        move_terminal=True,
        index=None,
        no_alias_old=False,
    ))

    assert result["ok"] is False
    assert result["reason"] == "target-registry-exists"
    assert set(registry.read_registry().keys()) == {"aura-refresh-test:operator", "aura-refresh-test:pilot"}


def test_seat_rehome_move_terminal_is_parked_by_default(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.delenv("AURA_ENABLE_UNSAFE_MOVE_TERMINAL", raising=False)
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "operator",
        "fleet": "aura-refresh-test",
        "runtime": "codex",
        "seat_instance_id": "si_source",
        "pane_ref": "tmux:aura-refresh-test:%341",
    })

    result = seat.run(argparse.Namespace(
        seat_action="rehome",
        source="aura-refresh-test:operator",
        name="pilot",
        fleet=None,
        role_home=None,
        manifest=None,
        move_terminal=True,
        index=None,
        no_alias_old=False,
    ))

    assert result["ok"] is False
    assert "parked" in result["error"]
    assert "holding discover" in result["safe_workflow"]
    assert registry.get_agent("aura-refresh-test:operator") is not None
    assert registry.get_agent("aura-refresh-test:pilot") is None


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


def test_seat_sweep_dry_run_lists_stale_registered_seats(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "alive",
        "fleet": "fleet",
        "runtime": "codex",
        "pane_ref": "tmux:fleet:%1",
    })
    registry.upsert_agent({
        "name": "stale",
        "fleet": "fleet",
        "runtime": "codex",
        "status": "dead",
        "pane_ref": "tmux:fleet:%2",
    })

    class FakeTerminal:
        @staticmethod
        def configure_session(fleet):
            return fleet

        @staticmethod
        def target_exists(target):
            return target == "tmux:fleet:%1"

    result = seat._sweep(argparse.Namespace(
        seat_action="sweep",
        fleet="fleet",
        include_hidden=False,
        confirm=False,
    ), registry, FakeTerminal)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["checked"] == 2
    assert result["alive"] == 1
    assert result["stale_count"] == 1
    assert result["suspect_count"] == 0
    assert result["stale"][0]["seat_ref"] == "fleet:stale"
    assert result["stale"][0]["checked_targets"] == ["tmux:fleet:%2"]
    assert registry.get_agent("stale", fleet="fleet") is not None


def test_seat_audit_reports_identity_and_instance_risks_without_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "alive",
        "fleet": "fleet",
        "runtime": "codex",
        "pane_ref": "tmux:fleet:%1",
        "seat_instance_id": "si_alive",
        "runtime_session_id": "session-1",
        "identity_provider": "desks",
        "identity_id": "r_alive",
    })
    registry.upsert_agent({
        "name": "stale",
        "fleet": "fleet",
        "runtime": "codex",
        "status": "dead",
        "pane_ref": "tmux:fleet:%2",
        "desks_identity_id": "r_stale",
    })

    before = registry.read_registry()

    class FakeTerminal:
        @staticmethod
        def configure_session(fleet):
            return fleet

        @staticmethod
        def target_exists(target):
            return target == "tmux:fleet:%1"

    monkeypatch.setattr(seat, "_pane_exists_anywhere", lambda pane_ref: False)

    result = seat._audit(argparse.Namespace(
        seat_action="audit",
        fleet="fleet",
        include_hidden=False,
    ), registry, FakeTerminal)

    assert result["ok"] is True
    assert result["schema"] == "aura.seat_audit.v1"
    assert result["read_only"] is True
    assert result["checked"] == 2
    by_ref = {row["seat_ref"]: row for row in result["rows"]}
    assert by_ref["fleet:alive"]["risk_flags"] == []
    stale_flags = set(by_ref["fleet:stale"]["risk_flags"])
    assert {
        "missing-pane",
        "dead-process",
        "identity-on-dead-row",
        "missing-seat-instance-id",
        "runtime-session-missing",
        "legacy-desks-alias-only",
    } <= stale_flags
    assert by_ref["fleet:stale"]["suggested_action"] == "archive-or-restore"
    assert registry.read_registry() == before


def test_seat_sweep_missing_active_seat_is_suspect_not_stale(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "worker",
        "fleet": "fleet",
        "runtime": "codex",
        "status": "idle",
        "terminal_ref": "fleet:old-name",
        "backend_ref": "fleet:old-name",
        "pane_ref": "tmux:fleet:%2",
    })

    class FakeTerminal:
        @staticmethod
        def configure_session(fleet):
            return fleet

        @staticmethod
        def target_exists(target):
            return False

    monkeypatch.setattr(seat, "_pane_exists_anywhere", lambda pane_ref: True)
    result = seat._sweep(argparse.Namespace(
        seat_action="sweep",
        fleet="fleet",
        include_hidden=False,
        confirm=True,
    ), registry, FakeTerminal)

    assert result["ok"] is True
    assert result["stale_count"] == 0
    assert result["suspect_count"] == 1
    assert result["suspect"][0]["seat_ref"] == "fleet:worker"
    assert result["suspect"][0]["reason"] == "registered-terminal-unverified"
    assert result["suspect"][0]["pane_exists_anywhere"] is True
    assert result["removed_count"] == 0
    assert registry.get_agent("worker", fleet="fleet") is not None


def test_seat_sweep_confirm_removes_stale_registered_seats(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "stale",
        "fleet": "fleet",
        "runtime": "codex",
        "status": "dead",
        "pane_ref": "tmux:fleet:%2",
    })

    class FakeTerminal:
        @staticmethod
        def configure_session(fleet):
            return fleet

        @staticmethod
        def target_exists(target):
            return False

    result = seat._sweep(argparse.Namespace(
        seat_action="sweep",
        fleet="fleet",
        include_hidden=False,
        confirm=True,
    ), registry, FakeTerminal)

    assert result["ok"] is True
    assert result["dry_run"] is False
    assert result["removed"] == ["fleet:stale"]
    assert registry.get_agent("stale", fleet="fleet") is None


def test_seat_archive_removes_non_live_row_and_writes_terminal_history(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import seat
    from lib import registry, session_ledger

    registry.upsert_agent({
        "name": "old-worker",
        "seat": "old-worker",
        "fleet": "fleet",
        "runtime": "codex",
        "status": "idle",
        "pane_ref": "tmux:fleet:%77",
        "runtime_session_id": "sess-1",
        "runtime_session_binding": "bound",
    })

    class FakeTerminal:
        @staticmethod
        def configure_session(fleet):
            return fleet

        @staticmethod
        def target_exists(target):
            return False

    monkeypatch.setattr(seat, "_pane_exists_anywhere", lambda pane_ref: False)

    result = seat._archive(argparse.Namespace(
        seat_action="archive",
        target="fleet:old-worker",
        reason="test-cleanup",
        force=False,
    ), registry, FakeTerminal)

    assert result["ok"] is True
    assert result["removed_current_row"] is True
    assert result["historical"] is True
    assert registry.get_agent("old-worker", fleet="fleet") is None

    rows = session_ledger.seat_history_for_target("fleet:old-worker")
    assert rows[-1]["event"] == "seat_archived"
    assert rows[-1]["after"]["status"] == "archived"
    latest = session_ledger.project_latest_from_ledger(fleet="fleet")
    assert latest[0]["restore_suppressed"] is True
    assert latest[0]["terminal_state"] == "terminal"


def test_seat_archive_refuses_live_row_without_force(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "worker",
        "fleet": "fleet",
        "runtime": "codex",
        "pane_ref": "tmux:fleet:%77",
    })

    class FakeTerminal:
        @staticmethod
        def configure_session(fleet):
            return fleet

        @staticmethod
        def target_exists(target):
            return target == "tmux:fleet:%77"

    monkeypatch.setattr(seat, "_pane_exists_anywhere", lambda pane_ref: True)

    result = seat._archive(argparse.Namespace(
        seat_action="archive",
        target="fleet:worker",
        reason=None,
        force=False,
    ), registry, FakeTerminal)

    assert result["ok"] is False
    assert result["error"] == "seat-appears-live"
    assert registry.get_agent("worker", fleet="fleet") is not None


def test_send_blocks_hidden_targets_without_operator_override(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.delenv("AURA_SEAT", raising=False)
    monkeypatch.delenv("AURA_AGENT_NAME", raising=False)
    monkeypatch.delenv("AURA_RUNTIME_SESSION_ID", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
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


def test_broadcast_live_scope_targets_registered_live_codex_seats(monkeypatch):
    from commands import broadcast

    registry_agents = [
        {"name": "engineer", "fleet": "flex", "runtime": "codex", "registered": True, "terminal_ref": "flex:engineer"},
        {"name": "runtime", "fleet": "flex", "runtime": "codex", "registered": True, "terminal_ref": "flex:runtime"},
        {"name": "shell", "fleet": "flex", "runtime": "shell", "registered": True, "terminal_ref": "flex:shell"},
        {"name": "dead", "fleet": "flex", "runtime": "codex", "registered": True, "terminal_ref": "flex:dead"},
        {"name": "ether", "fleet": "_aura-ether", "runtime": "codex", "registered": True, "hidden": True},
    ]

    class FakeRegistry:
        @staticmethod
        def list_agents(fleet=None, include_hidden=False):
            rows = [a for a in registry_agents if fleet is None or a.get("fleet") == fleet]
            if not include_hidden:
                rows = [a for a in rows if not FakeRegistry.is_hidden_agent(a)]
            return rows

        @staticmethod
        def is_hidden_agent(record):
            return bool(record.get("hidden")) or record.get("kind") == "ether" or str(record.get("fleet") or "").startswith("_")

        @staticmethod
        def is_hidden_fleet(fleet):
            return bool(fleet and str(fleet).startswith("_"))

    class FakeTerminal:
        @staticmethod
        def target_exists(target):
            return target in {"flex:engineer", "flex:runtime", "flex:shell"}

    sent = []

    class FakeSend:
        @staticmethod
        def run(args):
            sent.append((args.target, args.message, args.transport))
            return {"ok": True, "target": args.target}

    monkeypatch.setattr(broadcast, "_registry", FakeRegistry)
    monkeypatch.setattr(broadcast, "_terminal", FakeTerminal)
    monkeypatch.setattr(broadcast, "_send", FakeSend)

    result = broadcast.run(argparse.Namespace(
        scope="live",
        runtime="codex",
        parts=["bind", "now"],
        sender="cli",
        transport="tmux",
        dedupe_key="bind-run",
        force=False,
        include_shell=False,
        allow_hidden=False,
    ))

    assert result["ok"] is True
    assert result["schema"] == "aura.broadcast_live.v1"
    assert result["scope"] == "live"
    assert result["runtime"] == "codex"
    assert result["fleet_count"] == 1
    assert result["count"] == 2
    assert result["sent_count"] == 2
    assert result["failed_count"] == 0
    assert result["targets"] == ["flex:engineer", "flex:runtime"]
    assert sent == [
        ("flex:engineer", "bind now", "tmux"),
        ("flex:runtime", "bind now", "tmux"),
    ]


def test_broadcast_live_scope_reports_partial_failures(monkeypatch):
    from commands import broadcast

    class FakeRegistry:
        @staticmethod
        def list_agents(fleet=None, include_hidden=False):
            return [
                {"name": "ok-seat", "fleet": "flex", "runtime": "codex", "registered": True, "terminal_ref": "flex:ok-seat"},
                {"name": "bad-seat", "fleet": "flex", "runtime": "codex", "registered": True, "terminal_ref": "flex:bad-seat"},
            ]

        @staticmethod
        def is_hidden_agent(record):
            return False

        @staticmethod
        def is_hidden_fleet(fleet):
            return False

    class FakeTerminal:
        @staticmethod
        def target_exists(target):
            return True

    class FakeSend:
        @staticmethod
        def run(args):
            if args.target == "flex:bad-seat":
                return {"ok": False, "error": "blocked"}
            return {"ok": True}

    monkeypatch.setattr(broadcast, "_registry", FakeRegistry)
    monkeypatch.setattr(broadcast, "_terminal", FakeTerminal)
    monkeypatch.setattr(broadcast, "_send", FakeSend)

    result = broadcast.run(argparse.Namespace(
        scope="all-live",
        runtime=None,
        parts=["hello"],
        sender="cli",
        transport="auto",
        dedupe_key=None,
        force=False,
        include_shell=False,
        allow_hidden=False,
    ))

    assert result["ok"] is False
    assert result["count"] == 2
    assert result["sent_count"] == 1
    assert result["failed_count"] == 1

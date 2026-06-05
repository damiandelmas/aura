import argparse
import json
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


def test_registry_normalizes_core_refs_at_write_boundary(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    from lib import registry

    registry.upsert_agent({
        "name": "worker",
        "fleet": "fleet",
        "runtime": "codex",
        "status": "IDLE",
        "pane_ref": "%42",
        "backend_ref": "fleet:%42",
        "session_id": "session-1",
        "launch_id": "aura-launch-1",
    })

    agent = registry.get_agent("fleet:worker")
    assert agent["seat"] == "worker"
    assert agent["seat_ref"] == "fleet:worker"
    assert agent["target"] == "fleet:worker"
    assert agent["status"] == "idle"
    assert agent["pane_ref"] == "tmux:fleet:%42"
    assert agent["backend_ref"] == "tmux:fleet:%42"
    assert agent["runtime_ref"] == "codex"
    assert agent["runtime_session_id"] == "session-1"
    assert agent["session_id"] == "session-1"
    assert agent["aura_launch_id"] == "aura-launch-1"
    assert agent["launch_ref"] == "aura-launch-1"


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


def test_rename_preserves_physical_refs_and_adds_alias(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    registry.upsert_agent({
        "name": "old-seat",
        "fleet": "unit-fleet",
        "runtime": "codex",
        "session_id": "session-1",
        "runtime_session_id": "session-1",
        "terminal_ref": "unit-fleet:old-seat",
        "backend_ref": "unit-fleet:old-seat",
        "pane_ref": "tmux:unit-fleet:%12",
        "cwd": "/tmp/repo",
    })

    result = registry.rename_agent(
        "unit-fleet:old-seat",
        new_name="leader-engine",
        metadata={"identity_provider": "runway", "identity_id": "pos_leader_engine"},
    )

    assert result["ok"] is True
    assert result["source"] == "unit-fleet:old-seat"
    assert result["target"] == "unit-fleet:leader-engine"
    assert registry.get_agent("unit-fleet:old-seat")["name"] == "leader-engine"
    assert registry.get_agent("unit-fleet:old-seat")["resolved_from"] == "unit-fleet:old-seat"
    moved = registry.get_agent("unit-fleet:leader-engine")
    assert moved["fleet"] == "unit-fleet"
    assert moved["seat_ref"] == "unit-fleet:leader-engine"
    assert moved["pane_ref"] == "tmux:unit-fleet:%12"
    assert moved["backend_ref"] == "unit-fleet:old-seat"
    assert moved["session_id"] == "session-1"
    assert moved["identity_provider"] == "runway"
    assert moved["identity_id"] == "pos_leader_engine"
    assert moved["rename_source"] == "unit-fleet:old-seat"
    assert registry.read_aliases()["unit-fleet:old-seat"]["target"] == "unit-fleet:leader-engine"
    assert registry.read_aliases()["unit-fleet:old-seat"]["reason"] == "rename"


def test_rename_repairs_same_incarnation_duplicate_target(tmp_path, monkeypatch):
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
        "rename_source": "aura-refresh-test:operator",
    })

    result = registry.rename_agent("aura-refresh-test:operator", new_name="pilot")

    assert result["ok"] is True
    assert result["repair_duplicate"] is True
    assert registry.read_registry().keys() == {"aura-refresh-test:pilot"}
    assert registry.get_agent("aura-refresh-test:pilot")["seat_instance_id"] == "si_same"
    assert registry.get_agent("aura-refresh-test:operator")["resolved_from"] == "aura-refresh-test:operator"
    assert registry.read_aliases()["aura-refresh-test:operator"]["target"] == "aura-refresh-test:pilot"


def test_rename_rejects_different_incarnation_target(tmp_path, monkeypatch):
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

    result = registry.rename_agent("aura-refresh-test:operator", new_name="pilot")

    assert result["ok"] is False
    assert result["reason"] == "target-registry-exists"
    assert set(registry.read_registry().keys()) == {"aura-refresh-test:operator", "aura-refresh-test:pilot"}


def test_aura_seat_rename_replaces_public_rehome_and_top_level_rename(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    registry.upsert_agent({
        "name": "old-seat",
        "fleet": "old-fleet",
        "runtime": "codex",
        "pane_ref": "tmux:old-fleet:%12",
    })

    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    top_help = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "aura"), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )
    seat_help = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "aura"), "seat", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )
    old_command = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "aura"), "seat", "rehome", "old-fleet:old-seat", "--name", "leader-engine"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )

    assert top_help.returncode == 0
    assert "rename" not in top_help.stdout
    assert seat_help.returncode == 0
    assert "rename" in seat_help.stdout
    assert "rehome" not in seat_help.stdout
    assert old_command.returncode != 0
    assert "invalid choice" in old_command.stderr
    assert registry.get_agent("old-fleet:old-seat") is not None
    assert registry.get_agent("flex-leaders:leader-engine") is None


def test_aura_rename_same_fleet_mirrors_terminal_without_unsafe_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.delenv("AURA_ENABLE_UNSAFE_MOVE_TERMINAL", raising=False)
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "old-seat",
        "fleet": "unitfleet",
        "runtime": "codex",
        "pane_ref": "tmux:unitfleet:%12",
        "terminal_ref": "unitfleet:old-seat",
        "backend_ref": "unitfleet:old-seat",
    })

    def fake_rename_terminal_exact(record, *, fleet, name):
        assert record["pane_ref"] == "tmux:unitfleet:%12"
        assert fleet == "unitfleet"
        assert name == "new-seat"
        return {
            "ok": True,
            "terminal_ref": "unitfleet:new-seat",
            "backend_ref": "unitfleet:new-seat",
            "pane_ref": "tmux:unitfleet:%12",
            "physical_fleet": "unitfleet",
        }

    monkeypatch.setattr(seat, "_rename_terminal_exact", fake_rename_terminal_exact)
    result = seat.run(argparse.Namespace(
        seat_action="rename",
        source="unitfleet:old-seat",
        name="new-seat",
    ))

    assert result["ok"] is True
    assert result["renamed"] is True
    moved = registry.get_agent("unitfleet:new-seat")
    assert moved["terminal_ref"] == "unitfleet:new-seat"
    assert moved["backend_ref"] == "unitfleet:new-seat"
    assert moved["pane_ref"] == "tmux:unitfleet:%12"
    assert moved["rename_source"] == "unitfleet:old-seat"
    assert result["alias"]["reason"] == "rename"


def test_rename_terminal_exact_never_rediscovers_or_moves_for_plain_rename(monkeypatch):
    from commands import seat

    record = {
        "name": "outreach",
        "seat": "outreach",
        "fleet": "flexchat-marketing",
        "physical_fleet": "flexchat-marketing",
        "runtime": "codex",
        "aura_launch_id": "aura-launch-outreach",
        "runtime_session_id": "session-outreach",
        "pane_ref": "tmux:flexchat-marketing:%64",
        "terminal_ref": "flexchat-marketing:outreach",
        "backend_ref": "flexchat-marketing:outreach",
    }

    monkeypatch.setattr(seat, "_list_tmux_panes", lambda: [
        {"session": "flexchat-marketing", "window_index": "2", "window_name": "outreach", "pane_id": "%64", "pane_pid": 640},
        {"session": "flexchat-marketing", "window_index": "4", "window_name": "shopify-scout", "pane_id": "%130", "pane_pid": 130},
    ])

    def fake_run_tmux(args):
        if args[:3] == ["display-message", "-p", "-t"]:
            target = args[3]
            fmt = args[4]
            if target == "flexchat-marketing:%64" and fmt == "#{session_name}:#{window_index}:#{window_name}:#{pane_id}":
                return subprocess.CompletedProcess(args, 0, stdout="flexchat-marketing:2:outreach:%64\n", stderr="")
            if target == "%64" and fmt == "#{session_name}:#{window_index}:#{window_name}:#{pane_id}":
                return subprocess.CompletedProcess(args, 0, stdout="flexchat-marketing:2:marketing-manager:%64\n", stderr="")
        if args[:2] == ["has-session", "-t"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:1] == ["move-window"]:
            raise AssertionError("plain seat rename must never move a tmux window")
        if args[:2] == ["rename-window", "-t"]:
            assert args[2] == "%64"
            assert args[3] == "marketing-manager"
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr=f"unexpected {args}")

    monkeypatch.setattr(seat, "_run_tmux", fake_run_tmux)

    result = seat._rename_terminal_exact(record, fleet="flexchat-marketing", name="marketing-manager")

    assert result["ok"] is True
    assert result["pane_ref"] == "tmux:flexchat-marketing:%64"


def test_rename_terminal_exact_refuses_cross_fleet_source(monkeypatch):
    from commands import seat

    record = {
        "name": "scout",
        "seat": "scout",
        "fleet": "flexchat-prospecting",
        "runtime": "codex",
        "pane_ref": "tmux:flexchat-prospecting:%210",
        "terminal_ref": "flexchat-prospecting:scout",
        "backend_ref": "flexchat-prospecting:scout",
    }

    calls = []

    def fake_run_tmux(args):
        calls.append(args)
        if args[:3] == ["display-message", "-p", "-t"]:
            return subprocess.CompletedProcess(args, 0, stdout="other-fleet:3:scout:%210\n", stderr="")
        if args[:2] == ["has-session", "-t"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:1] in (["rename-window"], ["move-window"]):
            raise AssertionError(f"unexpected mutating tmux command: {args}")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr=f"unexpected {args}")

    monkeypatch.setattr(seat, "_run_tmux", fake_run_tmux)

    result = seat._rename_terminal_exact(record, fleet="flexchat-prospecting", name="fitcert-scout")

    assert result["ok"] is False
    assert result["error"] == "rename-source-fleet-mismatch"
    assert not any(call[:1] == ["rename-window"] for call in calls)
    assert not any(call[:1] == ["move-window"] for call in calls)


def test_aura_rename_stays_on_source_pane_with_neighbor_session_match(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "scout",
        "fleet": "flexchat-prospecting",
        "runtime": "codex",
        "pane_ref": "tmux:flexchat-prospecting:%210",
        "terminal_ref": "flexchat-prospecting:scout",
        "backend_ref": "flexchat-prospecting:scout",
        "runtime_session_id": "019e2d69-fitcert",
    })
    registry.upsert_agent({
        "name": "shopify-scout",
        "fleet": "flexchat-prospecting",
        "runtime": "codex",
        "pane_ref": "tmux:flexchat-prospecting:%214",
        "terminal_ref": "flexchat-prospecting:shopify-scout",
        "backend_ref": "flexchat-prospecting:shopify-scout",
        "runtime_session_id": "019e95d8-shopify",
    })

    monkeypatch.setattr(seat, "_list_tmux_panes", lambda: [
        {"session": "flexchat-prospecting", "window_index": "1", "window_name": "scout", "pane_id": "%210", "pane_pid": 48932},
        {"session": "flexchat-prospecting", "window_index": "2", "window_name": "shopify-scout", "pane_id": "%214", "pane_pid": 60847},
    ])

    def fake_run_tmux(args):
        if args[:3] == ["display-message", "-p", "-t"]:
            target = args[3]
            fmt = args[4]
            if target == "flexchat-prospecting:%210" and fmt == "#{session_name}:#{window_index}:#{window_name}:#{pane_id}":
                return subprocess.CompletedProcess(args, 0, stdout="flexchat-prospecting:1:scout:%210\n", stderr="")
            if target == "%210" and fmt == "#{session_name}:#{window_index}:#{window_name}:#{pane_id}":
                return subprocess.CompletedProcess(args, 0, stdout="flexchat-prospecting:1:fitcert-scout:%210\n", stderr="")
            if target == "flexchat-prospecting:%214":
                raise AssertionError("rename must not inspect the neighboring Shopify pane")
        if args[:2] == ["has-session", "-t"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:1] == ["move-window"]:
            raise AssertionError("seat rename must never move a tmux window")
        if args[:2] == ["rename-window", "-t"]:
            assert args[2] == "%210"
            assert args[3] == "fitcert-scout"
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(args, 1, stdout="", stderr=f"unexpected {args}")

    monkeypatch.setattr(seat, "_run_tmux", fake_run_tmux)

    result = seat.run(argparse.Namespace(
        seat_action="rename",
        source="flexchat-prospecting:scout",
        name="fitcert-scout",
    ))

    assert result["ok"] is True
    fitcert = registry.get_agent("flexchat-prospecting:fitcert-scout")
    shopify = registry.get_agent("flexchat-prospecting:shopify-scout")
    assert fitcert["pane_ref"] == "tmux:flexchat-prospecting:%210"
    assert fitcert["runtime_session_id"] == "019e2d69-fitcert"
    assert shopify["pane_ref"] == "tmux:flexchat-prospecting:%214"
    assert shopify["runtime_session_id"] == "019e95d8-shopify"

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


def test_cut_records_diagnostic_cache_invalidation(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / ".aura" / "registry" / "seats.json"))

    from commands import cut
    from lib import registry

    before = {
        "name": "worker",
        "fleet": "fleet",
        "runtime": "codex",
        "seat_ref": "fleet:worker",
        "terminal_ref": "fleet:worker",
    }
    result = {"ok": True, "name": "fleet:worker", "force": True, "terminal": "killed"}

    cut._record_stop(result, before, "fleet:worker")

    path = tmp_path / ".aura" / "seats" / "fleet:worker" / "diagnostics" / "cache-invalidations.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["target"] == "fleet:worker"
    assert rows[-1]["reason"] == "seat-cut"
    assert rows[-1]["source_command"] == "aura seat cut"
    assert rows[-1]["cache_owner"] == "aura"
    assert rows[-1]["caches"] == ["posture", "sense", "watch"]
    assert result["diagnostic_cache_invalidation"]["target"] == "fleet:worker"


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
        "identity_provider": "desks",
        "identity_id": "r_stale",
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
    from lib import registry, session_ledger

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
    invalidation_path = tmp_path / ".aura" / "seats" / "fleet:stale" / "diagnostics" / "cache-invalidations.jsonl"
    invalidation = json.loads(invalidation_path.read_text(encoding="utf-8").splitlines()[-1])
    assert invalidation["reason"] == "seat-swept-removed"
    assert invalidation["source_command"] == "aura seat sweep"
    rows = session_ledger.seat_history_for_target("fleet:stale")
    assert rows[-1]["event"] == "seat_swept_removed"
    assert rows[-1]["after"]["status"] == "swept_removed"
    latest = session_ledger.project_latest_from_ledger(fleet="fleet")
    assert latest[0]["restore_suppressed"] is True
    assert latest[0]["terminal_state"] == "terminal"


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
    assert result["diagnostic_cache_invalidation"]["reason"] == "seat-archived"
    invalidation_path = tmp_path / ".aura" / "seats" / "fleet:old-worker" / "diagnostics" / "cache-invalidations.jsonl"
    invalidation = json.loads(invalidation_path.read_text(encoding="utf-8").splitlines()[-1])
    assert invalidation["source_command"] == "aura seat archive"
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


def test_seat_quarantine_hides_non_live_row_without_removing_registry(tmp_path, monkeypatch):
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

    result = seat._quarantine(argparse.Namespace(
        seat_action="quarantine",
        target="fleet:old-worker",
        reason="test-quarantine",
        force=False,
    ), registry, FakeTerminal)

    assert result["ok"] is True
    assert result["hidden_from_live_views"] is True
    row = registry.get_agent("old-worker", fleet="fleet")
    assert row["status"] == "quarantined"
    assert row["restore_suppressed"] is True
    assert row["terminal_state"] == "terminal"
    assert result["diagnostic_cache_invalidation"]["reason"] == "seat-quarantined"
    invalidation_path = tmp_path / ".aura" / "seats" / "fleet:old-worker" / "diagnostics" / "cache-invalidations.jsonl"
    invalidation = json.loads(invalidation_path.read_text(encoding="utf-8").splitlines()[-1])
    assert invalidation["source_command"] == "aura seat quarantine"

    rows = session_ledger.seat_history_for_target("fleet:old-worker")
    assert rows[-1]["event"] == "seat_quarantined"
    assert rows[-1]["after"]["status"] == "quarantined"


def test_seat_quarantine_refuses_live_row_without_force(tmp_path, monkeypatch):
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

    result = seat._quarantine(argparse.Namespace(
        seat_action="quarantine",
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
        "name": "lead",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_lead",
        "pane_ref": "tmux:unitfleet:%1",
    })
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
        sender="unitfleet:lead",
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


def test_inspect_default_uses_status_not_raw_capture(monkeypatch):
    from commands import inspect

    seen = {}

    class FakeCheck:
        @staticmethod
        def run(args):
            seen["output"] = args.output
            return {"ok": True, "name": "worker", "fleet": "unitfleet", "status": "idle"}

    monkeypatch.setattr(inspect, "check", FakeCheck)

    result = inspect.run(argparse.Namespace(name="unitfleet:worker", raw=False, sense=False, lines=40, format="text"))

    assert seen["output"] is False
    assert result["ok"] is True
    assert result["inspect_mode"] == "status"
    assert "output" not in result


def test_broadcast_targets_registered_fleet_agents_and_excludes_shell(monkeypatch):
    from commands import broadcast

    registry_agents = [
        {"name": "claude1", "fleet": "triad", "registered": True, "terminal_ref": "triad:claude1"},
        {"name": "hermes1", "fleet": "triad", "registered": True, "terminal_ref": "triad:hermes1"},
        {"name": "stale", "fleet": "triad", "registered": True, "terminal_ref": "triad:stale"},
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
        @staticmethod
        def target_exists(target):
            return target in {"triad:claude1", "triad:hermes1"}

    sent = []

    class FakeSend:
        @staticmethod
        def run(args):
            sent.append((args.target, args.message, args.transport, args.service_sender))
            return {"ok": True, "target": args.target}

    monkeypatch.setattr(broadcast, "_registry", FakeRegistry)
    monkeypatch.setattr(broadcast, "_terminal", FakeTerminal)
    monkeypatch.setattr(broadcast, "_send", FakeSend)

    args = argparse.Namespace(
        fleet="triad",
        fleet_arg=None,
        message="ping",
        sender=None,
        service_sender="chatbot-pipeline",
        transport="tmux",
        dedupe_key=None,
        force=False,
        include_shell=False,
        allow_hidden=False,
    )
    result = broadcast.run(args)

    assert result["ok"] is True
    assert result["schema"] == "aura.broadcast_fleet.v1"
    assert result["count"] == 2
    assert [x[0] for x in sent] == ["triad:claude1", "triad:hermes1"]
    assert all(x[1] == "ping" for x in sent)
    assert all(x[3] == "chatbot-pipeline" for x in sent)


def test_broadcast_parses_message_when_fleet_flag_is_set(monkeypatch):
    from commands import broadcast

    class FakeRegistry:
        @staticmethod
        def list_agents(fleet=None, include_hidden=False):
            return [{"name": "claude1", "fleet": fleet, "registered": True, "terminal_ref": f"{fleet}:claude1"}]
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
        @staticmethod
        def target_exists(target):
            return target == "triad:claude1"

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
    assert sent == [("triad:claude1", "hello world")]


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

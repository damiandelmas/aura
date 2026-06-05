"""Tests for stable Aura fleet identity commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_fleets_resolve_creates_stable_id_for_named_fleet(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import fleets

    first = fleets.run(argparse.Namespace(fleets_action="resolve", target="flex-specialists"))
    second = fleets.run(argparse.Namespace(fleets_action="resolve", target="flex-specialists"))

    assert first["ok"] is True
    assert first["fleet"]["fleet_id"].startswith("f_")
    assert second["fleet"]["fleet_id"] == first["fleet"]["fleet_id"]
    assert second["fleet"]["current_name"] == "flex-specialists"
    assert second["fleet"]["tmux_session"] == "flex-specialists"


def test_sessions_fleets_includes_fleet_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import sessions
    from lib import registry, seat_status, session_ledger

    registry.upsert_agent({
        "name": "worker",
        "seat": "worker",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
        "runtime_session_id": "session-1",
        "runtime_session_binding": "bound",
        "identity_provider": "desks",
        "identity_id": "r_test",
    })
    session_ledger.append_seat_event(
        event="seat_spawned",
        after=registry.get_agent("worker", fleet="unitfleet"),
        source_command="test",
    )
    monkeypatch.setattr(
        seat_status,
        "list_seat_statuses",
        lambda include_hidden=False, terminal=None: [
            {
                "name": "worker",
                "seat": "worker",
                "fleet": "unitfleet",
                "terminal": "alive",
                "liveness": "alive",
                "managed_state": "spawned_bound",
                "runtime": "codex",
                "runtime_session_id": "session-1",
                "runtime_session_binding": "bound",
            }
        ],
    )

    result = sessions.run(argparse.Namespace(sessions_action="fleets"))

    assert result["ok"] is True
    assert result["live"][0]["fleet"] == "unitfleet"
    assert result["live"][0]["fleet_id"].startswith("f_")
    assert result["live"][0]["live_seats"] == 1
    assert result["live"][0]["bound_seats"] == 1


def test_fleet_history_builds_restore_commands(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import fleets
    from lib import registry, session_ledger

    current = registry.upsert_agent({
        "name": "worker",
        "seat": "worker",
        "fleet": "unitfleet",
        "runtime": "codex",
        "cwd": str(tmp_path),
        "registered": True,
        "runtime_session_id": "session-1",
        "runtime_session_binding": "bound",
        "identity_provider": "desks",
        "identity_id": "r_test",
    })
    session_ledger.append_seat_event(
        event="seat_spawned",
        after=current,
        source_command="test",
    )
    session_ledger.append_seat_event(
        event="seat_cut",
        before=current,
        source_command="test",
    )
    monkeypatch.setattr(
        fleets.list_cmd,
        "run",
        lambda _args: [],
    )

    result = fleets.run(argparse.Namespace(fleets_action="history", target="unitfleet"))

    assert result["ok"] is True
    assert result["state"] == "historical"
    assert result["fleet_id"].startswith("f_")
    assert result["seats"][0]["seat"] == "worker"
    assert result["seats"][0]["restore"]["ready"] is True
    assert "--fleet-id" in result["seats"][0]["restore"]["command"]
    assert "--resume-session session-1" in result["seats"][0]["restore"]["command"]
    assert result["seats"][0]["restore"]["post_bind_command"] == (
        "aura seat tag unitfleet:worker --set identity_provider=desks --set identity_id=r_test"
    )


def test_fleet_history_does_not_restore_keeper_worker_threads(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import fleets
    from lib import registry, session_ledger

    keeper_job = tmp_path / "state" / "keeper-jobs" / "memory.job"
    keeper_job.mkdir(parents=True)
    (keeper_job / "result.json").write_text('{"ok": true, "thread_id": "keeper-thread"}\n', encoding="utf-8")

    real = registry.upsert_agent({
        "name": "worker",
        "seat": "worker",
        "fleet": "unitfleet",
        "runtime": "codex",
        "cwd": str(tmp_path),
        "registered": True,
        "runtime_session_id": "real-thread",
        "runtime_session_binding": "bound",
    })
    keeper = dict(real)
    keeper["runtime_session_id"] = "keeper-thread"
    keeper["session_id"] = "keeper-thread"
    session_ledger.append_seat_event(event="seat_spawned", after=real, source_command="test")
    session_ledger.append_seat_event(event="session_bound_hook", after=keeper, source_command="test")
    monkeypatch.setattr(fleets.list_cmd, "run", lambda _args: [])

    result = fleets.run(argparse.Namespace(fleets_action="history", target="unitfleet"))

    assert result["ok"] is True
    assert result["seats"][0]["restore"]["ready"] is True
    assert "--resume-session real-thread" in result["seats"][0]["restore"]["command"]
    assert "keeper-thread" not in result["seats"][0]["restore"]["command"]


def test_fleet_rename_dry_run_writes_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import fleets as fleets_cmd
    from lib import fleets, registry, tmux_mirror

    original_fleet = fleets.ensure_fleet("oldfleet")
    registry.upsert_agent({
        "name": "worker",
        "seat": "worker",
        "fleet": "oldfleet",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:oldfleet:%77",
        "terminal_ref": "oldfleet:worker",
        "backend_ref": "oldfleet:worker",
        "fleet_id": original_fleet["fleet_id"],
    })
    monkeypatch.setattr(fleets_cmd, "_tmux_session_exists", lambda name: name == "oldfleet")
    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: {
        "ok": True,
        "panes": [{"tmux_session": "oldfleet", "physical_fleet": "oldfleet", "pane_id": "%77"}],
    })

    result = fleets_cmd.run(argparse.Namespace(
        fleets_action="rename",
        old="oldfleet",
        new="newfleet",
        dry_run=True,
        confirm=False,
    ))

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert registry.get_agent("oldfleet:worker") is not None
    assert registry.get_agent("newfleet:worker") is None
    assert registry.read_aliases() == {}
    assert fleets.resolve("oldfleet")["current_name"] == "oldfleet"


def test_fleet_rename_confirm_readdresses_live_topology(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import fleets as fleets_cmd
    from lib import events, fleets, placements, queued_messages, registry, report_subscriptions, tmux_mirror

    package_root = tmp_path / "state" / "agents" / "i_worker"
    package_root.mkdir(parents=True)
    manifest_path = package_root / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema": "aura.agent_manifest.v1", "runtime": "codex", "fleet": "oldfleet", "seat": "worker"}) + "\n",
        encoding="utf-8",
    )

    fleet_record = fleets.ensure_fleet("oldfleet")
    registry.upsert_agent({
        "name": "worker",
        "seat": "worker",
        "fleet": "oldfleet",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:oldfleet:%77",
        "terminal_ref": "oldfleet:worker",
        "backend_ref": "oldfleet:worker",
        "fleet_id": fleet_record["fleet_id"],
        "agent_package_id": "i_worker",
        "agent_package_root": str(package_root),
    })
    registry.upsert_agent({
        "name": "stale",
        "seat": "stale",
        "fleet": "oldfleet",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:oldfleet:%88",
        "terminal_ref": "oldfleet:stale",
        "backend_ref": "oldfleet:stale",
        "fleet_id": fleet_record["fleet_id"],
    })
    registry.upsert_agent({
        "name": "lead",
        "seat": "lead",
        "fleet": "oldfleet",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:oldfleet:%78",
        "terminal_ref": "oldfleet:lead",
        "backend_ref": "oldfleet:lead",
        "fleet_id": fleet_record["fleet_id"],
    })
    placements.add_member("ops-wave", "oldfleet:worker", role="worker")
    queued_messages.create(target="oldfleet:worker", message="next", sender="oldfleet:lead")
    job = {
        "schema": "aura.event.job.v1",
        "job_id": "evt_unit",
        "name": "ops",
        "kind": "interval",
        "target": "oldfleet:worker",
        "sender": "oldfleet:lead",
        "status": "running",
    }
    events.save_state(job)
    report_subscriptions.create(name="ops-checkins", to="oldfleet:lead", fleet="oldfleet", target="oldfleet:worker")
    discord_dir = tmp_path / "state" / "discord"
    discord_dir.mkdir(parents=True)
    (discord_dir / "channel-bindings.json").write_text(json.dumps({
        "schema": "aura.discord.channel_bindings.v1",
        "bindings": {
            "chan": {
                "default_target": "oldfleet:worker",
                "aliases": {"lead": "oldfleet:lead"},
            }
        },
    }) + "\n", encoding="utf-8")

    tmux_calls = []
    monkeypatch.setattr(fleets_cmd, "_tmux_session_exists", lambda name: name == "oldfleet")
    monkeypatch.setattr(fleets_cmd, "_run_tmux", lambda args: (
        tmux_calls.append(args) or __import__("subprocess").CompletedProcess(args, 0, stdout="", stderr="")
    ))
    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: {
        "ok": True,
        "panes": [
            {"tmux_session": "oldfleet", "physical_fleet": "oldfleet", "pane_id": "%77"},
            {"tmux_session": "oldfleet", "physical_fleet": "oldfleet", "pane_id": "%78"},
        ],
    })

    result = fleets_cmd.run(argparse.Namespace(
        fleets_action="rename",
        old="oldfleet",
        new="newfleet",
        dry_run=False,
        confirm=True,
    ))

    assert result["ok"] is True
    assert ["rename-session", "-t", "oldfleet", "newfleet"] in tmux_calls
    moved = registry.get_agent("newfleet:worker")
    stale = registry.get_agent("oldfleet:stale")
    assert moved["pane_ref"] == "tmux:newfleet:%77"
    assert moved["terminal_ref"] == "newfleet:worker"
    assert stale is not None
    assert registry.read_aliases()["oldfleet:worker"]["target"] == "newfleet:worker"
    renamed_fleet = fleets.resolve("newfleet")
    assert renamed_fleet["fleet_id"] == fleet_record["fleet_id"]
    assert "oldfleet" in renamed_fleet["aliases"]
    assert placements.get_placement("ops-wave")["members"][0]["seat_ref"] == "newfleet:worker"
    assert queued_messages.list_records()[0]["target"] == "newfleet:worker"
    assert queued_messages.list_records()[0]["sender"] == "newfleet:lead"
    assert events.load_state("evt_unit")["target"] == "newfleet:worker"
    subscription = report_subscriptions.load("ops-checkins")
    assert subscription["fleet"] == "newfleet"
    assert subscription["target"] == "newfleet:worker"
    assert subscription["to"] == "newfleet:lead"
    bindings = json.loads((discord_dir / "channel-bindings.json").read_text(encoding="utf-8"))
    assert bindings["bindings"]["chan"]["default_target"] == "newfleet:worker"
    assert bindings["bindings"]["chan"]["aliases"]["lead"] == "newfleet:lead"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["fleet"] == "newfleet"


def test_fleet_rename_refuses_target_fleet_collision(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import fleets as fleets_cmd
    from lib import fleets

    fleets.ensure_fleet("oldfleet")
    fleets.ensure_fleet("newfleet")
    monkeypatch.setattr(fleets_cmd, "_tmux_session_exists", lambda name: name == "oldfleet")

    result = fleets_cmd.run(argparse.Namespace(
        fleets_action="rename",
        old="oldfleet",
        new="newfleet",
        dry_run=False,
        confirm=True,
    ))

    assert result["ok"] is False
    assert "target fleet already exists" in result["error"]

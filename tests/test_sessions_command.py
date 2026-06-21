"""Tests for `aura sessions` row contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_sessions_parser_accepts_footer_actions(monkeypatch):
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("aura_cli_parser", str(ROOT / "cli" / "aura"))
    spec = importlib.util.spec_from_loader("aura_cli_parser", loader)
    aura_cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(aura_cli)

    for action in ("footer", "bind-footer"):
        captured = {}
        monkeypatch.setattr(aura_cli.sessions_cmd, "run", lambda args: captured.update(vars(args)) or {"ok": True})
        monkeypatch.setattr(aura_cli, "output", lambda _result: None)
        old_argv = sys.argv
        try:
            sys.argv = ["aura", "sessions", action, "--target", "unitfleet:engineer"]
            aura_cli.main()
        finally:
            sys.argv = old_argv
        assert captured["command"] == "sessions"
        assert captured["sessions_action"] == action
        assert captured["target"] == "unitfleet:engineer"


def test_sessions_rows_emit_fleet_seat_and_target(monkeypatch):
    from commands import sessions

    monkeypatch.setattr(
        sessions.list_cmd,
        "run",
        lambda _args: [
            {
                "seat": "specialist-cell",
                "fleet": "flex-specialists",
                "runtime": "codex",
                "terminal": "alive",
                "runtime_session_id": "019dec35-4cd3-7550-83d3-53d50e837e5d",
                "runtime_session_binding": "bound",
                "runtime_session_bind_method": "argv-resume",
            }
        ],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action=None,
        fleet=None,
        live=True,
        include_hidden=True,
    ))

    assert result["ok"] is True
    assert result["rows"][0]["seat"] == "specialist-cell"
    assert "name" not in result["rows"][0]
    assert "runtime_session_confidence" not in result["rows"][0]
    assert result["rows"][0]["target"] == "flex-specialists:specialist-cell"
    assert result["rows"][0]["seat_ref"] == "flex-specialists:specialist-cell"


def test_sessions_rows_fall_back_to_legacy_name(monkeypatch):
    from commands import sessions

    monkeypatch.setattr(
        sessions.list_cmd,
        "run",
        lambda _args: [
            {
                "name": "engineer",
                "fleet": "flex-leaders-2",
                "runtime": "codex",
                "terminal": "alive",
            }
        ],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action=None,
        fleet=None,
        live=True,
        include_hidden=True,
    ))

    assert result["rows"][0]["seat"] == "engineer"
    assert "name" not in result["rows"][0]
    assert result["rows"][0]["target"] == "flex-leaders-2:engineer"


def test_restore_plan_prefers_package_agent_spawn(monkeypatch, tmp_path):
    from commands import sessions

    package_root = tmp_path / "agents" / "i_pkg"
    monkeypatch.setattr(
        sessions.list_cmd,
        "run",
        lambda _args: [
            {
                "seat": "manager",
                "fleet": "flexchat-global",
                "runtime": "codex",
                "terminal": "alive",
                "runtime_session_id": "019e47f8-34d9-7a62-8527-7abbafae773d",
                "session_id": "019e47f8-34d9-7a62-8527-7abbafae773d",
                "runtime_session_binding": "bound",
                "runtime_session_bind_method": "codex-hook",
                "runtime_session_source": "codex-hook:session-start",
                "cwd": "/home/axp/projects/flexgraph/chatbot",
                "agent_package_id": "i_f259b2504cbe",
                "agent_package_address": "flexchat:global:manager",
                "agent_package_root": str(package_root),
                "codex_package_root": str(package_root),
                "codex_package_codex_home": str(package_root / ".codex"),
            }
        ],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="restore-plan",
        fleet=None,
        live=True,
        include_hidden=False,
    ))

    row = result["rows"][0]
    assert row["restore_ready"] is True
    assert row["restore_evidence_source"] == "package-local-runtime-state"
    assert row["restore_evidence_rank"] == 100
    assert row["restore_command_kind"] == "agent-spawn-resume"
    assert row["agent_package_id"] == "i_f259b2504cbe"
    assert row["restore_command"] == (
        "aura agent spawn flexchat:global:manager "
        "--fleet flexchat-global --seat manager "
        "--cwd /home/axp/projects/flexgraph/chatbot "
        "--resume-session 019e47f8-34d9-7a62-8527-7abbafae773d "
        "--as-pane --wait"
    )


def test_restore_plan_recovers_launch_history_from_capsule_jsonl(monkeypatch, tmp_path):
    from commands import sessions

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    nonce = "aura-launch-restore-history-test"
    capsule = tmp_path / "capsule"
    codex_home = capsule / "codex-home"
    jsonl = codex_home / "sessions" / "2026" / "05" / "26" / "restore.jsonl"
    jsonl.parent.mkdir(parents=True)
    jsonl.write_text(
        json.dumps({
            "type": "session_meta",
            "payload": {
                "id": "session-recovered",
                "cwd": "/repo/fitcert",
                "timestamp": "2026-05-26T09:58:00Z",
                "aura_launch_id": nonce,
            },
        }) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sessions.list_cmd,
        "run",
        lambda _args: [
            {
                "seat": "pipeline",
                "fleet": "flexchat-fitcert",
                "runtime": "codex",
                "terminal": "dead",
                "runtime_session_binding": "unbound",
                "cwd": "/repo/fitcert",
                "aura_launch_id": nonce,
                "codex_box_root": str(capsule),
                "codex_box_codex_home": str(codex_home),
            }
        ],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="restore-plan",
        fleet=None,
        live=False,
        include_hidden=True,
        from_ledger=False,
        latest_per_seat=False,
    ))

    row = result["rows"][0]
    assert row["restore_ready"] is True
    assert row["session_id"] == "session-recovered"
    assert row["runtime_session_source"] == "codex-jsonl:nonce"
    assert row["runtime_session_bind_method"] == "nonce-jsonl"
    assert row["restore_evidence_source"] == "launch-history-codex-jsonl"
    assert row["restore_evidence_rank"] == 80
    assert row["runtime_session_jsonl"] == str(jsonl)
    assert row["runtime_session_evidence"]["nonce"] == nonce
    assert row["restore_command"] == (
        "aura spawn pipeline --runtime codex --fleet flexchat-fitcert "
        "--cwd /repo/fitcert --resume-session session-recovered --as-pane --wait"
    )


def test_restore_plan_package_evidence_wins_after_launch_history_recovery(monkeypatch, tmp_path):
    from commands import sessions

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    nonce = "aura-launch-package-history-test"
    package_root = tmp_path / "agents" / "i_pkg"
    codex_home = package_root / ".codex"
    jsonl = codex_home / "sessions" / "2026" / "05" / "26" / "package.jsonl"
    jsonl.parent.mkdir(parents=True)
    jsonl.write_text(
        json.dumps({
            "type": "session_meta",
            "payload": {
                "id": "session-package-recovered",
                "cwd": "/repo/fitcert",
                "timestamp": "2026-05-26T10:04:00Z",
            },
        }) + f"\n{{\"type\":\"event\",\"message\":\"{nonce}\"}}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sessions.list_cmd,
        "run",
        lambda _args: [
            {
                "seat": "pipeline",
                "fleet": "flexchat-fitcert",
                "runtime": "codex",
                "terminal": "dead",
                "runtime_session_binding": "unbound",
                "cwd": "/repo/fitcert",
                "aura_launch_id": nonce,
                "agent_package_id": "i_pkg",
                "agent_package_address": "flexchat:fitcert:pipeline",
                "agent_package_root": str(package_root),
                "codex_package_root": str(package_root),
                "codex_package_codex_home": str(codex_home),
            }
        ],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="restore-plan",
        fleet=None,
        live=False,
        include_hidden=True,
        from_ledger=False,
        latest_per_seat=False,
    ))

    row = result["rows"][0]
    assert row["restore_ready"] is True
    assert row["session_id"] == "session-package-recovered"
    assert row["restore_evidence_source"] == "package-local-runtime-state"
    assert row["restore_evidence_rank"] == 100
    assert row["restore_command_kind"] == "agent-spawn-resume"
    assert row["restore_command"] == (
        "aura agent spawn flexchat:fitcert:pipeline --fleet flexchat-fitcert "
        "--seat pipeline --cwd /repo/fitcert "
        "--resume-session session-package-recovered --as-pane --wait"
    )


def test_restore_plan_warns_when_launch_history_missing(monkeypatch, tmp_path):
    from commands import sessions

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(
        sessions.list_cmd,
        "run",
        lambda _args: [
            {
                "seat": "pipeline",
                "fleet": "flexchat-fitcert",
                "runtime": "codex",
                "terminal": "dead",
                "runtime_session_binding": "unbound",
                "cwd": "/repo/fitcert",
                "aura_launch_id": "aura-launch-missing-history-test",
            }
        ],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="restore-plan",
        fleet=None,
        live=False,
        include_hidden=True,
        from_ledger=False,
        latest_per_seat=False,
    ))

    row = result["rows"][0]
    assert row["restore_ready"] is False
    assert row["restore_reason"] == "missing-session-id"
    assert "launch-history-session-not-found" in row["warnings"]
    assert row["restore_launch_history_error"] == "codex sessions directory not found"


def test_restore_plan_includes_placement_and_event_reconciliation(monkeypatch, tmp_path):
    from commands import event, sessions
    from lib import events, placements, registry, report_subscriptions

    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    registry.upsert_agent({
        "seat": "pipeline",
        "name": "pipeline",
        "fleet": "flexchat-fitcert",
        "runtime": "codex",
        "registered": True,
    })
    placements.add_member("fitcert-wave", "flexchat-fitcert:pipeline", role="pipeline", kind="workstream")
    job = event._make_job(argparse.Namespace(
        name="fitcert-cadence",
        target="flexchat-fitcert:pipeline",
        sender="aura-event",
        every=300,
        ticks=None,
        template="tick {tick}",
        run_id="unit-run",
        start_delay=0,
        no_daemon=True,
    ))
    events.save_state(job)
    events.index_name("fitcert-cadence", job["job_id"])
    report_subscriptions.create(
        name="fitcert-checkins",
        to="flexchat-fitcert:floor-manager",
        placement="fitcert-wave",
        sender="aura-event",
    )
    monkeypatch.setattr(
        sessions.list_cmd,
        "run",
        lambda _args: [
            {
                "seat": "pipeline",
                "fleet": "flexchat-fitcert",
                "runtime": "codex",
                "terminal": "alive",
                "runtime_session_id": "session-fitcert",
                "session_id": "session-fitcert",
                "runtime_session_binding": "bound",
                "runtime_session_source": "codex-hook:session-start",
                "cwd": "/repo/fitcert",
            }
        ],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="restore-plan",
        fleet=None,
        live=True,
        include_hidden=False,
    ))

    row = result["rows"][0]
    assert result["reconciliation"] == {
        "placements": 1,
        "event_jobs": 1,
        "report_subscriptions": 1,
    }
    assert row["reconciliation"]["target"] == "flexchat-fitcert:pipeline"
    assert row["reconciliation"]["placements"][0]["name"] == "fitcert-wave"
    assert row["reconciliation"]["event_jobs"][0]["name"] == "fitcert-cadence"
    assert row["reconciliation"]["report_subscriptions"][0]["name"] == "fitcert-checkins"
    assert row["reconciliation"]["report_subscriptions"][0]["reasons"] == ["source-placement"]


def test_sessions_fleets_counts_same_seat_name_per_fleet(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "fleet-a")

    from commands import sessions
    from lib import registry, terminal

    registry.upsert_agent({
        "name": "lead",
        "fleet": "fleet-a",
        "runtime": "codex",
        "registered": True,
        "terminal_ref": "fleet-a:lead",
        "runtime_session_id": "session-a",
        "runtime_session_source": "argv:codex-resume",
        "identity_provider": "desks",
        "identity_id": "r_a",
    })
    registry.upsert_agent({
        "name": "lead",
        "fleet": "fleet-b",
        "runtime": "codex",
        "registered": True,
        "terminal_ref": "fleet-b:lead",
        "runtime_session_id": "session-b",
        "runtime_session_source": "argv:codex-resume",
    })

    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "target_exists", lambda target: target in {"fleet-a:lead", "fleet-b:lead"})
    monkeypatch.setattr(terminal, "capture_output", lambda target, lines=20: ["ready"])

    result = sessions.run(argparse.Namespace(sessions_action="fleets"))

    by_fleet = {row["fleet"]: row for row in result["fleets"]}
    assert by_fleet["fleet-a"]["registry_seats"] == 1
    assert by_fleet["fleet-b"]["registry_seats"] == 1
    assert by_fleet["fleet-a"]["live_seats"] == 1
    assert by_fleet["fleet-b"]["live_seats"] == 1
    assert by_fleet["fleet-a"]["bound_seats"] == 1
    assert by_fleet["fleet-b"]["bound_seats"] == 1


def test_bind_nonce_searches_runtime_capsule_codex_home(monkeypatch, tmp_path):
    import json
    from commands import sessions
    from lib import registry

    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    workdir = tmp_path / "work"
    workdir.mkdir()
    capsule = tmp_path / "capsule"
    jsonl = capsule / "codex-home" / "sessions" / "2026" / "05" / "16" / "rollout-session-capsule.jsonl"
    jsonl.parent.mkdir(parents=True)
    nonce = "aura-launch-capsule"
    jsonl.write_text(
        "\n".join([
            json.dumps({"type": "session_meta", "payload": {"id": "session-capsule", "cwd": str(workdir)}}),
            json.dumps({"type": "message", "payload": {"text": nonce}}),
            "",
        ]),
        encoding="utf-8",
    )

    registry.upsert_agent({
        "name": "builder",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
        "cwd": str(workdir),
        "runtime_home": str(capsule),
        "codex_box_root": str(capsule),
        "codex_box_codex_home": str(capsule / "codex-home"),
        "aura_launch_id": nonce,
    })

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-nonce",
        nonce=nonce,
        target="unitfleet:builder",
        jsonl=None,
    ))

    assert result["ok"] is True
    assert result["runtime_session_id"] == "session-capsule"
    assert result["jsonl"] == str(jsonl)
    assert result["runtime_capsule_session"] == str(capsule / "runtime-session.json")
    body = json.loads((capsule / "runtime-session.json").read_text(encoding="utf-8"))
    assert body["runtime_session_id"] == "session-capsule"
    assert body["jsonl"] == str(jsonl)


def test_sessions_footer_reports_pane_candidate_without_mutating(monkeypatch, tmp_path):
    from commands import sessions
    from lib import registry, terminal

    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    registry.upsert_agent({
        "name": "engineer",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:unitfleet:%44",
        "runtime_session_id": "old-session",
        "runtime_session_source": "argv:codex-resume",
    })
    captured = {}

    def capture_output(target, lines=80):
        captured["target"] = target
        captured["lines"] = lines
        return [
            "work output",
            "codex session 019e1111-2222-7333-8444-555555555555",
        ]

    monkeypatch.setattr(terminal, "capture_output", capture_output)

    result = sessions.run(argparse.Namespace(
        sessions_action="footer",
        target="unitfleet:engineer",
        runtime=None,
        lines=40,
    ))

    assert result["ok"] is True
    assert captured == {"target": "tmux:unitfleet:%44", "lines": 40}
    assert result["candidate"]["session_id"] == "019e1111-2222-7333-8444-555555555555"
    assert result["source_scope"] == "footer-keyword"
    assert result["stale_registry_session"] is True
    assert registry.get_agent("engineer", fleet="unitfleet")["runtime_session_id"] == "old-session"


def test_sessions_bind_footer_dry_run_does_not_mutate(monkeypatch, tmp_path):
    from commands import sessions
    from lib import registry, terminal

    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    registry.upsert_agent({
        "name": "engineer",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:unitfleet:%44",
        "runtime_session_binding": "unbound",
    })
    monkeypatch.setattr(
        terminal,
        "capture_output",
        lambda target, lines=80: ["ctx 019e1111-2222-7333-8444-555555555555"],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-footer",
        target="unitfleet:engineer",
        runtime=None,
        seat_instance_id=None,
        dry_run=True,
        lines=80,
    ))

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["runtime_session_source"] == "codex-footer:capture"
    assert registry.get_agent("engineer", fleet="unitfleet").get("runtime_session_id") is None


def test_sessions_bind_footer_updates_stale_session(monkeypatch, tmp_path):
    from commands import sessions
    from lib import registry, terminal

    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    registry.upsert_agent({
        "name": "engineer",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:unitfleet:%44",
        "cwd": str(tmp_path),
        "seat_instance_id": "si_footer",
        "runtime_session_id": "old-session",
        "runtime_session_source": "argv:codex-resume",
        "runtime_session_binding": "bound",
    })
    monkeypatch.setattr(
        terminal,
        "capture_output",
        lambda target, lines=80: ["Codex thread 019e1111-2222-7333-8444-555555555555"],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-footer",
        target="unitfleet:engineer",
        runtime=None,
        seat_instance_id="si_footer",
        dry_run=False,
        lines=80,
    ))

    assert result["ok"] is True
    assert result["runtime_session_id"] == "019e1111-2222-7333-8444-555555555555"
    assert result["runtime_session_source"] == "codex-footer:capture"
    assert result["runtime_session_bind_method"] == "footer-capture"
    assert result["stale_previous_session_id"] == "old-session"
    row = registry.get_agent("engineer", fleet="unitfleet")
    assert row["runtime_session_id"] == "019e1111-2222-7333-8444-555555555555"
    assert row["runtime_session_bind_method"] == "footer-capture"


def test_sessions_bind_footer_refuses_unregistered_target(monkeypatch, tmp_path):
    from commands import sessions

    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-footer",
        target="unitfleet:missing",
        runtime=None,
        seat_instance_id=None,
        dry_run=False,
        lines=80,
    ))

    assert result["ok"] is False
    assert result["error"] == "target-seat-not-registered"


def test_sessions_bind_footer_refuses_seat_instance_mismatch(monkeypatch, tmp_path):
    from commands import sessions
    from lib import registry, terminal

    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    registry.upsert_agent({
        "name": "engineer",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_actual",
    })
    monkeypatch.setattr(
        terminal,
        "capture_output",
        lambda target, lines=80: ["session 019e1111-2222-7333-8444-555555555555"],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-footer",
        target="unitfleet:engineer",
        runtime=None,
        seat_instance_id="si_wrong",
        dry_run=False,
        lines=80,
    ))

    assert result["ok"] is False
    assert result["error"] == "seat-instance-mismatch"


def test_sessions_bind_footer_refuses_ambiguous_candidates(monkeypatch, tmp_path):
    from commands import sessions
    from lib import registry, terminal

    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    registry.upsert_agent({
        "name": "engineer",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
    })
    monkeypatch.setattr(
        terminal,
        "capture_output",
        lambda target, lines=80: [
            "session 019e1111-2222-7333-8444-555555555555",
            "thread 019e6666-7777-7888-8999-aaaaaaaaaaaa",
        ],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-footer",
        target="unitfleet:engineer",
        runtime=None,
        seat_instance_id=None,
        dry_run=False,
        lines=80,
    ))

    assert result["ok"] is False
    assert result["error"] == "footer-session-ambiguous"


def test_codex_bind_hook_script_binds_capsule_session_quietly(monkeypatch, tmp_path):
    import json
    import os
    import subprocess
    from lib import registry

    state = tmp_path / ".aura"
    capsule = tmp_path / "capsule"
    codex_home = capsule / "codex-home"
    codex_home.mkdir(parents=True)
    monkeypatch.setenv("AURA_STATE_DIR", str(state))

    registry.upsert_agent({
        "name": "builder",
        "fleet": "unitfleet",
        "runtime": "codex",
        "registered": True,
        "cwd": str(tmp_path),
        "seat_instance_id": "si_hook_script",
        "codex_box_root": str(capsule),
        "codex_box_codex_home": str(codex_home),
    })

    env = {
        **os.environ,
        "AURA_STATE_DIR": str(state),
        "AURA_FLEET": "unitfleet",
        "AURA_SEAT": "builder",
        "AURA_RUNTIME": "codex",
        "AURA_SEAT_INSTANCE_ID": "si_hook_script",
        "AURA_RUNTIME_CAPSULE_REF": str(capsule),
    }
    payload = {
        "hook_event_name": "SessionStart",
        "session_id": "thread-hook-script",
        "transcript_path": str(codex_home / "sessions" / "rollout.jsonl"),
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "hooks" / "codex_bind_hook.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=5,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    row = registry.get_agent("builder", fleet="unitfleet")
    assert row["runtime_session_id"] == "thread-hook-script"
    assert (capsule / "runtime-session.json").is_file()
    receipt = (capsule / "receipts" / "codex-bind-hook.jsonl").read_text(encoding="utf-8")
    assert '"ok": true' in receipt


def test_codex_bind_hook_script_refuses_removed_omx_runtime(monkeypatch, tmp_path):
    import json
    import os
    import subprocess
    from lib import registry

    state = tmp_path / ".aura"
    capsule = tmp_path / "omx-agent"
    codex_home = capsule / ".codex"
    codex_home.mkdir(parents=True)
    (capsule / "manifest.json").write_text(
        json.dumps({"schema": "aura.agent_manifest.v1", "runtime": "omx"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AURA_STATE_DIR", str(state))

    registry.upsert_agent({
        "name": "pipeline",
        "fleet": "flexgraph-chatbot",
        "runtime": "omx",
        "registered": True,
        "cwd": str(tmp_path),
        "seat_instance_id": "si_omx_hook",
        "omx_box_root": str(capsule),
        "omx_box_codex_home": str(codex_home),
        "omx_box_omx_root": str(capsule),
        "agent_package_id": "i_pkg",
        "agent_package_root": str(capsule),
    })

    env = {
        **os.environ,
        "AURA_STATE_DIR": str(state),
        "AURA_FLEET": "flexgraph-chatbot",
        "AURA_SEAT": "pipeline",
        "AURA_RUNTIME": "omx",
        "AURA_SEAT_INSTANCE_ID": "si_omx_hook",
        "AURA_RUNTIME_CAPSULE_REF": str(capsule),
        "AURA_AGENT_PACKAGE_ID": "i_pkg",
        "AURA_AGENT_PACKAGE_ROOT": str(capsule),
    }
    payload = {
        "hook_event_name": "SessionStart",
        "session_id": "thread-omx-hook",
        "transcript_path": str(codex_home / "sessions" / "rollout.jsonl"),
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "hooks" / "codex_bind_hook.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=5,
    )

    # omx is no longer a spawnable runtime, so its hook can never legitimately
    # fire; bind-hook refuses the runtime and writes nothing. The hook script
    # itself stays quiet and exits 0 (it never breaks a native session).
    assert result.returncode == 0
    assert result.stdout == ""
    row = registry.get_agent("pipeline", fleet="flexgraph-chatbot")
    assert row["runtime"] == "omx"
    assert row.get("runtime_session_id") in (None, "")
    assert not (capsule / "runtime-session.json").exists()


def test_codex_bind_hook_ignores_mismatched_keeper_codex_home(monkeypatch, tmp_path):
    import json
    import os
    import subprocess
    from lib import registry

    state = tmp_path / ".aura"
    target_package = tmp_path / "target-agent"
    keeper_package = tmp_path / "keeper-agent"
    (target_package / ".codex").mkdir(parents=True)
    (keeper_package / ".codex").mkdir(parents=True)
    (target_package / "manifest.json").write_text(
        json.dumps({"schema": "aura.agent_manifest.v1", "runtime": "codex"}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AURA_STATE_DIR", str(state))

    registry.upsert_agent({
        "name": "manager",
        "fleet": "flexgraph-chatbot-adapters",
        "runtime": "codex",
        "registered": True,
        "cwd": str(tmp_path),
        "seat_instance_id": "si_target",
        "agent_package_id": "i_target",
        "agent_package_root": str(target_package),
    })

    env = {
        **os.environ,
        "AURA_STATE_DIR": str(state),
        "AURA_FLEET": "flexgraph-chatbot-adapters",
        "AURA_SEAT": "manager",
        "AURA_RUNTIME": "codex",
        "AURA_SEAT_INSTANCE_ID": "si_target",
        "AURA_AGENT_PACKAGE_ID": "i_target",
        "AURA_AGENT_PACKAGE_ROOT": str(target_package),
        "AURA_RUNTIME_CAPSULE_REF": str(target_package),
        "CODEX_HOME": str(keeper_package / ".codex"),
    }
    payload = {
        "hook_event_name": "SessionStart",
        "session_id": "keeper-thread",
        "transcript_path": str(keeper_package / ".codex" / "sessions" / "keeper.jsonl"),
    }
    result = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "hooks" / "codex_bind_hook.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=5,
    )

    assert result.returncode == 0
    assert result.stdout == ""
    row = registry.get_agent("manager", fleet="flexgraph-chatbot-adapters")
    assert "runtime_session_id" not in row


# ---------------------------------------------------------------------------
# _heal tests (Node E)
# ---------------------------------------------------------------------------

def _make_heal_args(*, target=None, fleet=None, all=False, dry_run=False, repair=False):
    """Build a minimal args Namespace for sessions._heal."""
    return argparse.Namespace(
        target=target,
        fleet=fleet,
        all=all,
        dry_run=dry_run,
        repair=repair,
    )


def _write_nonce_jsonl(jsonl_path, nonce, session_id, cwd=None):
    """Write a minimal Codex JSONL with the nonce string and a session_meta row."""
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    jsonl_path.write_text(
        json.dumps({
            "type": "session_meta",
            "payload": {
                "id": session_id,
                "cwd": cwd or "/repo/heal-test",
                "timestamp": "2026-06-04T10:00:00Z",
                "aura_launch_id": nonce,
            },
        }) + "\n",
        encoding="utf-8",
    )


def test_heal_non_package_alive_unbound_seat_heals_via_nonce(monkeypatch, tmp_path):
    """An alive, unbound, non-package codex seat with a findable launch nonce must be healed."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    nonce = "aura-launch-heal-nonce-test-01"
    session_id = "019f1234-heal-nonce-0000-000000000001"
    workdir = str(tmp_path / "repo")
    codex_home = tmp_path / "codex-home"
    jsonl = codex_home / "sessions" / "heal-test.jsonl"
    _write_nonce_jsonl(jsonl, nonce, session_id, cwd=workdir)

    pane_ref = "tmux:healfleet:%42"

    from commands import sessions
    from lib import registry, runtime_session, terminal as terminal_mod

    registry.upsert_agent({
        "name": "engineer",
        "fleet": "healfleet",
        "runtime": "codex",
        "registered": True,
        "cwd": workdir,
        "workdir": workdir,
        "aura_launch_id": nonce,
        "pane_ref": pane_ref,
        # Non-package seat: no agent_package_id, no agent_package_root
        "codex_box_codex_home": str(codex_home),
    })

    # Make the terminal report pane as alive
    monkeypatch.setattr(terminal_mod, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal_mod, "target_exists", lambda target: target == pane_ref)

    result = sessions._heal(_make_heal_args(target="healfleet:engineer"))

    assert result["ok"] is True
    assert result["healed"] == 1
    assert result["refused"] == 0
    assert result["skipped"] == 0
    assert result["results"][0]["status"] == "healed"
    assert result["results"][0]["method"] == "nonce"
    assert result["results"][0]["session_id"] == session_id

    # Verify registry was actually updated
    row = registry.get_agent("engineer", fleet="healfleet")
    assert runtime_session.is_bound_session(row) is True
    assert row["runtime_session_id"] == session_id
    assert row["runtime_session_source"] == "codex-jsonl:nonce"


def test_heal_binds_claude_seat_via_pane_session_fk(monkeypatch, tmp_path):
    """An alive, unbound claude-code seat must heal through the pane->session FK.

    Regression: heal previously skipped any non-codex/omx runtime as
    'unsupported-runtime', so claude seats stayed unbound forever even though
    bind-pane/bind-hook supported them. Now claude routes to attempt b (pane),
    which resolves via the statusline-captured map (tmux-pane:claude-statusline-map).
    """
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    from commands import sessions
    from lib import registry, runtime_session, terminal as terminal_mod, pane_resolver

    pane_ref = "tmux:cfleet:%47"
    session_id = "0a9a591b-claude-fk-0000-000000000001"

    registry.upsert_agent({
        "name": "manager", "fleet": "cfleet", "runtime": "claude-code",
        "registered": True, "pane_ref": pane_ref, "cwd": str(tmp_path / "repo"),
    })  # no session bound -> unbound

    monkeypatch.setattr(terminal_mod, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal_mod, "target_exists", lambda target: target == pane_ref)
    # the claude pane->session FK resolves the live session exactly
    monkeypatch.setattr(pane_resolver, "resolve_pane", lambda **kw: {
        "ok": True,
        "runtime_session_id": session_id,
        "runtime_session_source": "tmux-pane:claude-statusline-map",
        "runtime_session_confidence": "exact",
        "pane_pid": None,
    })
    monkeypatch.setattr(pane_resolver, "bind_gates", lambda res, previous=None, repair=False: {"ok": True})

    result = sessions._heal(_make_heal_args(target="cfleet:manager"))

    assert result["healed"] == 1, result
    assert result["results"][0]["status"] == "healed"
    assert result["results"][0]["method"] == "pane"
    row = registry.get_agent("manager", fleet="cfleet")
    assert runtime_session.is_bound_session(row) is True
    assert row["runtime_session_source"] == "tmux-pane:claude-statusline-map"


def test_heal_contaminated_package_record_is_refused(monkeypatch, tmp_path):
    """A contaminated package record (runtime_home under a different root) is refused — no registry write."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    nonce = "aura-launch-heal-contaminated-test-02"
    session_id = "019f1234-heal-cont-0000-000000000002"
    scout_root = str(tmp_path / "i_scout")
    manager_root = str(tmp_path / "i_manager")

    codex_home = tmp_path / "i_scout" / ".codex"
    jsonl = codex_home / "sessions" / "contaminated.jsonl"
    # Write the nonce in the scout package's codex home
    _write_nonce_jsonl(jsonl, nonce, session_id, cwd=scout_root)

    pane_ref = "tmux:contamfleet:%99"

    from commands import sessions
    from lib import registry, terminal as terminal_mod

    registry.upsert_agent({
        "name": "scout",
        "fleet": "contamfleet",
        "runtime": "codex",
        "registered": True,
        "cwd": scout_root,
        "workdir": scout_root,
        "aura_launch_id": nonce,
        "pane_ref": pane_ref,
        # Contaminated: agent_package_id/root point to scout, but runtime_home
        # and native_state_ref point to manager (the bind_guard detects this)
        "agent_package_id": "i_scout",
        "agent_package_root": scout_root,
        "runtime_home": manager_root,
        "native_state_ref": f"{manager_root}/.codex",
    })

    monkeypatch.setattr(terminal_mod, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal_mod, "target_exists", lambda target: target == pane_ref)

    result = sessions._heal(_make_heal_args(target="contamfleet:scout"))

    assert result["ok"] is True
    assert result["refused"] == 1
    assert result["healed"] == 0
    row_after = registry.get_agent("scout", fleet="contamfleet")
    assert "runtime_session_id" not in (row_after or {})
    assert result["results"][0]["status"] == "refused"
    assert result["results"][0]["reason"] == "package-env-mismatch"


def test_heal_seat_with_no_nonce_and_no_exact_pane_evidence_is_skipped(monkeypatch, tmp_path):
    """A seat with no aura_launch_id and no exact pane evidence is skipped (no-exact-evidence)."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    pane_ref = "tmux:noevfleet:%77"

    from commands import sessions
    from lib import registry, runtime_session, terminal as terminal_mod

    registry.upsert_agent({
        "name": "worker",
        "fleet": "noevfleet",
        "runtime": "codex",
        "registered": True,
        "cwd": str(tmp_path / "repo"),
        "pane_ref": pane_ref,
        # No aura_launch_id
    })

    monkeypatch.setattr(terminal_mod, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal_mod, "target_exists", lambda target: target == pane_ref)

    # Make pane resolver return no exact evidence (pane doesn't actually exist in tmux)
    from lib import pane_resolver
    monkeypatch.setattr(
        pane_resolver,
        "resolve_pane",
        lambda pane=None, current=False: {"ok": False, "error": "pane-not-found", "pane": pane},
    )

    result = sessions._heal(_make_heal_args(target="noevfleet:worker"))

    assert result["ok"] is True
    assert result["skipped"] == 1
    assert result["healed"] == 0
    assert result["refused"] == 0
    assert result["results"][0]["status"] == "skipped"
    assert result["results"][0]["reason"] == "no-exact-evidence"

    # Confirm registry row stays unbound
    row = registry.get_agent("worker", fleet="noevfleet")
    assert not runtime_session.is_bound_session(row)


def test_heal_dry_run_performs_no_registry_write(monkeypatch, tmp_path):
    """--dry-run must report would-heal but never write the registry."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    nonce = "aura-launch-heal-dryrun-test-04"
    session_id = "019f1234-heal-dry0-0000-000000000004"
    workdir = str(tmp_path / "repo")
    codex_home = tmp_path / "codex-home-dry"
    jsonl = codex_home / "sessions" / "dryrun.jsonl"
    _write_nonce_jsonl(jsonl, nonce, session_id, cwd=workdir)

    pane_ref = "tmux:dryfleet:%55"

    from commands import sessions
    from lib import registry, runtime_session, terminal as terminal_mod

    registry.upsert_agent({
        "name": "builder",
        "fleet": "dryfleet",
        "runtime": "codex",
        "registered": True,
        "cwd": workdir,
        "workdir": workdir,
        "aura_launch_id": nonce,
        "pane_ref": pane_ref,
        "codex_box_codex_home": str(codex_home),
    })

    monkeypatch.setattr(terminal_mod, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal_mod, "target_exists", lambda target: target == pane_ref)

    result = sessions._heal(_make_heal_args(target="dryfleet:builder", dry_run=True))

    assert result["ok"] is True
    assert result["dry_run"] is True
    # dry-run still counts as "healed" (would-heal) in the healed counter
    assert result["healed"] == 1
    assert result["results"][0]["status"] == "would-heal"
    assert result["results"][0]["method"] == "nonce"
    assert result["results"][0]["session_id"] == session_id

    # Registry must NOT have been updated
    row = registry.get_agent("builder", fleet="dryfleet")
    assert not runtime_session.is_bound_session(row), "dry-run must not write the registry"
    assert "session_id" not in row


# ---- phantom-binding invariant + self-heal (fix/binding-invariant-selfheal) ---- #

def test_normalize_downgrades_phantom_bound_to_unbound():
    """INVARIANT: a row claiming bound with no runtime session id is a phantom."""
    from lib import registry, runtime_session
    out = registry.normalize_agent_record({
        "name": "manager", "fleet": "pfleet", "runtime": "claude-code",
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": "tmux-pane:env",
        # no runtime_session_id / session_id
    })
    assert out["runtime_session_binding"] == "unbound"
    assert out.get("runtime_session_phantom_downgraded") is True
    assert out.get("runtime_session_bind_method") is None
    assert runtime_session.is_bound_session(out) is False


def test_normalize_keeps_real_bound_row():
    from lib import registry, runtime_session
    out = registry.normalize_agent_record({
        "name": "manager", "fleet": "pfleet", "runtime": "claude-code",
        "runtime_session_binding": "bound", "runtime_session_id": "real-sess-1",
    })
    assert out["runtime_session_binding"] == "bound"
    assert out.get("runtime_session_phantom_downgraded") is None
    assert runtime_session.is_bound_session(out) is True


def test_upsert_refuses_to_persist_phantom_bound(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    from lib import registry, runtime_session
    registry.upsert_agent({
        "name": "manager", "fleet": "pfleet", "runtime": "claude-code",
        "registered": True, "pane_ref": "tmux:pfleet:%9",
        "runtime_session_binding": "bound",            # phantom in -> must store unbound
        "runtime_session_bind_method": "tmux-pane:env",
    })
    row = registry.get_agent("manager", fleet="pfleet")
    assert row["runtime_session_binding"] == "unbound"
    assert not row.get("runtime_session_id")
    assert runtime_session.is_bound_session(row) is False


def test_heal_does_not_skip_phantom_bound_record(monkeypatch, tmp_path):
    """A phantom-bound record (binding=bound, runtime_session_id null, even with a
    stale session_id) must NOT be skipped as already-bound — it heals to the real
    live session via the pane->session FK."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    from commands import sessions
    from lib import registry, runtime_session, terminal as terminal_mod, pane_resolver, bind_guard

    pane_ref = "tmux:pfleet:%9"
    real_session = "1111aaaa-real-fk-0000-000000000001"
    phantom = {
        "name": "manager", "fleet": "pfleet", "runtime": "claude-code",
        "registered": True, "pane_ref": pane_ref, "cwd": str(tmp_path / "repo"),
        "runtime_session_binding": "bound",
        "session_id": "stale-recorded-nowhere",   # is_bound_session() True...
        "runtime_session_id": None,                # ...but no canonical runtime session
    }
    # feed heal the raw phantom candidate (bypassing the normalize downgrade)
    monkeypatch.setattr(registry, "list_agents", lambda fleet=None, include_hidden=False: [dict(phantom)])
    monkeypatch.setattr(terminal_mod, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal_mod, "target_exists", lambda target: target == pane_ref)
    monkeypatch.setattr(pane_resolver, "resolve_pane", lambda **kw: {
        "ok": True, "runtime_session_id": real_session,
        "runtime_session_source": "tmux-pane:claude-statusline-map",
        "runtime_session_confidence": "exact", "pane_pid": None,
    })
    monkeypatch.setattr(pane_resolver, "bind_gates", lambda res, previous=None, repair=False: {"ok": True})
    monkeypatch.setattr(bind_guard, "body_gates", lambda *a, **k: {"ok": True})

    result = sessions._heal(_make_heal_args(all=True))
    statuses = {r["seat"]: r["status"] for r in result["results"]}
    assert statuses.get("pfleet:manager") != "skipped", result   # NOT 'already-bound'
    assert result["healed"] == 1, result
    row = registry.get_agent("manager", fleet="pfleet")
    assert row.get("runtime_session_id") == real_session
    assert runtime_session.is_bound_session(row) is True


def test_phantom_bound_seat_self_heals_to_real_session(monkeypatch, tmp_path):
    """Acceptance: a phantom-bound row entering the registry is downgraded to
    unbound (invariant), then the sweep binds it to the real live session."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    from commands import sessions
    from lib import registry, runtime_session, terminal as terminal_mod, pane_resolver, bind_guard

    pane_ref = "tmux:pfleet:%9"
    real_session = "2222bbbb-real-fk-0000-000000000002"
    registry.upsert_agent({
        "name": "manager", "fleet": "pfleet", "runtime": "claude-code",
        "registered": True, "pane_ref": pane_ref, "cwd": str(tmp_path / "repo"),
        "runtime_session_binding": "bound", "runtime_session_bind_method": "tmux-pane:env",
    })
    # invariant: stored unbound (phantom can't persist)
    assert registry.get_agent("manager", fleet="pfleet")["runtime_session_binding"] == "unbound"

    monkeypatch.setattr(terminal_mod, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal_mod, "target_exists", lambda target: target == pane_ref)
    monkeypatch.setattr(pane_resolver, "resolve_pane", lambda **kw: {
        "ok": True, "runtime_session_id": real_session,
        "runtime_session_source": "tmux-pane:claude-statusline-map",
        "runtime_session_confidence": "exact", "pane_pid": None,
    })
    monkeypatch.setattr(pane_resolver, "bind_gates", lambda res, previous=None, repair=False: {"ok": True})
    monkeypatch.setattr(bind_guard, "body_gates", lambda *a, **k: {"ok": True})

    result = sessions._heal(_make_heal_args(target="pfleet:manager"))
    assert result["healed"] == 1, result
    row = registry.get_agent("manager", fleet="pfleet")
    assert row["runtime_session_id"] == real_session
    assert runtime_session.is_bound_session(row) is True

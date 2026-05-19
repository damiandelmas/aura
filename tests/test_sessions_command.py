"""Tests for `aura sessions` row contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


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


def test_sessions_rows_mark_bound_omx_restore_ready(monkeypatch):
    from commands import sessions

    monkeypatch.setattr(
        sessions.list_cmd,
        "run",
        lambda _args: [
            {
                "seat": "pipeline",
                "fleet": "flexgraph-chatbot",
                "runtime": "omx",
                "terminal": "alive",
                "runtime_session_id": "019e3334-6cf5-72cb-aafb-9e423bfb9f86",
                "session_id": "019e3334-6cf5-72cb-aafb-9e423bfb9f86",
                "runtime_session_binding": "bound",
                "runtime_session_bind_method": "codex-hook",
                "runtime_session_source": "codex-hook:session-start",
                "cwd": "/repo/flexgraph/chatbot",
            }
        ],
    )

    result = sessions.run(argparse.Namespace(
        sessions_action=None,
        fleet=None,
        live=True,
        include_hidden=True,
    ))

    row = result["rows"][0]
    assert row["runtime_capabilities"]["supports_resume"] is True
    assert row["restore_ready"] is True
    assert row["restore_reason"] == "bound-session-id-and-runtime-resume-supported"


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


def test_codex_bind_hook_script_accepts_omx_package_without_capsule_residue(monkeypatch, tmp_path):
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

    assert result.returncode == 0
    assert result.stdout == ""
    row = registry.get_agent("pipeline", fleet="flexgraph-chatbot")
    assert row["runtime"] == "omx"
    assert row["runtime_session_id"] == "thread-omx-hook"
    assert "runtime_capsule_session" not in row
    assert not (capsule / "runtime-session.json").exists()
    assert not (capsule / "receipts").exists()
    assert not (capsule / "artifacts").exists()

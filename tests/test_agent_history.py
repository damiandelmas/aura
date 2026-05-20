import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _create_agent(tmp_path, *, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    result = agent_packages.create(
        address="flexgraph:chatbot:pipeline:conductor",
        runtime="codex",
        profile=None,
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="pipeline",
        alias="pipeline-conductor",
    )
    return result["agent"]


def test_build_returns_current_rows_for_package_id(monkeypatch, tmp_path):
    agent = _create_agent(tmp_path, monkeypatch=monkeypatch)

    from lib import agent_history, registry

    registry.write_registry(
        {
            "flexgraph-chatbot:pipeline": {
                "name": "pipeline",
                "seat": "pipeline",
                "fleet": "flexgraph-chatbot",
                "runtime": "codex",
                "cwd": str(tmp_path / "unit"),
                "agent_package_id": agent["agent_id"],
                "runtime_session_id": "session-current",
                "aura_launch_id": "launch-current",
                "seat_instance_id": "si_current",
                "ignored_none": None,
            },
            "flexgraph-chatbot:other": {
                "name": "other",
                "fleet": "flexgraph-chatbot",
                "runtime_session_id": "session-other",
            },
        }
    )

    result = agent_history.build("pipeline-conductor")

    assert result["schema"] == "aura.agent_history.v1"
    assert result["identity"] == agent["agent_id"]
    assert result["current"] == [
        {
            "ref": "flexgraph-chatbot:pipeline",
            "session_id": "session-current",
            "runtime": "codex",
            "cwd": str(tmp_path / "unit"),
            "aura_launch_id": "launch-current",
            "seat_instance_id": "si_current",
        }
    ]


def test_build_matches_current_rows_through_aura_identity(monkeypatch, tmp_path):
    agent = _create_agent(tmp_path, monkeypatch=monkeypatch)

    from lib import agent_history, registry

    registry.write_registry(
        {
            "ops:lead": {
                "name": "lead",
                "fleet": "ops",
                "identity_provider": "aura-agent",
                "identity_id": agent["agent_id"],
                "runtime_session_id": "session-identity",
            },
            "ops:not-agent": {
                "name": "not-agent",
                "fleet": "ops",
                "identity_provider": "desks",
                "identity_id": agent["agent_id"],
                "runtime_session_id": "session-desks",
            },
        }
    )

    result = agent_history.build(agent["agent_id"])

    assert result["current"] == [{"ref": "ops:lead", "session_id": "session-identity"}]


def test_build_returns_matching_session_ledger_history(monkeypatch, tmp_path):
    agent = _create_agent(tmp_path, monkeypatch=monkeypatch)

    from lib import agent_history, session_ledger

    session_ledger.append_record(
        {
            "timestamp": "2026-05-20T17:00:16+00:00",
            "event": "seat_spawned",
            "agent_package_id": agent["agent_id"],
            "fleet": "flexgraph-chatbot",
            "seat": "pipeline",
            "runtime": "codex",
            "runtime_session_id": "session-ledger",
            "aura_launch_id": "launch-older",
        }
    )
    session_ledger.append_record(
        {
            "timestamp": "2026-05-20T17:01:16+00:00",
            "event": "seat_spawned",
            "agent_package_id": agent["agent_id"],
            "fleet": "flexgraph-chatbot",
            "seat": "pipeline",
            "runtime": "codex",
            "runtime_session_id": "session-ledger",
            "aura_launch_id": "launch-ledger",
        }
    )
    session_ledger.append_record(
        {
            "timestamp": "2026-05-20T17:02:16+00:00",
            "event": "seat_restarted",
            "before": {
                "fleet": "flexgraph-chatbot",
                "seat": "pipeline",
                "identity_provider": "aura-agent",
                "identity_id": agent["agent_id"],
                "runtime_session_id": "session-before",
            },
            "after": {
                "fleet": "flexgraph-chatbot",
                "seat": "pipeline",
                "identity_provider": "aura-agent",
                "identity_id": agent["agent_id"],
                "runtime_session_id": "session-after",
                "seat_instance_id": "si_after",
            },
        }
    )
    session_ledger.append_record(
        {
            "timestamp": "2026-05-20T17:03:16+00:00",
            "event": "seat_spawned",
            "fleet": "other",
            "seat": "worker",
            "runtime_session_id": "session-other",
        }
    )

    result = agent_history.build("pipeline-conductor")

    assert result["history"] == [
        {
            "ref": "flexgraph-chatbot:pipeline",
            "session_id": "session-ledger",
            "event": "seat_spawned",
            "timestamp": "2026-05-20T17:01:16+00:00",
            "runtime": "codex",
            "aura_launch_id": "launch-ledger",
        },
        {
            "ref": "flexgraph-chatbot:pipeline",
            "session_id": "session-after",
            "event": "seat_restarted",
            "timestamp": "2026-05-20T17:02:16+00:00",
            "seat_instance_id": "si_after",
        },
    ]


def test_write_creates_aura_json_without_mutating_manifest(monkeypatch, tmp_path):
    agent = _create_agent(tmp_path, monkeypatch=monkeypatch)

    from lib import agent_history, registry

    root = Path(agent["root"])
    manifest_path = root / "manifest.json"
    manifest_before = manifest_path.read_text(encoding="utf-8")
    registry.write_registry(
        {
            "flexgraph-chatbot:pipeline": {
                "name": "pipeline",
                "fleet": "flexgraph-chatbot",
                "agent_package_id": agent["agent_id"],
                "runtime_session_id": "session-current",
            }
        }
    )

    path = agent_history.write("pipeline-conductor")
    written = json.loads(path.read_text(encoding="utf-8"))

    assert path == root / "aura.json"
    assert written["schema"] == "aura.agent_history.v1"
    assert written["identity"] == agent["agent_id"]
    assert written["current"] == [{"ref": "flexgraph-chatbot:pipeline", "session_id": "session-current"}]
    assert manifest_path.read_text(encoding="utf-8") == manifest_before


def test_generated_entries_omit_null_heavy_noise(monkeypatch, tmp_path):
    agent = _create_agent(tmp_path, monkeypatch=monkeypatch)

    from lib import agent_history, registry

    registry.write_registry(
        {
            "flexgraph-chatbot:pipeline": {
                "name": "pipeline",
                "fleet": "flexgraph-chatbot",
                "agent_package_id": agent["agent_id"],
                "runtime_session_id": None,
                "runtime": None,
                "cwd": None,
            }
        }
    )

    result = agent_history.build("pipeline-conductor")

    assert result["current"] == [{"ref": "flexgraph-chatbot:pipeline"}]
    assert all(value is not None for entry in result["current"] for value in entry.values())


def test_agent_history_cli_and_command_envelope(monkeypatch, tmp_path):
    agent = _create_agent(tmp_path, monkeypatch=monkeypatch)

    from commands import agent as agent_cmd
    from lib import registry

    registry.write_registry(
        {
            "flexgraph-chatbot:pipeline": {
                "name": "pipeline",
                "fleet": "flexgraph-chatbot",
                "agent_package_id": agent["agent_id"],
                "runtime_session_id": "session-current",
            }
        }
    )

    result = agent_cmd.run(argparse.Namespace(agent_action="history", ref="pipeline-conductor", write=True))

    assert result["ok"] is True
    assert Path(result["path"]).is_file()
    assert result["history"]["current"] == [{"ref": "flexgraph-chatbot:pipeline", "session_id": "session-current"}]

    env = {**os.environ, "AURA_STATE_DIR": str(tmp_path / "state")}
    cli = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "aura"), "agent", "history", "pipeline-conductor"],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    output = json.loads(cli.stdout)
    assert output["ok"] is True
    assert output["history"]["identity"] == agent["agent_id"]

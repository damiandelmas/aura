import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_agent_create_writes_minimal_package(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    result = agent_packages.create(
        address="flexgraph:chatbot:pipeline:conductor",
        runtime="omx",
        profile="omx/aura-operator",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="pipeline",
        alias="pipeline-conductor",
    )

    assert result["ok"] is True
    agent = result["agent"]
    root = Path(agent["root"])
    assert agent["agent_id"].startswith("i_")
    assert agent["address"] == "flexgraph:chatbot:pipeline:conductor"
    assert agent["profile"] == "omx/aura-operator"
    assert (root / "agent.json").is_file()
    assert (root / "home").is_dir()
    assert (root / ".codex").is_dir()
    assert (root / ".omx" / "state").is_dir()
    assert (root / ".desks" / "identity.json").is_file()
    assert (root / "receipts").is_dir()
    assert (root / "artifacts").is_dir()


def test_agent_inspect_resolves_address_and_alias(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    created = agent_packages.create(
        address="flexgraph:chatbot:engineer:runtime",
        runtime="codex",
        profile="worker",
        cwd=str(tmp_path),
        fleet="flexgraph-chatbot",
        seat="engineer",
        alias="eng-runtime",
    )

    by_address = agent_packages.inspect("flexgraph:chatbot:engineer:runtime")
    by_alias = agent_packages.inspect("eng-runtime")

    assert by_address["ok"] is True
    assert by_address["agent"]["agent_id"] == created["agent"]["agent_id"]
    assert by_alias["agent"]["root"] == created["agent"]["root"]
    assert by_address["agent"]["profile"] == "codex/worker"
    assert "agent_json" in by_address["files"]


def test_agent_spawn_delegates_package_roots(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import agent as agent_cmd
    from commands import spawn
    from lib import agent_packages

    created = agent_packages.create(
        address="flexgraph:chatbot:pipeline:conductor",
        runtime="omx",
        profile="omx/aura-operator",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="pipeline",
        alias=None,
    )
    captured = {}

    def fake_spawn(args):
        captured.update(vars(args))
        return {
            "ok": True,
            "name": args.name,
            "fleet": args.fleet,
            "runtime": args.runtime,
            "cwd": args.cwd,
            "runtime_capsule_ref": args._agent_package["root"],
        }

    monkeypatch.setattr(spawn, "run", fake_spawn)
    result = agent_cmd.run(
        argparse.Namespace(
            agent_action="spawn",
            ref="flexgraph:chatbot:pipeline:conductor",
            cwd=None,
            fleet=None,
            seat=None,
            prompt=None,
            model=None,
            wait=False,
            timeout=30,
            as_pane=True,
        )
    )

    assert result["ok"] is True
    assert captured["runtime"] == "omx"
    assert captured["omx_profile"] is None
    assert captured["runtime_profile"] == "omx/aura-operator"
    assert captured["identity_provider"] == "aura-agent"
    assert captured["identity_id"] == created["agent"]["agent_id"]
    assert captured["_agent_package"]["root"] == created["agent"]["root"]
    inspected = agent_packages.inspect(created["agent"]["agent_id"])
    assert inspected["agent"]["spawn_history"][0]["runtime_capsule_ref"] == created["agent"]["root"]


def test_agent_spawn_latest_resume_reads_package_runtime_session(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import agent as agent_cmd
    from commands import spawn
    from lib import agent_packages

    created = agent_packages.create(
        address="flexgraph:chatbot:pipeline:conductor",
        runtime="omx",
        profile="omx/aura-operator",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="pipeline",
        alias="pipeline-conductor",
    )
    root = Path(created["agent"]["root"])
    (root / "runtime-session.json").write_text(
        json.dumps({"runtime_session_id": "019e3334-6cf5-72cb-aafb-9e423bfb9f86"}) + "\n",
        encoding="utf-8",
    )
    captured = {}

    def fake_spawn(args):
        captured.update(vars(args))
        return {
            "ok": True,
            "name": args.name,
            "fleet": args.fleet,
            "runtime": args.runtime,
            "runtime_session_id": args.resume_session,
            "runtime_capsule_ref": args._agent_package["root"],
        }

    monkeypatch.setattr(spawn, "run", fake_spawn)
    result = agent_cmd.run(
        argparse.Namespace(
            agent_action="spawn",
            ref="pipeline-conductor",
            cwd=None,
            fleet=None,
            seat=None,
            prompt=None,
            resume_session="latest",
            model=None,
            wait=False,
            timeout=30,
            as_pane=True,
        )
    )

    assert result["ok"] is True
    assert captured["resume_session"] == "019e3334-6cf5-72cb-aafb-9e423bfb9f86"
    assert captured["runtime"] == "omx"


def test_codex_prepare_box_supports_agent_package_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    source_codex = tmp_path / "source-codex"
    source_codex.mkdir()
    monkeypatch.setenv("AURA_CODEX_SOURCE_CODEX_HOME", str(source_codex))
    cwd = tmp_path / "project"
    cwd.mkdir()

    from lib import codex

    root = tmp_path / "state" / "agents" / "i_pkg"
    box = codex.prepare_box(
        fleet="fleet",
        seat="seat",
        source_cwd=str(cwd),
        profile=None,
        root_override=root,
        package_layout=True,
    )

    assert box.root == root.resolve()
    assert box.home == root / "home"
    assert box.codex_home == root / ".codex"
    assert (root / ".codex" / "hooks.json").is_file()


def test_agent_cli_create_and_inspect_public_argv(tmp_path):
    env = {**os.environ, "AURA_STATE_DIR": str(tmp_path / "state")}
    create = subprocess.run(
        [
            sys.executable,
            str(ROOT / "cli" / "aura"),
            "agent",
            "create",
            "flexgraph:chatbot:pipeline:conductor",
            "--runtime",
            "omx",
            "--profile",
            "omx/aura-operator",
            "--cwd",
            str(tmp_path / "unit"),
            "--fleet",
            "flexgraph-chatbot",
            "--seat",
            "pipeline",
            "--alias",
            "pipeline-conductor",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    created = json.loads(create.stdout)
    assert created["ok"] is True

    inspect = subprocess.run(
        [
            sys.executable,
            str(ROOT / "cli" / "aura"),
            "agent",
            "inspect",
            "pipeline-conductor",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    inspected = json.loads(inspect.stdout)
    assert inspected["ok"] is True
    assert inspected["agent"]["address"] == "flexgraph:chatbot:pipeline:conductor"
    assert inspected["agent"]["root"] == created["agent"]["root"]
    assert Path(inspected["agent"]["root"], ".codex").is_dir()


def test_agent_index_corruption_fails_loudly(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    from lib import agent_packages

    agent_packages.index_path().parent.mkdir(parents=True)
    agent_packages.index_path().write_text("{not-json", encoding="utf-8")

    try:
        agent_packages.inspect("anything")
    except ValueError as exc:
        assert "invalid agent package index" in str(exc)
    else:
        raise AssertionError("corrupt index should not silently reset")

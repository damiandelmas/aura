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
    assert (root / "manifest.json").is_file()
    assert not (root / "agent.json").exists()
    assert (root / ".codex").is_dir()
    assert (root / ".omx" / "state").is_dir()
    assert not (root / "home").exists()
    assert not (root / ".desks").exists()
    assert not (root / "runtime").exists()
    assert not (root / "receipts").exists()
    assert not (root / "artifacts").exists()
    body = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert body == {
        "argv": ["omx"],
        "cwd": str((tmp_path / "unit").resolve()),
        "env": {"CODEX_HOME": ".codex", "OMX_ROOT": ".", "OMX_TEAM_STATE_ROOT": ".omx/state"},
        "fleet": "flexgraph-chatbot",
        "profile": "omx/aura-operator",
        "resume": {"default": "latest"},
        "runtime": "omx",
        "schema": "aura.agent_manifest.v1",
        "seat": "pipeline",
    }


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
    assert "manifest" in by_address["files"]
    root = Path(created["agent"]["root"])
    assert (root / ".codex").is_dir()
    assert not (root / ".omx").exists()


def test_agent_adopt_root_indexes_existing_package_body(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    root = tmp_path / "state" / "agents" / "i_existing"
    (root / ".codex").mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "aura.agent_manifest.v1",
                "runtime": "codex",
                "cwd": str(tmp_path / "unit"),
                "fleet": "flexgraph-chatbot",
                "seat": "manager",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    adopted = agent_packages.adopt_root(
        root=str(root),
        address="flexgraph:chatbot:ops:manager",
        alias="ops-manager",
    )
    resolved = agent_packages.resolve("ops-manager")
    census = agent_packages.census()

    assert adopted["ok"] is True
    assert adopted["agent"]["agent_id"] == "i_existing"
    assert resolved["root"] == str(root.resolve())
    assert census["packages"][0]["indexed"] is True
    assert census["packages"][0]["classification"] == "durable-package-unbound"


def test_agent_adopt_root_refuses_broken_body(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    root = tmp_path / "state" / "agents" / "i_broken"
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "aura.agent_manifest.v1",
                "runtime": "codex",
                "cwd": str(tmp_path / "unit"),
                "fleet": "flexgraph-chatbot",
                "seat": "manager",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        agent_packages.adopt_root(
            root=str(root),
            address="flexgraph:chatbot:ops:broken",
        )
    except FileNotFoundError as exc:
        assert "missing-runtime-root:.codex" in str(exc)
    else:
        raise AssertionError("broken package body should not be indexed")

    assert agent_packages.read_index()["agents"] == {}


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
            resume_session=None,
            fresh=True,
            model=None,
            wait=False,
            timeout=30,
            as_pane=True,
        )
    )

    assert result["ok"] is True
    assert captured["runtime"] == "omx"
    assert captured["resume_session"] is None
    assert captured["omx_profile"] is None
    assert captured["runtime_profile"] == "omx/aura-operator"
    assert captured["identity_provider"] == "aura-agent"
    assert captured["identity_id"] == created["agent"]["agent_id"]
    assert captured["_agent_package"]["root"] == created["agent"]["root"]
    inspected = agent_packages.inspect(created["agent"]["agent_id"])
    assert "spawn_history" not in inspected["agent"]
    body = json.loads((Path(created["agent"]["root"]) / "manifest.json").read_text(encoding="utf-8"))
    assert "spawn_history" not in body


def test_agent_spawn_defaults_to_latest_valid_package_runtime_session(monkeypatch, tmp_path):
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
    from lib import registry

    registry.upsert_agent({
        "name": "pipeline",
        "fleet": "flexgraph-chatbot",
        "runtime": "omx",
        "agent_package_id": created["agent"]["agent_id"],
        "runtime_session_id": "newer-unbound",
        "runtime_session_binding": "unbound",
        "runtime_session_updated_at_ms": 9,
    })
    registry.upsert_agent({
        "name": "pipeline-old",
        "fleet": "flexgraph-chatbot",
        "runtime": "omx",
        "agent_package_id": created["agent"]["agent_id"],
        "runtime_session_id": "019e3334-6cf5-72cb-aafb-9e423bfb9f86",
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": "codex-hook",
        "runtime_session_bind_source": "codex-hook:session-start",
        "runtime_session_updated_at_ms": 1,
    })
    registry.upsert_agent({
        "name": "pipeline-wrong-runtime",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
        "agent_package_id": created["agent"]["agent_id"],
        "runtime_session_id": "wrong-runtime",
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": "codex-hook",
        "runtime_session_bind_source": "codex-hook:session-start",
        "runtime_session_updated_at_ms": 20,
    })
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
            resume_session=None,
            fresh=False,
            model=None,
            wait=False,
            timeout=30,
            as_pane=True,
        )
    )

    assert result["ok"] is True
    assert captured["resume_session"] == "019e3334-6cf5-72cb-aafb-9e423bfb9f86"
    assert captured["runtime"] == "omx"


def test_agent_spawn_latest_resume_reads_package_runtime_session(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import agent as agent_cmd
    from commands import spawn
    from lib import agent_packages, registry

    created = agent_packages.create(
        address="flexgraph:chatbot:pipeline:conductor",
        runtime="omx",
        profile="omx/aura-operator",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="pipeline",
        alias="pipeline-conductor",
    )
    registry.upsert_agent({
        "name": "pipeline",
        "fleet": "flexgraph-chatbot",
        "runtime": "omx",
        "agent_package_id": created["agent"]["agent_id"],
        "runtime_session_id": "019e3334-6cf5-72cb-aafb-9e423bfb9f86",
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": "codex-hook",
        "runtime_session_bind_source": "codex-hook:session-start",
        "runtime_session_updated_at_ms": 1,
    })
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
            fresh=False,
            model=None,
            wait=False,
            timeout=30,
            as_pane=True,
        )
    )

    assert result["ok"] is True
    assert captured["resume_session"] == "019e3334-6cf5-72cb-aafb-9e423bfb9f86"
    assert captured["runtime"] == "omx"


def test_agent_spawn_default_resume_requires_valid_package_session(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import agent as agent_cmd
    from commands import spawn
    from lib import agent_packages, registry

    created = agent_packages.create(
        address="flexgraph:chatbot:pipeline:conductor",
        runtime="omx",
        profile="omx/aura-operator",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="pipeline",
        alias="pipeline-conductor",
    )
    registry.upsert_agent({
        "name": "pipeline",
        "fleet": "flexgraph-chatbot",
        "runtime": "omx",
        "agent_package_id": created["agent"]["agent_id"],
        "runtime_session_id": "unbound-session",
        "runtime_session_binding": "unbound",
        "runtime_session_updated_at_ms": 1,
    })

    called = False

    def fake_spawn(_args):
        nonlocal called
        called = True
        return {"ok": True}

    monkeypatch.setattr(spawn, "run", fake_spawn)
    result = agent_cmd.run(
        argparse.Namespace(
            agent_action="spawn",
            ref="pipeline-conductor",
            cwd=None,
            fleet=None,
            seat=None,
            prompt=None,
            resume_session=None,
            fresh=False,
            model=None,
            wait=False,
            timeout=30,
            as_pane=True,
        )
    )

    assert result["ok"] is False
    assert result["error"] == "agent-spawn-args-failed"
    assert "no latest runtime session" in result["detail"]
    assert called is False


def test_agent_spawn_fresh_bypasses_manifest_resume_default(monkeypatch, tmp_path):
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
    captured = {}

    def fake_spawn(args):
        captured.update(vars(args))
        return {"ok": True, "name": args.name, "fleet": args.fleet, "runtime": args.runtime}

    monkeypatch.setattr(spawn, "run", fake_spawn)
    result = agent_cmd.run(
        argparse.Namespace(
            agent_action="spawn",
            ref="pipeline-conductor",
            cwd=None,
            fleet=None,
            seat=None,
            prompt=None,
            resume_session=None,
            fresh=True,
            model=None,
            wait=False,
            timeout=30,
            as_pane=True,
        )
    )

    assert result["ok"] is True
    assert captured["identity_id"] == created["agent"]["agent_id"]
    assert captured["resume_session"] is None


def test_agent_spawn_fresh_conflicts_with_resume_session(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import agent as agent_cmd
    from lib import agent_packages

    agent_packages.create(
        address="flexgraph:chatbot:pipeline:conductor",
        runtime="omx",
        profile="omx/aura-operator",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="pipeline",
        alias="pipeline-conductor",
    )

    result = agent_cmd.run(
        argparse.Namespace(
            agent_action="spawn",
            ref="pipeline-conductor",
            cwd=None,
            fleet=None,
            seat=None,
            prompt=None,
            resume_session="latest",
            fresh=True,
            model=None,
            wait=False,
            timeout=30,
            as_pane=True,
        )
    )

    assert result["ok"] is False
    assert result["error"] == "agent-spawn-args-failed"
    assert "use either --fresh or --resume-session" in result["detail"]


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
    assert box.codex_home == root / ".codex"
    assert not (root / "home").exists()
    assert not (root / "runtime").exists()
    assert (root / ".codex" / "hooks.json").is_file()
    hooks = json.loads((root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    assert "SessionStart" in hooks["hooks"]
    assert "Stop" in hooks["hooks"]
    assert "PreCompact" in hooks["hooks"]
    assert "aura_keeper_hook.py Stop" in hooks["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert "aura_keeper_hook.py PreCompact" in hooks["hooks"]["PreCompact"][0]["hooks"][0]["command"]
    meta = box.metadata()
    assert meta["codex_isolation"] == "aura-agent-package"
    assert meta["codex_package_root"] == str(root.resolve())
    assert meta["codex_package_codex_home"] == str(root / ".codex")
    assert meta["codex_aura_keeper_hook_installed"] is True
    assert not any(key.startswith("codex_box_") for key in meta)


def test_omx_prepare_box_supports_agent_package_layout(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AURA_OMX_BOX_SETUP", "0")
    cwd = tmp_path / "project"
    cwd.mkdir()

    from lib import omx, omx_adapter

    monkeypatch.setattr(
        omx.omx_adapter,
        "apply_adapter",
        lambda **_: omx_adapter.OmxAdapterResult(enabled=True),
    )
    root = tmp_path / "state" / "agents" / "i_pkg_omx"
    box = omx.prepare_box(
        fleet="fleet",
        seat="seat",
        source_cwd=str(cwd),
        profile=None,
        root_override=root,
        package_layout=True,
    )

    assert box.root == root.resolve()
    assert box.codex_home == root / ".codex"
    assert box.omx_root == root.resolve()
    assert box.omx_state == root / ".omx"
    assert not (root / "home").exists()
    assert not (root / "runtime").exists()
    meta = box.metadata()
    assert meta["omx_isolation"] == "aura-agent-package"
    assert meta["omx_package_root"] == str(root.resolve())
    assert meta["omx_package_codex_home"] == str(root / ".codex")
    assert meta["omx_package_omx_state"] == str(root / ".omx")
    assert not any(key.startswith("omx_box_") for key in meta)


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


def test_agent_resolve_reads_legacy_agent_json(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    root = agent_packages.agents_root() / "i_legacy"
    root.mkdir(parents=True)
    (root / "agent.json").write_text(
        json.dumps(
            {
                "schema": "aura.agent_package.v1",
                "agent_id": "i_legacy",
                "address": "legacy:agent",
                "runtime": "omx",
                "cwd": str(tmp_path),
                "fleet": "legacy",
                "seat": "agent",
                "root": str(root),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agent_packages.write_index(
        {
            "agents": {"i_legacy": str(root)},
            "addresses": {"legacy:agent": "i_legacy"},
            "aliases": {"legacy-agent": "i_legacy"},
        }
    )

    resolved = agent_packages.resolve("legacy-agent")

    assert resolved["agent_id"] == "i_legacy"
    assert resolved["runtime"] == "omx"
    assert resolved["root"] == str(root)


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


def test_agent_census_classifies_package_bodies_and_registry_ghosts(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages, registry

    bound = agent_packages.create(
        address="flexgraph:chatbot:ops:manager",
        runtime="codex",
        profile="worker",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="manager",
        alias=None,
    )["agent"]
    unbound = agent_packages.create(
        address="flexgraph:chatbot:ops:observer",
        runtime="codex",
        profile="worker",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="observer",
        alias=None,
    )["agent"]
    registry.upsert_agent({
        "name": "manager",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
        "agent_package_id": bound["agent_id"],
        "agent_package_root": bound["root"],
        "runtime_session_id": "019e3334-6cf5-72cb-aafb-9e423bfb9f86",
        "runtime_session_binding": "bound",
    })
    registry.upsert_agent({
        "name": "ghost",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
        "agent_package_id": "i_missingghost",
        "runtime_session_id": "019e3334-6cf5-72cb-aafb-9e423bfb9f87",
        "runtime_session_binding": "bound",
    })

    result = agent_packages.census()
    by_id = {row["agent_id"]: row for row in result["packages"]}

    assert result["ok"] is True
    assert by_id[bound["agent_id"]]["classification"] == "durable-package-bound"
    assert by_id[bound["agent_id"]]["bindings"][0]["ref"] == "flexgraph-chatbot:manager"
    assert by_id[unbound["agent_id"]]["classification"] == "durable-package-unbound"
    assert by_id["i_missingghost"]["classification"] == "registry-ghost"
    assert "missing-package-root" in by_id["i_missingghost"]["findings"]
    assert result["counts"]["durable-package-bound"] == 1
    assert result["counts"]["durable-package-unbound"] == 1
    assert result["counts"]["registry-ghost"] == 1


def test_agent_census_reports_duplicate_live_bindings(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages, registry

    agent = agent_packages.create(
        address="flexgraph:chatbot:ops:manager",
        runtime="codex",
        profile="worker",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="manager",
        alias=None,
    )["agent"]
    for name, session_id in [("manager", "s1"), ("manager-copy", "s2")]:
        registry.upsert_agent({
            "name": name,
            "fleet": "flexgraph-chatbot",
            "runtime": "codex",
            "agent_package_id": agent["agent_id"],
            "agent_package_root": agent["root"],
            "runtime_session_id": session_id,
            "runtime_session_binding": "bound",
        })

    package = agent_packages.census()["packages"][0]

    assert package["classification"] == "durable-package-duplicate-bindings"
    assert package["findings"] == ["duplicate-live-seat-for-package"]
    assert [binding["ref"] for binding in package["bindings"]] == [
        "flexgraph-chatbot:manager",
        "flexgraph-chatbot:manager-copy",
    ]

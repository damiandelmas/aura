import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _assert_thin_agent_index(agent_packages):
    index = json.loads(agent_packages.index_path().read_text(encoding="utf-8"))
    assert "addresses" not in index
    assert "aliases" not in index
    for meta in index.get("agents", {}).values():
        if isinstance(meta, dict):
            assert "address" not in meta
    return index


def test_agent_create_writes_minimal_package(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    result = agent_packages.create(
        address="flexgraph:chatbot:pipeline:conductor",
        runtime="codex",
        profile="codex/aura-operator",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="pipeline",
        alias="pipeline-conductor",
    )

    assert result["ok"] is True
    agent = result["agent"]
    root = Path(agent["root"])
    assert agent["agent_id"].startswith("i_")
    assert "address" not in agent
    assert agent["alias"] == "pipeline-conductor"
    assert agent["profile"] == "codex/aura-operator"
    assert (root / "manifest.json").is_file()
    assert not (root / "agent.json").exists()
    assert (root / ".codex").is_dir()
    assert not (root / "home").exists()
    assert not (root / ".desks").exists()
    assert not (root / "runtime").exists()
    assert not (root / "receipts").exists()
    assert not (root / "artifacts").exists()
    body = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert body == {
        "argv": ["codex"],
        "cwd": str((tmp_path / "unit").resolve()),
        "env": {"CODEX_HOME": ".codex"},
        "fleet": "flexgraph-chatbot",
        "profile": "codex/aura-operator",
        "resume": {"default": "latest"},
        "runtime": "codex",
        "schema": "aura.agent_manifest.v1",
        "seat": "pipeline",
    }
    index = _assert_thin_agent_index(agent_packages)
    assert index["agents"][agent["agent_id"]] == {
        "alias": "pipeline-conductor",
        "root": agent["root"],
    }


def test_agent_inspect_resolves_alias_and_id(monkeypatch, tmp_path):
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

    by_id = agent_packages.inspect(created["agent"]["agent_id"])
    by_alias = agent_packages.inspect("eng-runtime")

    assert by_id["ok"] is True
    assert by_id["agent"]["agent_id"] == created["agent"]["agent_id"]
    assert by_alias["agent"]["root"] == created["agent"]["root"]
    assert by_id["agent"]["profile"] == "codex/worker"
    assert "manifest" in by_id["files"]
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
    _assert_thin_agent_index(agent_packages)


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


def test_agent_clone_preserves_package_body_and_updates_manifest(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    source = agent_packages.create(
        address="flexgraph:chatbot:ops:manager",
        runtime="codex",
        profile="codex/aura-operator",
        cwd=str(tmp_path / "source-unit"),
        fleet="flexgraph-chatbot",
        seat="manager",
        alias="ops-manager",
    )["agent"]
    source_root = Path(source["root"])
    (source_root / ".codex" / "skills" / "local-skill").mkdir(parents=True)
    (source_root / ".codex" / "skills" / "local-skill" / "SKILL.md").write_text("skill\n", encoding="utf-8")
    (source_root / ".codex" / "state").mkdir(parents=True, exist_ok=True)
    (source_root / ".codex" / "state" / "runtime.json").write_text('{"ok":true}\n', encoding="utf-8")
    (source_root / "aura.json").write_text('{"schema":"aura.agent_history.v1"}\n', encoding="utf-8")

    cloned = agent_packages.clone(
        "ops-manager",
        address="flexgraph:chatbot:ops:manager-clone",
        alias="ops-manager-clone",
        cwd=str(tmp_path / "clone-unit"),
        fleet="flexgraph-clone",
        seat="manager-clone",
    )["agent"]
    clone_root = Path(cloned["root"])
    clone_manifest = json.loads((clone_root / "manifest.json").read_text(encoding="utf-8"))

    assert cloned["agent_id"] != source["agent_id"]
    assert clone_manifest["cwd"] == str((tmp_path / "clone-unit").resolve())
    assert clone_manifest["fleet"] == "flexgraph-clone"
    assert clone_manifest["seat"] == "manager-clone"
    assert (clone_root / ".codex" / "skills" / "local-skill" / "SKILL.md").read_text(encoding="utf-8") == "skill\n"
    assert (clone_root / ".codex" / "state" / "runtime.json").is_file()
    assert (clone_root / "aura.json").is_file()
    assert agent_packages.resolve("ops-manager-clone")["agent_id"] == cloned["agent_id"]
    assert agent_packages.resolve("ops-manager")["agent_id"] == source["agent_id"]
    _assert_thin_agent_index(agent_packages)


def test_agent_promote_seat_copies_runtime_home_and_binds_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages, registry

    codex_home = tmp_path / "seat-box" / "codex-home"
    (codex_home / "skills" / "local-skill").mkdir(parents=True)
    (codex_home / "skills" / "local-skill" / "SKILL.md").write_text("skill\n", encoding="utf-8")
    registry.upsert_agent({
        "name": "manager",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
        "cwd": str(tmp_path / "unit"),
        "codex_box_codex_home": str(codex_home),
        "runtime_session_id": "019e3334-6cf5-72cb-aafb-9e423bfb9f86",
        "runtime_session_binding": "bound",
    })

    promoted = agent_packages.promote_seat(
        "flexgraph-chatbot:manager",
        address="flexgraph:chatbot:ops:manager",
        alias="ops-manager",
    )
    root = Path(promoted["agent"]["root"])
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    record = registry.get_agent("flexgraph-chatbot:manager")

    assert promoted["ok"] is True
    assert manifest["runtime"] == "codex"
    assert manifest["cwd"] == str((tmp_path / "unit").resolve())
    assert manifest["fleet"] == "flexgraph-chatbot"
    assert manifest["seat"] == "manager"
    assert (root / ".codex" / "skills" / "local-skill" / "SKILL.md").read_text(encoding="utf-8") == "skill\n"
    assert record["agent_package_id"] == promoted["agent"]["agent_id"]
    assert record["agent_package_address"] == "flexgraph:chatbot:ops:manager"
    assert record["agent_package_root"] == str(root)
    assert record["codex_box_codex_home"] == str(codex_home)
    assert promoted["registry"]["runtime_process_still_uses_original_home"] is True
    assert agent_packages.resolve("ops-manager")["agent_id"] == promoted["agent"]["agent_id"]
    _assert_thin_agent_index(agent_packages)


def test_agent_rename_updates_index_manifest_and_registry_binding(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages, registry

    agent = agent_packages.create(
        address="flexgraph:chatbot:ops:manager",
        runtime="codex",
        profile="worker",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="manager",
        alias="ops-manager",
    )["agent"]
    registry.upsert_agent({
        "name": "manager",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
        "agent_package_id": agent["agent_id"],
        "agent_package_root": agent["root"],
        "agent_package_address": "flexgraph:chatbot:ops:manager",
        "identity_label": "flexgraph:chatbot:ops:manager",
    })

    renamed = agent_packages.rename(
        "ops-manager",
        address="flexgraph:chatbot:ops:lead",
        alias="ops-lead",
        fleet="flexgraph-chatbot",
        seat="manager",
    )
    record = registry.get_agent("flexgraph-chatbot:manager")
    manifest = json.loads((Path(agent["root"]) / "manifest.json").read_text(encoding="utf-8"))

    assert renamed["ok"] is True
    assert renamed["previous"] == {
        "address": None,
        "alias": "ops-manager",
    }
    assert agent_packages.resolve("ops-lead")["agent_id"] == agent["agent_id"]
    try:
        agent_packages.resolve("ops-manager")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("old alias should not resolve after rename")
    assert record["agent_package_address"] == "flexgraph:chatbot:ops:lead"
    assert record["identity_label"] == "flexgraph:chatbot:ops:lead"
    assert manifest["fleet"] == "flexgraph-chatbot"
    assert manifest["seat"] == "manager"
    _assert_thin_agent_index(agent_packages)


def test_agent_rename_refuses_live_fleet_default_drift(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages, registry

    agent = agent_packages.create(
        address="flexgraph:chatbot:ops:manager",
        runtime="codex",
        profile="worker",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="manager",
        alias="ops-manager",
    )["agent"]
    registry.upsert_agent({
        "name": "manager",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
        "agent_package_id": agent["agent_id"],
        "agent_package_root": agent["root"],
    })

    try:
        agent_packages.rename(
            "ops-manager",
            address="flexgraph:chatbot:ops:lead",
            alias="ops-lead",
            fleet="other-fleet",
        )
    except ValueError as exc:
        assert "live registry binding" in str(exc)
    else:
        raise AssertionError("live package default drift should be refused")

    assert agent_packages.resolve("ops-manager")["agent_id"] == agent["agent_id"]


def test_agent_hooks_audit_and_repair_package_codex_hooks(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    agent_packages.create(
        address="flexgraph:chatbot:ops:manager",
        runtime="codex",
        profile="worker",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="manager",
        alias="ops-manager",
    )

    before = agent_packages.hooks("ops-manager")
    repaired = agent_packages.hooks("ops-manager", repair=True)
    after = agent_packages.hooks("ops-manager")

    assert before["packages"][0]["ok"] is False
    assert set(before["packages"][0]["findings"]) == {
        "missing-hook:session_start",
        "missing-hook:keeper_stop",
        "missing-hook:keeper_precompact",
    }
    assert repaired["packages"][0]["ok"] is True
    assert repaired["packages"][0]["repair"]["ok"] is True
    assert after["packages"][0]["ok"] is True
    assert after["packages"][0]["findings"] == []


def test_agent_spawn_delegates_package_roots(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import agent as agent_cmd
    from commands import spawn
    from lib import agent_packages

    created = agent_packages.create(
        address="flexgraph:chatbot:pipeline:conductor",
        runtime="codex",
        profile="codex/aura-operator",
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
            ref=created["agent"]["agent_id"],
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
    assert captured["runtime"] == "codex"
    assert captured["resume_session"] is None
    assert captured["runtime_profile"] == "codex/aura-operator"
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
        runtime="codex",
        profile="codex/aura-operator",
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
        "runtime": "codex",
        "agent_package_id": created["agent"]["agent_id"],
        "runtime_session_id": "newer-unbound",
        "runtime_session_binding": "unbound",
        "runtime_session_updated_at_ms": 9,
    })
    registry.upsert_agent({
        "name": "pipeline-old",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
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
        "runtime": "hermes",
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
    assert captured["runtime"] == "codex"


def test_agent_spawn_latest_resume_reads_package_runtime_session(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import agent as agent_cmd
    from commands import spawn
    from lib import agent_packages, registry

    created = agent_packages.create(
        address="flexgraph:chatbot:pipeline:conductor",
        runtime="codex",
        profile="codex/aura-operator",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="pipeline",
        alias="pipeline-conductor",
    )
    registry.upsert_agent({
        "name": "pipeline",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
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
    assert captured["runtime"] == "codex"


def test_agent_spawn_default_resume_requires_valid_package_session(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import agent as agent_cmd
    from commands import spawn
    from lib import agent_packages, registry

    created = agent_packages.create(
        address="flexgraph:chatbot:pipeline:conductor",
        runtime="codex",
        profile="codex/aura-operator",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="pipeline",
        alias="pipeline-conductor",
    )
    registry.upsert_agent({
        "name": "pipeline",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
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
        runtime="codex",
        profile="codex/aura-operator",
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
        runtime="codex",
        profile="codex/aura-operator",
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
    assert hooks["hooks"]["Stop"][0]["hooks"][0]["timeout"] == 10
    assert hooks["hooks"]["PreCompact"][0]["hooks"][0]["timeout"] == 10
    meta = box.metadata()
    assert meta["codex_isolation"] == "aura-agent-package"
    assert meta["codex_package_root"] == str(root.resolve())
    assert meta["codex_package_codex_home"] == str(root / ".codex")
    assert meta["codex_aura_keeper_hook_installed"] is True
    assert not any(key.startswith("codex_box_") for key in meta)


def test_agent_resolve_requires_manifest_json(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    root = agent_packages.agents_root() / "i_package"
    root.mkdir(parents=True)
    (root / "agent.json").write_text(
        json.dumps(
            {
                "schema": "aura.agent_package.v1",
                "agent_id": "i_package",
                "address": "unit:agent",
                "runtime": "omx",
                "cwd": str(tmp_path),
                "fleet": "unit",
                "seat": "agent",
                "root": str(root),
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agent_packages.write_index(
        {
            "agents": {"i_package": str(root)},
            "addresses": {"unit:agent": "i_package"},
            "aliases": {"unit-agent": "i_package"},
        }
    )

    try:
        agent_packages.resolve("i_package")
    except FileNotFoundError as exc:
        assert "missing manifest.json" in str(exc)
    else:
        raise AssertionError("agent.json must not satisfy package manifest resolution")


def test_agent_legacy_address_map_resolves_until_rewritten(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    root = agent_packages.agents_root() / "i_package"
    (root / ".codex").mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "aura.agent_manifest.v1",
                "runtime": "codex",
                "cwd": str(tmp_path),
                "fleet": "unit",
                "seat": "agent",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    agent_packages.index_path().parent.mkdir(parents=True, exist_ok=True)
    agent_packages.index_path().write_text(
        json.dumps(
            {
                "schema": agent_packages.INDEX_SCHEMA,
                "agents": {
                    "i_package": {
                        "root": str(root),
                        "address": "unit:agent",
                        "alias": "unit-agent",
                    }
                },
                "addresses": {"unit:agent": "i_package"},
                "aliases": {"unit-agent": "i_package"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    legacy = agent_packages.resolve("unit:agent")
    assert legacy["agent_id"] == "i_package"
    assert legacy["address"] == "unit:agent"

    agent_packages.write_index(agent_packages.read_index())
    rewritten = json.loads(agent_packages.index_path().read_text(encoding="utf-8"))
    assert "addresses" not in rewritten
    assert "aliases" not in rewritten
    assert "address" not in rewritten["agents"]["i_package"]
    assert agent_packages.resolve("unit-agent")["agent_id"] == "i_package"
    try:
        agent_packages.resolve("unit:agent")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("rewritten thin index should not keep address resolution")


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


# ---------------------------------------------------------------------------
# archive tests
# ---------------------------------------------------------------------------

def _make_fake_panes_runner(live_pane_ids):
    """Return a tmux runner stub that reports the given pane IDs as alive."""
    import subprocess

    class FakeResult:
        returncode = 0
        stderr = ""

        def __init__(self, stdout):
            self.stdout = stdout

    def runner(cmd, **kwargs):
        lines = []
        for pid in live_pane_ids:
            lines.append(f"fake-session\t%0\t0\tfakewin\t{pid}\t0\t12345\t/tmp\tbash\t1")
        return FakeResult("\n".join(lines))

    return runner


def test_agent_archive_codex_body_no_live_seat(monkeypatch, tmp_path):
    """Archive a codex body: body moved, sessions preserved, index cleared, ledger event written."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "seats.json"))

    from lib import agent_packages, registry, tmux_mirror

    # Create the agent body.
    agent = agent_packages.create(
        address="flexgraph:chatbot:ops:manager",
        runtime="codex",
        profile="worker",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="manager",
        alias="ops-manager",
    )["agent"]
    root = Path(agent["root"])

    # Plant a .codex/sessions file so we can verify it survives the move.
    sessions_dir = root / ".codex" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    sessions_file = sessions_dir / "session-abc.json"
    sessions_file.write_text('{"session_id":"abc"}\n', encoding="utf-8")

    # Add a registry row for this package.
    registry.upsert_agent({
        "name": "manager",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
        "agent_package_id": agent["agent_id"],
        "agent_package_root": agent["root"],
        "runtime_session_id": "019e3334-6cf5-72cb-aafb-9e423bfb9f86",
        "runtime_session_binding": "bound",
    })

    # No live panes.
    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda: {
        "ok": True, "schema": "aura.tmux_mirror.v1",
        "counts": {"sessions": 0, "panes": 0},
        "sessions": [], "panes": [],
    })

    result = agent_packages.archive("ops-manager", reason="test-retire")

    assert result["ok"] is True
    assert result["agent_id"] == agent["agent_id"]
    assert result["deindexed"] is True
    assert len(result["archived_rows"]) == 1
    assert result["archived_rows"][0]["ref"] == "flexgraph-chatbot:manager"

    # Body moved.
    assert not root.exists()
    archived_to = Path(result["body_archived_to"])
    assert archived_to.exists()
    assert archived_to.is_dir()

    # .codex/sessions preserved.
    assert (archived_to / ".codex" / "sessions" / "session-abc.json").exists()

    # Index cleared.
    index = agent_packages.read_index()
    assert agent["agent_id"] not in index.get("agents", {})

    # Registry row removed.
    assert registry.get_agent("flexgraph-chatbot:manager") is None

    # Ledger event written.
    from lib import session_ledger
    ledger_path = session_ledger.ledger_path()
    assert ledger_path.exists()
    events = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    seat_archived = [e for e in events if e.get("event") == "seat_archived"]
    assert len(seat_archived) == 1
    assert seat_archived[0]["evidence"]["agent_package_id"] == agent["agent_id"]


def test_agent_archive_dry_run_performs_no_writes(monkeypatch, tmp_path):
    """dry-run: nothing moved or removed, plan is returned."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "seats.json"))

    from lib import agent_packages, registry, tmux_mirror

    agent = agent_packages.create(
        address="flexgraph:chatbot:ops:observer",
        runtime="codex",
        profile="worker",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="observer",
        alias="obs-agent",
    )["agent"]
    root = Path(agent["root"])

    registry.upsert_agent({
        "name": "observer",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
        "agent_package_id": agent["agent_id"],
        "agent_package_root": agent["root"],
    })

    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda: {
        "ok": True, "schema": "aura.tmux_mirror.v1",
        "counts": {"sessions": 0, "panes": 0},
        "sessions": [], "panes": [],
    })

    result = agent_packages.archive("obs-agent", dry_run=True)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert "plan" in result
    plan = result["plan"]
    assert plan["agent_id"] == agent["agent_id"]
    assert plan["body_root"] == str(root)
    assert "flexgraph-chatbot:observer" in plan["rows_to_archive"]
    assert plan["deindex"] is True

    # Nothing should have moved or been removed.
    assert root.exists()
    assert agent_packages.resolve("obs-agent")["agent_id"] == agent["agent_id"]
    assert registry.get_agent("flexgraph-chatbot:observer") is not None


def test_agent_archive_refuses_live_seat_without_force(monkeypatch, tmp_path):
    """A body with a live pane should be refused without --force."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "seats.json"))

    from lib import agent_packages, registry, tmux_mirror

    agent = agent_packages.create(
        address="flexgraph:chatbot:ops:live-agent",
        runtime="codex",
        profile="worker",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="live-agent",
        alias="live-a",
    )["agent"]
    root = Path(agent["root"])

    # Register a row with a fake live pane.
    registry.upsert_agent({
        "name": "live-agent",
        "fleet": "flexgraph-chatbot",
        "runtime": "codex",
        "agent_package_id": agent["agent_id"],
        "agent_package_root": agent["root"],
        "pane_ref": "tmux:fake-session:%99",
    })

    # Mirror reports pane %99 as alive.
    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda: {
        "ok": True, "schema": "aura.tmux_mirror.v1",
        "counts": {"sessions": 1, "panes": 1},
        "sessions": ["fake-session"],
        "panes": [{"pane_id": "%99", "tmux_session": "fake-session"}],
    })

    result_no_force = agent_packages.archive("live-a")

    assert result_no_force["ok"] is False
    assert result_no_force["error"] == "agent-has-live-seat"
    assert any(r["pane_ref"] == "tmux:fake-session:%99" for r in result_no_force["live"])

    # Body untouched.
    assert root.exists()
    assert registry.get_agent("flexgraph-chatbot:live-agent") is not None

    # With --force it should succeed.
    result_force = agent_packages.archive("live-a", force=True)

    assert result_force["ok"] is True
    assert result_force["agent_id"] == agent["agent_id"]
    assert not root.exists()
    assert registry.get_agent("flexgraph-chatbot:live-agent") is None

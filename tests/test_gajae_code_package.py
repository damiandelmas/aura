import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _quick_args(runtime="gajae-code", **overrides):
    values = dict(
        runtime=runtime,
        default=False,
        new=None,
        profile=None,
        preset=None,
        fleet=None,
        seat=None,
        cwd=None,
        prompt=None,
        work=None,
        model=None,
        wait=False,
        timeout=30,
        as_pane=True,
        attach=False,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def _spawn_args(tmp_path, package, **overrides):
    values = dict(
        name="gajae-code-seat",
        fleet=None,
        fleet_id=None,
        knowledge=None,
        memory=None,
        resume_session=None,
        fork_session=None,
        identity_provider="aura-agent",
        identity_id=package["agent_id"],
        identity_label=package.get("alias") or package["agent_id"],
        at=None,
        prompt=None,
        work=None,
        cwd=str(tmp_path),
        context=None,
        wait=False,
        timeout=30,
        model=None,
        as_pane=True,
        silent=False,
        runtime="gajae-code",
        profile=None,
        runtime_profile=None,
        boxed=False,
        omx_profile=None,
        launch_command=None,
        _agent_package={
            "agent_id": package["agent_id"],
            "alias": package.get("alias"),
            "root": package["root"],
            "runtime": package["runtime"],
            "argv": package.get("argv"),
            "env": package.get("env"),
        },
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def test_agent_create_writes_gajae_code_package(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages, runtime_hygiene

    result = agent_packages.create(
        address="aura:quick:gajae-code",
        runtime="gajae-code",
        profile=None,
        cwd=str(tmp_path / "project"),
        fleet="quick-gajae-code",
        seat="gajae-code",
        alias="quick-gajae-code",
    )

    agent = result["agent"]
    root = Path(agent["root"])
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert manifest == {
        "argv": ["gjc"],
        "cwd": str((tmp_path / "project").resolve()),
        "env": {
            "GJC_CODING_AGENT_DIR": ".gjc/agent",
            "GJC_CONFIG_DIR": ".gjc",
        },
        "fleet": "quick-gajae-code",
        "runtime": "gajae-code",
        "schema": "aura.agent_manifest.v1",
        "seat": "gajae-code",
    }
    assert sorted(path.name for path in root.iterdir()) == [".gjc", "manifest.json"]
    assert (root / ".gjc" / "agent").is_dir()
    assert not (root / ".codex").exists()
    assert not (root / ".omx").exists()
    assert runtime_hygiene.severe_findings(runtime_hygiene.package_runtime_findings(root, manifest)) == []


def test_gajae_code_adopt_root_requires_package_agent_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages

    root = tmp_path / "state" / "agents" / "i_gjc"
    root.mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "aura.agent_manifest.v1",
                "runtime": "gajae-code",
                "cwd": str(tmp_path),
                "argv": ["gjc"],
                "env": {"GJC_CONFIG_DIR": ".gjc", "GJC_CODING_AGENT_DIR": ".gjc/agent"},
                "fleet": "quick-gajae-code",
                "seat": "gajae-code",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        agent_packages.adopt_root(
            root=str(root),
            address="aura:quick:gajae-code",
        )
    except FileNotFoundError as exc:
        assert "missing-runtime-root:.gjc/agent" in str(exc)
    else:
        raise AssertionError("broken Gajae-Code package body should not be indexed")


def test_quick_gajae_code_uses_canonical_package_without_runtime_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)

    from commands import quick

    captured = {}

    def fake_spawn_run(args):
        captured.update(vars(args))
        return {"ok": True, "name": args.name, "fleet": args.fleet}

    monkeypatch.setattr(quick.spawn, "run", fake_spawn_run)
    monkeypatch.setattr(quick, "_now_minute", lambda: "2026-06-03-1338")
    monkeypatch.setattr(quick, "_shortid", lambda: "abc123")

    result = quick.run(_quick_args())

    assert result["ok"] is True
    assert result["quick_profile"] is None
    assert captured["runtime"] == "gajae-code"
    assert captured["runtime_profile"] is None
    assert captured["boxed"] is False
    assert captured["identity_provider"] == "aura-agent"
    assert captured["fresh"] is True
    assert captured["_agent_package"]["alias"] == "quick-gajae-code"
    assert captured["_agent_package"]["env"] == {
        "GJC_CONFIG_DIR": ".gjc",
        "GJC_CODING_AGENT_DIR": ".gjc/agent",
    }
    package_root = Path(captured["_agent_package"]["root"])
    assert (package_root / ".gjc" / "agent").is_dir()
    assert sorted(path.name for path in package_root.iterdir()) == [".gjc", "manifest.json"]
    assert "quick_agent_package_address" not in result


def test_quick_gajae_code_rejects_runtime_profile_flags(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import quick

    monkeypatch.setattr(quick.spawn, "run", lambda _args: (_ for _ in ()).throw(AssertionError("spawn should not run")))

    result = quick.run(_quick_args(default=True))

    assert result["ok"] is False
    assert result["error"] == "quick-launch-invalid"
    assert "do not support runtime profiles" in result["detail"]


def test_spawn_gajae_code_package_env_is_package_rooted(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn
    from lib import agent_packages, registry

    package = agent_packages.create(
        address="aura:quick:gajae-code",
        runtime="gajae-code",
        profile=None,
        cwd=str(tmp_path),
        fleet="unitfleet",
        seat="gajae-code-seat",
        alias="quick-gajae-code",
    )["agent"]

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"
        last_command = None
        last_env = None

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            FakeTerminal.last_command = command
            FakeTerminal.last_env = env
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%7"}

    result = spawn._spawn_terminal_runtime(_spawn_args(tmp_path, package), FakeTerminal, lambda x: x)
    root = Path(package["root"]).resolve()

    assert result["ok"] is True
    assert FakeTerminal.last_command == "gjc"
    assert FakeTerminal.last_env["GJC_CONFIG_DIR"] == str(root / ".gjc")
    assert FakeTerminal.last_env["GJC_CODING_AGENT_DIR"] == str(root / ".gjc" / "agent")
    assert result["runtime_home"] == str(root)
    assert result["native_state_ref"] == str(root / ".gjc")
    assert result["gajae_code_package_gjc_config"] == str(root / ".gjc")
    assert result["gajae_code_package_gjc_agent"] == str(root / ".gjc" / "agent")
    record = registry.get_agent("unitfleet:gajae-code-seat")
    assert record["agent_package_id"] == package["agent_id"]
    assert record["gajae_code_package_gjc_agent"] == str(root / ".gjc" / "agent")

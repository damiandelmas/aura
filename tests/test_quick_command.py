import argparse
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _args(runtime="codex", **overrides):
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


def test_quick_default_codex_creates_profile_and_delegates_package_spawn(monkeypatch, tmp_path):
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
    monkeypatch.setattr(quick, "_now_minute", lambda: "2026-05-14-1420")
    monkeypatch.setattr(quick, "_shortid", lambda: "abc123")

    result = quick.run(_args("codex", default=True))

    profile_root = tmp_path / "state" / "runtime-profiles" / "codex" / "default"
    assert result["ok"] is True
    assert result["quick"] is True
    assert result["quick_profile"] == "default"
    assert (profile_root / "codex-home-template").is_dir()
    assert captured["runtime"] == "codex"
    assert captured["runtime_profile"] == "codex/default"
    assert captured["boxed"] is True
    assert captured["identity_provider"] == "aura-agent"
    assert captured["fresh"] is True
    assert captured["_agent_package"]["alias"] == "quick-codex"
    assert Path(captured["_agent_package"]["root"]).is_dir()
    assert captured["fleet"] == "quick-2026-05-14-1420"
    assert captured["name"] == "codex-abc123"
    assert captured["cwd"] == str(Path.cwd())
    assert result["quick_agent_package_alias"] == "quick-codex"
    assert result["quick_agent_package_root"] == captured["_agent_package"]["root"]
    package_root = Path(captured["_agent_package"]["root"])
    manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["runtime"] == "codex"
    assert sorted(path.name for path in package_root.iterdir()) == [".codex", "manifest.json"]
    assert not (Path.cwd() / ".codex").exists()
    assert not (Path.cwd() / ".omx").exists()


def test_quick_default_omx_uses_package_body_and_runtime_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import quick

    captured = {}
    monkeypatch.setattr(quick.spawn, "run", lambda args: captured.update(vars(args)) or {"ok": True})
    monkeypatch.setattr(quick, "_now_minute", lambda: "2026-05-14-1420")
    monkeypatch.setattr(quick, "_shortid", lambda: "feed01")

    result = quick.run(_args("omx", default=True, cwd=str(tmp_path / "project")))

    profile_root = tmp_path / "state" / "runtime-profiles" / "omx" / "default"
    assert result["ok"] is True
    assert (profile_root / "codex-home-template").is_dir()
    assert captured["runtime"] == "omx"
    assert captured["omx_profile"] is None
    assert captured["runtime_profile"] == "omx/default"
    assert captured["boxed"] is False
    assert captured["name"] == "omx-feed01"
    assert captured["identity_provider"] == "aura-agent"
    assert captured["fresh"] is True
    assert captured["_agent_package"]["alias"] == "quick-omx"
    assert result["quick_agent_package_alias"] == "quick-omx"
    package_root = Path(captured["_agent_package"]["root"])
    manifest = json.loads((package_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["runtime"] == "omx"
    assert sorted(path.name for path in package_root.iterdir()) == [".codex", ".omx", "manifest.json"]


def test_quick_new_generated_profile_uses_safe_name(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import quick

    captured = {}
    monkeypatch.setattr(quick.spawn, "run", lambda args: captured.update(vars(args)) or {"ok": True})
    monkeypatch.setattr(quick, "_now_minute", lambda: "2026-05-14-1420")
    monkeypatch.setattr(quick, "_shortid", lambda: "beaded")

    result = quick.run(_args("codex", new=""))

    assert result["quick_profile"] == "quick-2026-05-14-1420-beaded"
    assert captured["runtime_profile"] == "codex/quick-2026-05-14-1420-beaded"
    assert captured["_agent_package"]["alias"] == "quick-codex"
    assert (tmp_path / "state" / "runtime-profiles" / "codex" / "quick-2026-05-14-1420-beaded").is_dir()


def test_quick_reuses_canonical_agent_package(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import quick

    roots = []

    def fake_spawn_run(args):
        roots.append(args._agent_package["root"])
        return {
            "ok": True,
            "name": args.name,
            "fleet": args.fleet,
            "runtime": args.runtime,
            "runtime_capsule_ref": args._agent_package["root"],
        }

    monkeypatch.setattr(quick.spawn, "run", fake_spawn_run)
    monkeypatch.setattr(quick, "_now_minute", lambda: "2026-05-14-1420")
    monkeypatch.setattr(quick, "_shortid", lambda: "abc123")

    first = quick.run(_args("omx", cwd=str(tmp_path / "one")))
    second = quick.run(_args("omx", cwd=str(tmp_path / "two")))

    assert first["ok"] is True
    assert second["ok"] is True
    assert roots[0] == roots[1]
    assert first["quick_agent_package_id"] == second["quick_agent_package_id"]


def test_quick_rejects_path_like_profile_before_spawn(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import quick

    def banned(_args):
        raise AssertionError("spawn should not run")

    monkeypatch.setattr(quick.spawn, "run", banned)
    result = quick.run(_args("codex", profile="../bad"))

    assert result["ok"] is False
    assert result["error"] == "quick-launch-invalid"
    assert "profile must be a single safe logical segment" in result["detail"]


def test_quick_preset_does_not_copy_user_global_skills(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    skills_root = tmp_path / "skills"
    for name in ("aura-view", "aura-report", "aura-queue", "aura-self-bind"):
        (skills_root / name).mkdir(parents=True)
        (skills_root / name / "SKILL.md").write_text(f"# {name}\n", encoding="utf-8")
    monkeypatch.setenv("AURA_QUICK_SKILLS_DIR", str(skills_root))

    from commands import quick

    monkeypatch.setattr(quick.spawn, "run", lambda args: {"ok": True})
    result = quick.run(_args("codex", new="worker", preset="worker"))

    dest = tmp_path / "state" / "runtime-profiles" / "codex" / "worker" / "codex-home-template" / "skills"
    assert result["ok"] is True
    assert result["quick_profile_meta"]["preset_skills"] == []
    assert result["quick_profile_meta"]["warnings"]
    assert not dest.exists()
    assert (tmp_path / "state" / "runtime-profiles" / "codex" / "worker" / "codex-home-template" / "config.toml").is_file()


def test_quick_existing_profile_missing_fails_before_spawn(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import quick

    monkeypatch.setattr(quick.spawn, "run", lambda args: (_ for _ in ()).throw(AssertionError("spawn should not run")))

    result = quick.run(_args("omx", profile="missing"))

    assert result["ok"] is False
    assert result["error"] == "quick-launch-invalid"
    assert "omx profile not found" in result["detail"]


def test_quick_hermes_profile_maps_to_native_runtime_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    hermes_profile = tmp_path / "home" / ".hermes" / "profiles" / "aura-operator"
    hermes_profile.mkdir(parents=True)

    from commands import quick

    captured = {}
    monkeypatch.setattr(quick.spawn, "run", lambda args: captured.update(vars(args)) or {"ok": True})

    result = quick.run(_args("hermes", profile="aura-operator"))

    assert result["ok"] is True
    assert captured["runtime"] == "hermes"
    assert captured["runtime_profile"] == "hermes/aura-operator"
    assert captured["boxed"] is False
    assert captured["omx_profile"] is None
    assert captured["_agent_package"] is None


def test_quick_hermes_without_profile_uses_native_default(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".hermes").mkdir(parents=True)

    from commands import quick

    captured = {}
    monkeypatch.setattr(quick.spawn, "run", lambda args: captured.update(vars(args)) or {"ok": True})

    result = quick.run(_args("hermes"))

    assert result["ok"] is True
    assert captured["runtime"] == "hermes"
    assert captured["runtime_profile"] is None
    assert captured["boxed"] is False
    assert result["quick_profile"] is None


def test_quick_hermes_default_maps_to_native_default(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".hermes").mkdir(parents=True)

    from commands import quick

    captured = {}
    monkeypatch.setattr(quick.spawn, "run", lambda args: captured.update(vars(args)) or {"ok": True})

    result = quick.run(_args("hermes", default=True))

    assert result["ok"] is True
    assert captured["runtime"] == "hermes"
    assert captured["runtime_profile"] == "hermes/default"
    assert result["quick_profile"] == "default"
    assert result["quick_profile_meta"]["profile_root"] == str(tmp_path / "home" / ".hermes")


def test_quick_hermes_new_profile_requires_native_hermes_create(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".hermes").mkdir(parents=True)

    from commands import quick

    result = quick.run(_args("hermes", new="worker"))

    assert result["ok"] is False
    assert result["error"] == "quick-launch-invalid"
    assert "hermes profile create" in result["detail"]


def test_quick_attach_switches_existing_tmux_client(monkeypatch):
    from commands import quick

    calls = []

    class Completed:
        returncode = 0

    monkeypatch.setenv("TMUX", "/tmp/tmux-1000/default,1,0")
    monkeypatch.setattr(quick.subprocess, "run", lambda argv: calls.append(argv) or Completed())

    assert quick.attach_to_result({"ok": True, "fleet": "quick-test"}) is None
    assert calls == [["tmux", "switch-client", "-t", "quick-test"]]


def test_quick_attach_requires_fleet():
    from commands import quick

    assert "fleet" in quick.attach_to_result({"ok": True})

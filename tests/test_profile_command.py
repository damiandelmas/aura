import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _args(action, **overrides):
    values = dict(
        profile_action=action,
        runtime=None,
        include_future=False,
        profile_ref=None,
        source_profile=None,
        preset=None,
        description=None,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def _write_skill(root: Path, name: str, body: str = "# Skill\n") -> None:
    skill = root / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(body, encoding="utf-8")


def test_profile_create_codex_from_aura_base_without_auth_or_global_config(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    home = tmp_path / "home"
    (home / ".codex").mkdir(parents=True)
    (home / ".codex" / "config.toml").write_text('# poisoned global config\n[tui]\nstatus_line = ["git-branch"]\n', encoding="utf-8")
    (home / ".codex" / "auth.json").write_text('{"token":"secret"}\n', encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    from commands import profile

    result = profile.run(_args("create", profile_ref="codex/dev"))

    root = tmp_path / "state" / "runtime-profiles" / "codex" / "dev"
    config = root / "codex-home-template" / "config.toml"
    assert result["ok"] is True
    assert result["schema"] == "aura.profile.create.v1"
    assert config.is_file()
    text = config.read_text(encoding="utf-8")
    assert "context-remaining" in text
    assert "status_line" in text
    assert "poisoned global config" not in text
    assert not (root / "codex-home-template" / "auth.json").exists()
    assert not (root / "codex-home-template" / "credentials.json").exists()


def test_profile_create_omx_uses_legacy_omx_profile_root(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import profile

    result = profile.run(_args("create", profile_ref="omx/dev"))

    root = tmp_path / "state" / "omx-profiles" / "dev"
    assert result["ok"] is True
    assert result["profile"]["root"] == str(root)
    assert (root / "codex-home-template" / "config.toml").is_file()
    assert (root / "omx-root-template").is_dir()


def test_profile_create_existing_fails_explicitly(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import profile

    assert profile.run(_args("create", profile_ref="codex/dev"))["ok"] is True
    result = profile.run(_args("create", profile_ref="codex/dev"))

    assert result["ok"] is False
    assert result["schema"] == "aura.profile.error.v1"
    assert result["error"] == "profile-exists"


def test_profile_create_from_existing_omx_profile_with_aura_operator_preset(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    skills = tmp_path / "skills"
    _write_skill(skills, "aura")
    _write_skill(skills, "aura-operator")
    _write_skill(skills, "desks")
    _write_skill(skills, "not-allowed")
    monkeypatch.setenv("AURA_PROFILE_SKILLS_SOURCE", str(skills))

    from commands import profile

    assert profile.run(_args("create", profile_ref="omx/default"))["ok"] is True
    result = profile.run(
        _args(
            "create",
            profile_ref="omx/aura-operator",
            source_profile="omx/default",
            preset="aura-operator",
        )
    )

    root = tmp_path / "state" / "omx-profiles" / "aura-operator"
    skill_root = root / "codex-home-template" / "skills"
    assert result["ok"] is True
    assert result["source_profile_ref"] == "omx/default"
    assert result["preset"] == "aura-operator"
    assert set(result["skills_applied"]) >= {"aura", "aura-operator", "desks"}
    assert "not-allowed" not in result["skills_applied"]
    assert (skill_root / "aura-operator" / "SKILL.md").is_file()
    assert not (skill_root / "not-allowed").exists()


def test_profile_create_from_rejects_paths_and_over_nested_refs(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import profile

    for raw in ("codex/codex/dev", "/tmp/foo", "../default", "~/x"):
        result = profile.run(_args("create", profile_ref="codex/dev", source_profile=raw))
        assert result["ok"] is False, raw
        assert result["error"] in {"invalid-profile-ref", "invalid-profile-create"}, raw
    assert not (tmp_path / "state" / "runtime-profiles" / "codex" / "dev").exists()


def test_profile_create_preset_rejects_symlink_before_publish(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    skills = tmp_path / "skills"
    _write_skill(skills, "aura")
    (skills / "aura" / "leak").symlink_to(tmp_path)
    monkeypatch.setenv("AURA_PROFILE_SKILLS_SOURCE", str(skills))

    from commands import profile

    result = profile.run(_args("create", profile_ref="omx/aura-operator", preset="aura-operator"))

    assert result["ok"] is False
    assert result["error"] == "unsafe-template"
    assert not (tmp_path / "state" / "omx-profiles" / "aura-operator").exists()


def test_profile_create_from_rejects_source_root_symlink_before_publish(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import profile

    assert profile.run(_args("create", profile_ref="omx/default"))["ok"] is True
    source_root = tmp_path / "state" / "omx-profiles" / "default"
    (source_root / "README.md").symlink_to(tmp_path)

    result = profile.run(_args("create", profile_ref="omx/aura-operator", source_profile="omx/default"))

    assert result["ok"] is False
    assert result["error"] == "unsafe-template"
    assert not (tmp_path / "state" / "omx-profiles" / "aura-operator").exists()


def test_profile_list_includes_profiles_and_future_classifications(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import profile

    profile.run(_args("create", profile_ref="codex/dev"))
    result = profile.run(_args("list", include_future=True))

    assert result["ok"] is True
    refs = {row["ref"] for row in result["profiles"]}
    assert "codex/dev" in refs
    kinds = {row["runtime"]: row["kind"] for row in result["classifications"]}
    assert kinds["opencode"] == "boxed-xdg-home"
    assert kinds["aider"] == "launch-preset"


def test_profile_inspect_redacts_hermes_native_profile(monkeypatch, tmp_path):
    home = tmp_path / "home"
    root = home / ".hermes" / "profiles" / "aura-operator"
    root.mkdir(parents=True)
    (root / ".env").write_text("SECRET=value\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    from commands import profile

    result = profile.run(_args("inspect", runtime="hermes", profile_ref="aura-operator"))

    assert result["ok"] is True
    row = result["profile"]
    assert row["ref"] == "hermes/aura-operator"
    assert row["native_profile"] is True
    assert row["contents_redacted"] is True
    assert "SECRET" not in str(result)


def test_profile_inspect_missing_and_invalid_refs_fail_explicitly(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import profile

    missing = profile.run(_args("inspect", profile_ref="codex/missing"))
    invalid = profile.run(_args("inspect", profile_ref="codex/codex/dev"))

    assert missing["ok"] is False
    assert missing["error"] == "profile-not-found"
    assert invalid["ok"] is False
    assert invalid["error"] == "invalid-profile-ref"


def test_profile_create_rejects_future_runtime_as_unsupported(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import profile

    result = profile.run(_args("create", profile_ref="opencode/dev"))

    assert result["ok"] is False
    assert result["error"] == "profile-create-unsupported"
    assert result["classification"]["kind"] == "boxed-xdg-home"

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
    assert 'status_line = ["model-with-reasoning", "git-branch", "current-dir", "session-id"]' in text
    assert "context-remaining" not in text
    assert "poisoned global config" not in text
    assert not (root / "codex-home-template" / "auth.json").exists()
    assert not (root / "codex-home-template" / "credentials.json").exists()


def test_profile_create_existing_fails_explicitly(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import profile

    assert profile.run(_args("create", profile_ref="codex/dev"))["ok"] is True
    result = profile.run(_args("create", profile_ref="codex/dev"))

    assert result["ok"] is False
    assert result["schema"] == "aura.profile.error.v1"
    assert result["error"] == "profile-exists"


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

    result = profile.run(_args("create", profile_ref="codex/aura-operator", preset="aura-operator"))

    assert result["ok"] is False
    assert result["error"] == "unsafe-template"
    assert not (tmp_path / "state" / "runtime-profiles" / "codex" / "aura-operator").exists()


def test_profile_create_from_rejects_source_root_symlink_before_publish(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import profile

    assert profile.run(_args("create", profile_ref="codex/default"))["ok"] is True
    source_root = tmp_path / "state" / "runtime-profiles" / "codex" / "default"
    (source_root / "README.md").symlink_to(tmp_path)

    result = profile.run(_args("create", profile_ref="codex/aura-operator", source_profile="codex/default"))

    assert result["ok"] is False
    assert result["error"] == "unsafe-template"
    assert not (tmp_path / "state" / "runtime-profiles" / "codex" / "aura-operator").exists()


def test_profile_list_includes_profiles_and_future_classifications(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import profile

    profile.run(_args("create", profile_ref="codex/dev"))
    result = profile.run(_args("list", include_future=True))

    assert result["ok"] is True
    refs = {row["ref"] for row in result["profiles"]}
    assert "codex/dev" in refs
    kinds = {row["runtime"]: row["kind"] for row in result["classifications"]}
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


def test_profile_list_includes_hermes_default_and_named_profiles(monkeypatch, tmp_path):
    home = tmp_path / "home"
    default_root = home / ".hermes"
    named_root = default_root / "profiles" / "aura-operator"
    named_root.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    from commands import profile

    result = profile.run(_args("list", runtime="hermes"))

    assert result["ok"] is True
    rows = {row["ref"]: row for row in result["profiles"]}
    assert rows["hermes/default"]["root"] == str(default_root)
    assert rows["hermes/aura-operator"]["root"] == str(named_root)


def test_profile_inspect_hermes_default_uses_root_home_and_redacts(monkeypatch, tmp_path):
    home = tmp_path / "home"
    root = home / ".hermes"
    root.mkdir(parents=True)
    (root / ".env").write_text("SECRET=value\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(home))

    from commands import profile

    result = profile.run(_args("inspect", runtime="hermes", profile_ref="default"))

    assert result["ok"] is True
    row = result["profile"]
    assert row["ref"] == "hermes/default"
    assert row["root"] == str(root)
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

    # goose is still a declared-but-unimplemented runtime; create must refuse it.
    result = profile.run(_args("create", profile_ref="goose/dev"))

    assert result["ok"] is False
    assert result["error"] == "profile-create-unsupported"
    assert result["classification"]["kind"] == "boxed-xdg-home"


def test_profile_create_claude_code_from_aura_base(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import profile

    result = profile.run(_args("create", profile_ref="claude-code/dev"))

    assert result["ok"] is True
    assert result["created"] is True
    assert "claude-home-template" in result["templates_applied"]
    settings = tmp_path / "state" / "runtime-profiles" / "claude-code" / "dev" / "claude-home-template" / "settings.json"
    assert settings.is_file()

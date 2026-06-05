import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_runtime_box_paths_use_safe_segments(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import runtime_boxes

    assert runtime_boxes.safe_segment("../bad fleet!") == "bad-fleet"
    assert runtime_boxes.runtime_home_root("codex", "my fleet", "seat/one") == (
        tmp_path / "state" / "runtime-homes" / "codex" / "my-fleet" / "seat-one"
    )
    assert runtime_boxes.runtime_profile_root("codex", "dev profile") == (
        tmp_path / "state" / "runtime-profiles" / "codex" / "dev-profile"
    )
    assert runtime_boxes.runtime_home_root("omx", "my fleet", "seat/one") == (
        tmp_path / "state" / "runtime-homes" / "omx" / "my-fleet" / "seat-one"
    )
    assert runtime_boxes.runtime_profile_root("omx", "dev") == (
        tmp_path / "state" / "runtime-profiles" / "omx" / "dev"
    )


def test_runtime_box_templates_copy_without_overwrite(tmp_path):
    from lib import runtime_boxes

    source = tmp_path / "profile" / "codex-home-template"
    destination = tmp_path / "box" / "codex-home"
    source.mkdir(parents=True)
    destination.mkdir(parents=True)
    (source / "new.txt").write_text("new\n", encoding="utf-8")
    (source / "keep.txt").write_text("template\n", encoding="utf-8")
    (destination / "keep.txt").write_text("existing\n", encoding="utf-8")

    copied = runtime_boxes.copy_template_tree_no_replace(source, destination)

    assert copied is True
    assert (destination / "new.txt").read_text(encoding="utf-8") == "new\n"
    assert (destination / "keep.txt").read_text(encoding="utf-8") == "existing\n"


def test_runtime_box_apply_templates_reports_applied_names(tmp_path):
    from lib import runtime_boxes

    root = tmp_path / "profile"
    (root / "home-template").mkdir(parents=True)
    (root / "codex-home-template").mkdir(parents=True)
    (root / "home-template" / "note.txt").write_text("home\n", encoding="utf-8")
    (root / "codex-home-template" / "note.txt").write_text("codex\n", encoding="utf-8")

    applied, names = runtime_boxes.apply_templates(
        root,
        {
            "home-template": tmp_path / "box" / "home",
            "codex-home-template": tmp_path / "box" / "codex-home",
            "missing-template": tmp_path / "box" / "missing",
        },
    )

    assert applied is True
    assert names == ("home-template", "codex-home-template")
    assert (tmp_path / "box" / "home" / "note.txt").read_text(encoding="utf-8") == "home\n"
    assert (tmp_path / "box" / "codex-home" / "note.txt").read_text(encoding="utf-8") == "codex\n"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink unavailable")
def test_runtime_box_templates_reject_file_symlink(tmp_path):
    from lib import runtime_boxes

    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    source = tmp_path / "profile" / "codex-home-template"
    source.mkdir(parents=True)
    os.symlink(outside, source / "leak.txt")

    with pytest.raises(ValueError, match="symlink rejected"):
        runtime_boxes.copy_template_tree_no_replace(source, tmp_path / "box")

    assert not (tmp_path / "box" / "leak.txt").exists()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink unavailable")
def test_runtime_box_templates_reject_directory_symlink(tmp_path):
    from lib import runtime_boxes

    outside = tmp_path / "outside"
    outside.mkdir()
    source = tmp_path / "profile" / "codex-home-template"
    source.mkdir(parents=True)
    os.symlink(outside, source / "linked-dir")

    with pytest.raises(ValueError, match="symlink rejected"):
        runtime_boxes.apply_templates(
            tmp_path / "profile",
            {"codex-home-template": tmp_path / "box" / "codex-home"},
        )

    assert not (tmp_path / "box" / "codex-home" / "linked-dir").exists()


@pytest.mark.parametrize(
    "value",
    [
        "dev",
        "aura-worker",
        "profile_01",
        "gpt-5.5",
    ],
)
def test_validate_logical_segment_accepts_safe_ids(value):
    from lib import runtime_boxes

    assert runtime_boxes.validate_logical_segment(value, label="profile") == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        ".",
        "..",
        "../secret",
        "/tmp/profile",
        "codex/dev",
        "codex\\dev",
        "dev profile",
        "dev/profile",
    ],
)
def test_validate_logical_segment_rejects_path_like_or_lossy_ids(value):
    from lib import runtime_boxes

    with pytest.raises(ValueError, match="profile must be a single safe logical segment"):
        runtime_boxes.validate_logical_segment(value, label="profile")


def test_codex_box_pretrusts_source_cwd(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_CODEX_SOURCE_CODEX_HOME", str(tmp_path / "source-codex"))
    source_cwd = tmp_path / "project"
    source_cwd.mkdir()

    from lib import codex

    box = codex.prepare_box(fleet="quick", seat="codex", source_cwd=str(source_cwd), profile=None)

    config = (box.codex_home / "config.toml").read_text(encoding="utf-8")
    assert box.source_cwd_trusted is True
    assert box.metadata()["codex_box_source_cwd_trusted"] is True
    assert f'[projects."{source_cwd}"]' in config
    assert 'trust_level = "trusted"' in config


def test_codex_box_installs_quiet_aura_session_start_hook(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_CODEX_SOURCE_CODEX_HOME", str(tmp_path / "source-codex"))
    source_cwd = tmp_path / "project"
    source_cwd.mkdir()

    from lib import codex

    box = codex.prepare_box(fleet="quick", seat="codex", source_cwd=str(source_cwd), profile=None)

    hooks_path = box.codex_home / "hooks.json"
    hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
    session_start = hooks["hooks"]["SessionStart"]
    aura_hooks = [
        hook
        for entry in session_start
        for hook in entry.get("hooks", [])
        if "codex_bind_hook.py" in hook.get("command", "")
    ]
    assert aura_hooks
    assert session_start[-1]["matcher"] == "startup|resume|clear"
    trust_keys = [key for key in hooks["state"] if key.startswith(f"{hooks_path}:session_start:")]
    assert trust_keys
    config = (box.codex_home / "config.toml").read_text(encoding="utf-8")
    assert f'[hooks.state."{trust_keys[-1]}"]' in config
    assert "codex_bind_hook.py" in box.metadata()["codex_box_aura_hook_command"]
    assert box.metadata()["codex_box_aura_hook_installed"] is True


def test_codex_box_pretrusts_profile_command_hooks(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_CODEX_SOURCE_CODEX_HOME", str(tmp_path / "source-codex"))
    source_cwd = tmp_path / "project"
    source_cwd.mkdir()
    profile_root = tmp_path / "state" / "runtime-profiles" / "codex" / "hook-lab"
    codex_template = profile_root / "codex-home-template"
    (codex_template / "hooks").mkdir(parents=True)
    (codex_template / "hooks" / "probe.py").write_text("print('{}')\n", encoding="utf-8")
    (codex_template / "hooks.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": 'python3 "$CODEX_HOME/hooks/probe.py" UserPromptSubmit',
                                    "timeout": 10,
                                }
                            ]
                        }
                    ],
                    "PreCompact": [
                        {
                            "matcher": "manual|auto",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": 'python3 "$CODEX_HOME/hooks/probe.py" PreCompact',
                                }
                            ],
                        }
                    ],
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )

    from lib import codex

    box = codex.prepare_box(fleet="quick", seat="codex", source_cwd=str(source_cwd), profile="hook-lab")

    hooks_path = box.codex_home / "hooks.json"
    hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
    state = hooks["state"]
    config = (box.codex_home / "config.toml").read_text(encoding="utf-8")
    expected_labels = {"user_prompt_submit", "pre_compact", "session_start"}
    trusted_labels = {
        key.split(":")[-3]
        for key, value in state.items()
        if key.startswith(str(hooks_path)) and value.get("trusted_hash", "").startswith("sha256:")
    }

    assert expected_labels <= trusted_labels
    assert str(hooks_path) in config
    assert "user_prompt_submit" in config
    assert "pre_compact" in config
    assert any(
        "codex_bind_hook.py" in hook.get("command", "")
        for entry in hooks["hooks"]["SessionStart"]
        for hook in entry.get("hooks", [])
    )


def test_codex_box_hook_pretrust_replaces_stale_trust_without_duplicates(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_CODEX_SOURCE_CODEX_HOME", str(tmp_path / "source-codex"))
    source_cwd = tmp_path / "project"
    source_cwd.mkdir()
    profile_root = tmp_path / "state" / "runtime-profiles" / "codex" / "hook-lab"
    codex_template = profile_root / "codex-home-template"
    codex_template.mkdir(parents=True)
    (codex_template / "hooks.json").write_text(
        json.dumps(
            {
                "state": {"keep-user-state": {"trusted_hash": "sha256:user"}},
                "hooks": {
                    "UserPromptSubmit": [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": "python3 hook.py",
                                    "timeout": "not-an-int",
                                }
                            ]
                        }
                    ],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    from lib import codex

    box = codex.prepare_box(fleet="quick", seat="codex", source_cwd=str(source_cwd), profile="hook-lab")
    hooks_path = box.codex_home / "hooks.json"
    key = f"{hooks_path}:user_prompt_submit:0:0"
    first_hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
    first_hash = first_hooks["state"][key]["trusted_hash"]
    assert first_hash.startswith("sha256:")
    assert first_hooks["state"]["keep-user-state"] == {"trusted_hash": "sha256:user"}

    config_path = box.codex_home / "config.toml"
    stale_block = f'[hooks.state."{key}"]\ntrusted_hash = "sha256:stale"\n'
    config_path.write_text(stale_block + "\n[after]\nvalue = true\n", encoding="utf-8")
    first_hooks["state"][key]["trusted_hash"] = "sha256:stale"
    hooks_path.write_text(json.dumps(first_hooks, indent=2) + "\n", encoding="utf-8")

    trusted = codex._trust_boxed_command_hooks(box.codex_home)
    config = config_path.read_text(encoding="utf-8")
    final_hooks = json.loads(hooks_path.read_text(encoding="utf-8"))

    assert trusted[key] == first_hash
    assert final_hooks["state"][key]["trusted_hash"] == first_hash
    assert config.count(f'[hooks.state."{key}"]') == 1
    assert f'trusted_hash = "{first_hash}"' in config
    assert "sha256:stale" not in config
    assert "[after]\nvalue = true\n" in config


def test_codex_box_uses_aura_base_config_and_auth_only_from_global(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    source = tmp_path / "source-codex"
    source.mkdir()
    (source / "config.toml").write_text('[tui]\nstatus_line = ["git-branch"]\n', encoding="utf-8")
    (source / "auth.json").write_text('{"token":"secret"}\n', encoding="utf-8")
    monkeypatch.setenv("AURA_CODEX_SOURCE_CODEX_HOME", str(source))
    cwd = tmp_path / "project"
    cwd.mkdir()

    from lib import codex

    box = codex.prepare_box(fleet="fleet", seat="seat", source_cwd=str(cwd), profile=None)

    config = (box.codex_home / "config.toml").read_text(encoding="utf-8")
    assert 'status_line = ["model-with-reasoning", "git-branch", "current-dir", "session-id"]' in config
    assert "context-remaining" not in config
    auth_dest = box.codex_home / "auth.json"
    assert auth_dest.is_symlink(), "auth.json must be a symlink, not a copy"
    assert auth_dest.resolve() == (source / "auth.json").resolve()
    config_dest = box.codex_home / "config.toml"
    assert not config_dest.is_symlink(), "config.toml must be a regular copy, not a symlink"
    assert config_dest.is_file()
    meta = box.metadata()
    assert meta["codex_box_behavior_source"] == "aura-runtime-base"
    assert meta["codex_box_auth_source"] == "user-global-auth-only"
    assert meta["codex_box_config_seeded"] is False


def test_codex_package_auth_seed_is_idempotent_when_source_is_package_home(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    package_root = tmp_path / "agent-package"
    codex_home = package_root / ".codex"
    codex_home.mkdir(parents=True)
    (codex_home / "auth.json").write_text('{"token":"package"}\n', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    cwd = tmp_path / "project"
    cwd.mkdir()

    from lib import codex

    box = codex.prepare_box(
        fleet="fleet",
        seat="seat",
        source_cwd=str(cwd),
        root_override=package_root,
        package_layout=True,
    )

    assert box.auth_seeded is True
    assert (codex_home / "auth.json").read_text(encoding="utf-8") == '{"token":"package"}\n'


# ---------------------------------------------------------------------------
# Auth symlink tests — codex.py
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink unavailable")
def test_codex_box_auth_files_are_symlinked_not_copied(monkeypatch, tmp_path):
    """prepare_box must symlink auth.json and credentials.json, not copy them."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    source = tmp_path / "source-codex"
    source.mkdir()
    (source / "auth.json").write_text('{"token":"live"}\n', encoding="utf-8")
    (source / "credentials.json").write_text('{"creds":"live"}\n', encoding="utf-8")
    monkeypatch.setenv("AURA_CODEX_SOURCE_CODEX_HOME", str(source))
    cwd = tmp_path / "project"
    cwd.mkdir()

    from lib import codex

    box = codex.prepare_box(fleet="f", seat="s", source_cwd=str(cwd))

    auth = box.codex_home / "auth.json"
    creds = box.codex_home / "credentials.json"
    assert auth.is_symlink(), "auth.json must be a symlink"
    assert creds.is_symlink(), "credentials.json must be a symlink"
    assert auth.resolve() == (source / "auth.json").resolve()
    assert creds.resolve() == (source / "credentials.json").resolve()
    # Reading through the symlink still works
    assert "live" in auth.read_text(encoding="utf-8")
    assert "live" in creds.read_text(encoding="utf-8")
    # config.toml must NOT be a symlink — it is a managed copy
    config = box.codex_home / "config.toml"
    assert not config.is_symlink()
    assert config.is_file()
    assert box.auth_seeded is True


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink unavailable")
def test_codex_box_auth_symlink_is_idempotent(monkeypatch, tmp_path):
    """Re-running prepare_box when the symlink is already correct must not error."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    source = tmp_path / "source-codex"
    source.mkdir()
    (source / "auth.json").write_text('{"token":"live"}\n', encoding="utf-8")
    monkeypatch.setenv("AURA_CODEX_SOURCE_CODEX_HOME", str(source))
    cwd = tmp_path / "project"
    cwd.mkdir()

    from lib import codex

    box = codex.prepare_box(fleet="f", seat="s", source_cwd=str(cwd))
    # Second call — symlink already exists and is correct
    box2 = codex.prepare_box(fleet="f", seat="s", source_cwd=str(cwd))

    auth = box2.codex_home / "auth.json"
    assert auth.is_symlink()
    assert auth.resolve() == (source / "auth.json").resolve()
    assert box2.auth_seeded is True


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink unavailable")
def test_codex_box_stale_auth_copy_archived_before_symlink(monkeypatch, tmp_path):
    """A pre-existing regular auth file must be archived to .auth-backups/."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    source = tmp_path / "source-codex"
    source.mkdir()
    (source / "auth.json").write_text('{"token":"fresh"}\n', encoding="utf-8")
    monkeypatch.setenv("AURA_CODEX_SOURCE_CODEX_HOME", str(source))
    cwd = tmp_path / "project"
    cwd.mkdir()

    from lib import codex

    box = codex.prepare_box(fleet="f", seat="s", source_cwd=str(cwd))
    # Simulate a stale copy left over from a previous run: replace the symlink
    # with a regular file.
    auth_dest = box.codex_home / "auth.json"
    auth_dest.unlink()
    auth_dest.write_text('{"token":"stale"}\n', encoding="utf-8")
    assert not auth_dest.is_symlink()

    # Trigger seed again via the internal helper
    codex._seed_codex_home(box.codex_home)

    assert auth_dest.is_symlink(), "stale copy should be replaced with a symlink"
    assert auth_dest.resolve() == (source / "auth.json").resolve()
    backup_dir = box.codex_home / ".auth-backups"
    backups = list(backup_dir.iterdir())
    assert backups, ".auth-backups/ must contain the archived stale file"
    archived_content = backups[0].read_text(encoding="utf-8")
    assert '"stale"' in archived_content


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink unavailable")
def test_codex_box_missing_source_auth_does_not_crash(monkeypatch, tmp_path):
    """If source auth files do not exist, box prep must not crash (auth_seeded=False)."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    empty_source = tmp_path / "empty-source-codex"
    empty_source.mkdir()
    monkeypatch.setenv("AURA_CODEX_SOURCE_CODEX_HOME", str(empty_source))
    cwd = tmp_path / "project"
    cwd.mkdir()

    from lib import codex

    box = codex.prepare_box(fleet="f", seat="s", source_cwd=str(cwd))

    assert box.auth_seeded is False
    assert not (box.codex_home / "auth.json").exists()
    assert not (box.codex_home / "credentials.json").exists()

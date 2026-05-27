import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_runtime_profile_ref_normalizes_canonical_refs():
    from lib import runtime_profiles

    ref = runtime_profiles.normalize_runtime_profile_ref("codex/dev", expected_runtime="codex")

    assert ref.runtime == "codex"
    assert ref.profile == "dev"
    assert ref.canonical == "codex/dev"


@pytest.mark.parametrize("raw", ["", "dev", "codex/dev/extra", "../codex/dev", "codex/dev profile"])
def test_runtime_profile_ref_rejects_malformed_or_path_like_refs(raw):
    from lib import runtime_profiles

    with pytest.raises(ValueError):
        runtime_profiles.normalize_runtime_profile_ref(raw)


def test_runtime_profile_ref_rejects_mismatched_runtime():
    from lib import runtime_profiles

    with pytest.raises(ValueError, match="not selected runtime codex"):
        runtime_profiles.normalize_runtime_profile_ref("omx/dev", expected_runtime="codex")


def test_runtime_profile_adapter_classification_matches_atlas():
    from lib import runtime_profiles

    assert runtime_profiles.classify_runtime_profile_adapter("hermes").kind.value == "native-ref"
    assert runtime_profiles.classify_runtime_profile_adapter("codex").kind.value == "boxed-template"
    assert runtime_profiles.classify_runtime_profile_adapter("omx").supports_box is True
    assert runtime_profiles.classify_runtime_profile_adapter("opencode").kind.value == "boxed-xdg-home"
    assert runtime_profiles.classify_runtime_profile_adapter("aider").kind.value == "launch-preset"


def test_template_safety_allows_config_skills_prompts_and_agents(tmp_path):
    from lib import runtime_profiles

    root = tmp_path / "profile"
    (root / "skills" / "aura-view").mkdir(parents=True)
    (root / "prompts").mkdir()
    (root / "agents").mkdir()
    (root / "config.toml").write_text("model = 'gpt-5.5'\n", encoding="utf-8")
    (root / "skills" / "aura-view" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (root / "prompts" / "operator.md").write_text("# prompt\n", encoding="utf-8")
    (root / "agents" / "executor.md").write_text("# agent\n", encoding="utf-8")

    assert runtime_profiles.scan_template_safety(root) == []
    runtime_profiles.validate_template_safety(root)


@pytest.mark.parametrize(
    ("relative", "reason"),
    [
        ("auth.json", "secret"),
        ("credentials.json", "secret"),
        (".env", "secret"),
        ("opencode.db", "database"),
        ("opencode.db-wal", "database"),
        ("sessions/session.json", "runtime-generated"),
        ("chat.jsonl", "history"),
        ("logs/agent.log", "runtime-generated"),
        ("cache/file", "runtime-generated"),
        ("state/update-check.json", "runtime-generated"),
        ("backups/old.json", "runtime-generated"),
        ("token-cache.json", "secret"),
    ],
)
def test_template_safety_denies_runtime_state_and_secret_material(tmp_path, relative, reason):
    from lib import runtime_profiles

    path = tmp_path / "profile" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("unsafe\n", encoding="utf-8")

    findings = runtime_profiles.scan_template_safety(tmp_path / "profile")

    assert any(finding.path == relative and finding.reason == reason for finding in findings)
    with pytest.raises(runtime_profiles.TemplateSafetyError):
        runtime_profiles.validate_template_safety(tmp_path / "profile")


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink unavailable")
def test_template_safety_rejects_symlinks(tmp_path):
    from lib import runtime_profiles

    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    root = tmp_path / "profile"
    root.mkdir()
    os.symlink(outside, root / "leak.txt")

    findings = runtime_profiles.scan_template_safety(root)

    assert findings == [runtime_profiles.TemplateSafetyFinding(path="leak.txt", reason="symlink")]


def test_runtime_box_copy_uses_template_safety_before_copying(tmp_path):
    from lib import runtime_boxes
    from lib import runtime_profiles

    source = tmp_path / "profile" / "codex-home-template"
    destination = tmp_path / "box" / "codex-home"
    source.mkdir(parents=True)
    destination.mkdir(parents=True)
    (source / "config.toml").write_text("safe\n", encoding="utf-8")
    (source / "auth.json").write_text("unsafe\n", encoding="utf-8")

    with pytest.raises(runtime_profiles.TemplateSafetyError):
        runtime_boxes.copy_template_tree_no_replace(source, destination)

    assert not (destination / "config.toml").exists()
    assert not (destination / "auth.json").exists()

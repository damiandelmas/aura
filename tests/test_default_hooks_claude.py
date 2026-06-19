"""H1 — default_hooks_claude(): the frozen seam between hooks and claude_box.

Verifies the seam-contract invariants (Phase D unit, lead-owned):
  - merges into a pre-seeded profile settings.json without dropping non-hook keys
  - idempotent: a second call is a byte-identical no-op
  - merge-or-create: absent file is created with only the hooks block
  - touches the `hooks` key only (statusLine ownership belongs to claude_box, seam v2 §1)
"""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _settings(config_dir: Path) -> dict:
    return json.loads((config_dir / "settings.json").read_text(encoding="utf-8"))


def test_merges_into_preseeded_profile_without_dropping_keys(tmp_path):
    from lib import hooks

    cfg = tmp_path / ".claude"
    cfg.mkdir(parents=True)
    # A profile already wrote settings.json: non-hook keys + a profile hook.
    cfg.joinpath("settings.json").write_text(
        json.dumps({
            "model": "claude-opus-4-8",
            "statusLine": {"type": "command", "command": "bash profile-status.sh"},
            "permissions": {"allow": ["Bash(git *)"]},
            "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "profile-guard.sh"}]}]},
        }, indent=2) + "\n",
        encoding="utf-8",
    )

    hooks.default_hooks_claude(str(cfg), seat_target="aura-engine:hooks")
    settings = _settings(cfg)

    # profile keys survive untouched
    assert settings["model"] == "claude-opus-4-8"
    assert settings["statusLine"] == {"type": "command", "command": "bash profile-status.sh"}
    assert settings["permissions"] == {"allow": ["Bash(git *)"]}
    # profile's own hook survives
    assert settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "profile-guard.sh"
    # Aura hooks block added across all five events
    assert set(settings["hooks"]) >= {
        "SessionStart", "UserPromptSubmit", "Stop", "PreCompact", "PostCompact"
    }


def test_registers_expected_scripts_and_timeouts(tmp_path):
    from lib import hooks

    cfg = tmp_path / ".claude"
    hooks.default_hooks_claude(str(cfg))
    settings = _settings(cfg)

    def cmds(event):
        out = []
        for entry in settings["hooks"][event]:
            out += [h["command"] for h in entry["hooks"]]
        return out

    ss = " ".join(cmds("SessionStart"))
    assert "claude_bind_hook.py" in ss and "claude_ambient_hook.py" in ss
    assert any("claude_ambient_hook.py" in c for c in cmds("UserPromptSubmit"))
    assert any("claude_keeper_hook.py" in c for c in cmds("Stop"))
    assert any("claude_keeper_hook.py" in c for c in cmds("PreCompact"))
    assert any("claude_ambient_hook.py" in c for c in cmds("PostCompact"))
    # timeouts present and in seconds (small integers)
    for event in ("SessionStart", "UserPromptSubmit", "Stop", "PreCompact", "PostCompact"):
        for entry in settings["hooks"][event]:
            for h in entry["hooks"]:
                assert isinstance(h["timeout"], int) and 0 < h["timeout"] <= 60


def test_idempotent_second_call_is_byte_identical(tmp_path):
    from lib import hooks

    cfg = tmp_path / ".claude"
    cfg.mkdir(parents=True)
    cfg.joinpath("settings.json").write_text(
        json.dumps({"model": "x", "hooks": {}}, indent=2) + "\n", encoding="utf-8"
    )

    hooks.default_hooks_claude(str(cfg))
    first = (cfg / "settings.json").read_text(encoding="utf-8")
    hooks.default_hooks_claude(str(cfg))
    second = (cfg / "settings.json").read_text(encoding="utf-8")

    assert first == second
    # no duplicate entries on re-run
    settings = json.loads(second)
    assert len(settings["hooks"]["SessionStart"]) == 2  # bind + ambient, not doubled
    assert len(settings["hooks"]["Stop"]) == 1


def test_merge_or_create_when_absent(tmp_path):
    from lib import hooks

    cfg = tmp_path / "box" / ".claude"  # does not exist yet
    hooks.default_hooks_claude(str(cfg))

    settings = _settings(cfg)
    assert "hooks" in settings
    # we never invent a statusLine (claude_box owns that — seam v2 §1)
    assert "statusLine" not in settings


def test_does_not_write_statusline(tmp_path):
    from lib import hooks

    cfg = tmp_path / ".claude"
    cfg.mkdir(parents=True)
    cfg.joinpath("settings.json").write_text(json.dumps({"hooks": {}}) + "\n", encoding="utf-8")

    hooks.default_hooks_claude(str(cfg))
    settings = _settings(cfg)
    # hooks lane must not touch statusLine; absent profile statusLine stays absent
    assert "statusLine" not in settings

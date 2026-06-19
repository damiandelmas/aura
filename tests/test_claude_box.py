"""Unit tests for the claude box-prep seam call site (claude-profiles lane).

Flipped to the REAL ``lib.hooks.default_hooks_claude`` at the hooks H1 checkpoint
(commit b0b2999, lead-verified). These prove the integrated behavior: a profile's
keys survive, this lane's ``statusLine`` lands, and the real hooks block is merged —
in the seam's fixed order, idempotently. One focused spy test asserts the call
contract (config_dir + seat_target forwarding).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _box(tmp_path):
    root = tmp_path / "i_unit"
    (root / ".claude").mkdir(parents=True)
    return root


def _settings(root):
    return json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))


def _hermetic_source(monkeypatch, tmp_path):
    # no real ~/.claude: a tmp (empty) source home for the auth-symlink step.
    monkeypatch.setenv("AURA_CLAUDE_SOURCE_CONFIG_DIR", str(tmp_path / "src"))


def test_real_merge_preserves_profile_adds_statusline_and_hooks(monkeypatch, tmp_path):
    from lib import claude_box

    root = _box(tmp_path)
    # a profile already wrote settings.json (own key + permissions, no statusLine)
    (root / ".claude" / "settings.json").write_text(
        json.dumps({"_PROFILE": "x", "permissions": {"defaultMode": "bypassPermissions"}}),
        encoding="utf-8",
    )
    _hermetic_source(monkeypatch, tmp_path)

    out = claude_box.prepare_package_box(root, workdir=str(tmp_path), profile=None,
                                         seat_target="qa:seat")
    s = _settings(root)

    # profile keys survive the seam merge
    assert s["_PROFILE"] == "x"
    assert s["permissions"]["defaultMode"] == "bypassPermissions"
    # this lane installed statusLine
    assert "aura-claude-statusline.sh" in s["statusLine"]["command"]
    # the REAL hooks block merged (hooks lane), touching only the hooks key
    assert set(s["hooks"]) >= {"SessionStart", "Stop", "PreCompact", "PostCompact", "UserPromptSubmit"}
    assert len(s["hooks"]["SessionStart"]) == 2          # bind + ambient
    assert out["hooks"] == "default_hooks_claude"
    assert out["statusline"] is True
    assert out["seat_target"] == "qa:seat"


def test_profile_statusline_not_clobbered(monkeypatch, tmp_path):
    from lib import claude_box

    root = _box(tmp_path)
    (root / ".claude" / "settings.json").write_text(
        json.dumps({"statusLine": {"type": "command", "command": "bash my-own.sh"}}),
        encoding="utf-8",
    )
    _hermetic_source(monkeypatch, tmp_path)

    out = claude_box.prepare_package_box(root, workdir=str(tmp_path), profile=None)

    assert _settings(root)["statusLine"]["command"] == "bash my-own.sh"   # untouched
    assert out["statusline"] is False


def test_idempotent_second_prep_byte_identical(monkeypatch, tmp_path):
    from lib import claude_box

    root = _box(tmp_path)
    _hermetic_source(monkeypatch, tmp_path)

    claude_box.prepare_package_box(root, workdir=str(tmp_path), profile=None, seat_target="f:s")
    first = (root / ".claude" / "settings.json").read_text(encoding="utf-8")
    claude_box.prepare_package_box(root, workdir=str(tmp_path), profile=None, seat_target="f:s")
    second = (root / ".claude" / "settings.json").read_text(encoding="utf-8")

    assert first == second                                  # byte-identical re-prep
    assert len(_settings(root)["hooks"]["SessionStart"]) == 2   # no double-append


def test_seat_target_forwarded_to_seam(monkeypatch, tmp_path):
    """Call contract: prepare_package_box forwards (config_dir, seat_target) verbatim."""
    from lib import claude_box, hooks as hooks_lib

    root = _box(tmp_path)
    _hermetic_source(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(hooks_lib, "default_hooks_claude",
                        lambda config_dir, *, seat_target=None: calls.append((config_dir, seat_target)))

    claude_box.prepare_package_box(root, workdir=str(tmp_path), profile=None, seat_target="flt:operator")
    claude_box.prepare_package_box(root, workdir=str(tmp_path), profile=None)  # None tolerated

    assert calls == [(str(root / ".claude"), "flt:operator"), (str(root / ".claude"), None)]


def test_pre_h1_guard_box_still_functional(monkeypatch, tmp_path):
    """Defensive: if default_hooks_claude is absent, prep still seeds the box."""
    from lib import claude_box, hooks as hooks_lib

    root = _box(tmp_path)
    _hermetic_source(monkeypatch, tmp_path)
    monkeypatch.delattr(hooks_lib, "default_hooks_claude", raising=False)

    out = claude_box.prepare_package_box(root, workdir=str(tmp_path), profile=None)

    assert out["hooks"] == "pending-h1"
    assert out["statusline"] is True
    assert (root / ".claude" / "settings.json").exists()

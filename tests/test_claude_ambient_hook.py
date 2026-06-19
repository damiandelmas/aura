"""H2 — claude_ambient_hook: SessionStart inject, UserPromptSubmit flag-gate, PostCompact."""

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


@pytest.fixture
def hook(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_FLEET", "F")
    monkeypatch.setenv("AURA_SEAT", "a")
    from hooks import claude_ambient_hook as mod
    return mod


def _drive(mod, monkeypatch, event, *, packet=None, calls=None):
    monkeypatch.setattr(mod, "load_event", lambda: event)
    if packet is not None:
        def fake_self():
            if calls is not None:
                calls.append(1)
            return packet
        monkeypatch.setattr(mod, "ambient_self", fake_self)
    return mod.main()


OK_PACKET = {"ok": True, "target": "F:a", "fleet": [{"target": "F:b"}],
             "warnings": [], "text": "[AURA AMBIENT]\nYou are a.\n[/AURA AMBIENT]"}


def test_sessionstart_injects_packet(hook, monkeypatch, capsys):
    _drive(hook, monkeypatch, {"hook_event_name": "SessionStart", "source": "startup"},
           packet=OK_PACKET)
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "[AURA AMBIENT]" in out["hookSpecificOutput"]["additionalContext"]


def test_sessionstart_compact_injects_ambient_without_recovery_prefix(hook, monkeypatch, capsys):
    # source=compact still orients via ambient, but does NOT prepend a recovery note —
    # doc-recovery is owned by the other lane's aura_compact_recovery_hook.
    _drive(hook, monkeypatch, {"hook_event_name": "SessionStart", "source": "compact"},
           packet=OK_PACKET)
    ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert ctx.startswith("[AURA AMBIENT]")
    assert "resumed after compaction" not in ctx


def test_userpromptsubmit_no_flag_is_silent_and_no_subprocess(hook, monkeypatch, capsys):
    calls = []
    rc = _drive(hook, monkeypatch, {"hook_event_name": "UserPromptSubmit"},
                packet=OK_PACKET, calls=calls)
    assert rc == 0
    assert capsys.readouterr().out == ""      # no injection
    assert calls == []                        # ambient_self NEVER called (cost-bug guard)


def test_userpromptsubmit_with_flag_injects_and_clears(hook, monkeypatch, capsys):
    hook.set_pending("join:fleet:F:newseat")
    assert hook.pending_path().exists()
    calls = []
    _drive(hook, monkeypatch, {"hook_event_name": "UserPromptSubmit"},
           packet=OK_PACKET, calls=calls)
    out = json.loads(capsys.readouterr().out)
    assert "[AURA AMBIENT]" in out["hookSpecificOutput"]["additionalContext"]
    assert calls == [1]                       # built exactly once
    assert not hook.pending_path().exists()   # flag consumed


def test_postcompact_sets_pending_no_output(hook, monkeypatch, capsys):
    _drive(hook, monkeypatch, {"hook_event_name": "PostCompact"})
    assert capsys.readouterr().out == ""
    assert hook.pending_path().exists()


def test_unresolved_injects_failclosed_note(hook, monkeypatch, capsys):
    _drive(hook, monkeypatch, {"hook_event_name": "SessionStart"},
           packet={"ok": False, "error": "self-target-not-resolved"})
    ctx = json.loads(capsys.readouterr().out)["hookSpecificOutput"]["additionalContext"]
    assert "do not guess your Aura fleet:seat" in ctx

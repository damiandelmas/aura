"""seat whoami: the read-only CLI contract the tmux layer consumes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


@pytest.fixture
def aura_state(monkeypatch, tmp_path):
    state_root = tmp_path / ".aura"
    state_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AURA_STATE_DIR", str(state_root))
    monkeypatch.delenv("AURA_SEAT_INSTANCE_ID", raising=False)
    monkeypatch.delenv("AURA_LAUNCH_ID", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    return state_root


def _whoami_args(**kw):
    base = {"seat_action": "whoami", "pane": None}
    base.update(kw)
    return argparse.Namespace(**base)


def test_whoami_resolves_pane_exact(aura_state):
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "architect",
        "fleet": "fleet-a",
        "runtime": "claude-code",
        "seat_instance_id": "si_arch",
        "runtime_session_id": "c4e128a2-aa27-4fda-8351-d22535e297cb",
        "pane_ref": "tmux:fleet-a:%0",
    })
    registry.upsert_agent({
        "name": "bash",
        "fleet": "fleet-b",
        "runtime": "codex",
        "seat_instance_id": "si_bash",
        "pane_ref": "tmux:fleet-b:%9",
    })

    result = seat.run(_whoami_args(pane="tmux:fleet-a:%0"))
    assert result["ok"] is True
    assert result["target"] == "fleet-a:architect"
    assert result["runtime"] == "claude-code"
    assert result["seat_instance_id"] == "si_arch"
    assert result["runtime_session_id"] == "c4e128a2-aa27-4fda-8351-d22535e297cb"
    assert "- aura: fleet-a:architect" in result["block"]
    assert "runtime: claude-code" in result["block"]


def test_whoami_unmanaged_pane_gives_adopt_hint(aura_state):
    from commands import seat

    result = seat.run(_whoami_args(pane="tmux:fleet-a:%404"))
    assert result["ok"] is False
    assert result["error"] == "unmanaged-pane"
    assert "aura seat adopt --pane tmux:fleet-a:%404" in result["hint"]
    assert "unmanaged pane tmux:fleet-a:%404" in result["block"]


def test_whoami_never_matches_by_window_name(aura_state):
    """A pane_ref miss must stay a miss — no fuzzy name fallback."""
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "scout",
        "fleet": "fleet-a",
        "runtime": "codex",
        "seat_instance_id": "si_scout",
        "pane_ref": "tmux:fleet-a:%1",
    })

    # Same fleet, different pane id: unmanaged, never the sibling row.
    result = seat.run(_whoami_args(pane="tmux:fleet-a:%2"))
    assert result["ok"] is False
    assert result["error"] == "unmanaged-pane"


def test_whoami_env_occupant_ladder(aura_state, monkeypatch):
    """No --pane: resolve this process by its own occupant env (si first)."""
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "operator",
        "fleet": "fleet-a",
        "runtime": "claude-code",
        "seat_instance_id": "si_op",
        "pane_ref": "tmux:fleet-a:%5",
    })
    monkeypatch.setenv("AURA_SEAT_INSTANCE_ID", "si_op")

    result = seat.run(_whoami_args())
    assert result["ok"] is True
    assert result["target"] == "fleet-a:operator"


def test_whoami_bad_pane_ref(aura_state):
    from commands import seat

    result = seat.run(_whoami_args(pane="fleet-a:architect"))
    assert result["ok"] is False
    assert result["error"] == "bad-pane-ref"


def test_whoami_launch_shown_when_no_session(aura_state):
    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "curator",
        "fleet": "fleet-a",
        "runtime": "claude-code",
        "seat_instance_id": "si_cur",
        "aura_launch_id": "aura-launch-5447c5b1ea094fcc",
        "pane_ref": "tmux:fleet-a:%7",
    })

    result = seat.run(_whoami_args(pane="tmux:fleet-a:%7"))
    assert result["ok"] is True
    assert "launch: aura-launch-5447c5b1ea094fcc" in result["block"]
    assert "session:" not in result["block"]

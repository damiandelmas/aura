"""_tmux_target: a pane id %N is globally unique and must resolve BARE.

Regression for the rename-collapse root cause — `tmux:<fleet>:%N` was returned as
`<fleet>:%N`, which tmux parsed as `session:window=%N`, found no such window, and
silently resolved to the session's ACTIVE window (the wrong pane). Every rename /
restart / stop / adopt of a non-active seat then hit the active pane and collapsed
rows onto one %N.
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_canonical_pane_ref_returns_bare_pane_id():
    from commands import seat
    # the exact bug: 3-segment canonical pane_ref must yield the bare %N
    assert seat._tmux_target("tmux:flexchat-website-automation:%319") == "%319"


def test_two_segment_and_bare_pane_id():
    from commands import seat
    assert seat._tmux_target("F:%9") == "%9"
    assert seat._tmux_target("%9") == "%9"


def test_never_session_qualifies_a_pane_id():
    from commands import seat
    # the failure mode was returning "<fleet>:%N" — assert that can never happen
    out = seat._tmux_target("tmux:any-fleet:%42")
    assert out == "%42"
    assert ":" not in out and out.startswith("%")


def test_window_ref_falls_back_to_stripped_value():
    from commands import seat
    # a window ref (no %N) keeps prior behaviour: tmux: stripped, session-qualified name
    assert seat._tmux_target("tmux:F:myseat") == "F:myseat"
    assert seat._tmux_target("") == ""

"""Prove pane_handle is a drop-in for all 7 existing pane-ref parsers.

The migration's risk is the `tmux:<fleet>:%N` format leaking across ~23 files in
7 slightly-different parsers. Before any consolidation, this proves the single
owner (lib/pane_handle) reproduces each current parser's exact contract across
the full input matrix — so swapping them in is behavior-preserving. It also
PINS the one pre-existing disagreement (live_topology parses window refs
differently) so the consolidation is done with eyes open.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))

from lib import pane_handle  # noqa: E402
from lib import tmux_mirror, seat_status, live_topology, registry, agent_packages  # noqa: E402
from commands import fleets as fleets_cmd  # noqa: E402

# Every form in circulation: canonical, prefix-less (the latent bug), bare,
# window refs (no %N), empties, multi-segment fleets.
INPUTS = [
    "tmux:aura:%26",
    "tmux:flexchat-sales:%130",
    "aura:%26",            # prefix-less pane_ref (some builders emit this today)
    "%5",                  # bare pane id
    "tmux:aura:worker",    # window ref (no %N)
    "aura:worker",         # prefix-less window ref
    "worker",              # bare window name
    "tmux:%9",             # prefixed bare pane (no fleet)
    "",
    None,
]


@pytest.mark.parametrize("value", INPUTS)
def test_pane_ref_parts_matches_tuple_family(value):
    # tmux_mirror._pane_ref_parts and fleets._pane_ref_key are the (tuple-always,
    # pane_id-None-when-not-a-pane) family.
    expected = tmux_mirror._pane_ref_parts(value)
    assert pane_handle.pane_ref_parts(value) == expected
    assert fleets_cmd._pane_ref_key(value) == expected


@pytest.mark.parametrize("value", INPUTS)
def test_pane_key_matches_none_family(value):
    # seat_status._extract_pane_key and agent_packages._pane_ref_key are the
    # (None-when-not-a-pane) family.
    expected = seat_status._extract_pane_key(value)
    assert pane_handle.pane_key(value) == expected
    assert agent_packages._pane_ref_key(value) == expected


@pytest.mark.parametrize("value", INPUTS)
def test_physical_fleet_matches_both_copies(value):
    expected = tmux_mirror._physical_fleet_from_ref(value)
    assert pane_handle.physical_fleet_from_ref(value) == expected
    assert registry._physical_fleet_from_ref(value) == expected


@pytest.mark.parametrize("value", [v for v in INPUTS if v and "%" in v])
def test_live_topology_agrees_on_actual_pane_refs(value):
    # live_topology._pane_ref_parts uses a DIFFERENT algorithm (scan for the %N
    # segment). It agrees with the canonical parser on real pane refs...
    assert pane_handle.pane_ref_parts(value) == live_topology._pane_ref_parts(value)


def test_live_topology_window_ref_divergence_is_pinned():
    # ...but DISAGREES on window refs (no %N): the canonical/tuple family returns
    # (fleet, None); live_topology returns (None, None). This pre-existing bug is
    # pinned so the consolidation pass switches live_topology knowingly.
    assert pane_handle.pane_ref_parts("tmux:aura:worker") == ("aura", None)
    assert live_topology._pane_ref_parts("tmux:aura:worker") == (None, None)


@pytest.mark.parametrize("value", INPUTS)
def test_is_pane_ref(value):
    assert pane_handle.is_pane_ref(value) == (pane_handle.pane_key(value) is not None)


def test_roundtrip_pane_handle():
    h = pane_handle.PaneHandle.from_ref("tmux:flexchat-sales:%130")
    assert h == pane_handle.PaneHandle("flexchat-sales", "%130")
    assert h.to_ref() == "tmux:flexchat-sales:%130"
    # prefix-less input canonicalizes to prefixed output (fixes the latent bug)
    assert pane_handle.PaneHandle.from_ref("aura:%26").to_ref() == "tmux:aura:%26"
    # fleet-less
    assert pane_handle.PaneHandle.from_ref("%5").to_ref() == "tmux:%5"


def test_make_and_canonicalization():
    assert pane_handle.PaneHandle.make("aura", "%26").to_ref() == "tmux:aura:%26"
    assert pane_handle.PaneHandle.make("", "%26").fleet is None


def test_window_handle_matches_tmux_split_semantics():
    from lib import tmux
    # WindowHandle splits on the FIRST colon like tmux._split_ref, default fleet aside.
    for value in ["tmux:aura:worker", "aura:worker", "worker", "tmux:aura:sub:win"]:
        wh = pane_handle.WindowHandle.from_ref(value, default_fleet=tmux.TMUX_SESSION)
        fleet, subject = tmux._split_ref(value)
        assert (wh.fleet, wh.window) == (fleet, subject)
    # a bare pane id is not a window
    assert pane_handle.WindowHandle.from_ref("%5") is None


def test_backend_ref_from_strips_prefix():
    assert pane_handle.backend_ref_from("tmux:aura:%26") == "aura:%26"
    assert pane_handle.backend_ref_from("aura:worker") == "aura:worker"
    assert pane_handle.backend_ref_from(None) is None

"""Contract canary — the test suite CANNOT touch live Aura state.

This is the gate against the live-registry-truncation outage class. The incident:
a test that wrote a small fixture dict clobbered the real registry (42 rows -> 4),
because ``AURA_REGISTRY_PATH`` still pointed at ``~/.aura`` and is honored *over*
``AURA_STATE_DIR`` by ``state.registry_path()``. Setting only ``AURA_STATE_DIR`` was
not enough; the path overrides had to be stripped.

``tests/conftest.py`` ENFORCES isolation (an autouse fixture that strips every
``AURA_*_PATH`` override + ambient seat identity and points state at a per-test tmp).
This file VERIFIES that enforcement holds — if any of these fail, isolation has
regressed and the suite can reach live state. Keep it dependency-light and fast so it
runs first and loud.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cli"))

LIVE_AURA = (Path.home() / ".aura").resolve()


def _under(child: Path, parent: Path) -> bool:
    child = child.resolve()
    return child == parent or parent in child.parents


def test_aura_state_dir_is_set_and_isolated():
    raw = os.environ.get("AURA_STATE_DIR")
    assert raw, "AURA_STATE_DIR is unset during tests — conftest isolation is missing"
    root = Path(raw).expanduser().resolve()
    assert root != LIVE_AURA, f"AURA_STATE_DIR points AT live state: {root}"
    assert not _under(root, LIVE_AURA), f"AURA_STATE_DIR nests under live ~/.aura: {root}"


def test_no_path_overrides_leak_to_live():
    # AURA_*_PATH overrides WIN over AURA_STATE_DIR — the exact truncation cause.
    leaked = sorted(v for v in os.environ if v.startswith("AURA_") and v.endswith("_PATH"))
    assert leaked == [], f"AURA_*_PATH override(s) present (they win over AURA_STATE_DIR): {leaked}"


def test_allow_shrink_not_forced_on():
    # The anti-truncation guard (write_registry refuses to shrink) must stay armed.
    assert not os.environ.get("AURA_REGISTRY_ALLOW_SHRINK"), \
        "AURA_REGISTRY_ALLOW_SHRINK is forced on — disables the registry shrink guard"


def test_resolution_functions_do_not_point_at_live():
    from lib import state, registry

    assert state.state_root() != LIVE_AURA
    assert not _under(state.state_root(), LIVE_AURA)
    rp = Path(registry.registry_path()).resolve()
    assert not _under(rp, LIVE_AURA), f"registry_path() resolves under live ~/.aura: {rp}"
    assert _under(rp, state.state_root()), "registry_path() is not under the isolated state root"


def test_seat_identity_env_is_stripped():
    # ambient seat identity must be gone, or resolution can bind to the live seat.
    for var in ("AURA_FLEET", "AURA_SEAT", "AURA_SEAT_INSTANCE_ID",
                "AURA_REGISTRY_PATH", "TMUX_PANE"):
        assert var not in os.environ, f"{var} leaked into the test environment"


def test_a_real_registry_write_cannot_reach_live():
    """Strongest guard, and self-safe.

    It refuses to write when resolution points at live, so a *broken* isolation fails
    this assertion BEFORE any write — the canary can never itself cause the outage it
    guards against. Then it round-trips a real ``write_registry`` and asserts the live
    ``seats.json`` is byte-identical.
    """
    from lib import registry

    rp = Path(registry.registry_path()).resolve()
    assert not _under(rp, LIVE_AURA), \
        f"registry_path() resolves to LIVE ({rp}) — refusing to write; isolation is broken"

    live_seats = LIVE_AURA / "registry" / "seats.json"
    before = live_seats.read_bytes() if live_seats.exists() else None

    registry.write_registry(registry.read_registry())  # round-trip into the isolated root

    assert rp.exists(), "isolated registry write did not land under the tmp state root"
    after = live_seats.read_bytes() if live_seats.exists() else None
    assert before == after, "the LIVE registry was modified by an isolated test write"

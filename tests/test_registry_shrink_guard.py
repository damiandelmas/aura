"""Acceptance tests for the registry shrink-guard (prevents the 42->4 live-registry clobber).

The guard refuses a single write that catastrophically shrinks a substantial
registry; it never trips on growth, single add/remove, gc, fleet rename, or
small/startup/test registries. Legit bulk clears opt in (allow_shrink / env).
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))

from lib import registry  # noqa: E402


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("AURA_REGISTRY_ALLOW_SHRINK", raising=False)
    return tmp_path


def _rows(n):
    return {f"f:s{i}": {"name": f"s{i}", "fleet": "f", "seat": f"s{i}", "seat_ref": f"f:s{i}"} for i in range(n)}


def test_a1_catastrophic_shrink_is_refused_and_file_unchanged(state):
    registry.write_registry(_rows(42))                       # 0->42 growth, allowed
    with pytest.raises(registry.RegistryShrinkGuard):
        registry.write_registry(_rows(4))                    # 42->4 catastrophic
    assert len(registry.read_registry()) == 42               # file untouched


def test_a2_allow_shrink_param_forces(state):
    registry.write_registry(_rows(42))
    registry.write_registry(_rows(4), allow_shrink=True)
    assert len(registry.read_registry()) == 4


def test_a3_env_override_forces(state, monkeypatch):
    registry.write_registry(_rows(42))
    monkeypatch.setenv("AURA_REGISTRY_ALLOW_SHRINK", "1")
    registry.write_registry(_rows(4))
    assert len(registry.read_registry()) == 4


def test_a4_add_is_allowed(state):
    registry.write_registry(_rows(42))
    registry.write_registry(_rows(43))
    assert len(registry.read_registry()) == 43


def test_a5_single_remove_is_allowed(state):
    registry.write_registry(_rows(42))
    registry.write_registry(_rows(41))
    assert len(registry.read_registry()) == 41


def test_a6_growth_from_empty_is_allowed(state):
    registry.write_registry(_rows(5))                        # 0->5, below floor
    assert len(registry.read_registry()) == 5


def test_a7_drop_below_floor_threshold(state):
    registry.write_registry(_rows(10))
    with pytest.raises(registry.RegistryShrinkGuard):
        registry.write_registry(_rows(4))                    # 10->4 (>50% drop, >=floor)
    # and just-above-ratio is allowed: 10 -> 6 (>= 50%)
    registry.write_registry(_rows(6))
    assert len(registry.read_registry()) == 6


def test_a8_writes_are_audited(state):
    registry.write_registry(_rows(42))
    with pytest.raises(registry.RegistryShrinkGuard):
        registry.write_registry(_rows(4))
    log = Path(registry.registry_path()).parent / "registry-writes.log"
    assert log.exists()
    body = log.read_text(encoding="utf-8")
    assert '"blocked": true' in body            # the refusal was recorded
    assert '"blocked": false' in body           # the allowed growth was recorded


def test_update_and_remove_paths_never_trip(state):
    # read-modify-write paths (the common case) must be immune by construction.
    registry.write_registry(_rows(20))
    registry.update_agent_record("s0", "f", lambda r: {**r, "name": "s0", "note": "x"})
    registry.remove_agent("s1", fleet="f")
    assert len(registry.read_registry()) == 19

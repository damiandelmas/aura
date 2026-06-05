from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


# Mirror snapshot shared by the FakeTerminal — lists the two pane_refs
# that FakeTerminal.target_exists() considers alive.
_FAKE_MIRROR = {
    "ok": True,
    "schema": "aura.tmux_mirror.v1",
    "panes": [
        {
            "pane_id": "%191",
            "pane_ref": "tmux:runway-engineering:%191",
            "tmux_session": "runway-engineering",
            "physical_fleet": "runway-engineering",
        },
        {
            "pane_id": "%222",
            "pane_ref": "tmux:runway-engineering:%222",
            "tmux_session": "runway-engineering",
            "physical_fleet": "runway-engineering",
        },
    ],
}


@pytest.fixture
def aura_state(monkeypatch, tmp_path):
    state_root = tmp_path / ".aura"
    desks_root = tmp_path / ".desks"
    state_root.mkdir(parents=True, exist_ok=True)
    desks_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("AURA_STATE_DIR", str(state_root))
    monkeypatch.setenv("DESKS_ROOT", str(desks_root))
    monkeypatch.setenv("AURA_FLEET", "runway-engineering")
    # Inject a controlled mirror so liveness is computed from the set,
    # not from a real (or missing) tmux server.
    from lib import tmux_mirror
    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: _FAKE_MIRROR)
    return state_root


class FakeTerminal:
    SESSION_NAME = "runway-engineering"
    alive = {"tmux:runway-engineering:%191", "tmux:runway-engineering:%222"}
    configured = []

    @classmethod
    def configure_session(cls, fleet):
        cls.configured.append(fleet)
        cls.SESSION_NAME = fleet
        return fleet

    @classmethod
    def target_exists(cls, target):
        return target in cls.alive

    @staticmethod
    def capture_output(_target, _lines=20):
        return ["ready"]


def test_status_projects_adopted_unbound_risks_without_session_id(aura_state):
    from lib import deferred, holding, queued_messages, registry, seat_status

    registry.upsert_agent({
        "name": "research-2",
        "seat": "research-2",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "status": "unknown",
        "registered": True,
        "registered_via": "adopt",
        "managed_state": "adopted_unbound",
        "seat_instance_id": "si_status001",
        "pane_ref": "tmux:runway-engineering:%191",
        "terminal_ref": "runway-engineering:research-2",
        "backend_ref": "runway-engineering:research-2",
        "runtime_session_binding": "unbound",
        "runtime_session_id": None,
    })
    holding.create_from_candidate({
        "source": "tmux",
        "pane_ref": "tmux:runway-engineering:%999",
        "tmux_session": "runway-engineering",
        "window_name": "bash",
        "pane_id": "%999",
    })
    queued_messages.create(target="runway-engineering:research-2", message="after report", sender="tester")
    deferred.create(
        target="runway-engineering:research-2",
        message="when free",
        sender="tester",
        dedupe_key="unit-dedupe",
    )

    row = seat_status.build_seat_status("runway-engineering:research-2", terminal=FakeTerminal)

    assert row["ok"] is True
    assert row["target"] == "runway-engineering:research-2"
    assert row["managed_state"] == "adopted_unbound"
    assert row["liveness"] == "alive"
    assert row["runtime_session_binding"] == "unbound"
    assert row["runtime_session_id"] is None
    assert row["session_id"] is None
    assert {
        "unbound_runtime_session",
        "identity_missing",
        "queued_messages_pending",
        "deferred_deliveries_pending",
        "holding_records_nearby",
    } <= set(row["risk_flags"])


def test_status_keeps_weak_codex_match_out_of_runtime_session_id(aura_state):
    from lib import registry, seat_status

    registry.upsert_agent({
        "name": "research-weak",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_status002",
        "pane_ref": "tmux:runway-engineering:%191",
        "runtime_session_id": "019dd797-1169-7931-b2f7-17824b3b7134",
        "runtime_session_source": "codex-state:cwd-start",
        "runtime_session_evidence": {"reason": "cwd-start-seat-name"},
        "runtime_session_cwd": "/repo",
    })

    row = seat_status.build_seat_status("runway-engineering:research-weak", terminal=FakeTerminal)

    assert row["runtime_session_binding"] == "unbound"
    assert row["runtime_session_id"] is None
    assert row["session_id"] is None
    assert row["runtime_session_possible_matches"][0]["runtime_session_id"] == "019dd797-1169-7931-b2f7-17824b3b7134"
    assert "possible_runtime_session_matches" in row["risk_flags"]


def test_status_joins_desks_identity_and_org_position(aura_state, tmp_path):
    from lib import registry, seat_status

    desks_root = Path(tmp_path / ".desks")
    identity_dir = desks_root / "identities" / "r_status001"
    identity_dir.mkdir(parents=True)
    (identity_dir / "identity.json").write_text(
        json.dumps({
            "schema": "desks.identity.v1",
            "identity_id": "r_status001",
            "current_name": "flex:systems:specialist:workstreams",
            "aliases": [],
        }),
        encoding="utf-8",
    )
    org_dir = desks_root / "organizations" / "flex"
    org_dir.mkdir(parents=True)
    (org_dir / "current-organization.yaml").write_text(
        """
product: flex
units:
  - unit: systems
    programs:
      - program: archeology
        fleets:
          - fleet/project: flex-systems-archeology
            seats:
              - seat: specialist-workstreams
                role: flex:systems:specialist:workstreams
                identity_id: r_status001
""".lstrip(),
        encoding="utf-8",
    )

    registry.upsert_agent({
        "name": "specialist-workstreams",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_status003",
        "pane_ref": "tmux:runway-engineering:%222",
        "identity_provider": "desks",
        "identity_id": "r_status001",
        "runtime_session_id": "019dd797-1169-7931-b2f7-17824b3b7134",
        "runtime_session_source": "argv:codex-resume",
    })

    row = seat_status.build_seat_status("runway-engineering:specialist-workstreams", terminal=FakeTerminal)

    assert row["runtime_session_binding"] == "bound"
    assert row["runtime_session_id"] == "019dd797-1169-7931-b2f7-17824b3b7134"
    assert row["restore_ready"] is True
    assert row["identity"] == {
        "provider": "desks",
        "id": "r_status001",
        "name": "flex:systems:specialist:workstreams",
        "current": {"position": "flex:systems:specialist:workstreams"},
    }
    assert row["org"]["unit"] == "systems"
    assert row["org"]["program"] == "archeology"
    assert "identity_missing" not in row["risk_flags"]
    assert "org_position_missing" not in row["risk_flags"]


def test_status_includes_runtime_profile_metadata(aura_state):
    from lib import registry, seat_status

    registry.upsert_agent({
        "name": "profiled-worker",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_status004",
        "pane_ref": "tmux:runway-engineering:%222",
        "runtime_profile": "aura-worker",
        "runtime_profile_ref": "codex/aura-worker",
        "runtime_profile_runtime": "codex",
        "runtime_profile_source": "desks",
    })

    row = seat_status.build_seat_status("runway-engineering:profiled-worker", terminal=FakeTerminal)

    assert row["runtime_profile"] == "aura-worker"
    assert row["runtime_profile_ref"] == "codex/aura-worker"
    assert row["runtime_profile_runtime"] == "codex"
    assert row["runtime_profile_source"] == "desks"


# ---------------------------------------------------------------------------
# Mirror-driven liveness tests (change 1 & 2)
# ---------------------------------------------------------------------------

def test_pane_ref_not_in_mirror_yields_missing_liveness(aura_state, monkeypatch):
    """A record whose %N is absent from the mirror must be historical (not stored status)."""
    from lib import registry, seat_status, tmux_mirror

    registry.upsert_agent({
        "name": "gone-worker",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_gone001",
        "pane_ref": "tmux:runway-engineering:%999",
        "status": "alive",  # stored status must NOT be trusted for liveness
    })

    row = seat_status.build_seat_status("runway-engineering:gone-worker", terminal=FakeTerminal)

    assert row["ok"] is True
    assert row["liveness"] == "missing"
    assert row["managed_state"] == "missing_pane"
    assert row["terminal"] == "missing"
    assert "missing_pane" in row["risk_flags"]


def test_stopped_seat_stays_stopped_when_pane_gone():
    """An in-memory record carrying managed_state=stopped must NOT flip to missing_pane
    when its pane is gone (e.g. a ledger-merged row read with a dead %N)."""
    from lib import seat_status

    state = seat_status._derive_managed_state(
        {"managed_state": "stopped"}, liveness="missing", binding="unbound"
    )
    assert state == "stopped"


def test_pane_ref_in_mirror_yields_alive_liveness(aura_state, monkeypatch):
    """%N present in the mirror → liveness is alive, overriding any stored status."""
    from lib import registry, seat_status

    registry.upsert_agent({
        "name": "live-worker",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_live001",
        "pane_ref": "tmux:runway-engineering:%191",
        "status": "idle",
    })

    row = seat_status.build_seat_status("runway-engineering:live-worker", terminal=FakeTerminal)

    assert row["ok"] is True
    assert row["liveness"] == "alive"
    assert row["terminal"] == "alive"
    assert "missing_pane" not in row["risk_flags"]


def test_name_only_record_falls_back_to_target_exists(aura_state, monkeypatch):
    """A record with no %N pane_ref (name-only / shell runtime) uses the target_exists fallback."""
    from lib import registry, seat_status

    registry.upsert_agent({
        "name": "shell-worker",
        "fleet": "runway-engineering",
        "runtime": "shell",
        "registered": True,
        "seat_instance_id": "si_shell001",
        # terminal_ref only — no pane_ref with a %N
        "terminal_ref": "runway-engineering:shell-worker",
    })

    class ShellTerminal:
        @staticmethod
        def configure_session(fleet):
            return fleet
        @staticmethod
        def target_exists(target):
            return target == "runway-engineering:shell-worker"

    row = seat_status.build_seat_status("runway-engineering:shell-worker", terminal=ShellTerminal)

    assert row["ok"] is True
    assert row["liveness"] == "alive"
    assert row["terminal"] == "alive"


def test_mirror_unavailable_falls_back_to_per_seat_target_exists(aura_state, monkeypatch):
    """When the mirror returns ok=False the code falls back to per-seat target_exists."""
    from lib import registry, seat_status, tmux_mirror

    # Override the fixture's mirror with a failing one.
    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: {"ok": False, "error": "no tmux", "panes": []})

    registry.upsert_agent({
        "name": "fallback-worker",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_fallback001",
        "pane_ref": "tmux:runway-engineering:%191",
        "status": "idle",
    })

    row = seat_status.build_seat_status("runway-engineering:fallback-worker", terminal=FakeTerminal)

    # FakeTerminal.target_exists knows %191 is alive → should still report alive.
    assert row["ok"] is True
    assert row["liveness"] == "alive"


def test_list_seat_statuses_single_mirror_join(aura_state, monkeypatch):
    """list_seat_statuses uses a single mirror call and computes liveness for all seats."""
    from lib import registry, seat_status, tmux_mirror

    call_count = {"n": 0}
    real_mirror = _FAKE_MIRROR

    def counting_mirror(**_kw):
        call_count["n"] += 1
        return real_mirror

    monkeypatch.setattr(tmux_mirror, "list_physical_panes", counting_mirror)

    registry.upsert_agent({
        "name": "alpha",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:runway-engineering:%191",
    })
    registry.upsert_agent({
        "name": "beta",
        "fleet": "runway-engineering",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:runway-engineering:%999",
    })

    rows = seat_status.list_seat_statuses(fleet="runway-engineering", terminal=FakeTerminal)

    assert call_count["n"] == 1  # single mirror call regardless of seat count
    by_name = {row["seat"]: row for row in rows}
    assert by_name["alpha"]["liveness"] == "alive"
    assert by_name["beta"]["liveness"] == "missing"
    assert by_name["beta"]["managed_state"] == "missing_pane"


def test_list_seat_statuses_liveness_is_session_aware(aura_state, monkeypatch):
    from lib import registry, seat_status, tmux_mirror

    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **_kw: {
        "ok": True,
        "schema": "aura.tmux_mirror.v1",
        "panes": [
            {
                "pane_id": "%777",
                "pane_ref": "tmux:new-fleet:%777",
                "tmux_session": "new-fleet",
                "physical_fleet": "new-fleet",
            }
        ],
    })

    registry.upsert_agent({
        "name": "worker",
        "fleet": "old-fleet",
        "runtime": "codex",
        "registered": True,
        "pane_ref": "tmux:old-fleet:%777",
    })

    rows = seat_status.list_seat_statuses(fleet="old-fleet", terminal=None)

    assert len(rows) == 1
    assert rows[0]["liveness"] == "missing"
    assert rows[0]["managed_state"] == "missing_pane"

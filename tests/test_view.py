import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_view_infers_product_scope_from_current_role(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "flex-leaders")
    monkeypatch.setenv("AURA_SEAT", "leader-engine")
    monkeypatch.setenv("AURA_RUNTIME", "codex")
    monkeypatch.setenv("CODEX_THREAD_ID", "019ddf5f-b386-7ef0-9f43-8329ab2019c7")
    monkeypatch.setenv("DESKS_PRODUCT", "flex")

    from lib import registry, reports
    from commands import view

    registry.upsert_agent({
        "name": "leader-engine",
        "fleet": "flex-leaders",
        "runtime": "codex",
        "status": "idle",
        "desks_product": "flex",
        "desks_unit": "engine",
        "runtime_session_id": "leader-session",
    })
    registry.upsert_agent({
        "name": "specialist-testing",
        "fleet": "flex-specialists",
        "runtime": "codex",
        "status": "working",
        "desks_product": "flex",
        "desks_unit": "engine",
    })
    registry.upsert_agent({
        "name": "demo-builder",
        "fleet": "flexgraph-workers",
        "runtime": "codex",
        "status": "working",
        "desks_product": "flexgraph",
        "desks_unit": "surfaces",
    })

    monkeypatch.setenv("AURA_SEAT", "specialist-testing")
    monkeypatch.setenv("AURA_FLEET", "flex-specialists")
    reports.append_report({
        "state": "working",
        "work": "Checking report verification",
        "done": [],
        "receipts": [],
        "next": "Return verification contract",
        "blockers": [],
    })
    monkeypatch.setenv("AURA_SEAT", "leader-engine")
    monkeypatch.setenv("AURA_FLEET", "flex-leaders")

    result = view.run(argparse.Namespace(scope=None, limit=10, include_hidden=False))

    assert result["ok"] is True
    assert result["view_scope"] == "scoped"
    assert result["scope_source"] == "context"
    assert result["scope"] == {"kind": "unit", "name": "flex:engine", "product": "flex", "unit": "engine"}
    assert result["counts"]["colleagues"] == 2
    assert {row["seat"] for row in result["colleagues"]} == {"leader-engine", "specialist-testing"}
    assert result["fleets"] == ["flex-leaders", "flex-specialists"]
    specialist = next(row for row in result["colleagues"] if row["seat"] == "specialist-testing")
    assert specialist["last_report"]["state"] == "working"
    assert specialist["last_report"]["work"] == "Checking report verification"


def test_view_can_scope_to_one_fleet(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "flex-leaders")
    monkeypatch.setenv("AURA_SEAT", "leader-engine")
    monkeypatch.setenv("AURA_RUNTIME", "codex")

    from lib import registry
    from commands import view

    registry.upsert_agent({"name": "leader-engine", "fleet": "flex-leaders", "runtime": "codex"})
    registry.upsert_agent({"name": "worker", "fleet": "flex-workers", "runtime": "codex"})

    result = view.run(argparse.Namespace(scope="fleet:flex-workers", limit=10, include_hidden=False))

    assert result["view_scope"] == "scoped"
    assert result["scope_source"] == "explicit"
    assert result["scope"] == {"kind": "fleet", "name": "flex-workers", "fleet": "flex-workers"}
    assert [row["seat"] for row in result["colleagues"]] == ["worker"]


def test_view_limit_bounds_colleague_rows(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "leader")
    monkeypatch.setenv("AURA_RUNTIME", "codex")

    from lib import registry
    from commands import view

    registry.upsert_agent({"name": "leader", "fleet": "unitfleet", "runtime": "codex"})
    registry.upsert_agent({"name": "worker-a", "fleet": "unitfleet", "runtime": "codex"})
    registry.upsert_agent({"name": "worker-b", "fleet": "unitfleet", "runtime": "codex"})

    result = view.run(argparse.Namespace(scope=None, limit=2, include_hidden=False))

    assert result["counts"]["colleagues"] == 3
    assert result["counts"]["colleagues_returned"] == 2
    assert len(result["colleagues"]) == 2


def test_view_includes_pending_queue_for_scoped_targets(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "leader")
    monkeypatch.setenv("AURA_RUNTIME", "codex")

    from lib import queued_messages, registry
    from commands import view

    registry.upsert_agent({"name": "leader", "fleet": "unitfleet", "runtime": "codex"})
    registry.upsert_agent({"name": "worker", "fleet": "unitfleet", "runtime": "codex"})
    queued = queued_messages.create(target="unitfleet:worker", message="after report", sender="tester")

    result = view.run(argparse.Namespace(scope="fleet:unitfleet", limit=10, include_hidden=False))

    assert result["counts"]["pending_queue"] == 1
    assert result["pending_queue"][0]["queue_id"] == queued["queue_id"]


def test_view_keys_latest_reports_by_fleet_and_seat(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_RUNTIME", "codex")
    monkeypatch.setenv("DESKS_PRODUCT", "flex")

    from lib import registry, reports
    from commands import view

    registry.upsert_agent({
        "name": "lead",
        "fleet": "fleet-a",
        "runtime": "codex",
        "desks_product": "flex",
    })
    registry.upsert_agent({
        "name": "lead",
        "fleet": "fleet-b",
        "runtime": "codex",
        "desks_product": "flex",
    })

    monkeypatch.setenv("AURA_SEAT", "lead")
    monkeypatch.setenv("AURA_FLEET", "fleet-a")
    reports.append_report({"state": "working", "work": "fleet-a work"})
    monkeypatch.setenv("AURA_FLEET", "fleet-b")
    reports.append_report({"state": "blocked", "work": "fleet-b work"})

    result = view.run(argparse.Namespace(scope=None, limit=10, include_hidden=False))

    by_target = {f"{row['fleet']}:{row['seat']}": row for row in result["colleagues"]}
    assert by_target["fleet-a:lead"]["last_report"]["work"] == "fleet-a work"
    assert by_target["fleet-b:lead"]["last_report"]["work"] == "fleet-b work"


def test_view_default_colleagues_include_runtime_profile_metadata(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SEAT", "leader")
    monkeypatch.setenv("AURA_RUNTIME", "codex")

    from lib import registry
    from commands import view

    registry.upsert_agent({
        "name": "worker",
        "fleet": "unitfleet",
        "runtime": "codex",
        "runtime_profile": "aura-worker",
        "runtime_profile_ref": "codex/aura-worker",
        "runtime_profile_runtime": "codex",
        "runtime_profile_source": "desks",
    })

    result = view.run(argparse.Namespace(scope="fleet:unitfleet", limit=10, include_hidden=False))

    worker = next(row for row in result["colleagues"] if row["seat"] == "worker")
    assert worker["runtime_profile"] == "aura-worker"
    assert worker["runtime_profile_ref"] == "codex/aura-worker"
    assert worker["runtime_profile_runtime"] == "codex"
    assert worker["runtime_profile_source"] == "desks"


def test_view_self_returns_current_managed_seat(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "runway-engineering")
    monkeypatch.setenv("AURA_SEAT", "lead-engineer")
    monkeypatch.setenv("AURA_RUNTIME", "codex")

    from commands import view

    monkeypatch.setattr(view, "_status_rows", lambda include_hidden=False: [
        {
            "target": "runway-engineering:lead-engineer",
            "seat": "lead-engineer",
            "fleet": "runway-engineering",
            "runtime": "codex",
            "runtime_session_id": "session-self",
            "runtime_session_binding": "bound",
            "seat_instance_id": "si_self",
            "identity_provider": "desks",
            "identity_id": "r_self",
            "identity_label": "runway:engineering:lead:engineer",
            "runtime_profile": "aura-worker",
            "runtime_profile_ref": "codex/aura-worker",
            "runtime_profile_runtime": "codex",
            "runtime_profile_source": "desks",
            "placements": [{"placement_id": "pl_factory", "name": "factory"}],
            "liveness": "alive",
            "managed_state": "spawned_bound",
        },
    ])

    result = view.run(argparse.Namespace(view_action="self", scope=None, limit=10, include_hidden=False))

    assert result["ok"] is True
    assert result["schema"] == "aura.view.self.v1"
    assert result["view_scope"] == "self"
    assert result["self"]["target"] == "runway-engineering:lead-engineer"
    assert result["self"]["runtime_session_id"] == "session-self"
    assert result["self"]["identity"]["id"] == "r_self"
    assert result["self"]["runtime_profile_ref"] == "codex/aura-worker"
    assert result["self"]["runtime_profile_source"] == "desks"
    assert result["self"]["placements"][0]["name"] == "factory"


def test_view_fleets_returns_live_fleet_index(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import registry
    from commands import view

    registry.write_registry({
        "runway-engineering:lead-engineer": {"name": "lead-engineer", "fleet": "runway-engineering", "pane_ref": "tmux:runway-engineering:%1"},
        "runway-engineering:worker": {"name": "worker", "fleet": "runway-engineering", "pane_ref": "tmux:runway-engineering:%2"},
        "runway-research:research-lead": {"name": "research-lead", "fleet": "runway-research", "backend_ref": "tmux:runway-research:research-lead"},
        "runway-research:stale": {"name": "stale", "fleet": "runway-research", "pane_ref": "tmux:runway-research:%4"},
        "runway-research:stopped": {"name": "stopped", "fleet": "runway-research", "pane_ref": "tmux:runway-research:%5", "managed_state": "stopped"},
    })
    monkeypatch.setattr(view.tmux_mirror, "list_physical_panes", lambda: {
        "ok": True,
        "panes": [
            {"tmux_session": "runway-engineering", "physical_fleet": "runway-engineering", "window_name": "lead-engineer", "pane_id": "%1", "pane_ref": "tmux:runway-engineering:%1", "terminal_ref": "tmux:runway-engineering:lead-engineer"},
            {"tmux_session": "runway-engineering", "physical_fleet": "runway-engineering", "window_name": "worker", "pane_id": "%2", "pane_ref": "tmux:runway-engineering:%2", "terminal_ref": "tmux:runway-engineering:worker"},
            {"tmux_session": "runway-research", "physical_fleet": "runway-research", "window_name": "research-lead", "pane_id": "%3", "pane_ref": "tmux:runway-research:%3", "terminal_ref": "tmux:runway-research:research-lead"},
            {"tmux_session": "runway-research", "physical_fleet": "runway-research", "window_name": "stopped", "pane_id": "%5", "pane_ref": "tmux:runway-research:%5", "terminal_ref": "tmux:runway-research:stopped"},
        ],
    })

    result = view.run(argparse.Namespace(view_action="fleets", view_target=None, scope=None, limit=10, include_hidden=False))

    assert result["ok"] is True
    assert result["schema"] == "aura.view.fleets.v1"
    assert result["view_scope"] == "live"
    assert result["scope"] == "live"
    assert result["fleets"] == [
        {"fleet": "runway-engineering", "seats": 2},
        {"fleet": "runway-research", "seats": 1},
    ]


def test_view_fleets_reports_tmux_mirror_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import view

    monkeypatch.setattr(view.tmux_mirror, "list_physical_panes", lambda: {
        "ok": False,
        "error": "no server running",
        "panes": [],
    })

    result = view.run(argparse.Namespace(view_action="fleets", view_target=None, scope=None, limit=10, include_hidden=False))

    assert result == {
        "ok": False,
        "schema": "aura.view.fleets.v1",
        "view_scope": "live",
        "scope": "live",
        "error": "tmux-mirror-unavailable",
        "detail": "no server running",
        "fleets": [],
    }


def test_view_fleet_reports_tmux_mirror_failure_instead_of_empty_roster(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import registry
    from commands import view

    registry.upsert_agent({
        "fleet": "aura-engine",
        "name": "adjunct-engineer",
        "runtime": "codex",
        "pane_ref": "tmux:aura-engine:%101",
    })
    monkeypatch.setattr(view.tmux_mirror, "list_physical_panes", lambda: {
        "ok": False,
        "error": "can't access /tmp/tmux-1000/default",
        "panes": [],
    })

    result = view.run(argparse.Namespace(view_action="fleet", view_target="aura-engine", scope=None, limit=10, include_hidden=False))

    assert result["ok"] is False
    assert result["schema"] == "aura.view.fleet.v1"
    assert result["view_scope"] == "fleet"
    assert result["error"] == "tmux-mirror-unavailable"
    assert result["fleet"] == "aura-engine"
    assert result["seats"] == []


def test_view_fleet_uses_tmux_join_not_stale_registry_projection(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import registry
    from commands import view

    registry.write_registry({
        "fitcert:pipeline": {
            "fleet": "fitcert",
            "name": "pipeline",
            "runtime": "codex",
            "runtime_session_id": "session-live",
            "pane_ref": "tmux:fitcert:%11",
            "managed_state": "missing_pane",
        },
        "fitcert:stale": {
            "fleet": "fitcert",
            "name": "stale",
            "runtime": "codex",
            "runtime_session_id": "session-stale",
            "pane_ref": "tmux:fitcert:%99",
            "managed_state": "spawned_bound",
        },
    })
    monkeypatch.setattr(view.tmux_mirror, "list_physical_panes", lambda: {
        "ok": True,
        "panes": [
            {"tmux_session": "fitcert", "physical_fleet": "fitcert", "window_name": "pipeline", "pane_id": "%11", "pane_ref": "tmux:fitcert:%11", "terminal_ref": "tmux:fitcert:pipeline"},
        ],
    })

    result = view.run(argparse.Namespace(view_action="fleet", view_target="fitcert", scope=None, limit=10, include_hidden=False))

    assert [row["target"] for row in result["seats"]] == ["fitcert:pipeline"]
    assert result["seats"][0]["liveness"] == "alive"
    assert result["seats"][0]["managed_state"] == "spawned_bound"


def test_view_fleet_returns_same_fleet_rows(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "runway-engineering")
    monkeypatch.setenv("AURA_SEAT", "lead-engineer")

    from commands import view

    monkeypatch.setattr(view, "_live_status_rows", lambda include_hidden=False: {
        "ok": True,
        "historical_count": 4,
        "rows": [
            {"target": "runway-engineering:lead-engineer", "seat": "lead-engineer", "fleet": "runway-engineering", "liveness": "alive", "managed_state": "spawned_unbound"},
            {"target": "runway-engineering:worker", "seat": "worker", "fleet": "runway-engineering", "liveness": "alive", "managed_state": "spawned_unbound"},
            {"target": "runway-marketing:other", "seat": "other", "fleet": "runway-marketing", "liveness": "alive", "managed_state": "spawned_unbound"},
        ],
    })

    result = view.run(argparse.Namespace(view_action="fleet", view_target=None, scope=None, limit=10, include_hidden=False))

    assert result["ok"] is True
    assert result["schema"] == "aura.view.fleet.v1"
    assert result["view_scope"] == "fleet"
    assert result["scope_source"] == "context"
    assert result["fleet"] == "runway-engineering"
    assert {row["target"] for row in result["seats"]} == {
        "runway-engineering:lead-engineer",
        "runway-engineering:worker",
    }


def test_view_fleet_accepts_explicit_fleet_and_flattens_latest_report(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import view

    def fake_live_status_rows(include_hidden=False):
        return {
            "ok": True,
            "historical_count": 2,
            "rows": [
                {
                    "target": "flexgraph-chatbot:engineering-lead",
                    "seat": "engineering-lead",
                    "fleet": "flexgraph-chatbot",
                    "status": "waiting",
                    "runtime": "codex",
                    "runtime_profile": "aura-worker",
                    "runtime_profile_ref": "codex/aura-worker",
                    "runtime_profile_runtime": "codex",
                    "runtime_profile_source": "desks",
                    "runtime_session_id": "session-engineering",
                    "liveness": "alive",
                    "managed_state": "spawned_bound",
                    "identity": {"provider": "desks", "id": "r_5c425f44", "name": "flexgraph:chatbot:engineering:lead"},
                    "latest_report": {"state": "parked", "work": "Loaded identity and waiting for assignment"},
                },
                {
                    "target": "other-fleet:lead",
                    "seat": "lead",
                    "fleet": "other-fleet",
                    "liveness": "alive",
                    "managed_state": "spawned_unbound",
                },
            ],
        }

    monkeypatch.setattr(view, "_live_status_rows", fake_live_status_rows)

    result = view.run(argparse.Namespace(view_action="fleet", view_target="flexgraph-chatbot", scope=None, limit=10, include_hidden=False))

    assert result == {
        "fleet": "flexgraph-chatbot",
        "seats": [
            {
                "target": "flexgraph-chatbot:engineering-lead",
                "status": "waiting",
                "liveness": "alive",
                "managed_state": "spawned_bound",
                "runtime": "codex",
                "runtime_profile": "aura-worker",
                "runtime_profile_ref": "codex/aura-worker",
                "runtime_profile_runtime": "codex",
                "runtime_profile_source": "desks",
                "session_id": "session-engineering",
                "identity": "r_5c425f44",
                "name": "flexgraph:chatbot:engineering:lead",
                "report": "Loaded identity and waiting for assignment",
            },
        ],
    }


def test_view_roster_returns_live_rows_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import view

    monkeypatch.setattr(view, "_live_status_rows", lambda include_hidden=False: {
        "ok": True,
        "historical_count": 3,
        "rows": [
            {"target": "runway-engineering:lead-engineer", "seat": "lead-engineer", "fleet": "runway-engineering", "liveness": "alive", "managed_state": "spawned_unbound"},
            {"target": "runway-research:research-lead", "seat": "research-lead", "fleet": "runway-research", "liveness": "alive", "managed_state": "spawned_unbound"},
        ],
    })

    result = view.run(argparse.Namespace(view_action="roster", scope=None, limit=10, include_hidden=False))

    assert result["ok"] is True
    assert result["schema"] == "aura.view.roster.v1"
    assert result["view_scope"] == "live"
    assert result["scope"] == "live"
    assert result["counts"] == {"fleets": 2, "seats": 2, "historical_seats": 3}
    assert result["fleets"] == ["runway-engineering", "runway-research"]
    assert {row["target"] for row in result["seats"]} == {
        "runway-engineering:lead-engineer",
        "runway-research:research-lead",
    }


def test_view_roster_reports_tmux_mirror_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import registry
    from commands import view

    registry.upsert_agent({"fleet": "aura-engine", "name": "adjunct-engineer", "pane_ref": "tmux:aura-engine:%101"})
    monkeypatch.setattr(view.tmux_mirror, "list_physical_panes", lambda: {
        "ok": False,
        "error": "no tmux socket",
        "panes": [],
    })

    result = view.run(argparse.Namespace(view_action="roster", scope=None, limit=10, include_hidden=False))

    assert result["ok"] is False
    assert result["schema"] == "aura.view.roster.v1"
    assert result["error"] == "tmux-mirror-unavailable"
    assert result["counts"] == {"fleets": 0, "seats": 0, "historical_seats": 1}
    assert result["seats"] == []


def test_view_roster_uses_tmux_join_and_keeps_historical_count(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import registry
    from commands import view

    registry.write_registry({
        "fleet-a:live": {"fleet": "fleet-a", "name": "live", "runtime": "codex", "pane_ref": "tmux:fleet-a:%1"},
        "fleet-b:stale": {"fleet": "fleet-b", "name": "stale", "runtime": "codex", "pane_ref": "tmux:fleet-b:%2"},
    })
    monkeypatch.setattr(view.tmux_mirror, "list_physical_panes", lambda: {
        "ok": True,
        "panes": [
            {"tmux_session": "fleet-a", "physical_fleet": "fleet-a", "window_name": "live", "pane_id": "%1", "pane_ref": "tmux:fleet-a:%1", "terminal_ref": "tmux:fleet-a:live"},
        ],
    })

    result = view.run(argparse.Namespace(view_action="roster", scope=None, limit=10, include_hidden=False))

    assert result["counts"] == {"fleets": 1, "seats": 1, "historical_seats": 2}
    assert result["fleets"] == ["fleet-a"]
    assert [row["target"] for row in result["seats"]] == ["fleet-a:live"]


def test_view_historical_returns_all_managed_rows(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import view

    monkeypatch.setattr(view, "_status_rows", lambda include_hidden=False: [
        {"target": "runway-engineering:lead-engineer", "seat": "lead-engineer", "fleet": "runway-engineering", "liveness": "alive", "managed_state": "spawned_unbound"},
        {"target": "runway-research:stale", "seat": "stale", "fleet": "runway-research", "liveness": "missing", "managed_state": "missing_pane"},
    ])

    result = view.run(argparse.Namespace(view_action="historical", scope=None, limit=10, include_hidden=False))

    assert result["ok"] is True
    assert result["schema"] == "aura.view.historical.v1"
    assert result["view_scope"] == "historical"
    assert result["counts"] == {"fleets": 2, "seats": 2}
    assert {row["target"] for row in result["seats"]} == {
        "runway-engineering:lead-engineer",
        "runway-research:stale",
    }


def test_view_self_rejects_stale_env_match(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "runway-engineering")
    monkeypatch.setenv("AURA_SEAT", "stale")

    from commands import view

    monkeypatch.setattr(view, "_status_rows", lambda include_hidden=False: [
        {
            "target": "runway-engineering:stale",
            "seat": "stale",
            "fleet": "runway-engineering",
            "liveness": "missing",
            "managed_state": "missing_pane",
        },
    ])

    result = view.run(argparse.Namespace(view_action="self", scope=None, limit=10, include_hidden=False))

    assert result["ok"] is False
    assert result["schema"] == "aura.view.self.v1"
    assert result["view_scope"] == "self"
    assert result["error"] == "self-not-live"
    assert result["matches"] == ["runway-engineering:stale"]


def test_view_live_alias_preserves_live_roster(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import view

    monkeypatch.setattr(view, "_live_status_rows", lambda include_hidden=False: {
        "ok": True,
        "historical_count": 2,
        "rows": [
            {"target": "runway-engineering:lead", "seat": "lead", "fleet": "runway-engineering", "liveness": "alive", "managed_state": "spawned_bound"},
        ],
    })

    result = view.run(argparse.Namespace(view_action="live", view_target=None, scope=None, limit=10, include_hidden=False))

    assert result["ok"] is True
    assert result["schema"] == "aura.view.live.v1"
    assert result["view_scope"] == "live"
    assert result["alias_of"] == "roster"
    assert [row["target"] for row in result["seats"]] == ["runway-engineering:lead"]


def test_view_placement_returns_live_members_and_hides_stale(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import view

    monkeypatch.setattr(view, "_status_rows", lambda include_hidden=False: [
        {"target": "flexgraph-chatbot:pipeline", "seat_ref": "flexgraph-chatbot:pipeline", "seat": "pipeline", "fleet": "flexgraph-chatbot", "runtime": "omx", "liveness": "alive", "managed_state": "spawned_bound"},
        {"target": "flexgraph-chatbot:stale", "seat_ref": "flexgraph-chatbot:stale", "seat": "stale", "fleet": "flexgraph-chatbot", "runtime": "omx", "liveness": "missing", "managed_state": "missing_pane"},
    ])
    monkeypatch.setattr(view.placements, "get_placement", lambda name: {
        "placement_id": "pl_factory",
        "kind": "workstream",
        "name": "factory-quality",
        "label": "Factory Quality",
        "members": [
            {"seat_ref": "flexgraph-chatbot:pipeline"},
            {"seat_ref": "flexgraph-chatbot:stale"},
            {"seat_ref": "flexgraph-chatbot:missing"},
        ],
    } if name in {"factory-quality", "pl_factory"} else None)

    result = view.run(argparse.Namespace(view_action="placement", view_target="factory-quality", scope=None, limit=10, include_hidden=False))

    assert result["ok"] is True
    assert result["schema"] == "aura.view.placement.v1"
    assert result["view_scope"] == "placement"
    assert result["placement"]["name"] == "factory-quality"
    assert result["counts"] == {"members": 3, "seats": 1, "hidden_non_live_members": 2, "missing_members": 1}
    assert [row["target"] for row in result["seats"]] == ["flexgraph-chatbot:pipeline"]


def test_view_placement_infers_single_self_placement(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "flexgraph-chatbot")
    monkeypatch.setenv("AURA_SEAT", "pipeline")

    from commands import view

    monkeypatch.setattr(view, "_status_rows", lambda include_hidden=False: [
        {
            "target": "flexgraph-chatbot:pipeline",
            "seat_ref": "flexgraph-chatbot:pipeline",
            "seat": "pipeline",
            "fleet": "flexgraph-chatbot",
            "liveness": "alive",
            "managed_state": "spawned_bound",
            "placements": [{"placement_id": "pl_factory", "name": "factory-quality"}],
        },
    ])
    monkeypatch.setattr(view.placements, "get_placement", lambda name: {
        "placement_id": "pl_factory",
        "kind": "workstream",
        "name": "factory-quality",
        "members": [{"seat_ref": "flexgraph-chatbot:pipeline"}],
    })

    result = view.run(argparse.Namespace(view_action="placement", view_target=None, scope=None, limit=10, include_hidden=False))

    assert result["ok"] is True
    assert result["source"] == "self"
    assert result["placement"]["name"] == "factory-quality"


def test_view_placement_requires_target_when_not_resolved(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "flexgraph-chatbot")
    monkeypatch.setenv("AURA_SEAT", "pipeline")

    from commands import view

    monkeypatch.setattr(view, "_status_rows", lambda include_hidden=False: [
        {"target": "flexgraph-chatbot:pipeline", "seat": "pipeline", "fleet": "flexgraph-chatbot", "liveness": "alive", "managed_state": "spawned_bound"},
    ])

    result = view.run(argparse.Namespace(view_action="placement", view_target=None, scope=None, limit=10, include_hidden=False))

    assert result["ok"] is False
    assert result["error"] == "placement-not-resolved"

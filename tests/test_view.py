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

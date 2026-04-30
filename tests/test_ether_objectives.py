import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_ether_objective_registry_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import objectives

    record = objectives.create_objective(
        "flex-release-parity",
        title="Flex release/parity",
        seats=["flex-leaders-2:engineer", "flex-leaders-2:testing-lead"],
    )

    assert record["schema"] == "aura.objective.v1"
    assert record["policies"]["non_actuating"] is True
    loaded = objectives.load_objective("flex-release-parity")
    assert loaded["seats"] == ["flex-leaders-2:engineer", "flex-leaders-2:testing-lead"]
    assert objectives.list_objectives()[0]["objective_id"] == "flex-release-parity"


def test_ether_evaluate_records_blocked_delivery_recommendation(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))

    from lib import delivery, ether, objectives, recommendations

    objective = objectives.create_objective(
        "flex-release-parity",
        seats=["flex-leaders-2:engineer", "flex-leaders-2:testing-lead"],
    )
    record = delivery.new_delivery_record(
        delivery_type="semantic_send",
        sender="flex-leaders-2:testing-lead",
        target="flex-leaders-2:engineer",
        backend="tmux",
        state="blocked",
        error="target-busy",
    )
    delivery.append_attempt(record, state="blocked", evidence={"blocker": "target-busy"})
    delivery.append_record(record)

    result = ether.evaluate_objective(objective)

    assert result["ok"] is True
    assert result["recorded"] is True
    assert result["state_packet"]["delivery_vector"]["blocked_messages"][0]["state"] == "blocked"
    rec = result["recommendation"]
    assert rec["schema"] == "aura.ether.recommendation.v1"
    assert rec["recommendation"]["action"] == "manager_dialogue"
    assert rec["recommendation"]["target"] == "flex-leaders-2:engineer"
    assert recommendations.list_recommendations(objective_id="flex-release-parity", status="open")[0]["recommendation_id"] == rec["recommendation_id"]


def test_ether_cli_dry_run_does_not_record(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))

    from commands import ether as ether_cmd
    from lib import delivery, objectives, recommendations

    objectives.create_objective("obj", seats=["fleet:worker"])
    record = delivery.new_delivery_record(
        delivery_type="semantic_send",
        sender="fleet:lead",
        target="fleet:worker",
        state="blocked",
        error="target-busy",
    )
    delivery.append_record(record)

    result = ether_cmd.run(argparse.Namespace(ether_area="evaluate", objective_id="obj", dry_run=True))

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["recommendation"]["recommendation"]["target"] == "fleet:worker"
    assert recommendations.list_recommendations() == []

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_ether_state_packet_ingests_deferred_and_session_records(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))

    from lib import deferred, ether, objectives, session_ledger

    objective = objectives.create_objective("obj", seats=["fleet:worker"])
    deferred.create(
        target="fleet:worker",
        message="hello",
        sender="fleet:lead",
        dedupe_key="k",
        blocked_reason="target-busy",
    )
    session_ledger.append_record({
        "event": "session_observed",
        "seat": "worker",
        "fleet": "fleet",
        "runtime": "codex",
        "runtime_session_id": "thread-1",
        "runtime_session_confidence": "high",
    })

    packet = ether.build_state_packet(objective)

    kinds = {signal["kind"] for signal in packet["signals"]}
    assert "delivery.deferred" in kinds
    assert "session.session_observed" in kinds
    assert packet["delivery_vector"]["deferred_messages"][0]["target"] == "fleet:worker"
    assert packet["session_vector"]["records"][0]["runtime_session_id"] == "thread-1"


def test_ether_session_info_signals_do_not_mark_state_blocked(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import ether, objectives, session_ledger

    objective = objectives.create_objective("obj", seats=["fleet:worker"])
    session_ledger.append_record({
        "event": "spawn",
        "seat": "worker",
        "fleet": "fleet",
        "runtime": "codex",
    })

    packet = ether.build_state_packet(objective)

    assert {signal["kind"] for signal in packet["signals"]} == {"session.spawn"}
    assert packet["state_vector"]["blocked"] == []


def test_ether_dedupes_open_blocked_delivery_recommendation(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))

    from lib import delivery, ether, objectives, recommendations

    objective = objectives.create_objective("obj", seats=["fleet:worker"])
    record = delivery.new_delivery_record(
        delivery_id="delivery-1",
        delivery_type="semantic_send",
        sender="fleet:lead",
        target="fleet:worker",
        state="blocked",
        error="target-busy",
    )
    delivery.append_record(record)

    first = ether.evaluate_objective(objective)
    second = ether.evaluate_objective(objective)

    assert first["recommendation"]["recommendation_id"] == second["recommendation"]["recommendation_id"]
    assert len(recommendations.list_recommendations(objective_id="obj", status="open")) == 1


def test_ether_ignores_blocked_delivery_after_deferred_recovery(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"))

    from lib import deferred, delivery, ether, objectives, recommendations

    objective = objectives.create_objective("obj", seats=["fleet:worker"])
    blocked = delivery.new_delivery_record(
        delivery_id="delivery-blocked",
        delivery_type="semantic_send",
        sender="fleet:lead",
        target="fleet:worker",
        state="blocked",
        error="target-busy",
        dedupe_key="same-message",
    )
    delivery.append_record(blocked)
    deferred_record = deferred.create(
        target="fleet:worker",
        message="hello",
        sender="fleet:lead",
        dedupe_key="same-message",
        blocked_reason="target-busy",
        blocked_message_id=blocked["message_id"],
    )

    before = ether.evaluate_objective(objective)
    assert before["recommendation"]["state"] == "blocked_delivery"

    delivered = delivery.new_delivery_record(
        delivery_id="delivery-delivered",
        delivery_type="semantic_send",
        sender="fleet:lead",
        target="fleet:worker",
        state="delivered",
        dedupe_key="same-message",
    )
    delivery.append_record(delivered)
    deferred_record["status"] = "delivered"
    deferred.save(deferred_record)

    after = ether.evaluate_objective(objective)
    assert after["recommendation"] is None
    assert after["resolved_recommendations"][0]["recommendation_id"] == before["recommendation"]["recommendation_id"]
    assert after["state_packet"]["delivery_vector"]["blocked_messages"] == []
    assert recommendations.list_recommendations(objective_id="obj", status="open") == []
    assert recommendations.list_recommendations(objective_id="obj", status="superseded")[0]["recommendation_id"] == before["recommendation"]["recommendation_id"]


def test_recommendation_ledger_lists_latest_status(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from lib import recommendations

    row = recommendations.append_recommendation({
        "objective_id": "obj",
        "state": "blocked_delivery",
        "recommendation": {"target": "fleet:worker"},
    })
    marked = recommendations.mark_recommendation(row["recommendation_id"], "superseded")

    assert marked["status"] == "superseded"
    assert recommendations.list_recommendations(objective_id="obj", status="open") == []
    assert recommendations.list_recommendations(objective_id="obj", status="superseded")[0]["recommendation_id"] == row["recommendation_id"]

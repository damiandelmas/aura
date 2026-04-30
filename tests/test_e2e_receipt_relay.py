"""Isolated Receipt Relay E2E for Aura telemetry coordination."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _write_executable(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_receipt_relay_telemetry_spine(monkeypatch, tmp_path):
    state_root = tmp_path / ".aura"
    artifact_root = tmp_path / "artifact"
    artifact_root.mkdir()
    fleet = f"aura-e2e-{tmp_path.name}"
    hidden_fleet = f"_aura-ether-{tmp_path.name}"
    monkeypatch.setenv("AURA_STATE_DIR", str(state_root))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(state_root / "registry" / "seats.json"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(state_root / "registry" / "deliveries.jsonl"))
    monkeypatch.setenv("AURA_FLEET", fleet)

    from commands import sessions
    from lib import (
        deferred,
        delivery,
        ether,
        event_sidecar,
        events,
        objectives,
        recommendations,
        registry,
        session_ledger,
    )

    # Seat map: three visible workers and one hidden Ether observer.
    for name in ("manager", "builder", "tester"):
        registry.upsert_agent({
            "name": name,
            "fleet": fleet,
            "runtime": "codex",
            "registered": True,
            "terminal_ref": f"{fleet}:{name}",
            "session_id": f"codex-{name}",
            "runtime_session_id": f"codex-{name}",
            "runtime_session_confidence": "high",
            "runtime_session_source": "e2e-fixture",
            "cwd": str(tmp_path),
        })
        session_ledger.append_record({
            "event": "session_observed",
            "seat": name,
            "fleet": fleet,
            "runtime": "codex",
            "runtime_session_id": f"codex-{name}",
            "runtime_session_confidence": "high",
            "cwd": str(tmp_path),
        })
    registry.upsert_agent({
        "name": "observer",
        "fleet": hidden_fleet,
        "runtime": "codex",
        "registered": True,
        "hidden": True,
        "kind": "ether",
        "terminal_ref": f"{hidden_fleet}:observer",
    })

    assert [row["name"] for row in registry.list_agents(fleet)] == ["builder", "manager", "tester"]
    assert registry.list_agents(hidden_fleet) == []
    assert registry.list_agents(hidden_fleet, include_hidden=True)[0]["name"] == "observer"

    # Receipt Relay artifact and test receipt.
    artifact = artifact_root / "hello.txt"
    receipt = artifact_root / "test-receipt.json"
    artifact.write_text("AURA_E2E_OK\n", encoding="utf-8")
    receipt.write_text(
        json.dumps({
            "mission": "receipt-relay",
            "checks": ["file_exists", "content_exact"],
            "artifact": str(artifact),
            "result": "pass",
        }, indent=2),
        encoding="utf-8",
    )
    assert artifact.read_text(encoding="utf-8").strip() == "AURA_E2E_OK"

    # Fake sidecar proves Clawhip evidence stays as delivery evidence.
    fake_clawhip = _write_executable(
        tmp_path / "clawhip",
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = \"status\" ]; then echo '{\"ok\":true,\"mode\":\"fake\"}'; exit 0; fi\n"
        "if [ \"$1\" = \"send\" ]; then echo '{\"ok\":true,\"message_id\":\"sidecar-e2e\"}'; exit 0; fi\n"
        "if [ \"$1\" = \"config\" ]; then echo '{\"missing\":[],\"forbidden\":[]}'; exit 0; fi\n"
        "if [ \"$1\" = \"emit\" ]; then echo '{\"ok\":true,\"event_id\":\"emit-e2e\"}'; exit 0; fi\n"
        "echo '{\"ok\":true}'\n",
    )
    monkeypatch.setenv("AURA_CLAWHIP_BIN", str(fake_clawhip))
    sidecar = event_sidecar.deliver_human_message(f"{fleet}:tester", "receipt relay starting", channel="discord:aura-ops")
    assert sidecar["ok"] is True
    assert delivery.iter_records()[-1]["delivery_type"] == "sidecar_delivery"

    # Intentional blocked tester -> manager report creates delivery evidence and a deferred outbox item.
    report = (
        "mission=receipt-relay\n"
        "role=tester\n"
        "result=pass\n"
        f"artifact={artifact}\n"
        f"receipt={receipt}\n"
        "next=manager can mark sprint complete"
    )
    blocked = delivery.new_delivery_record(
        delivery_type="semantic_send",
        sender=f"{fleet}:tester",
        target=f"{fleet}:manager",
        state="blocked",
        backend="tmux",
        error="target-busy",
    )
    delivery.append_attempt(blocked, state="blocked", evidence={"blocker": "target-busy"})
    delivery.append_record(blocked)
    deferred_record = deferred.create(
        target=f"{fleet}:manager",
        message=report,
        sender=f"{fleet}:tester",
        dedupe_key="receipt-relay-report",
        blocked_reason="target-busy",
        blocked_message_id=blocked["message_id"],
        retry_every_seconds=1,
        ttl_seconds=60,
    )
    assert deferred_record["status"] == "pending"

    job = {
        "schema": "aura.event.job.v1",
        "job_id": "evt_e2e_receipt_relay",
        "name": "receipt-relay-heartbeat",
        "target": f"{fleet}:manager",
        "sender": "aura-event",
        "consecutive_errors": 1,
        "updated_at": events.now_iso(),
    }
    events.save_state(job)

    objective = objectives.create_objective(
        "receipt-relay",
        seats=[f"{fleet}:manager", f"{fleet}:builder", f"{fleet}:tester"],
    )
    first_eval = ether.evaluate_objective(objective)
    packet = first_eval["state_packet"]
    kinds = {signal["kind"] for signal in packet["signals"]}
    assert {"delivery.blocked", "delivery.deferred", "session.session_observed", "event.errors"} <= kinds
    assert first_eval["recommendation"]["recommendation"]["target"] == f"{fleet}:manager"
    assert len(recommendations.list_recommendations(objective_id="receipt-relay", status="open")) == 1

    second_eval = ether.evaluate_objective(objective)
    assert second_eval["recommendation"]["recommendation_id"] == first_eval["recommendation"]["recommendation_id"]
    assert len(recommendations.list_recommendations(objective_id="receipt-relay", status="open")) == 1

    # Recovery uses a fake Aura binary so deferred retry exercises the real run_once state transition.
    fake_aura = _write_executable(
        tmp_path / "aura",
        "#!/usr/bin/env bash\n"
        "echo '{\"ok\":true,\"message_id\":\"aura-msg-recovered\",\"submitted_verified\":true}'\n",
    )
    monkeypatch.setenv("AURA_BIN", str(fake_aura))
    recovered = deferred.run_once(deferred_record["deferred_id"])
    assert recovered["ok"] is True
    assert recovered["state"] == "delivered"
    assert deferred.load(deferred_record["deferred_id"])["status"] == "delivered"

    restore = sessions.run(type("Args", (), {
            "sessions_action": "restore-plan",
            "fleet": fleet,
        "live": False,
        "min_confidence": None,
        "include_hidden": False,
    })())
    assert restore["ok"] is True
    assert restore["restore_ready"] == 3
    assert all(row["restore_ready"] for row in restore["rows"])

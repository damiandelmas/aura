import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_route_execution_defers_busy_target(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import route
    from lib import registry

    registry.upsert_agent({"name": "manager", "fleet": "fleet", "runtime": "codex"})

    captured = {}

    class FakeSend:
        @staticmethod
        def run(args):
            captured.update(vars(args))
            return {
                "ok": True,
                "blocked": True,
                "deferred": True,
                "reason": "target-busy",
                "deferred_record": {"deferred_id": "aura-defer-route"},
            }

    monkeypatch.setattr(route, "send", FakeSend)

    result = route._execute_action({
        "fleet": "fleet",
        "target_seat": "manager",
        "message": "continue",
        "dedupe_key": "route-key",
    })

    assert result["status"] == "deferred"
    assert captured["defer_if_busy"] is True
    assert captured["defer_ttl"] == "15m"
    assert captured["defer_retry_every"] == "15s"

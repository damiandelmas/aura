import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _report(*, fleet, seat, report_id="rpt-1"):
    return {
        "report_id": report_id,
        "state": "working",
        "fleet": fleet,
        "seat": seat,
        "status": "active",
    }


def test_queued_match_by_live_name_only(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, queued_messages

    registry.upsert_agent({
        "name": "worker",
        "fleet": "fleet",
        "runtime": "codex",
        "seat_instance_id": "si_worker",
        "pane_ref": "tmux:fleet:%1",
    })

    record = {"status": "pending", "after": "next-report", "target": "fleet:worker"}

    # Report from the live seat matches.
    assert queued_messages._matches_report(record, _report(fleet="fleet", seat="worker")) is True
    # Report from a different seat does NOT match (no history reach-back).
    assert queued_messages._matches_report(record, _report(fleet="fleet", seat="other")) is False


def test_queued_match_by_occupant_after_rename(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, queued_messages

    # The seat now lives under a renamed name; the old name has no live row.
    registry.upsert_agent({
        "name": "renamed",
        "fleet": "fleet",
        "runtime": "codex",
        "seat_instance_id": "si_keep",
        "pane_ref": "tmux:fleet:%5",
    })

    record = {
        "status": "pending",
        "after": "next-report",
        "target": "fleet:old-name",
        "occupant_seat_instance_id": "si_keep",
    }

    assert queued_messages._matches_report(record, _report(fleet="fleet", seat="renamed")) is True


def test_queued_no_match_wrong_occupant_same_name(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, queued_messages

    # The name was reused by a new incarnation (new si).
    registry.upsert_agent({
        "name": "worker",
        "fleet": "fleet",
        "runtime": "codex",
        "seat_instance_id": "si_new",
        "pane_ref": "tmux:fleet:%9",
    })

    # Old record's sender occupant id is stale.
    record = {
        "status": "pending",
        "after": "next-report",
        "target": "fleet:worker",
        "occupant_seat_instance_id": "si_old",
    }

    # The live row blocks history reach-back: a report from the new worker still
    # matches by live-name (the record targets that physical name), but a report
    # from any OTHER seat must not match via the stale occupant id.
    assert queued_messages._matches_report(record, _report(fleet="fleet", seat="elsewhere")) is False


def test_resolve_occupant_si_wins_over_default_ref(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    registry.upsert_agent({
        "name": "occupant-seat",
        "fleet": "fleet",
        "runtime": "codex",
        "seat_instance_id": "si_live",
        "pane_ref": "tmux:fleet:%2",
    })
    registry.upsert_agent({
        "name": "other-seat",
        "fleet": "fleet",
        "runtime": "codex",
        "seat_instance_id": "si_other",
        "pane_ref": "tmux:fleet:%3",
    })

    row = registry.resolve_occupant(seat_instance_id="si_live", default_ref="fleet:other-seat")
    assert row is not None
    assert row["name"] == "occupant-seat"


def test_resolve_occupant_fallback_only_when_absent(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry

    registry.upsert_agent({
        "name": "named-seat",
        "fleet": "fleet",
        "runtime": "codex",
        "seat_instance_id": "si_named",
        "pane_ref": "tmux:fleet:%4",
    })

    # Occupant id matches nothing -> fall back to default_ref via resolve_live.
    row = registry.resolve_occupant(seat_instance_id="si_missing", default_ref="fleet:named-seat")
    assert row is not None
    assert row["name"] == "named-seat"

    # No occupant id, no default -> None.
    assert registry.resolve_occupant(seat_instance_id="si_missing") is None


def test_sender_canon_no_name_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import registry, reports

    # A new incarnation now holds the name "worker" (si_new). The env-inferred
    # sender carries a stale si (si_gone) that resolves to nothing.
    registry.upsert_agent({
        "name": "worker",
        "fleet": "fleet",
        "runtime": "codex",
        "seat_instance_id": "si_new",
        "pane_ref": "tmux:fleet:%10",
    })

    monkeypatch.setenv("AURA_SEAT_INSTANCE_ID", "si_gone")
    monkeypatch.delenv("AURA_LAUNCH_ID", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)

    sender = reports._resolve_sender_for_report("worker", "fleet")
    # Occupant ids present but resolve to nothing -> return env identity unchanged,
    # never redirect to the reused name's current row.
    assert sender == {"fleet": "fleet", "seat": "worker"}

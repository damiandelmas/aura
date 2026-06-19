import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _args(action, **overrides):
    values = dict(
        notes_action=action,
        target=None, session=None, grep=None, with_note=False, limit=None,
        index=None, anchor=None,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def _ledger(tmp_path, monkeypatch, records):
    path = tmp_path / "annotations.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    monkeypatch.setenv("AURA_NOTES_LEDGER", str(path))
    return path


_REAL = {"ts": "2026-06-18T10:00:00-0700", "target": "flex-engine:bugs", "note": "algebra module looks good",
         "session_id": "sid-aaa", "message_position": 518, "content_sha256": "abc123",
         "message_type": "assistant"}
_EMPTY = {"ts": "2026-06-18T09:00:00-0700", "target": "playground:wild", "note": "\x1b",
          "session_id": "sid-bbb", "message_position": 5, "content_sha256": "def456"}
_LEGACY = {"ts": "2026-06-12T08:00:00-0700", "target": "old:seat", "note": "legacy id form",
           "session_id": "sid-ccc", "message_id": "sid-ccc:transcript:7", "content_sha256": "ghi789"}


def test_notes_list_all_and_with_note(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch, [_REAL, _EMPTY, _LEGACY])
    from commands import notes

    full = notes.run(_args("list"))
    assert full["ok"] and full["count"] == 3

    # the ESC-only note is not meaningful; --with-note hides it
    only_real = notes.run(_args("list", with_note=True))
    assert only_real["count"] == 2
    assert all(n["has_note"] for n in only_real["notes"])
    assert {n["target"] for n in only_real["notes"]} == {"flex-engine:bugs", "old:seat"}


def test_notes_list_filters_and_order(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch, [_REAL, _EMPTY, _LEGACY])
    from commands import notes

    # newest first
    rows = notes.run(_args("list"))["notes"]
    assert rows[0]["ts"] >= rows[-1]["ts"]

    assert notes.run(_args("list", target="flex-engine:bugs"))["count"] == 1
    assert notes.run(_args("list", grep="algebra"))["count"] == 1
    assert notes.run(_args("list", session="sid-bbb"))["count"] == 1
    assert notes.run(_args("list", limit=1))["count"] == 1


def test_notes_legacy_id_normalizes_to_anchor(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch, [_LEGACY])
    from commands import notes

    row = notes.run(_args("list"))["notes"][0]
    # position recovered from the legacy "<sid>:transcript:N" message_id
    assert row["position"] == 7
    assert row["anchor"] == "old:seat@sid-ccc#7"
    assert row["flex_chunk_id"] == "sid-ccc_7"


def test_notes_show_index_returns_record(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch, [_REAL])
    from commands import notes

    out = notes.run(_args("show", index=1))
    assert out["ok"]
    assert out["note"]["note"] == "algebra module looks good"
    assert out["note"]["anchor"] == "flex-engine:bugs@sid-aaa#518"


def test_notes_show_requires_index_or_anchor(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch, [_REAL])
    from commands import notes

    out = notes.run(_args("show"))
    assert out["ok"] is False
    assert "index" in out["error"] or "anchor" in out["error"]

    missing = notes.run(_args("show", index=99))
    assert missing["ok"] is False

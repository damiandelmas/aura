"""H0 — ambient packet builder (ported from the recovered stash, de-fused from bind).

Unit-level: monkeypatch seat_status / reports / agent_map so no live registry is
needed. Asserts self-resolution discipline (pane→env→session, never guess) and the
roster packet shape.
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _row(target, *, fleet="F", liveness="alive", managed="spawned_bound",
         pane=None, hidden=False, **extra):
    seat = target.split(":", 1)[1]
    row = {
        "target": target, "fleet": fleet, "seat": seat, "name": seat,
        "liveness": liveness, "managed_state": managed, "hidden": hidden,
        "runtime_session_binding": "bound", "risk_flags": [],
    }
    if pane:
        row["pane_ref"] = pane
    row.update(extra)
    return row


def _patch(monkeypatch, *, rows, self_status=None, context=None):
    from lib import ambient

    monkeypatch.setattr(ambient.reports, "infer_context",
                        lambda: (context or {}))
    monkeypatch.setattr(ambient.seat_status, "list_seat_statuses",
                        lambda **kw: list(rows))
    if self_status is not None:
        monkeypatch.setattr(ambient.seat_status, "build_seat_status",
                            lambda target, **kw: {"ok": True, **self_status})
    monkeypatch.setattr(ambient.agent_map_lib, "build_agent_map",
                        lambda *a, **k: {"ok": True, "position_notes": {}, "unit": None})
    return ambient


def test_build_ambient_explicit_target_roster(monkeypatch):
    me = _row("F:a")
    colleague = _row("F:b")
    stopped = _row("F:c", managed="stopped")
    hidden = _row("F:d", hidden=True)
    ambient = _patch(monkeypatch, rows=[me, colleague, stopped, hidden], self_status=me)

    packet = ambient.build_ambient("F:a")
    assert packet["ok"] and packet["schema"] == "aura.ambient.v1"
    assert packet["target"] == "F:a"
    # roster excludes self, stopped, hidden
    fleet_targets = {r["target"] for r in packet["fleet"]}
    assert fleet_targets == {"F:b"}
    assert "[AURA AMBIENT]" in packet["text"] and "You are a." in packet["text"]


def test_self_resolution_via_pane(monkeypatch):
    me = _row("F:a", pane="tmux:F:%5")
    other = _row("F:b", pane="tmux:F:%6")
    ambient = _patch(monkeypatch, rows=[me, other], self_status=me,
                     context={"pane": "%5"})
    packet = ambient.build_ambient("self")
    assert packet["ok"] and packet["target"] == "F:a"


def test_self_unresolved_returns_structured_error(monkeypatch):
    ambient = _patch(monkeypatch, rows=[], context={})
    packet = ambient.build_ambient("self")
    assert packet["ok"] is False
    assert packet["error"] in {"self-target-not-resolved", "self-target-not-live"}


def test_self_ambiguous_pane_refuses(monkeypatch):
    a = _row("F:a", pane="tmux:F:%5")
    b = _row("F:b", pane="tmux:F:%5")  # same pane on two live rows
    ambient = _patch(monkeypatch, rows=[a, b], context={"pane": "%5"})
    packet = ambient.build_ambient("self")
    assert packet["ok"] is False
    assert packet["error"] == "tmux-pane-mapped-to-multiple-live-seats"


def test_warnings_env_mismatch(monkeypatch):
    me = _row("F:a")
    ambient = _patch(monkeypatch, rows=[me], self_status=me)
    monkeypatch.setenv("AURA_FLEET", "OTHER")
    monkeypatch.setenv("AURA_SEAT", "a")
    packet = ambient.build_ambient("F:a")
    assert "env-fleet-mismatch" in packet["warnings"]


def test_module_is_runtime_agnostic():
    text = (ROOT / "cli" / "lib" / "ambient.py").read_text(encoding="utf-8").lower()
    for runtime_word in ("codex", "claude", "gajae", "hermes", "bind_hook"):
        assert runtime_word not in text, f"ambient.py must stay runtime-agnostic: {runtime_word}"

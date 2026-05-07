from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_list_keeps_same_seat_name_in_different_fleets(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_FLEET", "fleet-a")

    from commands import list as list_cmd
    from lib import mesh, registry, terminal

    registry.upsert_agent({
        "name": "lead",
        "fleet": "fleet-a",
        "runtime": "codex",
        "registered": True,
        "terminal_ref": "fleet-a:lead",
    })
    registry.upsert_agent({
        "name": "lead",
        "fleet": "fleet-b",
        "runtime": "codex",
        "registered": True,
        "terminal_ref": "fleet-b:lead",
    })

    monkeypatch.setattr(mesh, "discover", lambda: {"ok": True, "agents": []})
    monkeypatch.setattr(terminal, "configure_session", lambda fleet: fleet)
    monkeypatch.setattr(terminal, "list_windows", lambda: [])
    monkeypatch.setattr(terminal, "target_exists", lambda target: False)

    rows = list_cmd.run(argparse.Namespace(fleet=None, status=None, mode=None, include_hidden=True))

    assert {f"{row['fleet']}:{row['name']}" for row in rows} == {"fleet-a:lead", "fleet-b:lead"}

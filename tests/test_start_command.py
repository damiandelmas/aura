from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli" / "aura"
sys.path.insert(0, str(ROOT / "cli"))


def test_start_delegates_to_fresh_codex_spawn(monkeypatch, tmp_path):
    from commands import start

    captured = {}

    def fake_spawn_run(args):
        captured.update(vars(args))
        return {"ok": True, "name": args.name, "fleet": args.fleet}

    monkeypatch.setattr(start.spawn, "run", fake_spawn_run)

    result = start.run(
        argparse.Namespace(
            fleet="flex-desks",
            seat="research",
            cwd=str(tmp_path),
            model=None,
        )
    )

    assert result == {"ok": True, "name": "research", "fleet": "flex-desks"}
    assert captured["name"] == "research"
    assert captured["fleet"] == "flex-desks"
    assert captured["cwd"] == str(tmp_path)
    assert captured["runtime"] == "codex"
    assert captured["as_pane"] is True
    assert captured["resume_session"] is None
    assert captured["identity_provider"] is None
    assert captured["identity_id"] is None
    assert captured["identity_label"] is None


def test_start_defaults_to_current_directory(monkeypatch, tmp_path):
    from commands import start

    captured = {}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(start.spawn, "run", lambda args: captured.update(vars(args)) or {"ok": True})

    result = start.run(argparse.Namespace(fleet="fleet", seat="seat", cwd=None, model="gpt-test"))

    assert result == {"ok": True}
    assert captured["cwd"] == str(tmp_path)
    assert captured["model"] == "gpt-test"


def test_start_help_is_available():
    result = subprocess.run(
        [sys.executable, str(CLI), "start", "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Start a fresh Codex seat in a fleet" in result.stdout
    assert "fleet" in result.stdout
    assert "seat" in result.stdout

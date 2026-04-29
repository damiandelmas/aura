"""Runtime session identity contract tests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_runtime_session_discovers_codex_thread_from_descendant(monkeypatch):
    from lib import runtime_session

    monkeypatch.setattr(runtime_session, "_descendant_pids", lambda pid: [pid, 1002])
    monkeypatch.setattr(
        runtime_session,
        "_read_process_environ",
        lambda pid: {"CODEX_THREAD_ID": "codex-thread-123"} if pid == 1002 else {},
    )

    result = runtime_session.discover_from_pane_pid("codex", 1001)

    assert result == {
        "runtime_session_id": "codex-thread-123",
        "runtime_session_env": "CODEX_THREAD_ID",
        "runtime_session_pid": 1002,
    }
    assert runtime_session.merge({"name": "engineer"}, result)["session_id"] == "codex-thread-123"


def test_spawn_exports_aura_runtime_env_and_records_pane_ref(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "unit"
    unit.mkdir()
    (unit / "AGENTS.md").write_text("agent context", encoding="utf-8")

    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": "unitfleet:codex-seat", "pane_id": "%42"}

    args = argparse.Namespace(
        name="codex-seat",
        runtime="codex",
        launch_command="printf ready",
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context="AGENTS.md",
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["pane_ref"] == "tmux:unitfleet:%42"
    assert created == [
        (
            "codex-seat",
            str(unit),
            True,
            "printf ready",
            {
                "AURA_AGENT_NAME": "codex-seat",
                "AURA_SEAT": "codex-seat",
                "AURA_FLEET": "unitfleet",
                "AURA_RUNTIME": "codex",
                "TERM": "xterm-256color",
                "COLORTERM": "truecolor",
                "FORCE_COLOR": "1",
                "CLICOLOR_FORCE": "1",
            },
            ["NO_COLOR"],
        )
    ]


def test_list_merges_runtime_session_id_from_pane(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import list as list_cmd
    from lib import mesh, registry, terminal

    registry.upsert_agent(
        {
            "name": "engineer",
            "fleet": "unitfleet",
            "runtime": "codex",
            "terminal_ref": "unitfleet:engineer",
            "pane_ref": "tmux:unitfleet:%42",
            "registered": True,
            "status": "running",
        }
    )

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def configure_session(_fleet):
            return "unitfleet"

        @staticmethod
        def target_exists(target):
            return target == "tmux:unitfleet:%42"

        @staticmethod
        def capture_output(_target, _lines=20):
            return ["ready"]

        @staticmethod
        def pane_pid(_target):
            return 1001

    monkeypatch.setattr(terminal, "SESSION_NAME", "unitfleet")
    monkeypatch.setattr(terminal, "configure_session", FakeTerminal.configure_session)
    monkeypatch.setattr(terminal, "target_exists", FakeTerminal.target_exists)
    monkeypatch.setattr(terminal, "capture_output", FakeTerminal.capture_output)
    monkeypatch.setattr(terminal, "pane_pid", FakeTerminal.pane_pid)
    monkeypatch.setattr(mesh, "discover", lambda: {"ok": True, "agents": []})

    from lib import runtime_session

    monkeypatch.setattr(
        runtime_session,
        "discover_from_pane_pid",
        lambda runtime, pane_pid: {
            "runtime_session_id": "codex-thread-123",
            "runtime_session_env": "CODEX_THREAD_ID",
            "runtime_session_pid": pane_pid,
        },
    )

    rows = list_cmd.run(argparse.Namespace(fleet="unitfleet", status=None, mode=None))

    assert rows[0]["session_id"] == "codex-thread-123"
    assert rows[0]["runtime_session_env"] == "CODEX_THREAD_ID"

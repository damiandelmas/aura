"""Runtime session identity contract tests."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_runtime_session_discovers_codex_thread_from_resume_argv(monkeypatch):
    from lib import runtime_session

    monkeypatch.setattr(runtime_session, "_descendant_pids", lambda pid: [pid, 1002])
    monkeypatch.setattr(
        runtime_session,
        "_read_process_cmdline",
        lambda pid: ["codex", "resume", "019dd2b7-8919-75d2-b472-7c778a93da92"] if pid == 1002 else [],
    )
    monkeypatch.setattr(
        runtime_session,
        "_read_process_environ",
        lambda pid: {"CODEX_THREAD_ID": "inherited-parent-thread"} if pid == 1002 else {},
    )

    result = runtime_session.discover_from_pane_pid("codex", 1001)

    assert result == {
        "runtime_session_id": "019dd2b7-8919-75d2-b472-7c778a93da92",
        "runtime_session_source": "argv:codex-resume",
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": "argv-resume",
        "runtime_session_bind_source": "argv:codex-resume",
        "runtime_session_confidence": "exact",
        "runtime_session_evidence": {
            "reason": "codex-resume-argv",
            "argv": ["codex", "resume", "019dd2b7-8919-75d2-b472-7c778a93da92"],
        },
        "runtime_session_pid": 1002,
    }
    assert runtime_session.merge({"name": "engineer"}, result)["session_id"] == "019dd2b7-8919-75d2-b472-7c778a93da92"


def test_runtime_session_discovers_codex_fork_source_from_argv(monkeypatch):
    from lib import runtime_session

    source_id = "019dd2b7-8919-75d2-b472-7c778a93da92"
    argv = ["codex", "--cd", "/unit", "fork", source_id, "continue here"]
    monkeypatch.setattr(runtime_session, "_descendant_pids", lambda pid: [pid, 1002])
    monkeypatch.setattr(
        runtime_session,
        "_read_process_cmdline",
        lambda pid: argv if pid == 1002 else [],
    )
    monkeypatch.setattr(runtime_session, "_read_process_environ", lambda pid: {})

    result = runtime_session.discover_from_pane_pid("codex", 1001)

    assert result["source_session_id"] == source_id
    assert "runtime_session_id" not in result
    assert result["runtime_session_source"] == "argv:codex-fork"
    assert result["runtime_session_binding"] == "pending-fork-child"
    assert result["runtime_session_confidence"] == "source-exact-child-pending"
    assert result["runtime_session_evidence"]["reason"] == "codex-fork-argv"


def test_runtime_session_merge_preserves_fork_source_when_child_binds():
    from lib import runtime_session

    record = {
        "name": "forked",
        "source_session_id": "019dd2b7-8919-75d2-b472-7c778a93da92",
        "runtime_session_mode": "native-fork",
        "runtime_session_source": "spawn:fork-session",
        "runtime_session_binding": "pending-fork-child",
    }
    child = {
        "runtime_session_id": "019e2d0f-1e2d-7bf2-9863-6253cb5ff857",
        "runtime_session_source": "codex-hook:session-start",
        "runtime_session_binding": "bound",
        "runtime_session_confidence": "exact",
    }

    merged = runtime_session.merge(record, child)

    assert merged["source_session_id"] == record["source_session_id"]
    assert merged["runtime_session_mode"] == "native-fork"
    assert merged["runtime_session_id"] == child["runtime_session_id"]
    assert merged["session_id"] == child["runtime_session_id"]
    assert merged["runtime_session_binding"] == "bound"


def test_runtime_session_ignores_inherited_codex_thread_env(monkeypatch):
    from lib import runtime_session

    monkeypatch.setattr(runtime_session, "_descendant_pids", lambda pid: [pid, 1002])
    monkeypatch.setattr(runtime_session, "_read_process_cmdline", lambda pid: ["codex"])
    monkeypatch.setattr(
        runtime_session,
        "_read_process_environ",
        lambda pid: {"CODEX_THREAD_ID": "inherited-parent-thread"} if pid == 1002 else {},
    )

    assert runtime_session.discover_from_pane_pid("codex", 1001) == {}


def test_runtime_session_recovers_fresh_codex_thread_from_state_db(monkeypatch, tmp_path):
    from lib import runtime_session

    db = tmp_path / "state_5.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE threads (
            id TEXT PRIMARY KEY,
            cwd TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL,
            updated_at_ms INTEGER NOT NULL,
            title TEXT NOT NULL,
            first_user_message TEXT NOT NULL,
            agent_nickname TEXT,
            agent_role TEXT,
            agent_path TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "019dd797-1169-7931-b2f7-17824b3b7134",
            "/repo/specialist-cell",
            1_777_438_495_400,
            1_777_438_540_766,
            "[AURA MESSAGE id=aura-msg from=cli]",
            "specialist-cell role memory validation",
            None,
            None,
            None,
        ),
    )
    conn.execute(
        "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "019dd797-dead-7931-b2f7-17824b3b7134",
            "/repo/specialist-cell",
            1_777_438_495_500,
            1_777_438_540_999,
            "other thread",
            "unrelated",
            None,
            None,
            None,
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("CODEX_STATE_DB", str(db))
    monkeypatch.setattr(runtime_session, "_descendant_pids", lambda pid: [pid, 1002])
    monkeypatch.setattr(runtime_session, "_read_process_cmdline", lambda pid: ["codex"])
    monkeypatch.setattr(runtime_session, "_process_cwd", lambda pid: "/repo/specialist-cell")
    monkeypatch.setattr(runtime_session, "_process_start_epoch", lambda pid: 1_777_438_495.450)
    monkeypatch.setattr(runtime_session, "_read_process_environ", lambda pid: {})

    result = runtime_session.discover_from_pane_pid("codex", 1001, seat_name="specialist-cell")

    assert "runtime_session_id" not in result
    assert result["runtime_session_source"] == "codex-state:cwd-start"
    assert result["runtime_session_binding"] == "unbound"
    assert result["runtime_session_diagnostics"]["reason"] == "codex-state-possible-match"
    assert result["runtime_session_possible_matches"][0]["runtime_session_id"] == "019dd797-1169-7931-b2f7-17824b3b7134"
    assert result["runtime_session_possible_matches"][0]["reason"] == "cwd-start-seat-name"


def test_runtime_session_prefers_currently_updated_state_candidate(monkeypatch, tmp_path):
    from lib import runtime_session

    db = tmp_path / "state_5.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE threads (
            id TEXT PRIMARY KEY,
            cwd TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL,
            updated_at_ms INTEGER NOT NULL,
            title TEXT NOT NULL,
            first_user_message TEXT NOT NULL,
            agent_nickname TEXT,
            agent_role TEXT,
            agent_path TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "019dd724-49b1-7503-99ac-7c534c6d5ec5",
                "/repo/flexsearch/main",
                1_777_430_973_050,
                1_777_438_147_251,
                "You are the manager seat for the Flex release/parity unit of work.",
                "You are the manager seat for the Flex release/parity unit of work.",
                None,
                None,
                None,
            ),
            (
                "019dd722-42f3-7592-919b-0b64eadea2bb",
                "/repo/flexsearch/main",
                1_777_430_840_277,
                1_777_430_927_933,
                "You are the long-horizon manager seat for the Flex release/parity plan sequence.",
                "You are the long-horizon manager seat for the Flex release/parity plan sequence.",
                None,
                None,
                None,
            ),
        ],
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("CODEX_STATE_DB", str(db))
    monkeypatch.setattr(runtime_session, "_descendant_pids", lambda pid: [pid])
    monkeypatch.setattr(runtime_session, "_read_process_cmdline", lambda pid: ["codex"])
    monkeypatch.setattr(runtime_session, "_process_cwd", lambda pid: "/repo/flexsearch/main")
    monkeypatch.setattr(runtime_session, "_process_start_epoch", lambda pid: 1_777_431_280.420)
    monkeypatch.setattr(runtime_session, "_read_process_environ", lambda pid: {})

    result = runtime_session.discover_from_pane_pid("codex", 1001, seat_name="flex-release-parity-manager")

    assert "runtime_session_id" not in result
    assert result["runtime_session_binding"] == "unbound"
    assert result["runtime_session_possible_matches"][0]["runtime_session_id"] == "019dd724-49b1-7503-99ac-7c534c6d5ec5"
    assert result["runtime_session_possible_matches"][0]["reason"] == "cwd-start-seat-name-currently-updated"


def test_runtime_session_does_not_match_single_word_seat_from_target_mentions(monkeypatch, tmp_path):
    from lib import runtime_session

    db = tmp_path / "state_5.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE threads (
            id TEXT PRIMARY KEY,
            cwd TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL,
            updated_at_ms INTEGER NOT NULL,
            title TEXT NOT NULL,
            first_user_message TEXT NOT NULL,
            agent_nickname TEXT,
            agent_role TEXT,
            agent_path TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "manager-thread",
                "/tmp/aura-codex-trio",
                1_777_517_843_387,
                1_777_517_904_628,
                "You are the manager for the Aura Codex trio Receipt Relay E2E.",
                "You are the manager for the Aura Codex trio Receipt Relay E2E.",
                None,
                None,
                None,
            ),
            (
                "tester-thread",
                "/tmp/aura-codex-trio",
                1_777_517_842_862,
                1_777_517_950_876,
                "You are the tester. Send aura-codex-trio:manager a report.",
                "You are the tester. Send aura-codex-trio:manager a report.",
                None,
                None,
                None,
            ),
        ],
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("CODEX_STATE_DB", str(db))
    monkeypatch.setattr(runtime_session, "_descendant_pids", lambda pid: [pid])
    monkeypatch.setattr(runtime_session, "_read_process_cmdline", lambda pid: ["codex"])
    monkeypatch.setattr(runtime_session, "_process_cwd", lambda pid: "/tmp/aura-codex-trio")
    monkeypatch.setattr(runtime_session, "_process_start_epoch", lambda pid: 1_777_517_819.0)
    monkeypatch.setattr(runtime_session, "_read_process_environ", lambda pid: {})

    result = runtime_session.discover_from_pane_pid("codex", 1001, seat_name="manager")

    assert "runtime_session_id" not in result
    assert result["runtime_session_binding"] == "unbound"
    assert result["runtime_session_possible_matches"][0]["runtime_session_id"] == "manager-thread"
    assert result["runtime_session_possible_matches"][0]["reason"] == "cwd-start-seat-name"


def test_runtime_session_launch_id_is_exact_join_key(monkeypatch, tmp_path):
    from lib import runtime_session

    db = tmp_path / "state_5.sqlite"
    conn = sqlite3.connect(db)
    conn.execute(
        """
        CREATE TABLE threads (
            id TEXT PRIMARY KEY,
            cwd TEXT NOT NULL,
            created_at_ms INTEGER NOT NULL,
            updated_at_ms INTEGER NOT NULL,
            title TEXT NOT NULL,
            first_user_message TEXT NOT NULL,
            agent_nickname TEXT,
            agent_role TEXT,
            agent_path TEXT
        )
        """
    )
    conn.executemany(
        "INSERT INTO threads VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "manager-thread",
                "/tmp/aura-codex-trio",
                1_777_517_843_387,
                1_777_517_904_628,
                "[AURA SEAT CONTEXT] fleet=lab seat=manager launch_id=aura-launch-manager [/AURA SEAT CONTEXT]",
                "[AURA SEAT CONTEXT]\nfleet=lab\nseat=manager\nlaunch_id=aura-launch-manager\n[/AURA SEAT CONTEXT]",
                None,
                None,
                None,
            ),
            (
                "tester-thread",
                "/tmp/aura-codex-trio",
                1_777_517_842_862,
                1_777_517_950_876,
                "You are the tester. Send aura-codex-trio:manager a report.",
                "You are the tester. Send aura-codex-trio:manager a report.",
                None,
                None,
                None,
            ),
        ],
    )
    conn.commit()
    conn.close()

    monkeypatch.setenv("CODEX_STATE_DB", str(db))
    monkeypatch.setattr(runtime_session, "_descendant_pids", lambda pid: [pid])
    monkeypatch.setattr(runtime_session, "_read_process_cmdline", lambda pid: ["codex"])
    monkeypatch.setattr(runtime_session, "_process_cwd", lambda pid: "/tmp/aura-codex-trio")
    monkeypatch.setattr(runtime_session, "_process_start_epoch", lambda pid: 1_777_517_819.0)
    monkeypatch.setattr(runtime_session, "_read_process_environ", lambda pid: {})

    result = runtime_session.discover_from_pane_pid(
        "codex",
        1001,
        seat_name="manager",
        launch_id="aura-launch-manager",
    )

    assert "runtime_session_id" not in result
    assert result["runtime_session_binding"] == "unbound"
    assert result["runtime_session_possible_matches"][0]["runtime_session_id"] == "manager-thread"
    assert result["runtime_session_possible_matches"][0]["reason"] == "aura-launch-id"


def test_spawn_exports_aura_runtime_env_and_records_pane_ref(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn
    monkeypatch.setattr(spawn.uuid, "uuid4", lambda: type("U", (), {"hex": "1234567890abcdef1234"})())

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
                "AURA_LAUNCH_ID": "aura-launch-1234567890abcdef",
                "TERM": "xterm-256color",
                "COLORTERM": "truecolor",
                "FORCE_COLOR": "1",
                "CLICOLOR_FORCE": "1",
            },
            [
                "NO_COLOR",
                "AURA_RUNTIME_SESSION_ID",
                "AURA_SESSION_ID",
                "CODEX_THREAD_ID",
                "CODEX_CI",
                "CLAUDE_SESSION_ID",
            ],
        )
    ]


def test_spawn_codex_resume_session_builds_autonomous_resume_command(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "unit"
    unit.mkdir()

    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, command))
            return {"ok": True, "target": "unitfleet:outreach", "pane_id": "%43"}

    session_id = "019dd1ba-70ff-72c3-8ccd-739cccf4e3fc"
    args = argparse.Namespace(
        name="outreach",
        runtime="codex",
        resume_session=session_id,
        launch_command=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert created[0][1] == f"codex --cd {unit} --dangerously-bypass-approvals-and-sandbox resume {session_id}"
    assert result["source_session_id"] == session_id
    assert result["session_id"] == session_id
    assert result["runtime_session_id"] == session_id
    assert result["runtime_session_source"] == "spawn:resume-session"
    assert result["runtime_session_confidence"] == "exact"
    assert result["runtime_session_mode"] == "native-resume"
    assert result["isolation"] == "shared-native-thread"
    assert result["backend_ref"] == "unitfleet:outreach"
    assert result["session_observation"]["status"] == "already-bound"


def test_spawn_codex_fork_session_records_parent_pending_child(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "unit"
    unit.mkdir()
    created = []
    sent = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, command))
            return {"ok": True, "target": "unitfleet:forked", "pane_id": "%43"}

        @staticmethod
        def send_text(name, text, submit=False):
            sent.append((name, text, submit))
            return {"ok": True}

    source_id = "019dd1ba-70ff-72c3-8ccd-739cccf4e3fc"
    args = argparse.Namespace(
        name="forked",
        runtime="codex",
        resume_session=None,
        fork_session=source_id,
        launch_command=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt="inherit and report",
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert created[0][1] == (
        f"codex --cd {unit} --dangerously-bypass-approvals-and-sandbox "
        f"fork {source_id} 'inherit and report'"
    )
    assert sent == []
    assert result["source_session_id"] == source_id
    assert result["runtime_session_mode"] == "native-fork"
    assert result["runtime_session_binding"] == "pending-fork-child"
    assert result["runtime_session_confidence"] == "source-exact-child-pending"
    assert "runtime_session_id" not in result
    assert result["prompt_delivery"] == {
        "submitted": True,
        "transport": "runtime-native-argv",
        "mode": "fork-argument",
    }
    assert result["session_observation"]["status"] == "pending"


def test_spawn_codex_fork_session_conflicts_and_unsupported_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "unit"
    unit.mkdir()

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

    source_id = "019dd1ba-70ff-72c3-8ccd-739cccf4e3fc"
    base = dict(
        name="forked",
        runtime="codex",
        resume_session=None,
        fork_session=source_id,
        launch_command=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    conflict = spawn._spawn_terminal_runtime(
        argparse.Namespace(**{**base, "resume_session": source_id}),
        FakeTerminal,
        lambda x: x,
    )
    assert conflict["ok"] is False
    assert conflict["error"] == "use either --resume-session or --fork-session, not both"

    command_conflict = spawn._spawn_terminal_runtime(
        argparse.Namespace(**{**base, "launch_command": "codex fork raw"}),
        FakeTerminal,
        lambda x: x,
    )
    assert command_conflict["ok"] is False
    assert command_conflict["error"] == "use either --fork-session or --command, not both"

    unsupported = spawn._spawn_terminal_runtime(
        argparse.Namespace(**{**base, "runtime": "shell"}),
        FakeTerminal,
        lambda x: x,
    )
    assert unsupported["ok"] is False
    assert unsupported["error"] == "runtime does not support native fork: shell"


def test_spawn_codex_resume_resolves_cwd_choice_to_requested_cwd(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    session_dir = tmp_path / "session"
    current_dir = tmp_path / "desks"
    session_dir.mkdir()
    current_dir.mkdir()
    keys = []
    captures = [
        [
            "Choose working directory to resume this session",
            "",
            f"  1. Use session directory ({session_dir})",
            f"  2. Use current directory ({current_dir})",
            "",
            "  Press enter to continue",
        ],
        ["› ready"],
    ]

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            return {"ok": True, "target": "unitfleet:substrate", "pane_id": "%43"}

        @staticmethod
        def capture_output(target, lines=80):
            return captures.pop(0)

        @staticmethod
        def send_keys(target, text, enter=False):
            keys.append((target, text, enter))
            return {"ok": True, "target": target}

    session_id = "019ddfa4-1b45-7eb0-9620-965f2ebb2482"
    args = argparse.Namespace(
        name="substrate",
        runtime="codex",
        resume_session=session_id,
        launch_command=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(current_dir),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["cwd_choice"]["detected"] is True
    assert result["cwd_choice"]["ok"] is True
    assert result["cwd_choice"]["selected_number"] == "2"
    assert result["cwd_choice"]["selected_path"] == str(current_dir)
    assert result["cwd_choice"]["selection_policy"] == "codex-current-directory"
    assert result["cwd_choice"]["verified"] is True
    assert keys == [("tmux:unitfleet:%43", "2", True)]


def test_codex_cwd_choice_prefers_current_directory_over_session_directory(tmp_path):
    from commands import spawn

    session_dir = tmp_path / "legacy-role-home"
    current_dir = tmp_path / "unit-root"
    session_dir.mkdir()
    current_dir.mkdir()

    result = spawn._codex_cwd_choice_from_capture(
        [
            "Choose working directory to resume this session",
            f"  1. Use session directory ({session_dir})",
            f"  2. Use current directory ({current_dir})",
            "  Press enter to continue",
        ],
        desired_cwd=None,
    )

    assert result["detected"] is True
    assert result["selection_policy"] == "codex-current-directory"
    assert result["selected"]["number"] == "2"
    assert result["selected"]["label"] == "Use current directory"
    assert result["selected"]["path"] == str(current_dir)


def test_codex_cwd_choice_still_prefers_current_directory_when_desired_cwd_is_legacy(tmp_path):
    from commands import spawn

    session_dir = tmp_path / "legacy-role-home"
    current_dir = tmp_path / "unit-root"
    session_dir.mkdir()
    current_dir.mkdir()

    result = spawn._codex_cwd_choice_from_capture(
        [
            "Choose working directory to resume this session",
            f"  1. Use session directory ({session_dir})",
            f"  2. Use current directory ({current_dir})",
            "  Press enter to continue",
        ],
        desired_cwd=str(session_dir),
    )

    assert result["selected"]["number"] == "2"
    assert result["selected"]["path"] == str(current_dir)


def test_spawn_codex_resume_polls_cwd_choice_before_resending(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    session_dir = tmp_path / "session"
    current_dir = tmp_path / "desks"
    session_dir.mkdir()
    current_dir.mkdir()
    prompt = [
        "Choose working directory to resume this session",
        "",
        f"  1. Use session directory ({session_dir})",
        f"  2. Use current directory ({current_dir})",
        "",
        "  Press enter to continue",
    ]
    keys = []
    captures = [prompt, prompt, ["› ready"]]

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            return {"ok": True, "target": "unitfleet:substrate", "pane_id": "%43"}

        @staticmethod
        def capture_output(target, lines=80):
            return captures.pop(0)

        @staticmethod
        def send_keys(target, text, enter=False):
            keys.append((target, text, enter))
            return {"ok": True, "target": target}

    args = argparse.Namespace(
        name="substrate",
        runtime="codex",
        resume_session="019ddfa4-1b45-7eb0-9620-965f2ebb2482",
        launch_command=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(current_dir),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["cwd_choice"]["ok"] is True
    assert result["cwd_choice"]["verified"] is True
    assert result["cwd_choice"]["send_attempts"] == [
        {
            "ok": True,
            "target": "tmux:unitfleet:%43",
            "verified": True,
            "verify_checks": [
                {"verified": False, "prompt_present": True},
                {"verified": True, "prompt_present": False},
            ],
        },
    ]
    assert keys == [("tmux:unitfleet:%43", "2", True)]


def test_spawn_codex_prompt_embeds_aura_launch_context(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_CODEX_STARTUP_READY_TIMEOUT", "0")

    from commands import spawn
    monkeypatch.setattr(spawn.uuid, "uuid4", lambda: type("U", (), {"hex": "abcdef1234567890ffff"})())

    unit = tmp_path / "unit"
    unit.mkdir()
    sent = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            return {"ok": True, "target": "unitfleet:builder", "pane_id": "%44"}

        @staticmethod
        def send_text(name, text, submit=False):
            sent.append((name, text, submit))
            return {"ok": True}

    args = argparse.Namespace(
        name="builder",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt="build the artifact",
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["aura_launch_id"] == "aura-launch-abcdef1234567890"
    assert sent[0][0] == "builder"
    assert sent[0][2] is True
    assert sent[0][1] == "build the artifact"
    assert "startup_handshake" not in result
    assert "agent_map_included" not in result["prompt_delivery"]


def test_spawn_codex_prompt_retries_submit_before_session_observation(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SPAWN_SESSION_OBSERVE_TIMEOUT", "0")
    monkeypatch.setenv("AURA_CODEX_STARTUP_READY_TIMEOUT", "0")

    from commands import spawn
    from lib import runtime_session

    monkeypatch.setattr(spawn.uuid, "uuid4", lambda: type("U", (), {"hex": "abcdef1234567890aaaa"})())

    unit = tmp_path / "unit"
    unit.mkdir()
    sent = []
    keys = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            return {"ok": True, "target": "unitfleet:builder", "pane_id": "%44"}

        @staticmethod
        def send_text(name, text, submit=False):
            sent.append((name, text, submit))
            return {"ok": True}

        @staticmethod
        def send_keys(name, text, enter=False):
            keys.append((name, text, enter))
            return {"ok": True, "target": name}

        @staticmethod
        def pane_pid(target):
            return 1001

    monkeypatch.setattr(
        runtime_session,
        "discover_for_target",
        lambda *args, **kwargs: {
            "runtime_session_source": "codex-state:cwd-start",
            "runtime_session_binding": "unbound",
            "runtime_session_diagnostics": {"reason": "codex-state-possible-match"},
            "runtime_session_possible_matches": [{
                "runtime_session_id": "codex-thread-after-submit",
                "reason": "aura-launch-id",
            }],
            "runtime_session_cwd": str(unit),
        },
    )

    args = argparse.Namespace(
        name="builder",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt="build the artifact",
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["prompt_delivery"]["submitted"] is True
    assert result["prompt_delivery"]["submit_retry"]["ok"] is True
    assert result["prompt_delivery"]["submit_retry"]["session_seen"] is True
    assert result["prompt_delivery"]["submit_retry"]["attempts"] == 1
    assert keys == [
        ("tmux:unitfleet:%44", "Enter", False),
    ]
    assert "runtime_session_id" not in result
    assert sent[0][0] == "builder"
    assert sent[0][1] == "build the artifact"


def test_spawn_codex_startup_handshake_waits_for_hook_bound_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_CODEX_STARTUP_HANDSHAKE", "1")
    monkeypatch.setenv("AURA_CODEX_STARTUP_READY_TIMEOUT", "1")

    from commands import spawn
    from lib import registry

    unit = tmp_path / "unit"
    unit.mkdir()
    sent = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            return {"ok": True, "target": "unitfleet:builder", "pane_id": "%44"}

        @staticmethod
        def send_text(name, text, submit=False):
            sent.append((name, text, submit))
            row = registry.get_agent("builder", fleet="unitfleet")
            registry.upsert_agent({
                **row,
                "name": "builder",
                "fleet": "unitfleet",
                "runtime_session_id": "codex-hook-thread",
                "session_id": "codex-hook-thread",
                "runtime_session_source": "codex-hook:session-start",
                "runtime_session_binding": "bound",
                "runtime_session_bind_method": "codex-hook",
                "runtime_session_bind_source": "codex-hook:session-start",
                "runtime_session_confidence": "exact",
            })
            return {"ok": True}

        @staticmethod
        def pane_pid(target):
            return 1001

    args = argparse.Namespace(
        name="builder",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert sent[0][1].startswith("[AURA STARTUP]")
    assert result["startup_readiness"]["ready"] is True
    assert result["ready"] is True
    assert result["ready_reason"] == "hook-bound"
    assert result["runtime_session_id"] == "codex-hook-thread"
    assert result["session_observation"]["status"] == "already-bound"


def test_spawn_auto_observes_codex_session_by_launch_id(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SPAWN_SESSION_OBSERVE_TIMEOUT", "0")

    from commands import spawn
    from lib import registry, runtime_session, session_ledger

    monkeypatch.setattr(spawn.uuid, "uuid4", lambda: type("U", (), {"hex": "feedfacecafebeef1234"})())

    unit = tmp_path / "unit"
    unit.mkdir()

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            return {"ok": True, "target": "unitfleet:builder", "pane_id": "%44"}

        @staticmethod
        def send_text(name, text, submit=False):
            return {"ok": True}

        @staticmethod
        def pane_pid(target):
            assert target == "tmux:unitfleet:%44"
            return 1001

    def fake_discover(runtime, terminal, target, *, seat_name=None, launch_id=None):
        assert runtime == "codex"
        assert seat_name == "builder"
        assert launch_id == "aura-launch-feedfacecafebeef"
        return {
            "runtime_session_source": "codex-state:cwd-start",
            "runtime_session_binding": "unbound",
            "runtime_session_diagnostics": {"reason": "codex-state-possible-match"},
            "runtime_session_possible_matches": [{
                "runtime_session_id": "codex-thread-launch",
                "reason": "aura-launch-id",
            }],
            "runtime_session_cwd": str(unit),
        }

    monkeypatch.setattr(runtime_session, "discover_for_target", fake_discover)

    args = argparse.Namespace(
        name="builder",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt="build the artifact",
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert "session_id" not in result
    assert "runtime_session_id" not in result
    assert result["session_observation"]["status"] == "pending"
    assert result["session_observation"]["last_runtime_session_binding"] == "unbound"

    agent = registry.get_agent("builder", fleet="unitfleet")
    assert "session_id" not in agent
    assert "runtime_session_id" not in agent

    rows = session_ledger.iter_records()
    assert not any(row.get("event") == "session_observed_after_spawn" and row.get("runtime_session_id") == "codex-thread-launch" for row in rows)


def test_spawn_session_observation_pending_without_high_confidence(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SPAWN_SESSION_OBSERVE_TIMEOUT", "0")

    from commands import spawn
    from lib import registry, runtime_session

    unit = tmp_path / "unit"
    unit.mkdir()

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            return {"ok": True, "target": "unitfleet:builder", "pane_id": "%44"}

        @staticmethod
        def pane_pid(target):
            return 1001

    monkeypatch.setattr(runtime_session, "discover_for_target", lambda *args, **kwargs: {})

    args = argparse.Namespace(
        name="builder",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["session_observation"]["status"] == "pending"
    assert result["session_observation"]["reason"] == "no-high-confidence-session-evidence"
    assert "runtime_session_id" not in result

    agent = registry.get_agent("builder", fleet="unitfleet")
    assert "runtime_session_id" not in agent


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
        lambda runtime, pane_pid, **kwargs: {
            "runtime_session_id": "codex-thread-123",
            "runtime_session_env": "CODEX_THREAD_ID",
            "runtime_session_source": "env:CODEX_THREAD_ID",
            "runtime_session_binding": "bound",
            "runtime_session_bind_method": "runtime-env",
            "runtime_session_bind_source": "env:CODEX_THREAD_ID",
            "runtime_session_pid": pane_pid,
        },
    )

    rows = list_cmd.run(argparse.Namespace(fleet="unitfleet", status=None, mode=None))

    engineer = next(row for row in rows if row["name"] == "engineer")
    assert engineer["session_id"] == "codex-thread-123"
    assert engineer["runtime_session_env"] == "CODEX_THREAD_ID"


def test_runtime_session_merge_preserves_exact_registry_binding_over_lower_live_heuristic():
    from lib import runtime_session

    record = {
        "name": "engineer",
        "session_id": "exact-thread",
        "runtime_session_id": "exact-thread",
        "runtime_session_source": "codex-jsonl:nonce",
        "runtime_session_confidence": "exact",
        "runtime_session_evidence": {"reason": "codex-jsonl-nonce"},
    }
    session = {
        "runtime_session_id": "heuristic-thread",
        "runtime_session_source": "codex-state:cwd-start",
        "runtime_session_confidence": "high",
        "runtime_session_evidence": {"reason": "cwd-start-seat-name"},
        "runtime_session_cwd": "/repo",
    }

    merged = runtime_session.merge(record, session)

    assert merged["session_id"] == "exact-thread"
    assert merged["runtime_session_id"] == "exact-thread"
    assert merged["runtime_session_source"] == "codex-jsonl:nonce"
    assert merged["runtime_session_confidence"] == "exact"


def test_runtime_session_merge_allows_exact_live_source_to_replace_exact_registry_binding():
    from lib import runtime_session

    record = {
        "name": "engineer",
        "session_id": "old-exact-thread",
        "runtime_session_id": "old-exact-thread",
        "runtime_session_source": "codex-jsonl:nonce",
        "runtime_session_confidence": "exact",
    }
    session = {
        "runtime_session_id": "new-exact-thread",
        "runtime_session_source": "argv:codex-resume",
        "runtime_session_confidence": "exact",
    }

    merged = runtime_session.merge(record, session)

    assert merged["session_id"] == "new-exact-thread"
    assert merged["runtime_session_id"] == "new-exact-thread"
    assert merged["runtime_session_source"] == "argv:codex-resume"


def test_runtime_session_merge_preserves_hook_binding_over_stale_resume_argv():
    from lib import runtime_session

    record = {
        "name": "lead-engineer",
        "session_id": "new-chat-thread",
        "runtime_session_id": "new-chat-thread",
        "runtime_session_source": "codex-hook:manual-chat-clear",
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": "codex-hook",
        "runtime_session_bind_source": "codex-hook:manual-chat-clear",
        "runtime_session_confidence": "exact",
        "runtime_session_evidence": {"reason": "codex-native-hook"},
    }
    session = {
        "runtime_session_id": "old-resume-thread",
        "runtime_session_source": "argv:codex-resume",
        "runtime_session_binding": "bound",
        "runtime_session_bind_method": "argv-resume",
        "runtime_session_bind_source": "argv:codex-resume",
        "runtime_session_confidence": "exact",
        "runtime_session_evidence": {"reason": "codex-resume-argv"},
        "runtime_session_pid": 1234,
    }

    merged = runtime_session.merge(record, session)

    assert merged["session_id"] == "new-chat-thread"
    assert merged["runtime_session_id"] == "new-chat-thread"
    assert merged["runtime_session_source"] == "codex-hook:manual-chat-clear"
    assert merged["runtime_session_bind_method"] == "codex-hook"
    assert merged["runtime_session_stale_process_evidence"]["runtime_session_id"] == "old-resume-thread"


def test_sessions_restore_plan_marks_high_confidence_codex_restore_ready(monkeypatch):
    from commands import sessions

    rows = [{
        "name": "engineer",
        "fleet": "flex-leaders-2",
        "runtime": "codex",
        "terminal": "alive",
        "status": "idle",
        "hidden": False,
        "kind": None,
        "session_id": "019dd2b7-8919-75d2-b472-7c778a93da92",
        "runtime_session_id": "019dd2b7-8919-75d2-b472-7c778a93da92",
        "runtime_session_source": "codex-state:cwd-start",
        "runtime_session_confidence": "high",
        "pane_ref": "tmux:flex-leaders-2:%291",
        "cwd": "/repo/flexsearch/main",
    }]

    monkeypatch.setattr(sessions.list_cmd, "run", lambda args: rows)

    result = sessions.run(argparse.Namespace(
        sessions_action="restore-plan",
        fleet=None,
        live=True,
        min_confidence=None,
        include_hidden=False,
    ))

    assert result["ok"] is True
    assert result["restore_ready"] == 0
    assert result["rows"][0]["restore_ready"] is False
    assert result["rows"][0]["restore_reason"] == "runtime-session-unbound"
    assert result["rows"][0]["restore_command"] is None


def test_runtime_session_self_prefers_current_codex_thread_env(monkeypatch):
    from lib import runtime_session

    monkeypatch.setenv("CODEX_THREAD_ID", "019dd624-0108-75a3-b0aa-5ac218048091")
    monkeypatch.setenv("AURA_RUNTIME_SESSION_ID", "stale-normalized-session")
    monkeypatch.setenv("AURA_RUNTIME", "codex")
    monkeypatch.delenv("AURA_SESSION_ID", raising=False)
    monkeypatch.setattr(runtime_session, "_tmux_current_fleet_seat", lambda: ("unitfleet", "engineer"))
    monkeypatch.setattr(runtime_session, "_tmux_current_pane_pid", lambda: 1001)
    monkeypatch.setattr(
        runtime_session,
        "discover_from_pane_pid",
        lambda runtime, pane_pid, seat_name=None: {
            "runtime_session_id": "019dd624-0108-75a3-b0aa-5ac218048091",
            "runtime_session_source": "argv:codex-resume",
            "runtime_session_confidence": "exact",
            "runtime_session_evidence": {"reason": "codex-resume-argv"},
        },
    )

    result = runtime_session.resolve_current_process()

    assert result["ok"] is True
    assert result["session_id"] == "019dd624-0108-75a3-b0aa-5ac218048091"
    assert result["runtime_session_source"] == "env:CODEX_THREAD_ID"
    assert result["runtime_session_confidence"] == "exact"
    assert result["cross_check"] == "confirmed"
    assert result["mismatch"] is False


def test_runtime_session_self_reports_stale_pane_cross_check_without_losing_env(monkeypatch):
    from lib import runtime_session

    monkeypatch.setenv("CODEX_THREAD_ID", "019dd624-0108-75a3-b0aa-5ac218048091")
    monkeypatch.setenv("AURA_RUNTIME", "codex")
    monkeypatch.delenv("AURA_RUNTIME_SESSION_ID", raising=False)
    monkeypatch.delenv("AURA_SESSION_ID", raising=False)
    monkeypatch.setattr(runtime_session, "_tmux_current_fleet_seat", lambda: ("unitfleet", "engineer"))
    monkeypatch.setattr(runtime_session, "_tmux_current_pane_pid", lambda: 1001)
    monkeypatch.setattr(
        runtime_session,
        "discover_from_pane_pid",
        lambda runtime, pane_pid, seat_name=None: {
            "runtime_session_id": "019dd679-a7e1-7021-a0c8-53a9bb9fd4ed",
            "runtime_session_source": "codex-state:cwd-start",
            "runtime_session_confidence": "high",
            "runtime_session_evidence": {"reason": "cwd-start-seat-name"},
        },
    )

    result = runtime_session.resolve_current_process()

    assert result["ok"] is True
    assert result["session_id"] == "019dd624-0108-75a3-b0aa-5ac218048091"
    assert result["runtime_session_source"] == "env:CODEX_THREAD_ID"
    assert result["runtime_session_confidence"] == "exact"
    assert result["cross_check"] == "mismatch"
    assert result["mismatch"] is True
    assert result["warning"] == "current-process-env-disagrees-with-pane-evidence"


def test_sessions_self_delegates_to_current_process_resolver(monkeypatch):
    from commands import sessions
    from lib import runtime_session

    monkeypatch.setattr(
        runtime_session,
        "resolve_current_process",
        lambda runtime=None: {"ok": True, "runtime": runtime, "session_id": "thread-1"},
    )

    result = sessions.run(argparse.Namespace(sessions_action="self", runtime="codex"))

    assert result == {"ok": True, "runtime": "codex", "session_id": "thread-1"}


def test_sessions_bind_current_resolves_and_updates_target_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import sessions
    from lib import registry, runtime_session

    monkeypatch.setattr(
        runtime_session,
        "resolve_current_process",
        lambda runtime=None: {
            "ok": True,
            "runtime": runtime or "codex",
            "session_id": "thread-current",
            "runtime_session_id": "thread-current",
            "runtime_session_source": "env:CODEX_THREAD_ID",
            "runtime_session_confidence": "exact",
            "cross_check": "confirmed",
            "warning": None,
            "fleet": "fleet-a",
            "seat": "engineer",
            "pane": "%1",
            "pane_pid": 123,
            "cwd": "/repo/current",
            "evidence": [{"source": "env:CODEX_THREAD_ID", "session_id": "thread-current"}],
        },
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-current",
        runtime="codex",
        target="fleet-a:engineer",
    ))

    assert result["ok"] is True
    assert result["session_id"] == "thread-current"
    assert result["runtime_session_source"] == "env:CODEX_THREAD_ID"
    assert result["runtime_session_confidence"] == "exact"
    assert result["cross_check"] == "confirmed"

    agent = registry.get_agent("engineer", fleet="fleet-a")
    assert agent["session_id"] == "thread-current"
    assert agent["runtime_session_id"] == "thread-current"
    assert agent["runtime_session_evidence"]["reason"] == "current-runtime-session"


def test_sessions_bind_current_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import sessions
    from lib import registry, runtime_session

    registry.upsert_agent({
        "name": "engineer",
        "fleet": "fleet-a",
        "runtime": "codex",
        "session_id": "thread-current",
        "runtime_session_id": "thread-current",
        "runtime_session_source": "env:CODEX_THREAD_ID",
        "runtime_session_confidence": "exact",
    })
    monkeypatch.setattr(
        runtime_session,
        "resolve_current_process",
        lambda runtime=None: {
            "ok": True,
            "runtime": "codex",
            "session_id": "thread-current",
            "runtime_session_source": "env:CODEX_THREAD_ID",
            "runtime_session_confidence": "exact",
            "cross_check": "single-source",
            "warning": None,
            "fleet": "fleet-a",
            "seat": "engineer",
            "cwd": "/repo/current",
            "evidence": [],
        },
    )

    args = argparse.Namespace(sessions_action="bind-current", runtime="codex", target="fleet-a:engineer")
    first = sessions.run(args)
    second = sessions.run(args)

    assert first["ok"] is True
    assert second["ok"] is True
    assert second["session_id"] == "thread-current"
    assert registry.get_agent("engineer", fleet="fleet-a")["runtime_session_confidence"] == "exact"


def test_sessions_bind_hook_follows_rehome_alias_without_recreating_source(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))

    from commands import sessions
    from lib import registry

    registry.upsert_agent({
        "name": "operator",
        "fleet": "aura-refresh-test",
        "runtime": "codex",
        "registered": True,
        "seat_instance_id": "si_hook",
        "pane_ref": "tmux:aura-refresh-test:%341",
    })
    rehome = registry.rehome_agent("aura-refresh-test:operator", new_name="pilot")
    assert rehome["ok"] is True

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-hook",
        runtime="codex",
        target="aura-refresh-test:operator",
        session_id="thread-hook",
        nonce=None,
        transcript_path="/tmp/thread.jsonl",
        hook_event="UserPromptSubmit",
        seat_instance_id="si_hook",
    ))

    assert result["ok"] is True
    assert result["target"] == "aura-refresh-test:pilot"
    assert set(registry.read_registry().keys()) == {"aura-refresh-test:pilot"}
    assert registry.get_agent("aura-refresh-test:pilot")["runtime_session_id"] == "thread-hook"
    assert registry.get_agent("aura-refresh-test:operator")["resolved_from"] == "aura-refresh-test:operator"


def test_sessions_bind_current_requires_exact_session(monkeypatch):
    from commands import sessions
    from lib import runtime_session

    monkeypatch.setattr(
        runtime_session,
        "resolve_current_process",
        lambda runtime=None: {
            "ok": True,
            "runtime": "codex",
            "session_id": "thread-high",
            "runtime_session_confidence": "high",
        },
    )

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-current",
        runtime="codex",
        target="fleet-a:engineer",
    ))

    assert result["ok"] is False
    assert result["error"] == "current runtime session id is not bound; use bind-nonce fallback"


def test_sessions_bind_nonce_default_target_prefers_aura_env(monkeypatch):
    from commands import sessions

    monkeypatch.setenv("AURA_FLEET", "fleet-a")
    monkeypatch.setenv("AURA_SEAT", "engineer")
    monkeypatch.setenv("TMUX_PANE", "%99")

    result = sessions._target_fleet_seat(None)

    assert result == ("fleet-a", "engineer")


def test_sessions_bind_nonce_default_target_uses_current_tmux_pane(monkeypatch):
    from commands import sessions

    calls = []

    class Result:
        returncode = 0
        stdout = "fleet-a\tengineer\n"

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Result()

    monkeypatch.delenv("AURA_FLEET", raising=False)
    monkeypatch.delenv("AURA_SEAT", raising=False)
    monkeypatch.delenv("AURA_AGENT_NAME", raising=False)
    monkeypatch.setenv("TMUX_PANE", "%99")
    monkeypatch.setattr(sessions.subprocess, "run", fake_run)

    result = sessions._target_fleet_seat(None)

    assert result == ("fleet-a", "engineer")
    assert calls == [["tmux", "display-message", "-p", "-t", "%99", "#{session_name}\t#{window_name}"]]


def test_sessions_bind_nonce_tmux_target_resolves_target_pane(monkeypatch):
    from commands import sessions

    calls = []

    class Result:
        returncode = 0
        stdout = "fleet-b\ttesting\n"

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return Result()

    monkeypatch.setattr(sessions.subprocess, "run", fake_run)

    result = sessions._target_fleet_seat("tmux:fleet-b:%42")

    assert result == ("fleet-b", "testing")
    assert calls == [["tmux", "display-message", "-p", "-t", "fleet-b:%42", "#{session_name}\t#{window_name}"]]


def test_sessions_bind_nonce_updates_target_registry(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    session_dir = tmp_path / ".codex" / "sessions" / "2026" / "04" / "29"
    session_dir.mkdir(parents=True)
    jsonl = session_dir / "rollout-2026-04-29T20-31-42-019ddc71-3db7-7c72-9ffd-8da9e3aa96a2.jsonl"
    nonce = "aura-session-nonce-test"
    jsonl.write_text(
        "\n".join([
            '{"timestamp":"2026-04-30T03:31:43.483Z","type":"session_meta","payload":{"id":"019ddc71-3db7-7c72-9ffd-8da9e3aa96a2","timestamp":"2026-04-30T03:31:42.449Z","cwd":"/repo"}}',
            '{"timestamp":"2026-04-30T03:31:44.000Z","type":"response_item","payload":{"output":"aura-session-nonce-test"}}',
        ]),
        encoding="utf-8",
    )

    from commands import sessions
    from lib import registry

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-nonce",
        nonce=nonce,
        target="fleet-a:engineer",
    ))

    assert result["ok"] is True
    assert result["session_id"] == "019ddc71-3db7-7c72-9ffd-8da9e3aa96a2"
    assert result["runtime_session_source"] == "codex-jsonl:nonce"
    assert result["runtime_session_confidence"] == "exact"

    agent = registry.get_agent("engineer", fleet="fleet-a")
    assert agent["session_id"] == "019ddc71-3db7-7c72-9ffd-8da9e3aa96a2"
    assert agent["runtime_session_evidence"]["nonce"] == nonce


def test_sessions_bind_nonce_prefers_target_registry_cwd_when_nonce_has_multiple_matches(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    session_dir = tmp_path / ".codex" / "sessions" / "2026" / "04" / "29"
    session_dir.mkdir(parents=True)
    nonce = "aura-session-nonce-shared"
    target_jsonl = session_dir / "target.jsonl"
    current_jsonl = session_dir / "current.jsonl"
    target_jsonl.write_text(
        "\n".join([
            '{"type":"session_meta","payload":{"id":"target-thread","cwd":"/repo/target"}}',
            '{"type":"response_item","payload":{"output":"aura-session-nonce-shared"}}',
        ]),
        encoding="utf-8",
    )
    current_jsonl.write_text(
        "\n".join([
            '{"type":"session_meta","payload":{"id":"current-thread","cwd":"/repo/current"}}',
            '{"type":"response_item","payload":{"output":"aura-session-nonce-shared"}}',
        ]),
        encoding="utf-8",
    )

    from commands import sessions
    from lib import registry

    registry.upsert_agent({
        "name": "engineer",
        "fleet": "fleet-a",
        "runtime": "codex",
        "runtime_session_cwd": "/repo/target",
    })

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-nonce",
        nonce=nonce,
        target="fleet-a:engineer",
        jsonl=None,
    ))

    assert result["ok"] is True
    assert result["session_id"] == "target-thread"
    assert result["jsonl"] == str(target_jsonl)


def test_sessions_bind_nonce_can_pin_jsonl_for_repair(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    session_dir = tmp_path / ".codex" / "sessions" / "2026" / "04" / "29"
    session_dir.mkdir(parents=True)
    nonce = "aura-session-nonce-pinned"
    target_jsonl = session_dir / "target.jsonl"
    current_jsonl = session_dir / "current.jsonl"
    target_jsonl.write_text(
        "\n".join([
            '{"type":"session_meta","payload":{"id":"target-thread","cwd":"/repo/target"}}',
            '{"type":"response_item","payload":{"output":"aura-session-nonce-pinned"}}',
        ]),
        encoding="utf-8",
    )
    current_jsonl.write_text(
        "\n".join([
            '{"type":"session_meta","payload":{"id":"current-thread","cwd":"/repo/current"}}',
            '{"type":"response_item","payload":{"output":"aura-session-nonce-pinned"}}',
        ]),
        encoding="utf-8",
    )

    from commands import sessions

    result = sessions.run(argparse.Namespace(
        sessions_action="bind-nonce",
        nonce=nonce,
        target="fleet-a:engineer",
        jsonl=str(target_jsonl),
    ))

    assert result["ok"] is True
    assert result["session_id"] == "target-thread"
    assert result["jsonl"] == str(target_jsonl)

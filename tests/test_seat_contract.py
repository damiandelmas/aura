import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli" / "aura"
sys.path.insert(0, str(ROOT / "cli"))


def test_shell_runtime_spec_exists():
    from lib import runtimes

    shell_runtime, shell_spec = runtimes.resolve_runtime("shell")

    assert shell_runtime == "shell"
    assert "command" in shell_spec
    assert runtimes.graceful_exit("future-runtime") == "/exit"


def test_codex_fork_command_uses_native_fork_and_quotes_prompt():
    from lib import runtimes

    session_id = "019dd1ba-70ff-72c3-8ccd-739cccf4e3fc"
    command = runtimes.build_fork_command(
        "codex",
        session_id,
        prompt="report 'ready'",
        cwd="/tmp/unit path",
    )

    assert command == (
        "codex --cd '/tmp/unit path' --dangerously-bypass-approvals-and-sandbox "
        f"fork {session_id} 'report '\"'\"'ready'\"'\"''"
    )


def test_initial_prompt_argv_runtime_commands_quote_prompt():
    import shlex

    from lib import runtimes

    codex_runtime, codex_spec = runtimes.resolve_runtime("codex")
    claude_runtime, claude_spec = runtimes.resolve_runtime("claude-code")
    shell_runtime, shell_spec = runtimes.resolve_runtime("shell")

    assert runtimes.supports_initial_prompt_argv(codex_runtime, codex_spec) is True
    assert runtimes.supports_initial_prompt_argv(claude_runtime, claude_spec) is True
    assert runtimes.supports_initial_prompt_argv(shell_runtime, shell_spec) is False

    codex_prompt = "say 'ready'"
    assert runtimes.build_command(
        "codex",
        codex_spec,
        name="worker",
        prompt=codex_prompt,
    ) == f"codex --dangerously-bypass-approvals-and-sandbox {shlex.quote(codex_prompt)}"
    assert runtimes.build_command(
        "shell",
        shell_spec,
        name="worker",
        prompt="not native",
    ) == "bash"


def test_write_submit_retry_detection_is_narrow():
    from lib.terminal_submit import delivery_blocker, needs_submit_retry, retry_submit

    assert needs_submit_retry(["Messages to be submitted after next tool call"]) is True
    assert needs_submit_retry(["Press Enter to submit"]) is True
    assert needs_submit_retry(["› [Pasted Content 1024 chars]", "", "gpt-5.5 high"]) is True
    assert needs_submit_retry(["› [Pasted Content 1024 chars]", "• Working (1s)"]) is False
    assert needs_submit_retry(["Working (2s)", "Running tool call"]) is False
    assert delivery_blocker(["› [Pasted Content 1024 chars]", "", "gpt-5.5 high"]) == "target-input-queued"
    assert delivery_blocker(["• Working (1s)", "Running tool call"]) == "target-busy"

    class FakeTerminal:
        calls = []

        @classmethod
        def send_keys(cls, name, text, enter=True):
            cls.calls.append((name, text, enter))
            return {"ok": True}

    assert retry_submit("seat1", FakeTerminal)["ok"] is True
    assert FakeTerminal.calls == [("seat1", "Enter", False)]


def test_spawn_prompt_retry_does_not_repaste_after_prompt_is_visible(monkeypatch):
    from commands import spawn
    from lib import runtime_session

    monkeypatch.setenv("AURA_CODEX_PROMPT_SUBMIT_RETRIES", "2")
    monkeypatch.setattr(runtime_session, "discover_for_target", lambda *args, **kwargs: {})

    class FakeTerminal:
        keys = []
        texts = []

        @staticmethod
        def capture_output(target, lines=80):
            return [
                "› HOOK LAB REPORT PROBE: do not edit files.",
                "• REPORT_PROBE_READY",
            ]

        @classmethod
        def send_keys(cls, target, text, enter=True):
            cls.keys.append((target, text, enter))
            return {"ok": True, "target": target, "submitted": False}

        @classmethod
        def send_text(cls, target, text, submit=True):
            cls.texts.append((target, text, submit))
            return {"ok": True, "target": target, "submitted": submit}

    result = spawn._retry_codex_prompt_submit(
        terminal=FakeTerminal,
        target="fleet:%1",
        seat="worker",
        launch_id="launch-1",
        prompt_text="HOOK LAB REPORT PROBE: do not edit files.",
    )

    assert result["ok"] is True
    assert result["session_seen"] is False
    assert [attempt["reason"] for attempt in result["results"]] == ["no-queued-input", "no-queued-input"]
    assert FakeTerminal.keys == []
    assert FakeTerminal.texts == []


def test_spawn_prompt_retry_repastes_when_startup_paste_lands_above_tui(monkeypatch):
    from commands import spawn
    from lib import runtime_session

    monkeypatch.setenv("AURA_CODEX_PROMPT_SUBMIT_RETRIES", "2")
    monkeypatch.setattr(runtime_session, "discover_for_target", lambda *args, **kwargs: {})

    class FakeTerminal:
        keys = []
        texts = []

        @staticmethod
        def capture_output(target, lines=80):
            return [
                "HOOK SMOKE PROBE: do not edit files.",
                "╭─────────────────────────────────────────╮",
                "│ >_ OpenAI Codex                         │",
                "╰─────────────────────────────────────────╯",
                "› Explain this codebase",
            ]

        @classmethod
        def send_keys(cls, target, text, enter=True):
            cls.keys.append((target, text, enter))
            return {"ok": True, "target": target, "submitted": enter}

        @classmethod
        def send_text(cls, target, text, submit=True):
            cls.texts.append((target, text, submit))
            return {"ok": True, "target": target, "submitted": submit}

    result = spawn._retry_codex_prompt_submit(
        terminal=FakeTerminal,
        target="fleet:%1",
        seat="worker",
        launch_id="launch-1",
        prompt_text="HOOK SMOKE PROBE: do not edit files.",
    )

    assert result["ok"] is True
    assert result["session_seen"] is False
    assert FakeTerminal.keys == [("fleet:%1", "C-u", False)]
    assert FakeTerminal.texts == [("fleet:%1", "HOOK SMOKE PROBE: do not edit files.", True)]
    assert result["results"][1]["reason"] == "startup-prompt-not-in-composer"


def test_spawn_prompt_retry_repastes_when_startup_paste_lands_above_skills_placeholder(monkeypatch):
    from commands import spawn
    from lib import runtime_session

    monkeypatch.setenv("AURA_CODEX_PROMPT_SUBMIT_RETRIES", "2")
    monkeypatch.setattr(runtime_session, "discover_for_target", lambda *args, **kwargs: {})

    class FakeTerminal:
        keys = []
        texts = []

        @staticmethod
        def capture_output(target, lines=80):
            return [
                "HOOK SMOKE PROBE: do not edit files.",
                "╭─────────────────────────────────────────╮",
                "│ >_ OpenAI Codex                         │",
                "╰─────────────────────────────────────────╯",
                "› Use /skills to list available skills",
            ]

        @classmethod
        def send_keys(cls, target, text, enter=True):
            cls.keys.append((target, text, enter))
            return {"ok": True, "target": target, "submitted": enter}

        @classmethod
        def send_text(cls, target, text, submit=True):
            cls.texts.append((target, text, submit))
            return {"ok": True, "target": target, "submitted": submit}

    result = spawn._retry_codex_prompt_submit(
        terminal=FakeTerminal,
        target="fleet:%1",
        seat="worker",
        launch_id="launch-1",
        prompt_text="HOOK SMOKE PROBE: do not edit files.",
    )

    assert result["ok"] is True
    assert result["session_seen"] is False
    assert FakeTerminal.keys == [("fleet:%1", "C-u", False)]
    assert FakeTerminal.texts == [("fleet:%1", "HOOK SMOKE PROBE: do not edit files.", True)]
    assert result["results"][1]["reason"] == "startup-prompt-not-in-composer"


def test_spawn_prompt_retry_does_not_accept_high_confidence_cwd_match(monkeypatch):
    from commands import spawn
    from lib import runtime_session

    monkeypatch.setenv("AURA_CODEX_PROMPT_SUBMIT_RETRIES", "1")
    monkeypatch.setattr(
        runtime_session,
        "discover_for_target",
        lambda *args, **kwargs: {
            "runtime_session_source": "codex-state:cwd-start",
            "runtime_session_binding": "unbound",
            "runtime_session_diagnostics": {
                "reason": "codex-state-possible-match",
                "confidence": "high",
            },
            "runtime_session_possible_matches": [{
                "runtime_session_id": "old-cwd-seat-name-match",
                "reason": "cwd-start-seat-name",
            }],
        },
    )

    class FakeTerminal:
        keys = []

        @staticmethod
        def capture_output(target, lines=80):
            return ["› [Pasted Content 1024 chars]"]

        @classmethod
        def send_keys(cls, target, text, enter=True):
            cls.keys.append((target, text, enter))
            return {"ok": True, "target": target, "submitted": enter}

    result = spawn._retry_codex_prompt_submit(
        terminal=FakeTerminal,
        target="fleet:%1",
        seat="worker",
        launch_id="launch-1",
        prompt_text="queued prompt",
    )

    assert result["ok"] is True
    assert result["session_seen"] is False
    assert FakeTerminal.keys == [("fleet:%1", "Enter", False)]


def test_spawn_prompt_retry_enters_only_when_input_is_queued(monkeypatch):
    from commands import spawn
    from lib import runtime_session

    monkeypatch.setenv("AURA_CODEX_PROMPT_SUBMIT_RETRIES", "1")
    monkeypatch.setattr(runtime_session, "discover_for_target", lambda *args, **kwargs: {})

    class FakeTerminal:
        keys = []

        @staticmethod
        def capture_output(target, lines=80):
            return ["› [Pasted Content 1024 chars]", "", "gpt-5.5 high"]

        @classmethod
        def send_keys(cls, target, text, enter=True):
            cls.keys.append((target, text, enter))
            return {"ok": True, "target": target, "submitted": False}

    result = spawn._retry_codex_prompt_submit(
        terminal=FakeTerminal,
        target="fleet:%1",
        seat="worker",
        launch_id="launch-1",
        prompt_text="queued prompt",
    )

    assert result["ok"] is True
    assert result["session_seen"] is False
    assert FakeTerminal.keys == [("fleet:%1", "Enter", False)]


def test_send_tmux_attempts_without_submit_verification(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))

    from commands import send

    class FakeTerminal:
        captures = [
            ["› [Pasted Content 1024 chars]", "", "gpt-5.5 high"],
            ["• Working (1s)"],
        ]
        keys = []

        @staticmethod
        def send_text(name, text, submit=True):
            return {"ok": True, "target": "unitfleet:worker", "bytes": len(text), "submitted": submit}

        @classmethod
        def capture_output(cls, name, lines=80):
            return cls.captures.pop(0)

        @classmethod
        def send_keys(cls, name, text, enter=True):
            cls.keys.append((name, text, enter))
            return {"ok": True, "target": "unitfleet:worker"}

    args = argparse.Namespace(
        target="worker",
        message="do the thing",
        sender="tester",
        dedupe_key="unit-send",
        force=False,
    )

    result = send._send_tmux(
        args,
        FakeTerminal,
        __import__("lib.delivery", fromlist=["delivery"]),
        terminal_target="unitfleet:worker",
        sender="tester",
        sender_kind="service",
    )
    assert result["ok"] is True
    assert result["submitted"] is True
    assert result["state"] == "attempted"
    assert result["submitted_verified"] is None
    assert result["submit_retry"] is None
    assert FakeTerminal.keys == []

    records = [
        json.loads(line)
        for line in (tmp_path / "deliveries.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert records[-1]["delivery_type"] == "semantic_send"
    assert records[-1]["state"] == "attempted"
    assert records[-1]["submitted_verified"] is None
    assert records[-1]["submit_retry"] is None


def test_send_tmux_does_not_inspect_queued_input_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))

    from commands import send

    class FakeTerminal:
        sent = False
        keys = []

        @staticmethod
        def capture_output(name, lines=80):
            return ["› [Pasted Content 1024 chars]", "", "gpt-5.5 high"]

        @classmethod
        def send_text(cls, name, text, submit=True):
            cls.sent = True
            return {"ok": True}

        @classmethod
        def send_keys(cls, name, text, enter=True):
            cls.keys.append((name, text, enter))
            return {"ok": True}

    args = argparse.Namespace(
        target="worker",
        message="do not append",
        sender="tester",
        dedupe_key="unit-block",
        force=False,
    )

    result = send._send_tmux(
        args,
        FakeTerminal,
        __import__("lib.delivery", fromlist=["delivery"]),
        terminal_target="unitfleet:worker",
        sender="tester",
        sender_kind="service",
    )

    assert result["ok"] is True
    assert FakeTerminal.sent is True
    assert result["state"] == "attempted"
    assert result["submitted_verified"] is None
    assert result["submit_retry"] is None
    assert FakeTerminal.keys == []


def test_tmux_send_text_waits_before_submit(monkeypatch):
    from lib import tmux

    calls = []
    sleeps = []

    def fake_run(cmd, capture_output=True, text=True):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setenv("AURA_TMUX_SUBMIT_DELAY_SECONDS", "0.5")
    monkeypatch.setattr(tmux, "target_exists", lambda name: True)
    monkeypatch.setattr(tmux, "pane_id", lambda name: "%42")
    monkeypatch.setattr(tmux.subprocess, "run", fake_run)
    monkeypatch.setattr(tmux.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = tmux.send_text("unitfleet:worker", "hello", submit=True)

    assert result["ok"] is True
    assert result["submitted"] is True
    assert result["submit_delay_seconds"] == 0.5
    assert sleeps == [0.5]
    assert calls[0][1] == "load-buffer"
    assert calls[1][1] == "paste-buffer"
    assert "-p" in calls[1]
    assert calls[2][-1] == "Enter"
    assert calls[3][1] == "delete-buffer"


def test_tmux_target_exists_uses_exact_window_names(monkeypatch):
    from lib import tmux

    monkeypatch.setattr(tmux, "TMUX_SESSION", "unitfleet")

    def fake_run(args):
        if args[:3] == ["list-windows", "-t", "unitfleet"]:
            return subprocess.CompletedProcess(args, 0, stdout="bash\nmock-efaa\n", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(tmux, "_run_tmux", fake_run)

    assert tmux.window_exists("mock-efaa") is True
    assert tmux.window_exists("mock") is False
    assert tmux.window_exists("unitfleet:mock-efaa") is True


def test_tmux_create_window_uses_requested_window_for_new_session(monkeypatch, tmp_path):
    from lib import tmux

    calls = []

    monkeypatch.setattr(tmux, "TMUX_SESSION", "freshfleet")
    monkeypatch.setattr(tmux, "_session", lambda: None)
    monkeypatch.setattr(tmux, "pane_id", lambda name: "%77" if name == "worker" else None)

    def fake_run(args):
        calls.append(args)
        if args[:6] == ["new-session", "-d", "-s", "freshfleet", "-n", "worker"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args in (
            ["set-option", "-t", "freshfleet", "base-index", "1"],
            ["set-window-option", "-t", "freshfleet", "pane-base-index", "1"],
            ["set-option", "-t", "freshfleet", "renumber-windows", "on"],
            ["move-window", "-r", "-t", "freshfleet"],
        ):
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        # set-environment scrub/set calls added by the session-env isolation fix
        if args[:3] == ["set-environment", "-t", "freshfleet"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(tmux, "_run_tmux", fake_run)

    result = tmux.create_window(
        "worker",
        str(tmp_path),
        detached=True,
        command="printf ready",
        env={"AURA_SEAT": "worker"},
        unset_env=["NO_COLOR"],
    )

    assert result["ok"] is True
    assert result["target"] == "freshfleet:worker"
    assert result["pane_id"] == "%77"
    # Verify the new-session call is present and correct.
    assert calls[0] == [
        "new-session",
        "-d",
        "-s",
        "freshfleet",
        "-n",
        "worker",
        "-e",
        "AURA_SEAT=worker",
        "-c",
        str(tmp_path),
        "env -u NO_COLOR AURA_SEAT=worker printf ready",
    ]
    # _apply_index_defaults follows immediately after new-session.
    assert ["set-option", "-t", "freshfleet", "base-index", "1"] in calls
    assert ["set-window-option", "-t", "freshfleet", "pane-base-index", "1"] in calls
    assert ["set-option", "-t", "freshfleet", "renumber-windows", "on"] in calls
    assert ["move-window", "-r", "-t", "freshfleet"] in calls
    # Session-env isolation: unset_env key must be scrubbed from the session env.
    assert ["set-environment", "-t", "freshfleet", "-u", "NO_COLOR"] in calls
    # AURA_SEAT is not a body-home key so no set-environment KEY=VAL call for it.
    assert not any(
        c[:4] == ["set-environment", "-t", "freshfleet"] and len(c) == 5 and c[3] == "AURA_SEAT"
        for c in calls
    )


def test_tmux_create_window_index_defaults_can_be_disabled(monkeypatch, tmp_path):
    from lib import tmux

    calls = []

    monkeypatch.setenv("AURA_TMUX_INDEX_DEFAULTS", "0")
    monkeypatch.setattr(tmux, "TMUX_SESSION", "zero-ok")
    monkeypatch.setattr(tmux, "_session", lambda: None)
    monkeypatch.setattr(tmux, "pane_id", lambda name: "%77" if name == "worker" else None)

    def fake_run(args):
        calls.append(args)
        if args[:6] == ["new-session", "-d", "-s", "zero-ok", "-n", "worker"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(tmux, "_run_tmux", fake_run)

    result = tmux.create_window("worker", str(tmp_path), detached=True, command="sleep 60")

    assert result["ok"] is True
    assert calls == [["new-session", "-d", "-s", "zero-ok", "-n", "worker", "-c", str(tmp_path), "sleep 60"]]


def test_tmux_create_window_retries_new_window_on_duplicate_session(monkeypatch, tmp_path):
    from lib import tmux

    calls = []

    monkeypatch.setattr(tmux, "TMUX_SESSION", "racefleet")
    monkeypatch.setattr(tmux, "_session", lambda: None)
    monkeypatch.setattr(tmux, "pane_id", lambda name: "%78" if name == "worker-b" else None)

    def fake_run(args):
        calls.append(args)
        if args[:6] == ["new-session", "-d", "-s", "racefleet", "-n", "worker-b"]:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="duplicate session: racefleet")
        if args in (
            ["set-option", "-t", "racefleet", "base-index", "1"],
            ["set-window-option", "-t", "racefleet", "pane-base-index", "1"],
            ["set-option", "-t", "racefleet", "renumber-windows", "on"],
            ["move-window", "-r", "-t", "racefleet"],
        ):
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[:5] == ["new-window", "-t", "racefleet", "-n", "worker-b"]:
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        raise AssertionError(args)

    monkeypatch.setattr(tmux, "_run_tmux", fake_run)

    result = tmux.create_window("worker-b", str(tmp_path), detached=True, command="sleep 60")

    assert result["ok"] is True
    assert result["target"] == "racefleet:worker-b"
    assert calls == [
        ["new-session", "-d", "-s", "racefleet", "-n", "worker-b", "-c", str(tmp_path), "sleep 60"],
        ["set-option", "-t", "racefleet", "base-index", "1"],
        ["set-window-option", "-t", "racefleet", "pane-base-index", "1"],
        ["set-option", "-t", "racefleet", "renumber-windows", "on"],
        ["move-window", "-r", "-t", "racefleet"],
        ["new-window", "-t", "racefleet", "-n", "worker-b", "-d", "-c", str(tmp_path), "sleep 60"],
    ]


def test_tmux_create_window_scrubs_session_env_on_duplicate_session_race(monkeypatch, tmp_path):
    """Duplicate-session race path must still scrub/set the session env when env/unset_env are present."""
    from lib import tmux

    calls = []
    monkeypatch.setattr(tmux, "TMUX_SESSION", "racefleet")
    monkeypatch.setattr(tmux, "_session", lambda: None)
    monkeypatch.setattr(tmux, "pane_id", lambda name: "%78")

    def fake_run(args):
        calls.append(args)
        if args[:6] == ["new-session", "-d", "-s", "racefleet", "-n", "race-seat"]:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="duplicate session: racefleet")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(tmux, "_run_tmux", fake_run)

    result = tmux.create_window(
        "race-seat", str(tmp_path), detached=True, command="codex",
        env={"CODEX_HOME": "/seat/home"}, unset_env=["CODEX_HOME", "OMX_ROOT"],
    )

    assert result["ok"] is True
    set_env_calls = [c for c in calls if c[:3] == ["set-environment", "-t", "racefleet"]]
    assert ["set-environment", "-t", "racefleet", "-u", "CODEX_HOME"] in set_env_calls
    assert ["set-environment", "-t", "racefleet", "-u", "OMX_ROOT"] in set_env_calls
    assert ["set-environment", "-t", "racefleet", "CODEX_HOME", "/seat/home"] in set_env_calls
    # the scrub must run before the new window is created in the raced session
    new_window_idx = next(i for i, c in enumerate(calls) if c[:3] == ["new-window", "-t", "racefleet"])
    last_scrub_idx = max(i for i, c in enumerate(calls) if c[:3] == ["set-environment", "-t", "racefleet"])
    assert last_scrub_idx < new_window_idx


def test_tmux_create_window_scrubs_session_env_for_unset_keys(monkeypatch, tmp_path):
    """Session env isolation: set-environment -u is issued for every unset_env key
    so runtime-created child panes don't inherit stale identity from the spawner."""
    from lib import tmux

    calls = []
    unset_keys = ["CODEX_HOME", "AURA_AGENT_PACKAGE_ID", "NO_COLOR"]

    monkeypatch.setattr(tmux, "TMUX_SESSION", "isofleet")
    monkeypatch.setattr(tmux, "_session", lambda: None)
    monkeypatch.setattr(tmux, "pane_id", lambda name: "%88" if name == "iso-seat" else None)

    def fake_run(args):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(tmux, "_run_tmux", fake_run)

    result = tmux.create_window(
        "iso-seat",
        str(tmp_path),
        detached=True,
        command="codex",
        env={"AURA_SEAT": "iso-seat", "CODEX_HOME": "/state/codex-home"},
        unset_env=unset_keys,
    )

    assert result["ok"] is True

    set_env_calls = [c for c in calls if c[:3] == ["set-environment", "-t", "isofleet"]]

    # Every key in unset_env must be scrubbed from the session environment.
    for key in unset_keys:
        assert ["set-environment", "-t", "isofleet", "-u", key] in set_env_calls, (
            f"expected set-environment -u {key} but got: {set_env_calls}"
        )

    # CODEX_HOME is present in env and is a body-home key: must be SET on session.
    assert ["set-environment", "-t", "isofleet", "CODEX_HOME", "/state/codex-home"] in set_env_calls

    # Non-body-home env key (AURA_SEAT) must NOT be written to session env via set-environment.
    assert not any(
        c == ["set-environment", "-t", "isofleet", "AURA_SEAT", "iso-seat"]
        for c in set_env_calls
    )


def test_tmux_create_window_scrubs_session_env_for_existing_session(monkeypatch, tmp_path):
    """When the tmux session already exists (new-window path), the session env
    is still scrubbed before creating the new window."""
    from lib import tmux

    calls = []

    monkeypatch.setattr(tmux, "TMUX_SESSION", "livefleet")
    monkeypatch.setattr(tmux, "_session", lambda: True)  # session already exists
    monkeypatch.setattr(tmux, "pane_id", lambda name: "%89" if name == "late-seat" else None)

    def fake_run(args):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(tmux, "_run_tmux", fake_run)

    result = tmux.create_window(
        "late-seat",
        str(tmp_path),
        detached=True,
        command="codex --dangerously-bypass-approvals-and-sandbox",
        env={"CODEX_HOME": "/state/codex-home"},
        unset_env=["CODEX_HOME", "AURA_AGENT_PACKAGE_ID", "AURA_AGENT_PACKAGE_ROOT"],
    )

    assert result["ok"] is True

    set_env_calls = [c for c in calls if c[:3] == ["set-environment", "-t", "livefleet"]]

    # Unset keys scrubbed from session.
    assert ["set-environment", "-t", "livefleet", "-u", "CODEX_HOME"] in set_env_calls
    assert ["set-environment", "-t", "livefleet", "-u", "AURA_AGENT_PACKAGE_ID"] in set_env_calls
    assert ["set-environment", "-t", "livefleet", "-u", "AURA_AGENT_PACKAGE_ROOT"] in set_env_calls

    # Body-home key in env set on session with correct value.
    assert ["set-environment", "-t", "livefleet", "CODEX_HOME", "/state/codex-home"] in set_env_calls

    # new-window must have been issued (existing-session path).
    assert any(c[:3] == ["new-window", "-t", "livefleet"] for c in calls)


def test_tmux_create_window_no_env_does_not_scrub_session(monkeypatch, tmp_path):
    """Legacy path: when neither env nor unset_env is given, no set-environment
    calls are emitted so untouched sessions are unaffected."""
    from lib import tmux

    calls = []

    monkeypatch.setenv("AURA_TMUX_INDEX_DEFAULTS", "0")
    monkeypatch.setattr(tmux, "TMUX_SESSION", "legacyfleet")
    monkeypatch.setattr(tmux, "_session", lambda: None)
    monkeypatch.setattr(tmux, "pane_id", lambda name: "%90")

    def fake_run(args):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(tmux, "_run_tmux", fake_run)

    result = tmux.create_window("plain-seat", str(tmp_path), command="bash")

    assert result["ok"] is True
    set_env_calls = [c for c in calls if c[0] == "set-environment"]
    assert set_env_calls == [], f"unexpected set-environment calls on no-env path: {set_env_calls}"


def test_spawn_runtime_session_env_scrub_covers_full_unset_list(monkeypatch, tmp_path):
    """Integration: spawn._spawn_terminal_runtime passes the full unset_env list
    to create_window, which in turn scrubs all of them from the tmux session env,
    including the identity/home leak keys."""
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_FLEET", "isofleet")
    monkeypatch.setenv("AURA_TMUX_INDEX_DEFAULTS", "0")

    from commands import spawn
    from lib import tmux as tmux_lib

    tmux_calls = []
    original_run_tmux = tmux_lib._run_tmux

    def capturing_run_tmux(args):
        tmux_calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(tmux_lib, "TMUX_SESSION", "isofleet")
    monkeypatch.setattr(tmux_lib, "_session", lambda: None)
    monkeypatch.setattr(tmux_lib, "pane_id", lambda name: "%91")
    monkeypatch.setattr(tmux_lib, "_run_tmux", capturing_run_tmux)

    class FakeTerminal:
        SESSION_NAME = "isofleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            # Delegate to the real tmux.create_window so we exercise the full path.
            return tmux_lib.create_window(name, workdir, detached=detached, command=command, env=env, unset_env=unset_env)

        @staticmethod
        def send_text(name, text, submit=True, submit_key="Enter"):
            return {"ok": True}

        @staticmethod
        def window_exists(name):
            return False

    args = argparse.Namespace(
        name="iso-worker",
        runtime="codex",
        launch_command="codex",
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(tmp_path),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True

    set_env_calls = [c for c in tmux_calls if c[:3] == ["set-environment", "-t", "isofleet"]]

    # All identity / runtime-home keys that spawn passes in unset_env must be scrubbed.
    expected_scrubbed = [
        "CODEX_HOME",
        "AURA_AGENT_PACKAGE_ID",
        "AURA_AGENT_PACKAGE_ROOT",
        "AURA_AGENT_PACKAGE_ADDRESS",
        "AURA_AGENT_PACKAGE_ALIAS",
        "AURA_RUNTIME_CAPSULE_REF",
        "NO_COLOR",
        "AURA_RUNTIME_SESSION_ID",
        "AURA_SESSION_ID",
        "CODEX_THREAD_ID",
        "CODEX_CI",
        "CLAUDE_SESSION_ID",
    ]
    for key in expected_scrubbed:
        assert ["set-environment", "-t", "isofleet", "-u", key] in set_env_calls, (
            f"expected session-env unset for {key}"
        )


def test_spawn_runtime_session_env_sets_body_home_on_session(monkeypatch, tmp_path):
    """Integration: when spawn sets CODEX_HOME in launch_env, create_window
    propagates it to the tmux session env so runtime-created child panes
    inherit the correct body home."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "bodyfleet")
    monkeypatch.setenv("AURA_TMUX_INDEX_DEFAULTS", "0")

    from commands import spawn
    from lib import tmux as tmux_lib

    tmux_calls = []

    def capturing_run_tmux(args):
        tmux_calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(tmux_lib, "TMUX_SESSION", "bodyfleet")
    monkeypatch.setattr(tmux_lib, "_session", lambda: None)
    monkeypatch.setattr(tmux_lib, "pane_id", lambda name: "%92")
    monkeypatch.setattr(tmux_lib, "_run_tmux", capturing_run_tmux)

    unit = tmp_path / "project"
    unit.mkdir()

    class FakeTerminal:
        SESSION_NAME = "bodyfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            return tmux_lib.create_window(name, workdir, detached=detached, command=command, env=env, unset_env=unset_env)

    args = argparse.Namespace(
        name="codex-body-seat",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        runtime_profile=None,
        boxed=True,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True

    set_env_calls = [c for c in tmux_calls if c[:3] == ["set-environment", "-t", "bodyfleet"]]

    # The codex box sets CODEX_HOME in launch_env.
    # It must be forwarded to the tmux session env.
    body_home_keys_set = {
        c[3]: c[4]
        for c in set_env_calls
        if len(c) == 5 and c[3] == "CODEX_HOME"
    }
    assert "CODEX_HOME" in body_home_keys_set, f"CODEX_HOME not set on session env; set_env_calls={set_env_calls}"

    # Value must match what spawn computed (codex box root under state dir).
    assert body_home_keys_set["CODEX_HOME"].startswith(str(tmp_path / "state" / "runtime-homes"))


def test_spawn_run_does_not_precreate_tmux_session(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import spawn
    from lib import terminal as terminal_module

    calls = []

    def fail_ensure_session():
        raise AssertionError("spawn.run should let create_window create a missing fleet")

    def fake_create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
        calls.append(("create_window", name, workdir, detached, command))
        return {"ok": True, "target": f"freshfleet:{name}", "pane_id": "%79"}

    monkeypatch.setattr(terminal_module, "configure_session", lambda name: setattr(terminal_module, "SESSION_NAME", name) or name)
    monkeypatch.setattr(terminal_module, "ensure_session", fail_ensure_session)
    monkeypatch.setattr(terminal_module, "window_exists", lambda name: False)
    monkeypatch.setattr(terminal_module, "create_window", fake_create_window)

    args = argparse.Namespace(
        name="worker",
        fleet="freshfleet",
        fleet_id=None,
        runtime="command",
        launch_command="sleep 60",
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(tmp_path),
        context=None,
        resume_session=None,
        identity_provider=None,
        identity_id=None,
        identity_label=None,
    )

    result = spawn.run(args)

    assert result["ok"] is True
    assert result["fleet"] == "freshfleet"
    assert calls == [("create_window", "worker", str(tmp_path), True, "sleep 60")]


def test_command_override_uses_command_runtime_and_no_claude_trace(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            assert unset_env == [
                "NO_COLOR",
                "AURA_RUNTIME_SESSION_ID",
                "AURA_SESSION_ID",
                "CODEX_THREAD_ID",
                "CODEX_CI",
                "CLAUDE_SESSION_ID",
                "CODEX_HOME",
                "AURA_AGENT_PACKAGE_ID",
                "AURA_AGENT_PACKAGE_ROOT",
                "AURA_AGENT_PACKAGE_ADDRESS",
                "AURA_AGENT_PACKAGE_ALIAS",
                "AURA_RUNTIME_CAPSULE_REF",
            ]
            return {"ok": True}

        @staticmethod
        def send_text(name, text, submit=True, submit_key="Enter"):
            return {"ok": True, "target": f"unitfleet:{name}", "text": text}

    args = argparse.Namespace(
        name="pyseat",
        runtime=None,
        launch_command="python3 -q",
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(tmp_path),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["runtime"] == "command"
    assert result["command"] == "python3 -q"
    assert result["cwd"] == str(tmp_path)
    assert "spawn_preflight" not in result
    assert "trace_cell" not in result or result["trace_cell"] is None


def test_spawn_terminal_runtime_returns_structured_invalid_cwd(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

    args = argparse.Namespace(
        name="codex-seat",
        runtime="codex",
        resume_session=None,
        fork_session=None,
        launch_command=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(tmp_path / "missing"),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is False
    assert result["error"] == "cwd-invalid"
    assert "cwd is not a directory" in result["detail"]


def test_spawn_work_file_context_and_workspace_session_record(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_CODEX_STARTUP_READY_TIMEOUT", "0")

    from commands import spawn
    from lib import workspace_state

    unit = tmp_path / "unit"
    unit.mkdir()
    context_file = unit / "AGENTS.md"
    work_file = unit / "WORK.md"
    context_file.write_text("You are the unit agent.\n", encoding="utf-8")
    work_file.write_text("Do the unit work.\n", encoding="utf-8")

    sent = []
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True}

        @staticmethod
        def send_text(name, text, submit=True, submit_key="Enter"):
            sent.append((name, text, submit, submit_key))
            return {"ok": True, "target": f"unitfleet:{name}", "text": text}

    args = argparse.Namespace(
        name="codex-seat",
        runtime="codex",
        launch_command="printf ready",
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work="WORK.md",
        cwd=str(unit),
        context="AGENTS.md",
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert len(created) == 1
    name, workdir, detached, command, env, unset_env = created[0]
    assert (name, workdir, detached, command) == ("codex-seat", str(unit), True, "printf ready")
    assert env["AURA_AGENT_NAME"] == "codex-seat"
    assert env["AURA_SEAT"] == "codex-seat"
    assert env["AURA_FLEET"] == "unitfleet"
    assert env["AURA_RUNTIME"] == "codex"
    assert env["AURA_LAUNCH_ID"].startswith("aura-launch-")
    assert env["TERM"] == "xterm-256color"
    assert env["COLORTERM"] == "truecolor"
    assert env["FORCE_COLOR"] == "1"
    assert env["CLICOLOR_FORCE"] == "1"
    assert unset_env == [
        "NO_COLOR",
        "AURA_RUNTIME_SESSION_ID",
        "AURA_SESSION_ID",
        "CODEX_THREAD_ID",
        "CODEX_CI",
        "CLAUDE_SESSION_ID",
        "CODEX_HOME",
        "AURA_AGENT_PACKAGE_ID",
        "AURA_AGENT_PACKAGE_ROOT",
        "AURA_AGENT_PACKAGE_ADDRESS",
        "AURA_AGENT_PACKAGE_ALIAS",
        "AURA_RUNTIME_CAPSULE_REF",
    ]
    assert "Do the unit work." in sent[0][1]
    assert "launch=aura-launch-" in sent[0][1]
    assert result["prompt_delivery"]["submitted"] is True
    assert "agent_map_included" not in result["prompt_delivery"]
    assert result["context_file"] == str(context_file)
    assert result["work_file"] == str(work_file)
    assert result["spawn_preflight"]["warnings"] == ["custom-codex-command-may-remain-unbound"]

    log_path = workspace_state.workspace_session_log(unit)
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["seat"] == "codex-seat"
    assert rows[-1]["runtime"] == "codex"
    assert rows[-1]["cwd"] == str(unit)
    assert rows[-1]["work_file"] == str(work_file)
    assert rows[-1]["workspace_root"] == str(unit)
    assert rows[-1]["workspace_key"] == workspace_state.workspace_key(unit)

    workspace_metadata = json.loads(workspace_state.workspace_metadata_path(unit).read_text(encoding="utf-8"))
    assert workspace_metadata["workspace_root"] == str(unit)
    assert workspace_metadata["workspace_key"] == workspace_state.workspace_key(unit)
    assert json.loads(workspace_state.latest_session_path(unit).read_text(encoding="utf-8"))["seat"] == "codex-seat"
    assert not (unit / ".aura" / "state").exists()
    assert not (unit / ".aura").exists()


def test_resolve_package_env_sets_codex_home_for_codex_package(tmp_path):
    from commands import spawn

    root = tmp_path / "i_scout"
    env, meta = spawn._resolve_package_env(
        {"root": str(root), "env": {"CODEX_HOME": ".codex"}},
        "codex",
    )
    assert env["CODEX_HOME"] == str((root / ".codex").resolve())
    assert meta == {}


def test_codex_package_spawn_sets_own_codex_home_over_contaminated_parent(monkeypatch, tmp_path):
    # Regression: a non-boxed codex package spawn must wire its OWN CODEX_HOME and
    # never inherit the spawner's (the factory-v2 fleet contamination class, where a
    # manager seat spawned a crew and every child read the manager's package body).
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_CODEX_STARTUP_READY_TIMEOUT", "0")
    # Contaminated parent environment (manager body) inherited by the spawn process.
    manager_root = tmp_path / "i_manager"
    monkeypatch.setenv("CODEX_HOME", str(manager_root / ".codex"))
    monkeypatch.setenv("AURA_AGENT_PACKAGE_ID", "i_manager")
    monkeypatch.setenv("AURA_AGENT_PACKAGE_ROOT", str(manager_root))

    from commands import spawn

    pkg_root = tmp_path / "i_scout"
    (pkg_root / ".codex").mkdir(parents=True)

    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((env, unset_env))
            return {"ok": True}

        @staticmethod
        def send_text(name, text, submit=True, submit_key="Enter"):
            return {"ok": True, "target": f"unitfleet:{name}", "text": text}

    args = argparse.Namespace(
        name="scout",
        runtime="codex",
        launch_command="printf ready",
        profile=None,
        runtime_profile=None,
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(tmp_path),
        context=None,
        _agent_package={
            "agent_id": "i_scout",
            "address": None,
            "alias": "shopify-scout",
            "root": str(pkg_root),
            "runtime": "codex",
            "argv": None,
            "env": {"CODEX_HOME": ".codex"},
        },
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True, result
    assert len(created) == 1
    env, unset_env = created[0]
    # Own home wins, not the inherited manager home.
    assert env["CODEX_HOME"] == str((pkg_root / ".codex").resolve())
    assert env["AURA_AGENT_PACKAGE_ROOT"] == str(pkg_root)
    assert env["AURA_AGENT_PACKAGE_ID"] == "i_scout"
    # Backstop: inherited identity/home vars are scrubbed so an unset can never leak.
    for key in (
        "CODEX_HOME",
        "AURA_AGENT_PACKAGE_ID",
        "AURA_AGENT_PACKAGE_ROOT",
        "AURA_RUNTIME_CAPSULE_REF",
    ):
        assert key in unset_env


def test_spawn_non_codex_does_not_claim_agent_map_injected(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "unit"
    unit.mkdir()
    sent = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%55"}

        @staticmethod
        def send_text(name, text, submit=True, submit_key="Enter"):
            sent.append((name, text, submit, submit_key))
            return {"ok": True}

    args = argparse.Namespace(
        name="shell-seat",
        runtime="command",
        resume_session=None,
        launch_command="bash",
        profile=None,
        model=None,
        as_pane=True,
        prompt="hello",
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert "agent_map_included" not in result["prompt_delivery"]
    assert sent[0][1] == "hello"


def test_spawn_hermes_profile_behavior_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    home = tmp_path / "home"
    (home / ".hermes" / "profiles" / "hermes-prof").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%79"}

    args = argparse.Namespace(
        name="hermes-seat",
        runtime="hermes",
        resume_session=None,
        launch_command=None,
        profile="hermes-prof",
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["runtime"] == "hermes"
    assert result["profile"] == "hermes-prof"
    assert result["runtime_profile_ref"] == "hermes/hermes-prof"
    assert result["command"] == "hermes -p hermes-prof"
    assert created[0][3] == "hermes -p hermes-prof"


def test_spawn_hermes_without_profile_uses_native_default(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    home = tmp_path / "home"
    (home / ".hermes").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%80"}

    args = argparse.Namespace(
        name="Hermes",
        runtime="hermes",
        resume_session=None,
        launch_command=None,
        profile=None,
        runtime_profile=None,
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["runtime"] == "hermes"
    assert result.get("profile") is None
    assert result["runtime_profile_ref"] == "hermes/default"
    assert result["runtime_home"] == str(home / ".hermes")
    assert result["command"] == "hermes"
    assert created[0][3] == "hermes"


def test_spawn_hermes_missing_explicit_profile_fails_before_terminal(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    home = tmp_path / "home"
    (home / ".hermes").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%81"}

    args = argparse.Namespace(
        name="Hermes",
        runtime="hermes",
        resume_session=None,
        launch_command=None,
        profile="missing",
        runtime_profile=None,
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is False
    assert result["error"] == "runtime-profile-not-found"
    assert result["runtime_profile_ref"] == "hermes/missing"
    assert created == []


def test_spawn_hermes_runtime_profile_ref_uses_named_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    home = tmp_path / "home"
    (home / ".hermes" / "profiles" / "aura-operator").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%82"}

    args = argparse.Namespace(
        name="hermes-seat",
        runtime="hermes",
        resume_session=None,
        launch_command=None,
        profile=None,
        runtime_profile="hermes/aura-operator",
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["profile"] == "aura-operator"
    assert result["runtime_profile_ref"] == "hermes/aura-operator"
    assert result["runtime_home"] == str(home / ".hermes" / "profiles" / "aura-operator")
    assert result["command"] == "hermes -p aura-operator"
    assert created[0][3] == "hermes -p aura-operator"


def test_spawn_hermes_runtime_profile_default_uses_root_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    home = tmp_path / "home"
    (home / ".hermes").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%83"}

    args = argparse.Namespace(
        name="hermes-seat",
        runtime="hermes",
        resume_session=None,
        launch_command=None,
        profile=None,
        runtime_profile="hermes/default",
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["profile"] == "default"
    assert result["runtime_profile_ref"] == "hermes/default"
    assert result["runtime_home"] == str(home / ".hermes")
    assert result["command"] == "hermes"
    assert created[0][3] == "hermes"


def test_spawn_codex_unboxed_behavior_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%80"}

    args = argparse.Namespace(
        name="codex-seat",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        runtime_profile=None,
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["runtime"] == "codex"
    assert result["command"] == "codex --dangerously-bypass-approvals-and-sandbox"
    assert "profile" not in result
    assert "runtime_home" not in result
    assert "native_state_ref" not in result
    assert "codex_isolation" not in result
    env = created[0][4]
    assert "CODEX_HOME" not in env
    assert "AURA_CODEX_BOX" not in env
    assert not (unit / ".codex").exists()


def test_spawn_codex_runtime_profile_uses_aura_box(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    source_codex_home = tmp_path / "source-codex"
    source_codex_home.mkdir()
    (source_codex_home / "auth.json").write_text('{"token":"unit"}\n', encoding="utf-8")
    (source_codex_home / "config.toml").write_text("model = 'unit'\n", encoding="utf-8")
    monkeypatch.setenv("AURA_STATE_DIR", str(state_dir))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(state_dir / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_CODEX_SOURCE_CODEX_HOME", str(source_codex_home))

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    profile_root = state_dir / "runtime-profiles" / "codex" / "dev"
    codex_template = profile_root / "codex-home-template"
    codex_template.mkdir(parents=True)
    (codex_template / "profile-note.md").write_text("codex profile\n", encoding="utf-8")
    (codex_template / "keep-existing.md").write_text("template\n", encoding="utf-8")

    box_codex_home = state_dir / "runtime-homes" / "codex" / "unitfleet" / "codex-profile-seat" / "codex-home"
    box_codex_home.mkdir(parents=True)
    (box_codex_home / "keep-existing.md").write_text("existing\n", encoding="utf-8")

    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%81"}

    args = argparse.Namespace(
        name="codex-profile-seat",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        runtime_profile="codex/dev",
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["runtime"] == "codex"
    assert result["profile"] == "dev"
    assert result["runtime_profile"] == "dev"
    assert result["runtime_profile_ref"] == "codex/dev"
    assert result["runtime_profile_source"] == "cli-runtime-profile"
    assert result["codex_isolation"] == "aura-seat-box"
    assert result["codex_profile"] == "dev"
    assert result["codex_profile_root"] == str(profile_root)
    assert result["codex_profile_applied"] is True
    assert result["codex_profile_templates_applied"] == ["codex-home-template"]
    assert result["runtime_home"] == str(state_dir / "runtime-homes" / "codex" / "unitfleet" / "codex-profile-seat")
    assert result["native_state_ref"] == str(box_codex_home)
    assert (box_codex_home / "profile-note.md").read_text(encoding="utf-8") == "codex profile\n"
    assert (box_codex_home / "keep-existing.md").read_text(encoding="utf-8") == "existing\n"
    assert (box_codex_home / "auth.json").is_file()
    assert (box_codex_home / "config.toml").is_file()
    assert not (unit / ".codex").exists()
    assert not (unit / ".omx").exists()

    _, workdir, _, command, env, _ = created[0]
    assert workdir == str(unit)
    assert command == "codex --dangerously-bypass-approvals-and-sandbox"
    assert env["HOME"] == str(state_dir / "runtime-homes" / "codex" / "unitfleet" / "codex-profile-seat" / "home")
    assert env["CODEX_HOME"] == str(box_codex_home)
    assert env["AURA_CODEX_BOX"] == str(state_dir / "runtime-homes" / "codex" / "unitfleet" / "codex-profile-seat")
    assert env["AURA_CODEX_PROFILE"] == "dev"


def test_spawn_codex_boxed_without_profile(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setenv("AURA_STATE_DIR", str(state_dir))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(state_dir / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%82"}

    args = argparse.Namespace(
        name="codex-boxed-seat",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        runtime_profile=None,
        boxed=True,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["codex_isolation"] == "aura-seat-box"
    assert "profile" not in result
    assert result["runtime_home"] == str(state_dir / "runtime-homes" / "codex" / "unitfleet" / "codex-boxed-seat")
    assert created[0][4]["CODEX_HOME"] == str(
        state_dir / "runtime-homes" / "codex" / "unitfleet" / "codex-boxed-seat" / "codex-home"
    )
    assert not (unit / ".codex").exists()


def test_spawn_codex_runtime_profile_mismatch_fails_before_terminal(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(*args, **kwargs):
            raise AssertionError("mismatched runtime profile should fail before creating a terminal")

    args = argparse.Namespace(
        name="codex-seat",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        runtime_profile="omx/dev",
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is False
    assert result["error"] == "invalid-runtime-profile"
    assert "selected runtime codex" in result["detail"]


@pytest.mark.parametrize(
    "runtime_profile",
    [
        "codex/..",
        "codex/.",
        "codex/dev profile",
        "codex/dev//extra",
        "/codex/dev",
    ],
)
def test_spawn_runtime_profile_rejects_unsafe_refs_before_terminal(monkeypatch, tmp_path, runtime_profile):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(*args, **kwargs):
            raise AssertionError("unsafe runtime profile should fail before creating a terminal")

    args = argparse.Namespace(
        name="codex-seat",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        runtime_profile=runtime_profile,
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is False
    assert result["error"] == "invalid-runtime-profile"


def test_spawn_codex_missing_runtime_profile_fails_before_terminal(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(*args, **kwargs):
            raise AssertionError("missing runtime profile should fail before creating a terminal")

    args = argparse.Namespace(
        name="codex-seat",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        runtime_profile="codex/missing",
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is False
    assert result["error"] == "codex-box-setup-failed"
    assert "codex runtime profile not found" in result["detail"]


def test_spawn_sets_flex_project_env_without_launch_packet(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_CODEX_STARTUP_READY_TIMEOUT", "0")

    from commands import spawn

    unit = tmp_path / "unit"
    main = unit / "main"
    flex_dir = unit / ".flex"
    flex_dir.mkdir(parents=True)
    main.mkdir()
    (flex_dir / "project.yaml").write_text(
        "version: 1\nproject:\n  name: demo-unit\ncommands: {}\n",
        encoding="utf-8",
    )

    sent = []
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True}

        @staticmethod
        def send_text(name, text, submit=True, submit_key="Enter"):
            sent.append((name, text, submit, submit_key))
            return {"ok": True, "target": f"unitfleet:{name}", "text": text}

    args = argparse.Namespace(
        name="codex-seat",
        runtime="codex",
        launch_command="printf ready",
        profile=None,
        model=None,
        as_pane=True,
        prompt="Begin.",
        work=None,
        cwd=str(main),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["flex_project_manifest"] == str(flex_dir / "project.yaml")
    assert result["flex_project_root"] == str(unit)
    env = created[0][4]
    assert env["FLEX_PROJECT_MANIFEST"] == str(flex_dir / "project.yaml")
    assert env["FLEX_PROJECT_ROOT"] == str(unit)
    text = sent[0][1]
    assert "[FLEX PROJECT RETRIEVAL]" not in text
    assert text.endswith("Begin.")
    # The augmented prompt must carry the nonce marker so the Codex session can
    # be auto-bound via _codex_session_from_nonce after spawn.
    assert "launch=aura-launch-" in text
    assert "flex_project_packet_delivered" not in result


def test_seat_inject_flex_skips_when_project_packet_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))

    unit = tmp_path / "unit"
    main = unit / "main"
    flex_dir = unit / ".flex"
    main.mkdir(parents=True)
    flex_dir.mkdir(parents=True)
    (flex_dir / "project.yaml").write_text("project:\n  name: demo-unit\n", encoding="utf-8")

    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "engineer",
        "fleet": "unitfleet",
        "runtime": "codex",
        "cwd": str(main),
        "pane_ref": "tmux:unitfleet:%1",
        "terminal_ref": "unitfleet:engineer",
    })

    sent = []

    class FakeTerminal:
        @staticmethod
        def configure_session(name):
            return name

        @staticmethod
        def target_exists(target):
            return target == "tmux:unitfleet:%1"

        @staticmethod
        def capture_output(target, lines=5000):
            return ["ready"]

        @staticmethod
        def send_text(target, text, submit=True):
            sent.append((target, text, submit))
            return {"ok": True, "target": target, "submitted": submit}

    result = seat._inject_flex(
        argparse.Namespace(target="unitfleet:engineer", force=False, dry_run=False, capture_lines=100),
        registry,
        FakeTerminal,
    )

    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "flex-project-packet-disabled"
    assert sent == []


def test_seat_inject_flex_disabled_even_with_existing_project_packet(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))

    unit = tmp_path / "unit"
    main = unit / "main"
    flex_dir = unit / ".flex"
    main.mkdir(parents=True)
    flex_dir.mkdir(parents=True)
    manifest = flex_dir / "project.yaml"
    manifest.write_text("project:\n  name: demo-unit\n", encoding="utf-8")

    from commands import seat
    from lib import registry

    registry.upsert_agent({
        "name": "engineer",
        "fleet": "unitfleet",
        "runtime": "codex",
        "cwd": str(main),
        "pane_ref": "tmux:unitfleet:%1",
    })

    class FakeTerminal:
        @staticmethod
        def configure_session(name):
            return name

        @staticmethod
        def target_exists(target):
            return True

        @staticmethod
        def capture_output(target, lines=5000):
            return [
                "[FLEX PROJECT RETRIEVAL]",
                f"manifest={manifest}",
                "[/FLEX PROJECT RETRIEVAL]",
            ]

        @staticmethod
        def send_text(target, text, submit=True):
            raise AssertionError("packet should not be sent twice")

    result = seat._inject_flex(
        argparse.Namespace(target="unitfleet:engineer", force=False, dry_run=False, capture_lines=100),
        registry,
        FakeTerminal,
    )

    assert result["ok"] is True
    assert result["skipped"] is True
    assert result["reason"] == "flex-project-packet-disabled"


def test_codex_runtime_default_uses_noninteractive_approval_flags():
    from lib import runtimes

    runtime, spec = runtimes.resolve_runtime("codex")
    command = runtimes.build_command(runtime, spec, name="ops", profile=None)

    assert command == "codex --dangerously-bypass-approvals-and-sandbox"


def test_claude_code_terminal_runtime_default_uses_noninteractive_approval_flags():
    from lib import runtimes

    runtime, spec = runtimes.resolve_runtime("claude-code")
    command = runtimes.build_command(runtime, spec, name="worker", profile=None)

    assert command == "claude --dangerously-skip-permissions"


def test_runtime_session_discovers_codex_thread_from_pane_process(monkeypatch):
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
    merged = runtime_session.merge({"name": "engineer"}, result)
    assert merged["session_id"] == "019dd2b7-8919-75d2-b472-7c778a93da92"


def test_terminal_backend_exports_pane_pid():
    from lib import terminal

    assert hasattr(terminal, "pane_pid")


def test_capture_sense_and_watch_commands_are_public_contract_names():
    help_result = subprocess.run(
        [sys.executable, str(CLI), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert help_result.returncode == 0
    assert "Agent-safe verbs: spawn, send, queue, report, view, inspect, event, placement." in help_result.stdout
    assert "Operator tools: seat, agent, skills, keeper, profile" in help_result.stdout
    assert "capture" in help_result.stdout
    assert "stop" not in help_result.stdout
    assert "ledger" not in help_result.stdout
    assert "rename" not in help_result.stdout
    assert "start" not in help_result.stdout
    assert "sense" in help_result.stdout
    assert "watch" in help_result.stdout
    assert "posture" in help_result.stdout
    assert "write" in help_result.stdout
    assert "dash" in help_result.stdout
    assert "event" in help_result.stdout
    assert "check" not in help_result.stdout
    assert "route" not in help_result.stdout
    assert "ether" not in help_result.stdout
    assert "sleep" not in help_result.stdout
    assert "set" not in help_result.stdout
    assert "==SUPPRESS==" not in help_result.stdout
    assert "--json" not in help_result.stdout


def test_archived_diagnostic_commands_are_not_cli_entrypoints():
    for command in ("route", "ether", "sleep", "set"):
        result = subprocess.run(
            [sys.executable, str(CLI), command, "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        assert result.returncode != 0
        assert "invalid choice" in result.stderr


def test_posture_cli_dispatches_to_posture_command(tmp_path):
    result = subprocess.run(
        [sys.executable, str(CLI), "posture"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={
            **os.environ,
            "AURA_STATE_DIR": str(tmp_path / ".aura"),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )

    assert result.returncode == 1
    assert json.loads(result.stdout) == {
        "ok": False,
        "error": "posture requires a seat name or --fleet",
    }


def test_cli_output_is_json_even_when_stdout_is_tty(monkeypatch, capsys):
    from lib.output import output

    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    output([{"name": "worker", "status": "idle"}])

    assert json.loads(capsys.readouterr().out) == [{"name": "worker", "status": "idle"}]


def test_event_start_uses_uuid_job_dir_and_name_index(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))

    result = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "event",
            "start",
            "--name",
            "flexgraph-ops",
            "--target",
            "operations-leader",
            "--as",
            "operations",
            "--every",
            "180",
            "--ticks",
            "40",
            "--template",
            "ops cadence tick {tick}/{ticks} run={run_id}",
            "--run-id",
            "unit-run",
            "--no-daemon",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={**os.environ, "AURA_STATE_DIR": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    job = data["job"]
    assert job["job_id"].startswith("evt_")
    assert job["name"] == "flexgraph-ops"
    assert job["target"] == "operations-leader"
    assert (tmp_path / "events" / "jobs" / job["job_id"] / "state.json").exists()
    assert not (tmp_path / "events" / "jobs" / "flexgraph-ops").exists()

    status = subprocess.run(
        [sys.executable, str(CLI), "event", "status", "flexgraph-ops"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={**os.environ, "AURA_STATE_DIR": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["job"]["job_id"] == job["job_id"]


def test_event_tick_updates_state_without_killing_job_on_delivery_error(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))

    from commands import event

    args = argparse.Namespace(
        name="ops",
        target="operations-leader",
        sender="operations",
        every=180,
        ticks=2,
        template="tick {tick}/{ticks}",
        run_id="unit-run",
        start_delay=0,
        no_daemon=True,
    )
    job = event._make_job(args)
    from lib import events

    events.save_state(job)
    events.index_name("ops", job["job_id"])

    monkeypatch.setattr(
        event,
        "_deliver",
        lambda job, tick: {
            "ok": False,
            "message_id": "aura-msg-unit",
            "stderr": "simulated delivery failure",
            "submitted_verified": False,
        },
    )
    result = event._tick(events.load_state(job["job_id"]), force=True)
    saved = events.load_state(job["job_id"])

    assert result["ran"] is True
    assert result["ok"] is False
    assert saved["status"] == "running"
    assert saved["tick"] == 0
    assert saved["consecutive_errors"] == 1
    assert saved["last_error"] == "simulated delivery failure"


def test_event_tick_skips_busy_target_without_consuming_tick(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))

    from commands import event
    from lib import events

    args = argparse.Namespace(
        name="ops",
        target="manager",
        sender="operations",
        every=180,
        ticks=2,
        template="tick {tick}/{ticks}",
        run_id="unit-run",
        start_delay=0,
        no_daemon=True,
    )
    job = event._make_job(args)
    events.save_state(job)
    events.index_name("ops", job["job_id"])

    monkeypatch.setattr(
        event,
        "_deliver",
        lambda job, tick: {
            "ok": True,
            "skipped": True,
            "reason": "target-busy",
            "submitted_verified": None,
        },
    )

    result = event._tick(events.load_state(job["job_id"]), force=True)
    saved = events.load_state(job["job_id"])

    assert result["ran"] is True
    assert result["ok"] is True
    assert result["delivery"]["skipped"] is True
    assert saved["status"] == "running"
    assert saved["tick"] == 0
    assert saved["last_delivery"]["reason"] == "target-busy"
    assert saved["consecutive_errors"] == 0


def test_event_update_mutates_interval_job_and_name_index(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))

    from commands import event
    from lib import events

    job = event._make_job(argparse.Namespace(
        name="ops",
        target="manager",
        sender="operations",
        every=180,
        ticks=2,
        template="tick {tick}/{ticks}",
        run_id="unit-run",
        start_delay=0,
        no_daemon=True,
    ))
    events.save_state(job)
    events.index_name("ops", job["job_id"])

    result = event.run(argparse.Namespace(
        event_action="update",
        ref="ops",
        name="ops-renamed",
        target="lead",
        sender="aura-event",
        every=60,
        ticks=None,
        clear_ticks=True,
        template="new tick {tick}",
        start_delay=10,
    ))

    assert result["ok"] is True
    assert result["changes"]["target"] == "lead"
    assert result["changes"]["interval_seconds"] == 60.0
    assert result["changes"]["ticks"] is None
    saved = events.load_state(job["job_id"])
    assert saved["name"] == "ops-renamed"
    assert saved["target"] == "lead"
    assert saved["sender"] == "aura-event"
    assert saved["interval_seconds"] == 60.0
    assert saved["ticks"] is None
    assert saved["template"] == "new tick {tick}"
    assert events.resolve_job_id("ops-renamed") == job["job_id"]
    with pytest.raises(FileNotFoundError):
        events.resolve_job_id("ops")


def test_event_retire_stops_job_without_deleting_state(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))

    from commands import event
    from lib import events

    job = event._make_job(argparse.Namespace(
        name="ops",
        target="manager",
        sender="operations",
        every=180,
        ticks=2,
        template="tick {tick}/{ticks}",
        run_id="unit-run",
        start_delay=0,
        no_daemon=True,
    ))
    events.save_state(job)
    events.index_name("ops", job["job_id"])

    result = event.run(argparse.Namespace(event_action="retire", ref="ops"))

    assert result["ok"] is True
    saved = events.load_state(job["job_id"])
    assert saved["status"] == "retired"
    assert saved["next_tick_at"] is None
    assert saved["running_at"] is None
    assert events.resolve_job_id("ops") == job["job_id"]


def test_event_status_and_list_include_operator_summary(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))

    from commands import event
    from lib import events

    job = event._make_job(argparse.Namespace(
        name="ops",
        target="manager",
        sender="operations",
        every=180,
        ticks=2,
        template="tick {tick}/{ticks}",
        run_id="unit-run",
        start_delay=0,
        no_daemon=True,
    ))
    job["last_tick_at"] = "2026-05-26T10:40:00+00:00"
    job["last_error"] = "simulated failure"
    job["consecutive_errors"] = 2
    events.save_state(job)
    events.index_name("ops", job["job_id"])

    status = event.run(argparse.Namespace(event_action="status", ref="ops"))
    listed = event.run(argparse.Namespace(event_action="list"))

    assert status["ok"] is True
    assert status["summary"]["owner"] == "operations"
    assert status["summary"]["target"] == "manager"
    assert status["summary"]["schedule"]["interval_seconds"] == 180.0
    assert status["summary"]["last_run_at"] == "2026-05-26T10:40:00+00:00"
    assert status["summary"]["next_run_at"].endswith("Z")
    assert status["summary"]["failure"] == {
        "last_error": "simulated failure",
        "consecutive_errors": 2,
    }
    assert listed["job_summaries"][0]["job_id"] == job["job_id"]


def test_event_target_blocker_detects_active_composer(monkeypatch):
    from commands import event

    def fake_run(cmd, text=True, capture_output=True, env=None):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=json.dumps({
                "ok": True,
                "status": "idle",
                "terminal": "alive",
                "output": [
                    "› human draft in progress",
                    "",
                    "  gpt-5.5 medium · ~/project",
                ],
            }),
            stderr="",
        )

    monkeypatch.setattr(event.subprocess, "run", fake_run)

    result = event._target_is_busy("manager")

    assert result["ok"] is True
    assert result["busy"] is False
    assert result["blocker"] is None


def test_spawn_runtime_choices_include_shell():
    help_result = subprocess.run(
        [sys.executable, str(CLI), "spawn", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert help_result.returncode == 0
    assert "shell" in help_result.stdout
    assert "--cwd" in help_result.stdout
    assert "--work" in help_result.stdout
    assert "--context" in help_result.stdout
    assert "--fork-session" in help_result.stdout


def test_stop_uses_runtime_specific_graceful_exit(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import cut
    from lib import registry

    sent = []
    killed = []
    sessions = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def configure_session(name):
            sessions.append(name)
            FakeTerminal.SESSION_NAME = name

        @staticmethod
        def window_exists(name):
            return name not in killed

        @staticmethod
        def send_text(name, text, submit=True, submit_key="Enter"):
            sent.append((name, text, submit, submit_key))
            return {"ok": True}

        @staticmethod
        def kill_window(name):
            killed.append(name)
            return {"ok": True}

    import lib.terminal as terminal_module
    import lib.mesh as mesh_module

    monkeypatch.setattr(terminal_module, "configure_session", FakeTerminal.configure_session)
    monkeypatch.setattr(terminal_module, "window_exists", FakeTerminal.window_exists)
    monkeypatch.setattr(terminal_module, "send_text", FakeTerminal.send_text)
    monkeypatch.setattr(terminal_module, "kill_window", FakeTerminal.kill_window)
    monkeypatch.setattr(mesh_module, "unregister", lambda name: {"ok": True})

    registry.upsert_agent({"name": "shellseat", "fleet": "unitfleet", "runtime": "shell", "registered": True})
    result = cut.run(argparse.Namespace(name="shellseat", force=False))

    assert result["ok"] is True
    assert result["graceful_attempted"] is True
    assert result["graceful_exit"] == "exit"
    assert sent[0][1] == "exit"
    assert sessions == ["unitfleet"]
    assert registry.get_agent("shellseat", fleet="unitfleet")["status"] == "dead"

    registry.upsert_agent({"name": "futureseat", "fleet": "unitfleet", "runtime": "future-runtime", "registered": True})
    result = cut.run(argparse.Namespace(name="futureseat", force=True))

    assert result["ok"] is True
    assert result["force"] is True
    assert result["graceful_attempted"] is False
    assert result["graceful_exit"] is None
    assert sent == [("shellseat", "exit", True, "Enter")]
    assert registry.get_agent("futureseat", fleet="unitfleet")["status"] == "dead"


def test_sense_uses_watch_stability_for_stuck_state(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SENSE_MODE", "heuristic")
    monkeypatch.setenv("AURA_SENSE_TTL_SECONDS", "11")

    from commands import check, sense
    from lib import registry, state

    registry.upsert_agent({"name": "busyseat", "fleet": "unitfleet", "runtime": "command", "registered": True})
    watch_dir = state.seat_dir("busyseat") / "watch"
    watch_dir.mkdir(parents=True)
    (watch_dir / "latest.json").write_text(json.dumps({
        "stable_count": 3,
        "silence_seconds": 15.0,
        "output_changed": False,
    }))

    monkeypatch.setattr(check, "run", lambda args: {
        "ok": True,
        "name": "busyseat",
        "fleet": "unitfleet",
        "runtime": "command",
        "status": "alive",
        "terminal": "alive",
        "terminal_ref": "tmux:unitfleet:busyseat",
        "output": ["BUSY busyseat"],
    })

    record = sense.run(argparse.Namespace(name="busyseat", lines=40, question=None, features=None))

    assert record["state"] == "stuck"
    assert record["capture_state"] == "live"
    assert record["freshness"] == "fresh"
    assert record["stale"] is False
    assert record["ttl_seconds"] == 11
    assert record["cache_owner"] == "aura"
    assert record["cache_key"] == "sense:busyseat"
    assert record["freshness_checked_at"] == record["at"]
    assert record["next_action"] == "inspect"
    assert record["source"]["watch"]["stable_count"] == 3
    assert any("stable for 3" in item for item in record["evidence"])


def test_sense_llm_mode_uses_structured_local_llm(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import check, sense
    from lib import registry, terminal_semantic_sense

    registry.upsert_agent({"name": "approvalseat", "fleet": "unitfleet", "runtime": "command", "registered": True})
    monkeypatch.setattr(check, "run", lambda args: {
        "ok": True,
        "name": "approvalseat",
        "fleet": "unitfleet",
        "runtime": "command",
        "status": "alive",
        "terminal": "alive",
        "terminal_ref": "tmux:unitfleet:approvalseat",
        "output": ["Do you want to proceed? [y/N]"],
    })
    monkeypatch.setattr(terminal_semantic_sense.local_llm, "ollama_chat", lambda *args, **kwargs: json.dumps({
        "state": "needs_human",
        "confidence": 0.91,
        "summary": "The seat is waiting for operator approval.",
        "next_action": "escalate",
        "evidence": ["Do you want to proceed? [y/N]"],
        "role": "worker",
        "current_task": "waiting for approval",
        "last_meaningful_event": "requested confirmation",
        "blockers": ["operator approval"],
        "features": {"awaiting_approval": True},
    }))

    record = sense.run(argparse.Namespace(
        name="approvalseat",
        lines=40,
        question=None,
        features="awaiting_approval",
        sense_mode="llm",
        model="local-test",
        llm_timeout=1,
        ollama_host="http://ollama.test",
    ))

    assert record["ok"] is True
    assert record["state"] == "needs_human"
    assert record["next_action"] == "escalate"
    assert record["source"]["sense_backend"] == "llm"
    assert record["source"]["llm"]["model"] == "local-test"
    assert record["features"]["awaiting_approval"] is True
    assert record["blockers"] == ["operator approval"]


def test_llm_sense_clamps_inconsistent_action_for_state():
    from lib import terminal_semantic_sense

    record = terminal_semantic_sense._coerce_result({
        "state": "ready",
        "confidence": 0.8,
        "next_action": "wait",
        "summary": "ready",
    }, None)

    assert record["state"] == "ready"
    assert record["next_action"] == "send"


def test_sense_llm_mode_supports_inline_contract(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import check, sense
    from lib import registry, terminal_semantic_sense

    registry.upsert_agent({"name": "workerseat", "fleet": "unitfleet", "runtime": "command", "registered": True})
    monkeypatch.setattr(check, "run", lambda args: {
        "ok": True,
        "name": "workerseat",
        "fleet": "unitfleet",
        "runtime": "command",
        "status": "alive",
        "terminal": "alive",
        "terminal_ref": "tmux:unitfleet:workerseat",
        "output": ["DONE wrote report.md", "READY workerseat"],
    })
    monkeypatch.setattr(terminal_semantic_sense.local_llm, "ollama_chat", lambda *args, **kwargs: json.dumps({
        "state": "done",
        "confidence": 0.88,
        "summary": "The worker completed the report.",
        "next_action": "capture",
        "evidence": ["DONE wrote report.md"],
        "contract_result": {
            "handoff_ready": "yes",
            "blocked_by": None,
            "next_step": "review report.md",
            "files_changed": "report.md",
        },
    }))

    contract = json.dumps({
        "name": "handoff",
        "fields": {
            "handoff_ready": "boolean",
            "blocked_by": "string|null",
            "next_step": {"type": "string", "required": True},
            "files_changed": "array",
        },
    })
    record = sense.run(argparse.Namespace(
        name="workerseat",
        lines=40,
        question=None,
        features=None,
        contract=contract,
        sense_mode="llm",
        model="local-test",
        llm_timeout=1,
        ollama_host="http://ollama.test",
    ))

    assert record["ok"] is True
    assert record["state"] == "done"
    assert record["contract"]["name"] == "handoff"
    assert record["contract"]["required"] == ["next_step"]
    assert record["contract_result"] == {
        "handoff_ready": True,
        "blocked_by": None,
        "next_step": "review report.md",
        "files_changed": ["report.md"],
    }


def test_sense_auto_mode_falls_back_when_llm_unavailable(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import check, sense
    from lib import registry, terminal_semantic_sense

    registry.upsert_agent({"name": "readyseat", "fleet": "unitfleet", "runtime": "command", "registered": True})
    monkeypatch.setattr(check, "run", lambda args: {
        "ok": True,
        "name": "readyseat",
        "fleet": "unitfleet",
        "runtime": "command",
        "status": "alive",
        "terminal": "alive",
        "terminal_ref": "tmux:unitfleet:readyseat",
        "output": ["READY readyseat"],
    })
    monkeypatch.setattr(terminal_semantic_sense.local_llm, "ollama_chat", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    record = sense.run(argparse.Namespace(
        name="readyseat",
        lines=40,
        question=None,
        features=None,
        sense_mode="auto",
        model="local-test",
        llm_timeout=1,
        ollama_host="http://ollama.test",
    ))

    assert record["ok"] is True
    assert record["state"] == "ready"
    assert record["source"]["sense_backend"] == "heuristic"
    assert record["source"]["fallback_used"] is True
    assert "offline" in record["source"]["llm_error"]


def test_watch_reuses_previous_sense_when_output_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import check, sense, watch
    from lib import registry

    registry.upsert_agent({"name": "steadyseat", "fleet": "unitfleet", "runtime": "command", "registered": True})
    monkeypatch.setattr(check, "run", lambda args: {
        "ok": True,
        "name": "steadyseat",
        "fleet": "unitfleet",
        "runtime": "command",
        "status": "alive",
        "terminal": "alive",
        "terminal_ref": "tmux:unitfleet:steadyseat",
        "output": ["READY steadyseat"],
    })

    calls = []

    def fake_sense_run(args):
        calls.append(args.name)
        return {
            "ok": True,
            "schema": "aura.sense.v1",
            "type": "sense",
            "sense_id": f"sense-{len(calls)}",
            "seat": args.name,
            "name": args.name,
            "at": watch._now(),
            "state": "ready",
            "confidence": 0.9,
            "next_action": "send",
            "summary": "ready",
            "evidence": ["READY steadyseat"],
        }

    monkeypatch.setattr(sense, "run", fake_sense_run)
    args = argparse.Namespace(
        name="steadyseat",
        lines=40,
        question=None,
        features=None,
        no_sense=False,
        sense=True,
        fresh_sense=False,
        sense_mode="llm",
        model="local-test",
        llm_timeout=1,
        ollama_host="http://ollama.test",
        contract=None,
    )

    first = watch.sample(args)
    second = watch.sample(args)

    assert len(calls) == 1
    assert first["sense_reused"] is False
    assert second["output_changed"] is False
    assert second["stable_count"] == 1
    assert second["sense_reused"] is True
    assert second["sense"]["sense_id"] == "sense-1"
    assert second["sense"]["freshness"] == "fresh"
    assert second["sense"]["stale"] is False
    assert second["sense"]["reused_age_seconds"] is not None
    assert second["sense"]["unchanged"] is True
    assert second["sense"]["reused_from_watch_id"] == first["watch_id"]

    args.fresh_sense = True
    third = watch.sample(args)
    assert len(calls) == 2
    assert third["sense_reused"] is False


def test_watch_runs_fresh_sense_when_previous_reuse_is_stale(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_SENSE_TTL_SECONDS", "1")

    from commands import check, sense, watch
    from lib import registry

    registry.upsert_agent({"name": "staleseat", "fleet": "unitfleet", "runtime": "command", "registered": True})
    monkeypatch.setattr(check, "run", lambda args: {
        "ok": True,
        "name": "staleseat",
        "fleet": "unitfleet",
        "runtime": "command",
        "status": "alive",
        "terminal": "alive",
        "terminal_ref": "tmux:unitfleet:staleseat",
        "output": ["READY staleseat"],
    })

    calls = []

    def fake_sense_run(args):
        calls.append(args.name)
        return {
            "ok": True,
            "schema": "aura.sense.v1",
            "type": "sense",
            "sense_id": f"sense-{len(calls)}",
            "seat": args.name,
            "name": args.name,
            "at": "1970-01-01T00:00:00+00:00" if len(calls) == 1 else watch._now(),
            "state": "ready",
            "confidence": 0.9,
            "next_action": "send",
            "summary": "ready",
            "evidence": ["READY staleseat"],
        }

    monkeypatch.setattr(sense, "run", fake_sense_run)
    args = argparse.Namespace(
        name="staleseat",
        lines=40,
        question=None,
        features=None,
        no_sense=False,
        sense=True,
        fresh_sense=False,
        sense_mode="llm",
        model="local-test",
        llm_timeout=1,
        ollama_host="http://ollama.test",
        contract=None,
    )

    first = watch.sample(args)
    second = watch.sample(args)

    assert first["sense_reused"] is False
    assert second["output_changed"] is False
    assert second["sense_reused"] is False
    assert second["sense"]["sense_id"] == "sense-2"
    assert len(calls) == 2


def test_single_seat_watch_iterations_are_bounded(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import check, sense, watch
    from lib import registry

    registry.upsert_agent({"name": "loopseat", "fleet": "unitfleet", "runtime": "command", "registered": True})
    monkeypatch.setattr(check, "run", lambda args: {
        "ok": True,
        "name": "loopseat",
        "fleet": "unitfleet",
        "runtime": "command",
        "status": "alive",
        "terminal": "alive",
        "terminal_ref": "tmux:unitfleet:loopseat",
        "output": ["READY loopseat"],
    })
    monkeypatch.setattr(sense, "run", lambda args: {
        "ok": True,
        "schema": "aura.sense.v1",
        "type": "sense",
        "seat": args.name,
        "name": args.name,
        "at": watch._now(),
        "state": "ready",
        "confidence": 0.9,
        "next_action": "send",
        "summary": "ready",
        "evidence": ["READY loopseat"],
    })

    result = watch.run(argparse.Namespace(
        name="loopseat",
        fleet=None,
        once=False,
        iterations=3,
        interval=0,
        lines=40,
        question=None,
        features=None,
        no_sense=False,
        sense=True,
        fresh_sense=False,
        sense_mode="llm",
        model="local-test",
        llm_timeout=1,
        ollama_host="http://ollama.test",
        contract=None,
    ))

    assert result["ok"] is True
    assert result["iterations"] == 3
    assert len(result["history"]) == 3
    assert result["history"][0]["output_changed"] is True
    assert result["history"][1]["sense_reused"] is True
    assert result["history"][2]["sense_reused"] is True


def test_perception_does_not_treat_done_inside_names_as_completion():
    from lib import terminal_perception

    record = terminal_perception.classify_terminal_state(
        "READY smoke-done\nACK smoke-ready Review output from smoke-done.",
        mechanical_status="alive",
        terminal="alive",
    )
    assert record["state"] == "ready"

    record = terminal_perception.classify_terminal_state(
        "done: stage complete",
        mechanical_status="alive",
        terminal="alive",
    )
    assert record["state"] == "done"


def test_fake_runtime_spawn_send_capture_stop_e2e(tmp_path):
    if shutil.which("tmux") is None:
        import pytest
        pytest.skip("tmux not installed")

    fleet = f"aura-e2e-{os.getpid()}"
    fake_runtime = ROOT / "tests" / "fixtures" / "fake_runtime.py"
    unit = tmp_path / "workspace"
    unit.mkdir()
    env = {
        **os.environ,
        "AURA_FLEET": fleet,
        "AURA_STATE_DIR": str(tmp_path),
        "AURA_REGISTRY_PATH": str(tmp_path / "agents.json"),
        "AURA_DELIVERY_LOG": str(tmp_path / "deliveries.jsonl"),
        "AURA_SENSE_MODE": "heuristic",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    def run_aura(*args):
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=env,
            timeout=20,
        )

    try:
        spawn_result = run_aura(
            "spawn",
            "fake1",
            "--command",
            f"{sys.executable} -u {fake_runtime} --name fake1 --mode echo",
            "--cwd",
            str(unit),
            "--as-pane",
        )
        assert spawn_result.returncode == 0, spawn_result.stderr + spawn_result.stdout
        assert '"runtime": "command"' in spawn_result.stdout
        assert '"trace_cell": "claude_code"' not in spawn_result.stdout
        assert '"pane_ref": "tmux:' + fleet + ':%' in spawn_result.stdout

        send_result = run_aura(
            "send",
            "fake1",
            "hello from e2e",
            "--as-service",
            "tester",
            "--transport",
            "tmux",
            "--dedupe-key",
            "fake-e2e-msg",
        )
        assert send_result.returncode == 0, send_result.stderr + send_result.stdout
        assert '"state": "attempted"' in send_result.stdout

        import time
        time.sleep(0.8)

        write_result = run_aura(
            "write",
            "fake1",
            "raw write hello",
            "--enter",
            "--as",
            "tester",
        )
        assert write_result.returncode == 0, write_result.stderr + write_result.stdout
        assert '"schema": "aura.write.v1"' in write_result.stdout
        assert '"state": "attempted"' in write_result.stdout

        explicit_write_result = run_aura(
            "write",
            f"tmux:{fleet}:fake1",
            "explicit write hello",
            "--enter",
            "--as",
            "tester",
        )
        assert explicit_write_result.returncode == 0, explicit_write_result.stderr + explicit_write_result.stdout
        assert f'"backend_ref": "tmux:{fleet}:fake1"' in explicit_write_result.stdout

        import time
        time.sleep(0.8)

        capture_result = run_aura("capture", "fake1", "--lines", "60")
        assert capture_result.returncode == 0, capture_result.stderr + capture_result.stdout
        assert "READY fake1" in capture_result.stdout
        assert "ACK fake1 hello from e2e" in capture_result.stdout
        assert "ACK fake1 raw write hello" in capture_result.stdout
        assert "ACK fake1 explicit write hello" in capture_result.stdout
        assert '"seat": "fake1"' in capture_result.stdout
        assert '"backend": "tmux"' in capture_result.stdout
        assert f'"backend_ref": "{fleet}:fake1"' in capture_result.stdout
        assert f'"seat_ref": "{fleet}:fake1"' in capture_result.stdout

        list_result = run_aura("list", "--fleet", fleet)
        assert list_result.returncode == 0, list_result.stderr + list_result.stdout
        assert '"seat": "fake1"' in list_result.stdout
        assert '"backend": "tmux"' in list_result.stdout
        assert f'"backend_ref": "{fleet}:fake1"' in list_result.stdout

        sense_result = run_aura("sense", "fake1", "--lines", "60")
        assert sense_result.returncode == 0, sense_result.stderr + sense_result.stdout
        assert '"schema": "aura.sense.v1"' in sense_result.stdout
        assert '"type": "sense"' in sense_result.stdout
        assert '"state": "ready"' in sense_result.stdout
        assert '"next_action": "send"' in sense_result.stdout
        assert (tmp_path / "seats" / "fake1" / "sense" / "events.jsonl").exists()
        assert (tmp_path / "seats" / "fake1" / "sense" / "latest.json").exists()

        sense_features_result = run_aura(
            "sense",
            "fake1",
            "--lines",
            "60",
            "--question",
            "Did it receive the raw write?",
            "--features",
            "state,last_visible_line,received_text,next_action,confidence,unsupported_demo",
        )
        assert sense_features_result.returncode == 0, sense_features_result.stderr + sense_features_result.stdout
        assert '"features"' in sense_features_result.stdout
        assert '"received_text": "ACK fake1 explicit write hello"' in sense_features_result.stdout
        assert '"unsupported_demo": {' in sense_features_result.stdout

        delivery_records = (tmp_path / "deliveries.jsonl").read_text(encoding="utf-8")
        assert '"type": "terminal_write"' in delivery_records

        watch_result = run_aura("watch", "fake1", "--once", "--lines", "40", "--interval", "0")
        assert watch_result.returncode == 0, watch_result.stderr + watch_result.stdout
        assert '"schema": "aura.watch.v1"' in watch_result.stdout
        assert '"type": "watch"' in watch_result.stdout
        assert '"seat": "fake1"' in watch_result.stdout
        assert '"output_changed": true' in watch_result.stdout
        assert '"stable_count": 0' in watch_result.stdout
        assert '"sense"' in watch_result.stdout
        assert (tmp_path / "seats" / "fake1" / "watch" / "events.jsonl").exists()
        assert (tmp_path / "seats" / "fake1" / "watch" / "latest.json").exists()

        second_watch_result = run_aura("watch", "fake1", "--once", "--lines", "40", "--interval", "0")
        assert second_watch_result.returncode == 0, second_watch_result.stderr + second_watch_result.stdout
        assert '"output_changed": false' in second_watch_result.stdout
        assert '"stable_count": 1' in second_watch_result.stdout

        fleet_watch_result = run_aura("watch", "--fleet", fleet, "--once", "--lines", "40", "--interval", "0")
        assert fleet_watch_result.returncode == 0, fleet_watch_result.stderr + fleet_watch_result.stdout
        assert '"schema": "aura.watch_fleet.v1"' in fleet_watch_result.stdout
        assert '"fleet": "' + fleet + '"' in fleet_watch_result.stdout
        assert '"count": 1' in fleet_watch_result.stdout
        assert '"seat": "fake1"' in fleet_watch_result.stdout
        assert '"samples"' in fleet_watch_result.stdout

        bounded_fleet_watch_result = run_aura(
            "watch",
            "--fleet",
            fleet,
            "--iterations",
            "2",
            "--interval",
            "0",
            "--lines",
            "40",
            "--no-sense",
        )
        assert bounded_fleet_watch_result.returncode == 0, bounded_fleet_watch_result.stderr + bounded_fleet_watch_result.stdout
        assert '"schema": "aura.watch_fleet.v1"' in bounded_fleet_watch_result.stdout
        assert '"iterations": 2' in bounded_fleet_watch_result.stdout
        assert '"history"' in bounded_fleet_watch_result.stdout

        spawn_result = run_aura(
            "spawn",
            "fake2",
            "--command",
            f"{sys.executable} -u {fake_runtime} --name fake2 --mode echo",
            "--cwd",
            str(unit),
            "--as-pane",
        )
        assert spawn_result.returncode == 0, spawn_result.stderr + spawn_result.stdout
        time.sleep(0.8)

        dash_tile_result = run_aura("dash", "tile", "--fleet", fleet)
        assert dash_tile_result.returncode == 0, dash_tile_result.stderr + dash_tile_result.stdout
        assert '"action": "tile"' in dash_tile_result.stdout
        assert '"dashboard": "dashboard"' in dash_tile_result.stdout

        windows_after_tile = subprocess.run(
            ["tmux", "list-windows", "-t", fleet, "-F", "#{window_name}"],
            text=True,
            capture_output=True,
            timeout=5,
        )
        assert "dashboard" in windows_after_tile.stdout.splitlines()
        assert "fake1" not in windows_after_tile.stdout.splitlines()
        assert "fake2" not in windows_after_tile.stdout.splitlines()

        tiled_write_result = run_aura("write", "fake2", "tiled hello", "--enter", "--as", "tester")
        assert tiled_write_result.returncode == 0, tiled_write_result.stderr + tiled_write_result.stdout
        time.sleep(0.8)
        tiled_capture_result = run_aura("capture", "fake2", "--lines", "80")
        assert tiled_capture_result.returncode == 0, tiled_capture_result.stderr + tiled_capture_result.stdout
        assert "ACK fake2 tiled hello" in tiled_capture_result.stdout
        assert '"terminal": "alive"' in tiled_capture_result.stdout
        assert '"pane_ref": "tmux:' + fleet + ':%' in tiled_capture_result.stdout

        dash_layout_result = run_aura("dash", "layout", "--fleet", fleet, "--layout", "even-horizontal")
        assert dash_layout_result.returncode == 0, dash_layout_result.stderr + dash_layout_result.stdout
        assert '"action": "layout"' in dash_layout_result.stdout

        dash_untile_result = run_aura("dash", "untile", "--fleet", fleet)
        assert dash_untile_result.returncode == 0, dash_untile_result.stderr + dash_untile_result.stdout
        assert '"action": "untile"' in dash_untile_result.stdout

        windows_after_untile = subprocess.run(
            ["tmux", "list-windows", "-t", fleet, "-F", "#{window_name}"],
            text=True,
            capture_output=True,
            timeout=5,
        )
        assert "fake1" in windows_after_untile.stdout.splitlines()
        assert "fake2" in windows_after_untile.stdout.splitlines()

        cut_result = run_aura("seat", "cut", "fake1", "--force")
        assert cut_result.returncode == 0, cut_result.stderr + cut_result.stdout
        assert '"cut": true' in cut_result.stdout

        cut_result = run_aura("seat", "cut", "fake2", "--force")
        assert cut_result.returncode == 0, cut_result.stderr + cut_result.stdout
        assert '"cut": true' in cut_result.stdout
    finally:
        subprocess.run(["tmux", "kill-session", "-t", fleet], capture_output=True, text=True)


def test_spawn_fleet_flag_controls_physical_tmux_session(tmp_path):
    if shutil.which("tmux") is None:
        import pytest
        pytest.skip("tmux not installed")

    fleet = f"aura-flag-{os.getpid()}"
    name = "fleetflag"
    fake_runtime = ROOT / "tests" / "fixtures" / "fake_runtime.py"
    unit = tmp_path / "workspace"
    unit.mkdir()
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path),
        "AURA_REGISTRY_PATH": str(tmp_path / "agents.json"),
        "AURA_DELIVERY_LOG": str(tmp_path / "deliveries.jsonl"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.pop("AURA_FLEET", None)
    env.pop("AURA_PROJECT", None)
    env.pop("AURA_TMUX_SESSION", None)

    try:
        spawn_result = subprocess.run(
            [
                sys.executable, str(CLI),
                "spawn", name,
                "--fleet", fleet,
                "--command", f"{sys.executable} -u {fake_runtime} --name {name} --mode echo",
                "--cwd", str(unit),
                "--as-pane",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=env,
            timeout=20,
        )
        assert spawn_result.returncode == 0, spawn_result.stderr + spawn_result.stdout
        assert f'"fleet": "{fleet}"' in spawn_result.stdout
        assert f'"terminal_ref": "{fleet}:{name}"' in spawn_result.stdout

        windows = subprocess.run(
            ["tmux", "list-windows", "-t", fleet, "-F", "#{window_name}"],
            text=True,
            capture_output=True,
            timeout=5,
        )
        assert windows.returncode == 0, windows.stderr
        assert name in windows.stdout.splitlines()
    finally:
        subprocess.run(["tmux", "kill-session", "-t", fleet], capture_output=True, text=True)
        # Regression guard cleanup: the old bug placed --fleet windows in aura.
        subprocess.run(["tmux", "kill-window", "-t", f"aura:{name}"], capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Safety fix: _tmux_target / kill_window / exact-match tests
# ---------------------------------------------------------------------------

def test_tmux_target_pane_ref_returned_unchanged():
    """Pane-id refs must pass through _tmux_target without an = prefix."""
    from lib.tmux import _tmux_target
    assert _tmux_target("tmux:fleet:%5") == "%5"
    assert _tmux_target("fleet:%5") == "%5"
    assert _tmux_target("%99") == "%99"


def test_tmux_target_name_ref_gets_exact_prefix():
    """Name-based targets must get a leading = so tmux uses exact matching."""
    from lib.tmux import _tmux_target
    assert _tmux_target("fleet:seat") == "=fleet:seat"
    assert _tmux_target("tmux:myfleet:engineer") == "=myfleet:engineer"


def test_kill_window_pane_ref_refused_on_fleet_mismatch(monkeypatch):
    """kill_window must refuse to kill a pane whose session != the recorded fleet."""
    from lib import tmux

    killed = []

    def fake_run(args):
        if args[:4] == ["display-message", "-p", "-t", "%7"]:
            # Pane %7 is actually in fleet-v2, not fleet.
            return subprocess.CompletedProcess(args, 0, stdout="fleet-v2\n", stderr="")
        killed.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(tmux, "_run_tmux", fake_run)

    tmux.kill_window("fleet:%7")

    assert killed == [], f"Expected no kill but got: {killed}"


def test_kill_window_pane_ref_kills_when_fleet_matches(monkeypatch):
    """kill_window proceeds with kill-pane when the pane belongs to the correct fleet."""
    from lib import tmux

    killed = []

    def fake_run(args):
        if args[:4] == ["display-message", "-p", "-t", "%7"]:
            return subprocess.CompletedProcess(args, 0, stdout="fleet\n", stderr="")
        killed.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(tmux, "_run_tmux", fake_run)

    tmux.kill_window("fleet:%7")

    assert killed == [["kill-pane", "-t", "%7"]]


def test_kill_window_name_target_uses_exact_prefix(monkeypatch):
    """kill_window name path must pass =fleet:seat to tmux, not a bare fleet:seat."""
    from lib import tmux

    killed = []

    def fake_run(args):
        if args[:3] == ["list-windows", "-t", "myfleet"]:
            return subprocess.CompletedProcess(args, 0, stdout="engineer\n", stderr="")
        killed.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(tmux, "_run_tmux", fake_run)

    tmux.kill_window("myfleet:engineer")

    assert len(killed) == 1
    assert killed[0] == ["kill-window", "-t", "=myfleet:engineer"]

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli" / "aura"
sys.path.insert(0, str(ROOT / "cli"))


def test_openclaw_and_shell_runtime_specs_exist():
    from lib import runtimes

    openclaw_runtime, openclaw_spec = runtimes.resolve_runtime("openclaw")
    shell_runtime, shell_spec = runtimes.resolve_runtime("shell")
    omx_runtime, omx_spec = runtimes.resolve_runtime("omx")

    assert openclaw_runtime == "openclaw"
    assert openclaw_spec["command"] == "openclaw"
    assert shell_runtime == "shell"
    assert "command" in shell_spec
    assert omx_runtime == "omx"
    assert omx_spec["command"] == "omx --direct --madmax"
    assert omx_spec["native_state"] == ".omx"
    assert runtimes.graceful_exit("future-runtime") == "/exit"


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
    assert calls == [
        [
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
        ],
        ["set-option", "-t", "freshfleet", "base-index", "1"],
        ["set-window-option", "-t", "freshfleet", "pane-base-index", "1"],
        ["set-option", "-t", "freshfleet", "renumber-windows", "on"],
        ["move-window", "-r", "-t", "freshfleet"],
    ]


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
        manifest=None,
        role_home=None,
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
    assert "trace_cell" not in result or result["trace_cell"] is None


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
    ]
    assert sent[0][1] == "Do the unit work.\n"
    assert result["prompt_delivery"]["submitted"] is True
    assert "agent_map_included" not in result["prompt_delivery"]
    assert result["context_file"] == str(context_file)
    assert result["work_file"] == str(work_file)

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

    legacy_log_path = unit / ".aura" / "state" / "sessions.jsonl"
    legacy_rows = [json.loads(line) for line in legacy_log_path.read_text(encoding="utf-8").splitlines()]
    assert legacy_rows[-1]["seat"] == "codex-seat"
    assert (unit / ".aura" / "state" / "latest-session.json").exists()


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


def test_spawn_omx_uses_aura_seat_box_without_project_mutation(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_OMX_BOX_SETUP", "0")

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
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%77"}

    args = argparse.Namespace(
        name="omx-seat",
        runtime="omx",
        resume_session=None,
        launch_command=None,
        profile=None,
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
    assert result["runtime"] == "omx"
    assert result["command"] == "omx --direct --madmax"
    assert result["omx_isolation"] == "aura-seat-box"
    assert "profile" not in result
    assert result["omx_profile_applied"] is False
    assert result["omx_profile_templates_applied"] == []
    assert result["omx_box_team_state_root"] == str(
        tmp_path / "state" / "omx-homes" / "unitfleet" / "omx-seat" / "omx-root" / ".omx" / "state"
    )
    assert result["runtime_home"] == result["omx_box_root"]
    assert result["native_state_ref"] == result["omx_box_omx_state"]
    assert not (unit / ".codex").exists()
    assert not (unit / ".omx").exists()

    _, workdir, _, command, env, _ = created[0]
    assert workdir == str(unit)
    assert command == "omx --direct --madmax"
    assert env["OMX_LAUNCH_POLICY"] == "direct"
    assert env["OMXBOX_ACTIVE"] == "1"
    assert env["OMX_AUTO_UPDATE"] == "0"
    assert env["OMX_NOTIFY_FALLBACK"] == "0"
    assert env["OMX_SOURCE_CWD"] == str(unit)
    assert "AURA_OMX_PROFILE" not in env
    assert env["OMX_TEAM_STATE_ROOT"] == str(
        tmp_path / "state" / "omx-homes" / "unitfleet" / "omx-seat" / "omx-root" / ".omx" / "state"
    )
    assert env["HOME"].startswith(str(tmp_path / "state" / "omx-homes" / "unitfleet" / "omx-seat"))
    assert env["CODEX_HOME"] == str(tmp_path / "state" / "omx-homes" / "unitfleet" / "omx-seat" / "codex-home")
    assert env["OMX_ROOT"] == str(tmp_path / "state" / "omx-homes" / "unitfleet" / "omx-seat" / "omx-root")
    assert result["omx_box_star_prompt_preseeded"] is True
    assert result["omx_box_source_cwd_trusted"] is True

    box = tmp_path / "state" / "omx-homes" / "unitfleet" / "omx-seat"
    assert (box / "home" / ".omx" / "state" / "star-prompt.json").is_file()
    config = (box / "codex-home" / "config.toml").read_text(encoding="utf-8")
    assert f'[projects."{unit}"]' in config
    assert 'trust_level = "trusted"' in config


def test_spawn_omx_applies_explicit_profile_template_to_seat_box(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setenv("AURA_STATE_DIR", str(state_dir))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(state_dir / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_OMX_BOX_SETUP", "0")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()

    profile_root = state_dir / "omx-profiles" / "dev"
    codex_template = profile_root / "codex-home-template"
    omx_template = profile_root / "omx-root-template"
    codex_template.mkdir(parents=True)
    omx_template.mkdir(parents=True)
    (codex_template / "profile-note.md").write_text("template note\n", encoding="utf-8")
    (codex_template / "keep-existing.md").write_text("template value\n", encoding="utf-8")
    (omx_template / "seed.txt").write_text("omx seed\n", encoding="utf-8")

    box_codex_home = state_dir / "omx-homes" / "unitfleet" / "omx-profile-seat" / "codex-home"
    box_codex_home.mkdir(parents=True)
    (box_codex_home / "keep-existing.md").write_text("existing value\n", encoding="utf-8")

    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%78"}

    args = argparse.Namespace(
        name="omx-profile-seat",
        runtime="omx",
        resume_session=None,
        launch_command=None,
        profile=None,
        omx_profile="dev",
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["runtime"] == "omx"
    assert result["profile"] == "dev"
    assert result["omx_profile"] == "dev"
    assert result["omx_profile_root"] == str(profile_root)
    assert result["omx_profile_applied"] is True
    assert result["omx_profile_templates_applied"] == ["codex-home-template", "omx-root-template"]
    assert (box_codex_home / "profile-note.md").read_text(encoding="utf-8") == "template note\n"
    assert (box_codex_home / "keep-existing.md").read_text(encoding="utf-8") == "existing value\n"
    assert (
        state_dir
        / "omx-homes"
        / "unitfleet"
        / "omx-profile-seat"
        / "omx-root"
        / "seed.txt"
    ).read_text(encoding="utf-8") == "omx seed\n"
    assert not (unit / ".codex").exists()
    assert not (unit / ".omx").exists()

    _, workdir, _, command, env, _ = created[0]
    assert workdir == str(unit)
    assert command == "omx --direct --madmax"
    assert env["AURA_OMX_PROFILE"] == "dev"
    assert env["CODEX_HOME"] == str(box_codex_home)
    assert env["OMX_TEAM_STATE_ROOT"] == str(
        state_dir / "omx-homes" / "unitfleet" / "omx-profile-seat" / "omx-root" / ".omx" / "state"
    )


def test_spawn_omx_missing_explicit_profile_fails(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_OMX_BOX_SETUP", "0")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(*args, **kwargs):
            raise AssertionError("OMX spawn should fail before creating a terminal")

    args = argparse.Namespace(
        name="omx-seat",
        runtime="omx",
        resume_session=None,
        launch_command=None,
        profile=None,
        omx_profile="missing",
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is False
    assert result["error"] == "omx-box-setup-failed"
    assert "omx profile not found" in result["detail"]
    assert not (unit / ".codex").exists()
    assert not (unit / ".omx").exists()


def test_spawn_omx_rejects_profile_template_symlink(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_OMX_BOX_SETUP", "0")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("do not copy\n", encoding="utf-8")
    profile_template = tmp_path / "state" / "omx-profiles" / "unsafe" / "codex-home-template"
    profile_template.mkdir(parents=True)
    os.symlink(outside, profile_template / "leak.txt")

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(*args, **kwargs):
            raise AssertionError("OMX spawn should fail before creating a terminal")

    args = argparse.Namespace(
        name="omx-seat",
        runtime="omx",
        resume_session=None,
        launch_command=None,
        profile=None,
        omx_profile="unsafe",
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is False
    assert result["error"] == "omx-box-setup-failed"
    assert "symlink rejected" in result["detail"]
    assert not (
        tmp_path
        / "state"
        / "omx-homes"
        / "unitfleet"
        / "omx-seat"
        / "codex-home"
        / "leak.txt"
    ).exists()


def test_spawn_omx_profile_flags_conflict(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()

    args = argparse.Namespace(
        name="omx-seat",
        runtime="omx",
        resume_session=None,
        launch_command=None,
        profile="legacy",
        omx_profile="modern",
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, object(), lambda x: x)

    assert result["ok"] is False
    assert result["error"] == "conflicting-omx-profile"


def test_spawn_hermes_profile_behavior_unchanged(monkeypatch, tmp_path):
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
    assert result["command"] == "hermes -p hermes-prof"
    assert created[0][3] == "hermes -p hermes-prof"


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


def test_spawn_codex_uses_desks_runtime_profile_when_cli_absent(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setenv("AURA_STATE_DIR", str(state_dir))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(state_dir / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    profile_root = state_dir / "runtime-profiles" / "codex" / "dev"
    (profile_root / "codex-home-template").mkdir(parents=True)
    (profile_root / "codex-home-template" / "profile-note.md").write_text("from desks\n", encoding="utf-8")
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%83"}

    args = argparse.Namespace(
        name="codex-desks-seat",
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
        _role_manifest_meta={"desks_runtime_profiles": {"codex": "codex/dev"}},
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["profile"] == "dev"
    assert result["runtime_profile_ref"] == "codex/dev"
    assert result["runtime_profile_source"] == "desks"
    assert result["desks_runtime_profile_ref"] == "codex/dev"
    assert result["desks_runtime_profiles"] == {"codex": "codex/dev"}
    assert result["codex_isolation"] == "aura-seat-box"
    assert created[0][4]["DESKS_RUNTIME_PROFILES"] == '{"codex": "codex/dev"}'
    assert created[0][4]["CODEX_HOME"] == str(
        state_dir / "runtime-homes" / "codex" / "unitfleet" / "codex-desks-seat" / "codex-home"
    )
    assert not (unit / ".codex").exists()

    from lib import workspace_state

    rows = [json.loads(line) for line in workspace_state.workspace_session_log(unit).read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["runtime_profile_ref"] == "codex/dev"
    assert rows[-1]["runtime_profile_source"] == "desks"
    assert rows[-1]["desks_runtime_profile_ref"] == "codex/dev"
    assert rows[-1]["desks_runtime_profiles"] == {"codex": "codex/dev"}
    assert rows[-1]["codex_profile"] == "dev"
    assert rows[-1]["codex_box_root"] == str(
        state_dir / "runtime-homes" / "codex" / "unitfleet" / "codex-desks-seat"
    )
    assert rows[-1]["codex_box_home"] == str(
        state_dir / "runtime-homes" / "codex" / "unitfleet" / "codex-desks-seat" / "home"
    )
    assert rows[-1]["codex_box_codex_home"] == str(
        state_dir / "runtime-homes" / "codex" / "unitfleet" / "codex-desks-seat" / "codex-home"
    )
    assert rows[-1]["codex_box_runtime"] == str(
        state_dir / "runtime-homes" / "codex" / "unitfleet" / "codex-desks-seat" / "runtime"
    )


def test_spawn_cli_runtime_profile_overrides_desks_ref(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setenv("AURA_STATE_DIR", str(state_dir))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(state_dir / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    for profile in ("dev", "ops"):
        (state_dir / "runtime-profiles" / "codex" / profile / "codex-home-template").mkdir(parents=True)
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%84"}

    args = argparse.Namespace(
        name="codex-override-seat",
        runtime="codex",
        resume_session=None,
        launch_command=None,
        profile=None,
        runtime_profile="codex/ops",
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
        _role_manifest_meta={"desks_runtime_profiles": {"codex": "codex/dev"}},
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["runtime_profile_ref"] == "codex/ops"
    assert result["runtime_profile_source"] == "cli-runtime-profile"
    assert "desks_runtime_profile_ref" not in result
    assert result["codex_profile"] == "ops"


def test_spawn_omx_uses_desks_runtime_profile_when_cli_absent(monkeypatch, tmp_path):
    state_dir = tmp_path / "state"
    monkeypatch.setenv("AURA_STATE_DIR", str(state_dir))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(state_dir / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    monkeypatch.setenv("AURA_OMX_BOX_SETUP", "0")

    from commands import spawn

    unit = tmp_path / "project"
    unit.mkdir()
    profile_root = state_dir / "omx-profiles" / "dev"
    (profile_root / "codex-home-template").mkdir(parents=True)
    created = []

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%85"}

    args = argparse.Namespace(
        name="omx-desks-seat",
        runtime="omx",
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
        _role_manifest_meta={"desks_runtime_profiles": {"omx": "omx/dev"}},
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["profile"] == "dev"
    assert result["runtime_profile_ref"] == "omx/dev"
    assert result["runtime_profile_source"] == "desks"
    assert result["desks_runtime_profile_ref"] == "omx/dev"
    assert result["omx_profile"] == "dev"
    assert created[0][4]["AURA_OMX_PROFILE"] == "dev"
    assert created[0][4]["OMX_TEAM_STATE_ROOT"] == str(
        state_dir / "omx-homes" / "unitfleet" / "omx-desks-seat" / "omx-root" / ".omx" / "state"
    )


def test_spawn_hermes_uses_desks_runtime_profile_when_cli_absent(monkeypatch, tmp_path):
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
            return {"ok": True, "target": f"unitfleet:{name}", "pane_id": "%86"}

    args = argparse.Namespace(
        name="hermes-desks-seat",
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
        _role_manifest_meta={"desks_runtime_profiles": {"hermes": "hermes/aura-operator"}},
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["runtime"] == "hermes"
    assert result["profile"] == "aura-operator"
    assert result["runtime_profile_ref"] == "hermes/aura-operator"
    assert result["runtime_profile_source"] == "desks"
    assert result["desks_runtime_profile_ref"] == "hermes/aura-operator"
    assert result["command"] == "hermes -p aura-operator"
    assert created[0][3] == "hermes -p aura-operator"


def test_spawn_desks_runtime_profile_mismatch_fails_before_terminal(monkeypatch, tmp_path):
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
            raise AssertionError("mismatched desks runtime profile should fail before creating a terminal")

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
        _role_manifest_meta={"desks_runtime_profiles": {"codex": "omx/dev"}},
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is False
    assert result["error"] == "invalid-desks-runtime-profile"
    assert "selected runtime codex" in result["detail"]
    assert "omx/dev" in result["detail"]


def test_role_metadata_reads_desks_runtime_profile_refs(tmp_path):
    from commands import spawn

    role_home = tmp_path / "desks" / "profiles" / "operator"
    role_home.mkdir(parents=True)
    (role_home / "profile.json").write_text(
        json.dumps({
            "profile_id": "operator",
            "identity_id": "operator-id",
            "runtime_profiles": {"codex": "codex/profile-default"},
        }),
        encoding="utf-8",
    )
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    manifest = {
        "role_home": role_home,
        "role_id": "operator",
        "product": "aura",
        "unit": "runtime",
        "manifest_path": role_home / "role.json",
        "workspace_root": workspace_root,
        "files": {},
        "seat": "operator-seat",
        "fleet": "operator-fleet",
        "runtime_profiles": {"codex": "codex/launch-override", "omx": "omx/dev"},
    }

    meta = spawn._role_metadata_from_manifest(manifest)

    assert meta["desks_profile_id"] == "operator"
    assert meta["desks_runtime_profiles"] == {
        "codex": "codex/launch-override",
        "omx": "omx/dev",
    }


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


def _write_role_home(tmp_path):
    role_home = tmp_path / "unit" / ".desks" / "roles" / "specialist-cell"
    role_home.mkdir(parents=True)
    workspace = tmp_path / "unit"
    for name in ("SOUL.md", "AGENTS.md", "MEMORY.md", "BOOTSTRAP.md", "COMPRESSION.md"):
        (role_home / name).write_text(f"# {name}\n", encoding="utf-8")
    (role_home / "sessions.json").write_text("[]\n", encoding="utf-8")
    manifest = {
        "schema": "desks.role.v1",
        "product": "flex",
        "unit": "engine",
        "role_id": "specialist-cell",
        "type": "specialist",
        "specialization": "cell",
        "seat": "specialist-cell",
        "fleet": "flex-specialists",
        "workspace_root": str(workspace),
        "files": {
            "soul": "SOUL.md",
            "agents": "AGENTS.md",
            "memory": "MEMORY.md",
            "bootstrap": "BOOTSTRAP.md",
            "compression": "COMPRESSION.md",
            "sessions": "sessions.json",
        },
    }
    (role_home / "role.json").write_text(json.dumps(manifest), encoding="utf-8")
    return role_home


def test_spawn_manifest_applies_desks_role_defaults(tmp_path):
    from commands import spawn

    role_home = _write_role_home(tmp_path)
    args = argparse.Namespace(
        name=None,
        manifest=str(role_home / "role.json"),
        role_home=None,
        fleet=None,
        cwd=None,
        runtime=None,
        profile=None,
        prompt=None,
        work=None,
        context=None,
    )

    result = spawn._apply_spawn_manifest(args)

    assert result["ok"] is True
    assert args.name == "specialist-cell"
    assert args.fleet == "flex-specialists"
    assert args.cwd == str(tmp_path / "unit")
    assert args.runtime == "codex"
    assert args.profile == "specialist-cell"
    assert args.context == str(role_home / "AGENTS.md")
    assert args.prompt == "\n".join([
        f"Read {role_home / 'BOOTSTRAP.md'} and follow it.",
        f"Use {role_home} as your Desks role home.",
    ])
    assert args._role_manifest_meta["desks_role_home"] == str(role_home)
    assert args._role_manifest_meta["desks_manifest"] == str(role_home / "role.json")
    assert args._role_manifest_meta["desks_bootstrap"] == str(role_home / "BOOTSTRAP.md")


def test_spawn_manifest_resume_keeps_metadata_without_bootstrap_prompt(tmp_path):
    from commands import spawn

    role_home = _write_role_home(tmp_path)
    session_id = "019dec35-4cd3-7550-83d3-53d50e837e5d"
    args = argparse.Namespace(
        name="specialist-cell",
        manifest=str(role_home / "role.json"),
        role_home=None,
        fleet="flex-specialists",
        cwd=None,
        runtime="codex",
        profile=None,
        prompt=None,
        work=None,
        context=None,
        resume_session=session_id,
    )

    result = spawn._apply_spawn_manifest(args)

    assert result["ok"] is True
    assert args.name == "specialist-cell"
    assert args.fleet == "flex-specialists"
    assert args.cwd == str(tmp_path / "unit")
    assert args.runtime == "codex"
    assert args.profile == "specialist-cell"
    assert args.context == str(role_home / "AGENTS.md")
    assert args.prompt is None
    assert args.resume_session == session_id
    assert args._role_manifest_meta["desks_role_home"] == str(role_home)
    assert args._role_manifest_meta["desks_bootstrap"] == str(role_home / "BOOTSTRAP.md")


def test_spawn_role_home_resolves_manifest(tmp_path):
    from commands import spawn

    role_home = _write_role_home(tmp_path)
    args = argparse.Namespace(
        name="specialist-cell",
        manifest=None,
        role_home=str(role_home),
        fleet=None,
        cwd=None,
        runtime=None,
        profile=None,
        prompt=None,
        work=None,
        context=None,
    )

    result = spawn._apply_spawn_manifest(args)

    assert result["ok"] is True
    assert args.name == "specialist-cell"
    assert args.fleet == "flex-specialists"


def test_spawn_manifest_infers_flex_project_env_from_workspace_context(tmp_path):
    from commands import spawn

    role_home = _write_role_home(tmp_path)
    project_manifest = tmp_path / "unit" / "context" / ".flex" / "project.yaml"
    project_manifest.parent.mkdir(parents=True)
    project_manifest.write_text("version: 1\nproject:\n  name: test\ncommands: {}\n", encoding="utf-8")
    args = argparse.Namespace(
        name=None,
        manifest=str(role_home / "role.json"),
        role_home=None,
        fleet=None,
        cwd=None,
        runtime=None,
        profile=None,
        prompt=None,
        work=None,
        context=None,
    )

    result = spawn._apply_spawn_manifest(args)

    assert result["ok"] is True
    assert args._role_manifest_meta["flex_project_manifest"] == str(project_manifest)
    assert args._role_manifest_meta["flex_project_root"] == str(project_manifest.parent.parent)


def test_spawn_manifest_allows_explicit_aura_address_to_differ_from_desks_defaults(tmp_path):
    from commands import spawn

    role_home = _write_role_home(tmp_path)
    args = argparse.Namespace(
        name="debug-1",
        manifest=str(role_home / "role.json"),
        role_home=None,
        fleet="scratch",
        cwd=None,
        runtime=None,
        profile=None,
        prompt=None,
        work=None,
        context=None,
    )

    result = spawn._apply_spawn_manifest(args)

    assert result["ok"] is True
    assert args.name == "debug-1"
    assert args.fleet == "scratch"
    assert args.profile == "specialist-cell"
    assert args._role_manifest_meta["desks_default_seat"] == "specialist-cell"
    assert args._role_manifest_meta["desks_default_fleet"] == "flex-specialists"


def test_spawn_manifest_rejects_absolute_role_file(tmp_path):
    from commands import spawn

    role_home = _write_role_home(tmp_path)
    manifest_path = role_home / "role.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["bootstrap"] = str(role_home / "BOOTSTRAP.md")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    args = argparse.Namespace(
        name=None,
        manifest=str(manifest_path),
        role_home=None,
        fleet=None,
        cwd=None,
        runtime=None,
        profile=None,
        prompt=None,
        work=None,
        context=None,
    )

    result = spawn._apply_spawn_manifest(args)

    assert result["ok"] is False
    assert "files.bootstrap must be relative" in result["error"]


def test_spawn_manifest_metadata_reaches_registry_and_workspace_record(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_CODEX_STARTUP_READY_TIMEOUT", "0")

    from commands import spawn
    from lib import registry, workspace_state

    role_home = _write_role_home(tmp_path)
    args = argparse.Namespace(
        name=None,
        manifest=str(role_home / "role.json"),
        role_home=None,
        fleet=None,
        cwd=None,
        runtime=None,
        launch_command="printf ready",
        resume_session=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        context=None,
    )
    applied = spawn._apply_spawn_manifest(args)
    assert applied["ok"] is True

    created = []
    sent = []

    class FakeTerminal:
        SESSION_NAME = "flex-specialists"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": "flex-specialists:specialist-cell", "pane_id": "%55"}

        @staticmethod
        def send_text(name, text, submit=True, submit_key="Enter"):
            sent.append((name, text, submit, submit_key))
            return {"ok": True, "target": f"flex-specialists:{name}", "text": text}

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["name"] == "specialist-cell"
    assert result["fleet"] == "flex-specialists"
    assert result["runtime"] == "codex"
    assert result["desks_role_home"] == str(role_home)
    assert result["desks_role_id"] == "specialist-cell"
    assert result["desks_product"] == "flex"
    assert result["desks_unit"] == "engine"
    assert result["desks_manifest"] == str(role_home / "role.json")
    assert result["desks_bootstrap"] == str(role_home / "BOOTSTRAP.md")
    assert created[0][4]["AURA_DESKS_ROLE_HOME"] == str(role_home)
    assert created[0][4]["AURA_DESKS_ROLE_ID"] == "specialist-cell"
    assert created[0][4]["DESKS_ROLE_HOME"] == str(role_home)
    assert created[0][4]["DESKS_ROLE_ID"] == "specialist-cell"
    assert created[0][4]["DESKS_PRODUCT"] == "flex"
    assert created[0][4]["DESKS_UNIT"] == "engine"
    assert created[0][4]["DESKS_MANIFEST"] == str(role_home / "role.json")
    assert created[0][4]["DESKS_DEFAULT_SEAT"] == "specialist-cell"
    assert created[0][4]["DESKS_DEFAULT_FLEET"] == "flex-specialists"
    assert sent[0][1].endswith(f"Read {role_home / 'BOOTSTRAP.md'} and follow it.\nUse {role_home} as your Desks role home.")

    agent = registry.get_agent("specialist-cell", fleet="flex-specialists")
    assert agent["desks_role_home"] == str(role_home)
    assert agent["desks_bootstrap"] == str(role_home / "BOOTSTRAP.md")

    workspace_root = tmp_path / "unit"
    rows = [json.loads(line) for line in workspace_state.workspace_session_log(workspace_root).read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["desks_role_home"] == str(role_home)
    assert rows[-1]["desks_manifest"] == str(role_home / "role.json")
    assert rows[-1]["workspace_root"] == str(workspace_root)

    legacy_rows = [
        json.loads(line)
        for line in (workspace_root / ".aura" / "state" / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert legacy_rows[-1]["desks_role_home"] == str(role_home)


def test_spawn_manifest_resume_does_not_send_bootstrap_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import spawn

    role_home = _write_role_home(tmp_path)
    session_id = "019dec35-4cd3-7550-83d3-53d50e837e5d"
    args = argparse.Namespace(
        name="specialist-cell",
        manifest=str(role_home / "role.json"),
        role_home=None,
        fleet="flex-specialists",
        cwd=None,
        runtime="codex",
        profile=None,
        prompt=None,
        work=None,
        context=None,
        resume_session=session_id,
        launch_command=None,
        model=None,
        as_pane=True,
    )
    applied = spawn._apply_spawn_manifest(args)
    assert applied["ok"] is True

    sent = []
    created = []

    class FakeTerminal:
        SESSION_NAME = "flex-specialists"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": "flex-specialists:specialist-cell", "pane_id": "%56"}

        @staticmethod
        def send_text(name, text, submit=True, submit_key="Enter"):
            sent.append((name, text, submit, submit_key))
            return {"ok": True}

        @staticmethod
        def pane_pid(_target):
            return 1234

    monkeypatch.setattr(spawn.uuid, "uuid4", lambda: type("U", (), {"hex": "feedfacecafebeef1234"})())

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    expected_command = (
        f"codex --cd {tmp_path / 'unit'} "
        f"--dangerously-bypass-approvals-and-sandbox resume {session_id}"
    )
    assert result["command"] == expected_command
    assert result["runtime_session_binding"] == "bound"
    assert result["runtime_session_id"] == session_id
    assert result["desks_role_home"] == str(role_home)
    assert "prompt_sent" not in result
    assert sent == []
    assert created[0][4]["DESKS_ROLE_HOME"] == str(role_home)


def test_spawn_terminal_exports_inferred_flex_project_env(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import spawn

    role_home = _write_role_home(tmp_path)
    project_manifest = tmp_path / "unit" / "context" / ".flex" / "project.yaml"
    project_manifest.parent.mkdir(parents=True)
    project_manifest.write_text("version: 1\nproject:\n  name: test\ncommands: {}\n", encoding="utf-8")
    args = argparse.Namespace(
        name=None,
        manifest=str(role_home / "role.json"),
        role_home=None,
        fleet=None,
        cwd=None,
        runtime=None,
        launch_command="printf ready",
        resume_session=None,
        profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        context=None,
    )
    applied = spawn._apply_spawn_manifest(args)
    assert applied["ok"] is True

    created = []

    class FakeTerminal:
        SESSION_NAME = "flex-specialists"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            created.append((name, workdir, detached, command, env, unset_env))
            return {"ok": True, "target": "flex-specialists:specialist-cell", "pane_id": "%55"}

        @staticmethod
        def send_text(name, text, submit=True, submit_key="Enter"):
            return {"ok": True, "target": f"flex-specialists:{name}", "text": text}

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert created[0][4]["FLEX_PROJECT_MANIFEST"] == str(project_manifest)
    assert created[0][4]["FLEX_PROJECT_ROOT"] == str(project_manifest.parent.parent)


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


def test_capture_stop_sense_and_watch_commands_are_public_contract_names():
    help_result = subprocess.run(
        [sys.executable, str(CLI), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert help_result.returncode == 0
    assert "capture" in help_result.stdout
    assert "stop" in help_result.stdout
    assert "sense" in help_result.stdout
    assert "watch" in help_result.stdout
    assert "write" in help_result.stdout
    assert "route" in help_result.stdout
    assert "dash" in help_result.stdout
    assert "event" in help_result.stdout
    assert "--json" not in help_result.stdout


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


def test_spawn_runtime_choices_include_openclaw_and_shell():
    help_result = subprocess.run(
        [sys.executable, str(CLI), "spawn", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert help_result.returncode == 0
    assert "openclaw" in help_result.stdout
    assert "shell" in help_result.stdout
    assert "omx" in help_result.stdout
    assert "--cwd" in help_result.stdout
    assert "--work" in help_result.stdout
    assert "--context" in help_result.stdout


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
    assert second["sense"]["unchanged"] is True
    assert second["sense"]["reused_from_watch_id"] == first["watch_id"]

    args.fresh_sense = True
    third = watch.sample(args)
    assert len(calls) == 2
    assert third["sense_reused"] is False


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

        done_result = run_aura("write", "fake1", "DONE ready for review", "--enter", "--as", "tester")
        assert done_result.returncode == 0, done_result.stderr + done_result.stdout
        time.sleep(0.8)

        route_dry_result = run_aura("route", "--fleet", fleet, "--dry-run", "--max-actions", "3", "--lines", "60")
        assert route_dry_result.returncode == 0, route_dry_result.stderr + route_dry_result.stdout
        assert '"schema": "aura.route.v1"' in route_dry_result.stdout
        assert '"dry_run": true' in route_dry_result.stdout
        assert '"source_seat": "fake1"' in route_dry_result.stdout
        assert '"target_seat": "fake2"' in route_dry_result.stdout
        assert '"status": "proposed"' in route_dry_result.stdout

        route_send_without_limit = run_aura("route", "--fleet", fleet, "--send", "--lines", "60")
        assert route_send_without_limit.returncode != 0
        assert "requires explicit --max-actions" in route_send_without_limit.stdout

        route_live_result = run_aura("route", "--fleet", fleet, "--send", "--max-actions", "1", "--lines", "60")
        assert route_live_result.returncode == 0, route_live_result.stderr + route_live_result.stdout
        assert '"dry_run": false' in route_live_result.stdout
        assert '"status": "sent"' in route_live_result.stdout

        route_duplicate_result = run_aura("route", "--fleet", fleet, "--send", "--max-actions", "1", "--lines", "60")
        assert route_duplicate_result.returncode == 0, route_duplicate_result.stderr + route_duplicate_result.stdout
        assert '"status": "skipped_duplicate"' in route_duplicate_result.stdout
        assert (tmp_path / "fleets" / fleet / "route" / "events.jsonl").exists()

        stop_result = run_aura("stop", "fake1", "--force")
        assert stop_result.returncode == 0, stop_result.stderr + stop_result.stdout
        assert '"stop": true' in stop_result.stdout

        stop_result = run_aura("stop", "fake2", "--force")
        assert stop_result.returncode == 0, stop_result.stderr + stop_result.stdout
        assert '"stop": true' in stop_result.stdout
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

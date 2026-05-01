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
    assert omx_spec["native_state"] == ".omx"
    assert runtimes.graceful_exit("future-runtime") == "/exit"


def test_write_submit_retry_detection_is_narrow():
    from commands.write import _needs_submit_retry, _retry_submit
    from lib.terminal_submit import delivery_blocker

    assert _needs_submit_retry(["Messages to be submitted after next tool call"]) is True
    assert _needs_submit_retry(["Press Enter to submit"]) is True
    assert _needs_submit_retry(["› [Pasted Content 1024 chars]", "", "gpt-5.5 high"]) is True
    assert _needs_submit_retry(["› [Pasted Content 1024 chars]", "• Working (1s)"]) is False
    assert _needs_submit_retry(["Working (2s)", "Running tool call"]) is False
    assert delivery_blocker(["› [Pasted Content 1024 chars]", "", "gpt-5.5 high"]) == "target-input-queued"
    assert delivery_blocker(["• Working (1s)", "Running tool call"]) == "target-busy"

    class FakeTerminal:
        calls = []

        @classmethod
        def send_keys(cls, name, text, enter=True):
            cls.calls.append((name, text, enter))
            return {"ok": True}

    assert _retry_submit("seat1", FakeTerminal)["ok"] is True
    assert FakeTerminal.calls == [("seat1", "Enter", False)]


def test_send_tmux_verifies_submit_and_retries(monkeypatch, tmp_path):
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
    )
    assert result["ok"] is True
    assert result["submitted"] is True
    assert result["submitted_verified"] is True
    assert result["submit_retry"] is True
    assert FakeTerminal.keys == [("unitfleet:worker", "Enter", False)]

    records = [
        json.loads(line)
        for line in (tmp_path / "deliveries.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert records[-1]["delivery_type"] == "semantic_send"
    assert records[-1]["submitted_verified"] is True
    assert records[-1]["submit_retry"] is True


def test_send_tmux_blocks_when_target_already_has_queued_input(monkeypatch, tmp_path):
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
    )

    assert result["ok"] is True
    assert FakeTerminal.sent is True
    assert result["submitted_verified"] is False
    assert result["submit_retry"] is True


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
    assert calls[2][-1] == "Enter"


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


def test_command_override_uses_command_runtime_and_no_claude_trace(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
            assert unset_env == ["NO_COLOR", "AURA_RUNTIME_SESSION_ID", "AURA_SESSION_ID", "CODEX_THREAD_ID", "CLAUDE_SESSION_ID"]
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
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

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
    assert unset_env == ["NO_COLOR", "AURA_RUNTIME_SESSION_ID", "AURA_SESSION_ID", "CODEX_THREAD_ID", "CLAUDE_SESSION_ID"]
    assert sent[0][1].startswith("[AURA SEAT CONTEXT]\nfleet=unitfleet\nseat=codex-seat\nlaunch_id=aura-launch-")
    assert sent[0][1].endswith("[/AURA SEAT CONTEXT]\n\nDo the unit work.\n")
    assert result["prompt_sent"] is True
    assert result["context_file"] == str(context_file)
    assert result["work_file"] == str(work_file)

    log_path = unit / ".aura" / "state" / "sessions.jsonl"
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["seat"] == "codex-seat"
    assert rows[-1]["runtime"] == "codex"
    assert rows[-1]["cwd"] == str(unit)
    assert rows[-1]["work_file"] == str(work_file)


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


def test_spawn_manifest_rejects_name_mismatch(tmp_path):
    from commands import spawn

    role_home = _write_role_home(tmp_path)
    args = argparse.Namespace(
        name="wrong-seat",
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

    assert result["ok"] is False
    assert "manifest seat mismatch" in result["error"]


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

    from commands import spawn
    from lib import registry

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
    assert sent[0][1].endswith(f"Read {role_home / 'BOOTSTRAP.md'} and follow it.\nUse {role_home} as your Desks role home.")

    agent = registry.get_agent("specialist-cell", fleet="flex-specialists")
    assert agent["desks_role_home"] == str(role_home)
    assert agent["desks_bootstrap"] == str(role_home / "BOOTSTRAP.md")

    rows = [
        json.loads(line)
        for line in (tmp_path / "unit" / ".aura" / "state" / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["desks_role_home"] == str(role_home)
    assert rows[-1]["desks_manifest"] == str(role_home / "role.json")


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
            "--as",
            "tester",
            "--transport",
            "tmux",
            "--dedupe-key",
            "fake-e2e-msg",
        )
        assert send_result.returncode == 0, send_result.stderr + send_result.stdout
        assert '"state": "delivered"' in send_result.stdout

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
        assert '"state": "delivered"' in write_result.stdout

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

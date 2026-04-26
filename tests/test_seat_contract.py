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
    from commands.write import _needs_submit_retry

    assert _needs_submit_retry(["Messages to be submitted after next tool call"]) is True
    assert _needs_submit_retry(["Press Enter to submit"]) is True
    assert _needs_submit_retry(["› [Pasted Content 1024 chars]", "", "gpt-5.5 high"]) is True
    assert _needs_submit_retry(["› [Pasted Content 1024 chars]", "• Working (1s)"]) is False
    assert _needs_submit_retry(["Working (2s)", "Running tool call"]) is False


def test_command_override_uses_command_runtime_and_no_claude_trace(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn

    class FakeTerminal:
        SESSION_NAME = "unitfleet"
        BACKEND_NAME = "tmux"

        @staticmethod
        def create_window(name, workdir, detached=False):
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
        def create_window(name, workdir, detached=False):
            created.append((name, workdir, detached))
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
    assert created == [("codex-seat", str(unit), True)]
    assert sent[0][1] == "printf ready"
    assert sent[1][1] == "Do the unit work.\n"
    assert result["prompt_sent"] is True
    assert result["context_file"] == str(context_file)
    assert result["work_file"] == str(work_file)

    log_path = unit / ".aura" / "state" / "sessions.jsonl"
    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["seat"] == "codex-seat"
    assert rows[-1]["runtime"] == "codex"
    assert rows[-1]["cwd"] == str(unit)
    assert rows[-1]["work_file"] == str(work_file)


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
            [sys.executable, str(CLI), "--json", *args],
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
                sys.executable, str(CLI), "--json",
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

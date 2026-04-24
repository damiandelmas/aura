import argparse
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

    assert openclaw_runtime == "openclaw"
    assert openclaw_spec["command"] == "openclaw"
    assert shell_runtime == "shell"
    assert "command" in shell_spec


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
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is True
    assert result["runtime"] == "command"
    assert result["command"] == "python3 -q"
    assert "trace_cell" not in result or result["trace_cell"] is None


def test_capture_stop_and_sense_commands_are_public_contract_names():
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


def test_fake_runtime_spawn_send_capture_stop_e2e(tmp_path):
    if shutil.which("tmux") is None:
        import pytest
        pytest.skip("tmux not installed")

    fleet = f"aura-e2e-{os.getpid()}"
    fake_runtime = ROOT / "tests" / "fixtures" / "fake_runtime.py"
    env = {
        **os.environ,
        "AURA_FLEET": fleet,
        "AURA_REGISTRY_PATH": str(tmp_path / "agents.json"),
        "AURA_DELIVERY_LOG": str(tmp_path / "deliveries.jsonl"),
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

        capture_result = run_aura("capture", "fake1", "--lines", "40")
        assert capture_result.returncode == 0, capture_result.stderr + capture_result.stdout
        assert "READY fake1" in capture_result.stdout
        assert "ACK fake1 hello from e2e" in capture_result.stdout

        sense_result = run_aura("sense", "fake1", "--lines", "40")
        assert sense_result.returncode == 0, sense_result.stderr + sense_result.stdout
        assert '"schema": "aura.sense.v1"' in sense_result.stdout
        assert '"type": "sense"' in sense_result.stdout
        assert '"state": "ready"' in sense_result.stdout
        assert '"next_action": "send"' in sense_result.stdout
        assert (tmp_path / "seats" / "fake1" / "sense" / "events.jsonl").exists()
        assert (tmp_path / "seats" / "fake1" / "sense" / "latest.json").exists()

        stop_result = run_aura("stop", "fake1", "--force")
        assert stop_result.returncode == 0, stop_result.stderr + stop_result.stdout
        assert '"stop": true' in stop_result.stdout
    finally:
        subprocess.run(["tmux", "kill-session", "-t", fleet], capture_output=True, text=True)

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

    assert openclaw_runtime == "openclaw"
    assert openclaw_spec["command"] == "openclaw"
    assert shell_runtime == "shell"
    assert "command" in shell_spec
    assert runtimes.graceful_exit("future-runtime") == "/exit"


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
    env = {
        **os.environ,
        "AURA_FLEET": fleet,
        "AURA_STATE_DIR": str(tmp_path),
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

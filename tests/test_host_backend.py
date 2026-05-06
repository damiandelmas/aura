import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli" / "aura"
sys.path.insert(0, str(ROOT / "cli"))


def _send_args(**overrides):
    values = {
        "target": "unitfleet:worker",
        "message": "host hello",
        "sender": "tester",
        "transport": "auto",
        "mode": "auto",
        "force": False,
        "nudge": False,
        "allow_hidden": False,
        "dedupe_key": "host-unit",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_send_auto_dispatches_host_backend(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / ".aura" / "registry" / "seats.json"))

    from commands import send
    from lib import registry, terminal

    registry.upsert_agent({
        "name": "worker",
        "fleet": "unitfleet",
        "runtime": "command",
        "delivery_backend": "host",
        "control_backend": "host",
        "host_socket": "/tmp/aura/hosts/unit.sock",
        "host_ref": "host:unitfleet:worker",
        "pane_ref": "tmux:unitfleet:%1",
    })
    monkeypatch.setattr(terminal, "configure_session", lambda name: name)
    monkeypatch.setattr(terminal, "target_exists", lambda target: True)
    monkeypatch.setattr(send, "_send_host", lambda args, record, delivery, sender=None: {
        "ok": True,
        "transport": "host",
        "target": args.target,
        "backend_ref": record["host_ref"],
    })
    monkeypatch.setattr(send, "_send_tmux", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("tmux path should not run")))

    result = send.run(_send_args())

    assert result["ok"] is True
    assert result["transport"] == "host"
    assert result["backend_ref"] == "host:unitfleet:worker"


def test_send_host_success_records_attempted_receipt(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))

    from commands import send
    from lib import delivery, host_client

    def fake_request(socket_path, payload, timeout=5.0):
        assert socket_path == "/tmp/aura/hosts/unit.sock"
        assert payload["op"] == "send"
        assert payload["launch_id"] == "aura-launch-unit"
        assert payload["submit"] is True
        assert "[AURA MESSAGE from=tester" in payload["text"]
        return {
            "ok": True,
            "op": "send",
            "delivery_id": payload["delivery_id"],
            "host_pid": 123,
            "child_pid": 456,
            "bytes_requested": 87,
            "bytes_written": 87,
            "write_complete": True,
            "child_alive_before": True,
            "child_alive_after": True,
            "outcome": "write_complete",
        }

    monkeypatch.setattr(host_client, "request", fake_request)
    record = {
        "name": "worker",
        "fleet": "unitfleet",
        "control_backend": "host",
        "delivery_backend": "host",
        "viewport_backend": "tmux",
        "host_socket": "/tmp/aura/hosts/unit.sock",
        "host_ref": "host:unitfleet:worker",
        "host_launch_id": "aura-launch-unit",
        "terminal_ref": "unitfleet:worker",
    }

    result = send._send_host(_send_args(), record, delivery, sender="tester")

    assert result["ok"] is True
    assert result["transport"] == "host"
    assert result["state"] == "attempted"
    assert result["submitted_verified"] is None
    delivery_record = result["record"]
    assert delivery_record["state"] == "attempted"
    assert delivery_record["backend"] == "host"
    assert delivery_record["write_ok"] is True
    assert delivery_record["fallback_used"] is False
    assert delivery_record["attempts"][-1]["evidence"]["backend"] == "host"
    assert delivery_record["attempts"][-1]["evidence"]["write_ok"] is True


def test_send_host_response_loss_records_ambiguous_without_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(tmp_path / "deliveries.jsonl"))

    from commands import send
    from lib import delivery, host_client

    def fake_request(socket_path, payload, timeout=5.0):
        raise host_client.HostClientError("timed out", stage="receive", possible_write=True)

    monkeypatch.setattr(host_client, "request", fake_request)
    record = {
        "name": "worker",
        "fleet": "unitfleet",
        "control_backend": "host",
        "delivery_backend": "host",
        "viewport_backend": "tmux",
        "host_socket": "/tmp/aura/hosts/unit.sock",
        "host_ref": "host:unitfleet:worker",
        "host_launch_id": "aura-launch-unit",
    }

    result = send._send_host(_send_args(dedupe_key="host-ambiguous"), record, delivery, sender="tester")

    assert result["ok"] is False
    assert result["transport"] == "host"
    assert result["state"] == "ambiguous"
    assert result["possible_write"] is True
    assert result["ambiguity_reason"] == "host_response_lost_after_request"
    delivery_record = result["record"]
    assert delivery_record["state"] == "ambiguous"
    assert delivery_record["fallback_used"] is False
    assert delivery_record["possible_write"] is True
    assert delivery_record["error_stage"] == "receive"


def test_host_backed_fake_runtime_spawn_send_inspect_stop_e2e(tmp_path):
    if shutil.which("tmux") is None:
        import pytest

        pytest.skip("tmux not installed")

    fleet = f"aura-host-e2e-{os.getpid()}"
    name = "hostfake"
    fake_runtime = ROOT / "tests" / "fixtures" / "fake_runtime.py"
    unit = tmp_path / "workspace"
    unit.mkdir()
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "AURA_REGISTRY_PATH": str(tmp_path / ".aura" / "registry" / "seats.json"),
        "AURA_DELIVERY_LOG": str(tmp_path / ".aura" / "registry" / "deliveries.jsonl"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    def run_aura(*args, timeout=20):
        result = subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=env,
            timeout=timeout,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        return json.loads(result.stdout)

    try:
        spawned = run_aura(
            "spawn",
            name,
            "--fleet",
            fleet,
            "--runtime",
            "command",
            "--command",
            f"{sys.executable} -u {fake_runtime} --name {name} --mode echo",
            "--cwd",
            str(unit),
            "--delivery-backend",
            "host",
            "--control-backend",
            "host",
            "--as-pane",
        )
        assert spawned["ok"] is True
        assert spawned["control_backend"] == "host"
        assert spawned["delivery_backend"] == "host"
        assert spawned["viewport_backend"] == "tmux"
        assert spawned["host_socket"]
        assert spawned["host_status"] == "alive"
        assert spawned["pane_ref"].startswith(f"tmux:{fleet}:%")

        sent = run_aura(
            "send",
            f"{fleet}:{name}",
            "host delivery smoke",
            "--as",
            "tester",
            "--dedupe-key",
            "host-e2e-smoke",
        )
        assert sent["ok"] is True
        assert sent["transport"] == "host"
        assert sent["state"] == "attempted"
        assert sent["submitted_verified"] is None

        deadline = time.time() + 5
        inspected = None
        while time.time() < deadline:
            inspected = run_aura("inspect", f"{fleet}:{name}", "--raw", "--lines", "80")
            output = "\n".join(inspected.get("output") or [])
            if "ACK hostfake host delivery smoke" in output:
                break
            time.sleep(0.2)
        assert inspected is not None
        output = "\n".join(inspected.get("output") or [])
        assert "READY hostfake" in output
        assert "ACK hostfake host delivery smoke" in output
        assert inspected["host"] == "alive"
        assert inspected["child"] == "alive"

        records = [
            json.loads(line)
            for line in (tmp_path / ".aura" / "registry" / "deliveries.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        final = records[-1]
        assert final["backend"] == "host"
        assert final["state"] == "attempted"
        assert final["write_ok"] is True
        assert final["fallback_used"] is False

        stopped = run_aura("stop", f"{fleet}:{name}", "--force")
        assert stopped["ok"] is True
        assert stopped["stop"] is True
        assert stopped["host_stop"]["ok"] is True
        assert stopped["host_stop"]["child_alive"] is False
    finally:
        subprocess.run(["tmux", "kill-session", "-t", fleet], capture_output=True, text=True)

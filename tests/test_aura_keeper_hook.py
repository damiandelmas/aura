import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load_hook():
    path = ROOT / "cli" / "hooks" / "aura_keeper_hook.py"
    spec = importlib.util.spec_from_file_location("aura_keeper_hook", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules.pop("aura_keeper_hook", None)
    spec.loader.exec_module(module)
    return module


def _write_transcript(path: Path, rows: int) -> None:
    path.write_text(
        "".join(
            json.dumps(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user" if n % 2 == 0 else "assistant",
                        "content": [{"type": "text", "text": f"message {n}"}],
                    },
                }
            )
            + "\n"
            for n in range(rows)
        ),
        encoding="utf-8",
    )


def test_trace_counter_ignores_tool_rows(tmp_path):
    hook = _load_hook()
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps({"type": "response_item", "payload": {"type": "message", "role": "user", "content": []}}),
                json.dumps({"type": "response_item", "payload": {"type": "function_call", "name": "exec_command"}}),
                json.dumps({"type": "response_item", "payload": {"type": "function_call_output", "output": "noise"}}),
                json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": {}}}),
                json.dumps({"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": []}}),
                json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": "hello"}}),
                json.dumps({"type": "event_msg", "payload": {"type": "agent_message", "message": "hi"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert hook._transcript_message_count({"transcript_path": str(transcript)}) == 4


def test_stop_launches_after_message_count_and_then_interval(tmp_path, monkeypatch):
    hook = _load_hook()
    root = tmp_path / "agent"
    transcript = tmp_path / "session.jsonl"
    launched = []

    monkeypatch.setattr(
        hook,
        "_launch_keeper",
        lambda root, *, target, boundary: launched.append({"target": target, "boundary": boundary}) or 123,
    )

    _write_transcript(transcript, 14)
    hook._handle_stop(root, {"transcript_path": str(transcript), "context_percent": 60}, "fleet:worker", "019e-session")
    assert launched == []

    _write_transcript(transcript, 15)
    hook._handle_stop(root, {"transcript_path": str(transcript), "context_percent": 60}, "fleet:worker", "019e-session")
    state = json.loads((root / "memories" / ".hook-state" / "aura-keeper-hook.json").read_text(encoding="utf-8"))

    assert launched == [{"target": "fleet:worker", "boundary": "m15"}]
    assert state["sessions"]["019e-session"]["last_trace_conversation_count"] == 15

    _write_transcript(transcript, 29)
    hook._handle_stop(root, {"transcript_path": str(transcript), "context_percent": 65}, "fleet:worker", "019e-session")
    assert launched == [{"target": "fleet:worker", "boundary": "m15"}]

    _write_transcript(transcript, 30)
    hook._handle_stop(root, {"transcript_path": str(transcript), "context_percent": 76}, "fleet:worker", "019e-session")
    assert launched[-1] == {"target": "fleet:worker", "boundary": "m30"}


def test_precompact_always_launches_keeper_memory(tmp_path, monkeypatch):
    hook = _load_hook()
    root = tmp_path / "agent"
    launched = []

    monkeypatch.setattr(
        hook,
        "_launch_keeper",
        lambda root, *, target, boundary: launched.append({"target": target, "boundary": boundary}) or 456,
    )

    hook._handle_precompact(root, "fleet:worker", "019e-session")
    hook._handle_precompact(root, "fleet:worker", "019e-session")

    state = json.loads((root / "memories" / ".hook-state" / "aura-keeper-hook.json").read_text(encoding="utf-8"))
    assert launched == [
        {"target": "fleet:worker", "boundary": "precompact"},
        {"target": "fleet:worker", "boundary": "precompact"},
    ]
    assert state["sessions"]["019e-session"]["precompact_count"] == 2


def test_percent_can_be_read_from_transcript(tmp_path):
    hook = _load_hook()
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        json.dumps({"usage": {"total_tokens": 2500, "context_window": 10000}}) + "\n"
        + json.dumps({"usage": {"total_tokens": 5200, "context_window": 10000}}) + "\n",
        encoding="utf-8",
    )

    assert hook._context_percent({"transcript_path": str(transcript)}) == 52


def test_percent_reads_real_codex_payload_info_shape(tmp_path):
    hook = _load_hook()
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {"total_token_usage": {"total_tokens": 4200}, "model_context_window": 10000},
                    "rate_limits": {"primary": {"used_percent": 99}},
                },
            }
        )
        + "\n"
        + json.dumps(
            {
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {"total_token_usage": {"total_tokens": 7600}, "model_context_window": 10000},
                    "rate_limits": {"primary": {"used_percent": 25}},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert hook._context_percent({"transcript_path": str(transcript)}) == 76
    assert hook._context_percent(
        {
            "payload": {
                "type": "token_count",
                "info": {"total_token_usage": {"total_tokens": 2600}, "model_context_window": 10000},
                "rate_limits": {"primary": {"used_percent": 99}},
            }
        }
    ) == 26


def test_rate_limit_percent_is_not_context_percent():
    hook = _load_hook()

    assert hook._context_percent({"rate_limits": {"primary": {"used_percent": 99}}}) is None


def test_failed_stop_launch_does_not_consume_message_count(tmp_path, monkeypatch):
    hook = _load_hook()
    root = tmp_path / "agent"
    transcript = tmp_path / "session.jsonl"
    calls = []
    _write_transcript(transcript, 15)

    def fake_launch(root, *, target, boundary):
        calls.append(boundary)
        return None if len(calls) == 1 else 123

    monkeypatch.setattr(hook, "_launch_keeper", fake_launch)

    hook._handle_stop(root, {"transcript_path": str(transcript), "context_percent": 60}, "fleet:worker", "019e-session")
    state = json.loads((root / "memories" / ".hook-state" / "aura-keeper-hook.json").read_text(encoding="utf-8"))
    assert "last_trace_conversation_count" not in state["sessions"]["019e-session"]
    assert state["sessions"]["019e-session"]["last_launch_failed_boundary"] == "m15"

    hook._handle_stop(root, {"transcript_path": str(transcript), "context_percent": 60}, "fleet:worker", "019e-session")
    state = json.loads((root / "memories" / ".hook-state" / "aura-keeper-hook.json").read_text(encoding="utf-8"))
    assert calls == ["m15", "m15"]
    assert state["sessions"]["019e-session"]["last_trace_conversation_count"] == 15


def test_default_message_count_thresholds(monkeypatch):
    hook = _load_hook()
    monkeypatch.delenv("AURA_KEEPER_FIRST_TRACE_MESSAGES", raising=False)
    monkeypatch.delenv("AURA_KEEPER_TRACE_INTERVAL_MESSAGES", raising=False)

    assert hook._first_trace_messages() == 15
    assert hook._trace_interval_messages() == 15


def test_hook_paused_by_session_state(tmp_path):
    hook = _load_hook()
    root = tmp_path / "agent"
    state_path = root / "memories" / ".hook-state" / "aura-keeper-hook.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "schema": "aura.keeper_hook_state.v1",
                "sessions": {
                    "019e-session": {
                        "disabled_for_manual_prompt_iteration": True,
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert hook._hook_paused(root, "019e-session") is True
    assert hook._hook_paused(root, "other-session") is False


def test_hook_paused_by_pause_file(tmp_path):
    hook = _load_hook()
    root = tmp_path / "agent"
    pause_path = root / "memories" / ".hook-state" / "keeper-paused"
    pause_path.parent.mkdir(parents=True)
    pause_path.write_text("manual prompt iteration\n", encoding="utf-8")

    assert hook._hook_paused(root, "019e-session") is True


def test_launch_keeper_returns_none_when_detach_fails(tmp_path, monkeypatch):
    hook = _load_hook()
    calls = []

    def fake_popen(cmd, **kwargs):
        calls.append(cmd)
        raise OSError("no-python")

    monkeypatch.setattr(hook.subprocess, "Popen", fake_popen)

    assert hook._launch_keeper(tmp_path / "agent", target="fleet:worker", boundary="75") is None
    assert calls


def test_launch_keeper_returns_detached_process_pid(tmp_path, monkeypatch):
    hook = _load_hook()

    class FakeProc:
        pid = 12345

    def fake_popen(cmd, **kwargs):
        assert cmd[-2:] == ["--boundary", "75"]
        assert kwargs["stdin"] is hook.subprocess.DEVNULL
        assert kwargs["start_new_session"] is True
        return FakeProc()

    monkeypatch.setattr(hook.subprocess, "Popen", fake_popen)

    assert hook._launch_keeper(tmp_path / "agent", target="fleet:worker", boundary="75") == 12345


def test_stop_hook_detaches_launcher_before_codex_timeout(tmp_path):
    hook_path = ROOT / "cli" / "hooks" / "aura_keeper_hook.py"
    root = tmp_path / "agent"
    (root / ".codex").mkdir(parents=True)
    (root / "manifest.json").write_text('{"runtime":"codex"}\n', encoding="utf-8")
    transcript = tmp_path / "session.jsonl"
    _write_transcript(transcript, 15)
    payload = {"hook_event_name": "Stop", "session_id": "019e-session", "context_percent": 60, "transcript_path": str(transcript)}

    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(hook_path), "Stop"],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=1,
        env={
            **os.environ,
            "AURA_AGENT_PACKAGE_ID": "i_pkg",
            "AURA_AGENT_PACKAGE_ROOT": str(root),
            "AURA_FLEET": "fleet",
            "AURA_SEAT": "worker",
            "AURA_KEEPER_HOOK_COMMAND": f"{sys.executable} -c 'import time; time.sleep(1)'",
        },
    )
    elapsed = time.monotonic() - started

    assert result.returncode == 0, result.stderr
    assert elapsed < 0.5
    launch_log = root / "memories" / ".hook-state" / "keeper-launch.log"
    assert '"pid"' in launch_log.read_text(encoding="utf-8")

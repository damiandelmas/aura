import importlib.util
import json
import sys
import subprocess
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


def test_stop_threshold_launches_highest_due_boundary_once(tmp_path, monkeypatch):
    hook = _load_hook()
    root = tmp_path / "agent"
    launched = []

    monkeypatch.setattr(
        hook,
        "_launch_keeper",
        lambda root, *, target, boundary: launched.append({"target": target, "boundary": boundary}) or 123,
    )

    hook._handle_stop(root, {"context_percent": 60}, "fleet:worker", "019e-session")
    state = json.loads((root / "memories" / ".hook-state" / "aura-keeper-hook.json").read_text(encoding="utf-8"))

    assert launched == [{"target": "fleet:worker", "boundary": "50"}]
    assert state["sessions"]["019e-session"]["fired_boundaries"] == [25, 50]

    hook._handle_stop(root, {"context_percent": 65}, "fleet:worker", "019e-session")
    assert launched == [{"target": "fleet:worker", "boundary": "50"}]

    hook._handle_stop(root, {"context_percent": 76}, "fleet:worker", "019e-session")
    assert launched[-1] == {"target": "fleet:worker", "boundary": "75"}


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


def test_failed_stop_launch_does_not_consume_boundary(tmp_path, monkeypatch):
    hook = _load_hook()
    root = tmp_path / "agent"
    calls = []

    def fake_launch(root, *, target, boundary):
        calls.append(boundary)
        return None if len(calls) == 1 else 123

    monkeypatch.setattr(hook, "_launch_keeper", fake_launch)

    hook._handle_stop(root, {"context_percent": 60}, "fleet:worker", "019e-session")
    state = json.loads((root / "memories" / ".hook-state" / "aura-keeper-hook.json").read_text(encoding="utf-8"))
    assert state["sessions"]["019e-session"]["fired_boundaries"] == []
    assert state["sessions"]["019e-session"]["last_launch_failed_boundary"] == 50

    hook._handle_stop(root, {"context_percent": 60}, "fleet:worker", "019e-session")
    state = json.loads((root / "memories" / ".hook-state" / "aura-keeper-hook.json").read_text(encoding="utf-8"))
    assert calls == ["50", "50"]
    assert state["sessions"]["019e-session"]["fired_boundaries"] == [25, 50]


def test_default_thresholds_stop_at_75(monkeypatch):
    hook = _load_hook()
    monkeypatch.delenv("AURA_KEEPER_MEMORY_THRESHOLDS", raising=False)

    assert hook._thresholds() == (25, 50, 75)


def test_launch_keeper_requires_ok_receipt(tmp_path, monkeypatch):
    hook = _load_hook()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout='{"ok": false, "error": "no-flex"}\n')

    monkeypatch.setattr(hook.subprocess, "run", fake_run)

    assert hook._launch_keeper(tmp_path / "agent", target="fleet:worker", boundary="75") is None


def test_launch_keeper_returns_worker_pid_from_receipt(tmp_path, monkeypatch):
    hook = _load_hook()

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout='{"ok": true, "pid": 12345}\n')

    monkeypatch.setattr(hook.subprocess, "run", fake_run)

    assert hook._launch_keeper(tmp_path / "agent", target="fleet:worker", boundary="75") == 12345

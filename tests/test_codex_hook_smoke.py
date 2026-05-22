import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMOKE_PATH = ROOT / "scripts" / "codex-hook-smoke.py"


def load_smoke_module():
    spec = importlib.util.spec_from_file_location("codex_hook_smoke", SMOKE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_codex_hook_smoke_trims_nested_failure_payloads():
    smoke = load_smoke_module()

    payload = {
        "long": "x" * 20,
        "items": [{"value": "y" * 20}, {"value": "z"}],
        "nested": {"number": 3},
    }

    trimmed = smoke._trim_json(payload, string_limit=8, list_limit=1)

    assert trimmed["long"] == "xxxxxxxx... <trimmed 12 chars>"
    assert trimmed["items"] == [{"value": "yyyyyyyy... <trimmed 12 chars>"}, {"trimmed_items": 1}]
    assert trimmed["nested"] == {"number": 3}


def test_codex_hook_smoke_failure_summary_includes_durable_evidence(monkeypatch, tmp_path):
    smoke = load_smoke_module()
    hook_log = tmp_path / "events.jsonl"
    hook_log.write_text(
        "\n".join([
            json.dumps({"event_arg": "SessionStart", "session_id": "thread-1"}),
            json.dumps({"event_arg": "UserPromptSubmit", "session_id": "thread-1"}),
            json.dumps({"event_arg": "AuraReportPublish", "session_id": "thread-1", "returncode": 1}),
            "",
        ]),
        encoding="utf-8",
    )

    def fake_run_json(cmd, *, env, timeout):
        if "inspect" in cmd:
            return {
                "runtime_session_binding": "unbound",
                "runtime_session_id": None,
                "runtime_session_evidence": {"reason": "unit-test"},
                "output": [f"line-{index}" for index in range(45)],
            }
        if "report" in cmd:
            return {"record": {"report_id": "rpt-1", "work": "unit"}}
        raise AssertionError(cmd)

    monkeypatch.setattr(smoke, "_safe_run_json", fake_run_json)

    summary = smoke._failure_summary(
        error=TimeoutError("missing hook"),
        phase="wait-aura-report-publish",
        state_dir=tmp_path,
        fleet="fleet",
        seat="seat",
        spawn={
            "ok": True,
            "name": "seat",
            "fleet": "fleet",
            "runtime": "codex",
            "command": "codex",
            "prompt_delivery": {"submitted": True, "extra": "x" * 30},
            "ignored": "not surfaced",
        },
        codex_home=tmp_path / "codex-home",
        hook_log=hook_log,
        env={"AURA_STATE_DIR": str(tmp_path)},
    )

    assert summary["ok"] is False
    assert summary["phase"] == "wait-aura-report-publish"
    assert summary["error"] == "TimeoutError: missing hook"
    assert summary["hook_event_names"] == ["SessionStart", "UserPromptSubmit", "AuraReportPublish"]
    assert summary["hook_event_count"] == 3
    assert summary["user_prompt_submit_count"] == 1
    assert summary["aura_report_publish_count"] == 1
    assert summary["inspect"]["runtime_session_binding"] == "unbound"
    assert summary["latest_report"] == {"report_id": "rpt-1", "work": "unit"}
    assert summary["spawn"]["prompt_delivery"]["submitted"] is True
    assert "ignored" not in summary["spawn"]
    assert len(summary["terminal_tail"]) == 40
    assert summary["terminal_tail"][0] == "line-5"


def test_codex_hook_smoke_write_profile_materializes_expected_hooks(tmp_path):
    smoke = load_smoke_module()

    root = smoke.write_profile(tmp_path, "hook-smoke")
    hooks = json.loads((root / "hooks.json").read_text(encoding="utf-8"))

    assert (root / "config.toml").read_text(encoding="utf-8") == "[features]\nhooks = true\n"
    assert (root / "hooks" / "codex_hook_smoke.py").is_file()
    assert set(hooks["hooks"]) == {"SessionStart", "UserPromptSubmit", "PreCompact", "PostCompact", "Stop"}
    assert hooks["hooks"]["Stop"][0]["hooks"][0]["timeout"] == 20
    assert "__AURA_CLI__" not in (root / "hooks" / "codex_hook_smoke.py").read_text(encoding="utf-8")

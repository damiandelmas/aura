import importlib.util
import json
import subprocess
import sys
from types import SimpleNamespace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATES_PATH = ROOT / "scripts" / "aura-test-gates.py"


def load_gates_module():
    spec = importlib.util.spec_from_file_location("aura_test_gates", GATES_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_confidence_gate_selects_full_and_focused_nonlive_steps():
    gates = load_gates_module()

    steps = gates.select_steps(["confidence"], include_live=False)

    names = [step.name for step in steps]
    assert names == [
        "full-nonlive",
        "py-compile",
        "diff-check",
        "codex-hook-nonlive",
        "runtime-plumbing",
    ]
    assert all("test_codex_hook_smoke_live.py" not in " ".join(step.command) for step in steps)


def test_include_live_appends_codex_live_smoke():
    gates = load_gates_module()

    steps = gates.select_steps(["baseline"], include_live=True)

    assert [step.name for step in steps] == ["baseline-pytest", "py-compile", "diff-check", "codex-hook-live"]
    assert steps[-1].env == {"AURA_RUN_LIVE_CODEX_SMOKE": "1"}
    assert "tests/test_codex_hook_smoke_live.py" in steps[-1].command
    assert steps[-1].timeout == 240


def test_hygiene_gate_runs_public_surface_compile_and_diff_check():
    gates = load_gates_module()

    steps = gates.select_steps(["hygiene"], include_live=False)

    assert [step.name for step in steps] == ["public-surface-contract", "py-compile", "diff-check"]
    assert steps[0].command == [*gates.PYTEST_BASE, "tests/test_public_surface_contract.py"]
    assert steps[-1].command == ["git", "diff", "--check"]


def test_dry_run_outputs_json_without_running_commands(capsys):
    gates = load_gates_module()

    result = gates.main(["--gate", "runtime", "--dry-run", "--timeout", "77"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["gates"] == ["runtime"]
    assert payload["dry_run"] is True
    assert payload["timeout_override"] == 77
    assert [row["name"] for row in payload["results"]] == ["runtime-plumbing"]
    assert payload["results"][0]["returncode"] is None
    assert payload["results"][0]["timeout_seconds"] == 77


def test_run_step_records_timeout(monkeypatch):
    gates = load_gates_module()

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=kwargs.get("args") or args[0],
            timeout=kwargs["timeout"],
            output="partial stdout",
            stderr="partial stderr",
        )

    monkeypatch.setattr(gates.subprocess, "run", fake_run)

    record = gates.run_step(gates.Step("slow", ["slow-command"], timeout=3), dry_run=False)

    assert record["ok"] is False
    assert record["timed_out"] is True
    assert record["returncode"] is None
    assert record["timeout_seconds"] == 3
    assert record["stdout_tail"] == "partial stdout"
    assert record["stderr_tail"] == "partial stderr"


def test_parse_pytest_summary_extracts_counts():
    gates = load_gates_module()

    result = gates._parse_pytest_summary(
        "...\n461 passed, 2 skipped, 8 warnings in 72.24s (0:01:12)\n"
    )

    assert result == {
        "summary_line": "461 passed, 2 skipped, 8 warnings in 72.24s (0:01:12)",
        "counts": {"passed": 461, "skipped": 2, "warnings": 8},
    }


def test_run_step_records_pytest_summary(monkeypatch):
    gates = load_gates_module()

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=".. [100%]\n2 passed in 0.01s\n",
            stderr="",
        )

    monkeypatch.setattr(gates.subprocess, "run", fake_run)

    record = gates.run_step(gates.Step("pytest", [*gates.PYTEST_BASE, "tests/unit.py"]), dry_run=False)

    assert record["ok"] is True
    assert record["summary_line"] == "2 passed in 0.01s"
    assert record["counts"] == {"passed": 2}


def test_run_steps_fail_fast_records_skipped_steps(monkeypatch):
    gates = load_gates_module()
    steps = [
        gates.Step("first", ["first"]),
        gates.Step("second", ["second"], timeout=22),
        gates.Step("third", ["third"]),
    ]

    def fake_run_step(step, **kwargs):
        return {
            "name": step.name,
            "command": step.command,
            "env": {"PYTHONDONTWRITEBYTECODE": "1"},
            "timeout_seconds": step.timeout,
            "dry_run": False,
            "ok": step.name != "first",
            "returncode": 1 if step.name == "first" else 0,
            "duration_seconds": 0.01,
        }

    monkeypatch.setattr(gates, "run_step", fake_run_step)

    results = gates.run_steps(steps, dry_run=False, fail_fast=True)

    assert [row["name"] for row in results] == ["first", "second", "third"]
    assert results[0]["ok"] is False
    assert results[1]["skipped"] is True
    assert results[1]["skip_reason"] == "fail-fast after first"
    assert results[1]["timeout_seconds"] == 22
    assert results[2]["skipped"] is True


def test_aggregate_results_sums_step_and_pytest_counts():
    gates = load_gates_module()

    aggregate = gates._aggregate_results([
        {"ok": True, "counts": {"passed": 2, "skipped": 1}},
        {"ok": False, "timed_out": True, "counts": {"failed": 1}},
        {"ok": None, "skipped": True},
        {"ok": True, "dry_run": True},
    ])

    assert aggregate == {
        "steps": {
            "total": 4,
            "passed": 1,
            "failed": 1,
            "skipped": 1,
            "timed_out": 1,
            "dry_run": 1,
        },
        "counts": {"passed": 2, "skipped": 1, "failed": 1},
    }


def test_main_reports_fail_fast_flag(capsys):
    gates = load_gates_module()

    result = gates.main(["--gate", "runtime", "--dry-run", "--fail-fast"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["fail_fast"] is True
    assert payload["aggregate"]["steps"]["passed"] == 0
    assert payload["aggregate"]["steps"]["dry_run"] == 1


def test_default_output_path_uses_aura_test_gates_dir():
    gates = load_gates_module()

    path = gates._default_output_path(
        gates_selected=["confidence", "live-codex"],
        started_at="2026-05-22T01:02:03.456789+00:00",
    )

    assert path == ROOT / ".aura" / "test-gates" / "20260522T010203456789Z-confidence-live-codex.json"


def test_output_writes_same_json_envelope(tmp_path, capsys):
    gates = load_gates_module()
    output_path = tmp_path / "evidence" / "gates.json"

    result = gates.main(["--gate", "runtime", "--dry-run", "--output", str(output_path)])

    assert result == 0
    printed = json.loads(capsys.readouterr().out)
    saved = json.loads(output_path.read_text(encoding="utf-8"))
    assert printed == saved
    assert printed["schema"] == "aura.test_gates.v1"
    assert printed["output_path"] == str(output_path)
    assert printed["repo_root"] == str(ROOT)
    assert printed["duration_seconds"] >= 0


def test_save_writes_default_evidence_path(capsys):
    gates = load_gates_module()

    result = gates.main(["--gate", "runtime", "--dry-run", "--save"])

    assert result == 0
    printed = json.loads(capsys.readouterr().out)
    output_path = Path(printed["output_path"])
    try:
        saved = json.loads(output_path.read_text(encoding="utf-8"))
        assert saved == printed
        assert output_path.parent == ROOT / ".aura" / "test-gates"
        assert output_path.name.endswith("-runtime.json")
    finally:
        output_path.unlink(missing_ok=True)


def test_verify_payload_accepts_clean_executed_evidence():
    gates = load_gates_module()

    result = gates._verify_payload({
        "schema": "aura.test_gates.v1",
        "ok": True,
        "gates": ["hygiene"],
        "aggregate": {
            "steps": {"total": 2, "passed": 2, "failed": 0, "skipped": 0, "timed_out": 0, "dry_run": 0},
            "counts": {},
        },
        "results": [
            {"name": "py-compile", "ok": True, "dry_run": False},
            {"name": "diff-check", "ok": True, "dry_run": False},
        ],
    })

    assert result["ok"] is True
    assert result["errors"] == []


def test_verify_payload_require_live_accepts_live_evidence():
    gates = load_gates_module()

    result = gates._verify_payload({
        "schema": "aura.test_gates.v1",
        "ok": True,
        "gates": ["confidence"],
        "include_live": True,
        "aggregate": {
            "steps": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "timed_out": 0, "dry_run": 0},
            "counts": {"passed": 2},
        },
        "results": [{
            "name": "codex-hook-live",
            "ok": True,
            "dry_run": False,
            "timed_out": False,
            "returncode": 0,
            "counts": {"passed": 2},
        }],
    }, require_live=True)

    assert result["ok"] is True
    assert result["require_live"] is True


def test_verify_payload_require_live_rejects_fake_live_evidence():
    gates = load_gates_module()

    result = gates._verify_payload({
        "schema": "aura.test_gates.v1",
        "ok": True,
        "gates": ["confidence"],
        "include_live": True,
        "aggregate": {
            "steps": {"total": 1, "passed": 0, "failed": 0, "skipped": 0, "timed_out": 0, "dry_run": 1},
            "counts": {},
        },
        "results": [{"name": "codex-hook-live", "ok": True, "dry_run": True, "returncode": None}],
    }, require_live=True, allow_dry_run=True)

    assert result["ok"] is False
    assert "live-step-not-executed-pass" in result["errors"]


def test_verify_payload_require_live_rejects_nonlive_confidence():
    gates = load_gates_module()

    result = gates._verify_payload({
        "schema": "aura.test_gates.v1",
        "ok": True,
        "gates": ["confidence"],
        "include_live": False,
        "aggregate": {
            "steps": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "timed_out": 0, "dry_run": 0},
            "counts": {"passed": 1},
        },
        "results": [{"name": "full-nonlive", "ok": True, "dry_run": False}],
    }, require_live=True)

    assert result["ok"] is False
    assert "live-not-included" in result["errors"]
    assert "live-step-missing" in result["errors"]


def test_verify_payload_rejects_failed_and_dry_run_evidence():
    gates = load_gates_module()

    result = gates._verify_payload({
        "schema": "aura.test_gates.v1",
        "ok": False,
        "gates": ["confidence"],
        "aggregate": {
            "steps": {"total": 2, "passed": 0, "failed": 1, "skipped": 0, "timed_out": 1, "dry_run": 1},
            "counts": {"failed": 1},
        },
        "results": [
            {"name": "full-nonlive", "ok": False, "timed_out": True},
            {"name": "runtime", "ok": True, "dry_run": True},
        ],
    })

    assert result["ok"] is False
    assert "payload-not-ok" in result["errors"]
    assert "failed-steps-present" in result["errors"]
    assert "timed_out-steps-present" in result["errors"]
    assert "dry-run-steps-present" in result["errors"]
    assert "pytest-failed-present" in result["errors"]
    assert "step-timed-out:full-nonlive" in result["errors"]
    assert "step-dry-run:runtime" in result["errors"]


def test_verify_evidence_cli_accepts_saved_clean_packet(tmp_path, capsys):
    gates = load_gates_module()
    evidence = tmp_path / "evidence.json"
    evidence.write_text(json.dumps({
        "schema": "aura.test_gates.v1",
        "ok": True,
        "gates": ["confidence"],
        "include_live": True,
        "aggregate": {
            "steps": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "timed_out": 0, "dry_run": 0},
            "counts": {"passed": 2},
        },
        "results": [{
            "name": "codex-hook-live",
            "ok": True,
            "dry_run": False,
            "timed_out": False,
            "returncode": 0,
            "counts": {"passed": 2},
        }],
    }), encoding="utf-8")

    result = gates.main(["--verify", str(evidence), "--require-live"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["path"] == str(evidence)
    assert payload["require_live"] is True


def test_verify_evidence_cli_rejects_dry_run_by_default(tmp_path, capsys):
    gates = load_gates_module()
    evidence = tmp_path / "dry-run.json"
    evidence.write_text(json.dumps({
        "schema": "aura.test_gates.v1",
        "ok": True,
        "gates": ["runtime"],
        "aggregate": {
            "steps": {"total": 1, "passed": 0, "failed": 0, "skipped": 0, "timed_out": 0, "dry_run": 1},
            "counts": {},
        },
        "results": [{"name": "runtime-plumbing", "ok": True, "dry_run": True}],
    }), encoding="utf-8")

    result = gates.main(["--verify", str(evidence)])

    assert result == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "dry-run-steps-present" in payload["errors"]

    allowed = gates.main(["--verify", str(evidence), "--allow-dry-run"])
    assert allowed == 0


def test_latest_evidence_path_picks_newest_file(tmp_path):
    gates = load_gates_module()
    old = tmp_path / "20260101-old.json"
    new = tmp_path / "20260102-new.json"
    old.write_text("{}", encoding="utf-8")
    new.write_text("{}", encoding="utf-8")

    assert gates.latest_evidence_path(tmp_path) == new


def test_latest_evidence_path_can_filter_by_gate(tmp_path):
    gates = load_gates_module()
    confidence = tmp_path / "20260101-confidence.json"
    hygiene = tmp_path / "20260102-hygiene.json"
    confidence.write_text("{}", encoding="utf-8")
    hygiene.write_text("{}", encoding="utf-8")

    assert gates.latest_evidence_path(tmp_path, gate="confidence") == confidence
    assert gates.latest_evidence_path(tmp_path, gate="runtime") is None


def test_verify_latest_reports_missing_evidence(monkeypatch, tmp_path, capsys):
    gates = load_gates_module()
    monkeypatch.setattr(gates, "latest_evidence_path", lambda directory=None, gate=None: None)

    result = gates.main(["--verify-latest", "--latest-gate", "confidence"])

    assert result == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["latest_gate"] == "confidence"
    assert payload["errors"] == ["no-saved-evidence"]


def test_verify_latest_uses_latest_saved_path(monkeypatch, tmp_path, capsys):
    gates = load_gates_module()
    evidence = tmp_path / "latest.json"
    evidence.write_text(json.dumps({
        "schema": "aura.test_gates.v1",
        "ok": True,
        "gates": ["hygiene"],
        "include_live": True,
        "aggregate": {
            "steps": {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "timed_out": 0, "dry_run": 0},
            "counts": {"passed": 2},
        },
        "results": [{
            "name": "codex-hook-live",
            "ok": True,
            "dry_run": False,
            "timed_out": False,
            "returncode": 0,
            "counts": {"passed": 2},
        }],
    }), encoding="utf-8")
    captured = {}

    def fake_latest(directory=None, gate=None):
        captured["gate"] = gate
        return evidence

    monkeypatch.setattr(gates, "latest_evidence_path", fake_latest)

    result = gates.main(["--verify-latest", "--latest-gate", "hygiene", "--require-live"])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["path"] == str(evidence)
    assert payload["require_live"] is True
    assert captured["gate"] == "hygiene"

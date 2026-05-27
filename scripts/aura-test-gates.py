#!/usr/bin/env python3
"""Run repeatable Aura test confidence gates."""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTEST_BASE = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
SUMMARY_RE = re.compile(r"(?P<count>\d+)\s+(?P<kind>passed|failed|skipped|warnings?|errors?|xfailed|xpassed)")
PYTEST_SUMMARY_RE = re.compile(
    r"(?P<summary>(?:\d+\s+(?:passed|failed|skipped|warnings?|errors?|xfailed|xpassed)"
    r"(?:,\s*)?)+\s+in\s+[\d.]+s(?:\s+\([^)]*\))?)"
)


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    timeout: int = 600


def _repo_paths(*patterns: str) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        paths.extend(glob.glob(str(ROOT / pattern)))
    return sorted(paths)


def _py_compile_step() -> Step:
    paths = [
        str(ROOT / "cli" / "aura"),
        *_repo_paths("cli/commands/*.py", "cli/lib/*.py"),
        str(ROOT / "scripts" / "codex-hook-smoke.py"),
        str(ROOT / "scripts" / "aura-test-gates.py"),
    ]
    return Step("py-compile", [sys.executable, "-m", "py_compile", *paths], timeout=120)


def _diff_check_step() -> Step:
    return Step("diff-check", ["git", "diff", "--check"], timeout=60)


def _pytest_step(name: str, *paths: str, env: dict[str, str] | None = None, timeout: int = 600) -> Step:
    return Step(name, [*PYTEST_BASE, *paths], env or {}, timeout=timeout)


def _public_surface_step() -> Step:
    return _pytest_step("public-surface-contract", "tests/test_public_surface_contract.py", timeout=60)


def gates() -> dict[str, list[Step]]:
    baseline = [
        _pytest_step(
            "baseline-pytest",
            "tests/test_seat_contract.py",
            "tests/test_registry_and_broadcast.py",
            "tests/test_state_paths.py",
            timeout=180,
        ),
        _py_compile_step(),
        _diff_check_step(),
    ]
    codex_hook = [
        _pytest_step(
            "codex-hook-nonlive",
            "tests/test_codex_hook_smoke.py",
            "tests/test_runtime_boxes.py",
            "tests/test_seat_contract.py",
            "tests/test_sessions_command.py",
            "tests/test_runtime_session_identity.py",
        )
    ]
    runtime = [
        _pytest_step(
            "runtime-plumbing",
            "tests/test_omx_adapter.py",
            "tests/test_runtime_boxes.py",
            "tests/test_profile_command.py",
            "tests/test_quick_command.py",
            "tests/test_seat_contract.py",
            "tests/test_terminal_posture.py",
        )
    ]
    full = [
        _pytest_step("full-nonlive", timeout=180),
        _py_compile_step(),
        _diff_check_step(),
    ]
    live_codex = [
        _pytest_step(
            "codex-hook-live",
            "tests/test_codex_hook_smoke_live.py",
            env={"AURA_RUN_LIVE_CODEX_SMOKE": "1"},
            timeout=240,
        )
    ]
    return {
        "baseline": baseline,
        "codex-hook": codex_hook,
        "runtime": runtime,
        "full": full,
        "hygiene": [_public_surface_step(), _py_compile_step(), _diff_check_step()],
        "live-codex": live_codex,
        "confidence": [*full, *codex_hook, *runtime],
    }


def _merged_env(extra: dict[str, str]) -> dict[str, str]:
    env = {**os.environ, **extra}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _parse_pytest_summary(stdout: str) -> dict[str, object]:
    match = None
    for match in PYTEST_SUMMARY_RE.finditer(stdout or ""):
        pass
    if match is None:
        return {}
    summary = match.group("summary").strip()
    counts: dict[str, int] = {}
    for item in SUMMARY_RE.finditer(summary):
        kind = item.group("kind")
        if kind == "warning":
            kind = "warnings"
        elif kind == "error":
            kind = "errors"
        counts[kind] = counts.get(kind, 0) + int(item.group("count"))
    return {"summary_line": summary, "counts": counts}


def _step_summary(step: Step, stdout: str) -> dict[str, object]:
    if step.command[:len(PYTEST_BASE)] == PYTEST_BASE:
        return _parse_pytest_summary(stdout)
    return {}


def run_step(step: Step, *, dry_run: bool, timeout_override: int | None = None) -> dict[str, object]:
    started = time.time()
    timeout = int(timeout_override or step.timeout)
    record: dict[str, object] = {
        "name": step.name,
        "command": step.command,
        "env": {"PYTHONDONTWRITEBYTECODE": "1", **step.env},
        "timeout_seconds": timeout,
        "dry_run": dry_run,
    }
    if dry_run:
        record.update({"ok": True, "returncode": None, "duration_seconds": 0.0})
        return record

    try:
        result = subprocess.run(
            step.command,
            cwd=ROOT,
            env=_merged_env(step.env),
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        record.update({
            "ok": False,
            "timed_out": True,
            "returncode": None,
            "duration_seconds": round(time.time() - started, 3),
            "stdout_tail": stdout[-4000:],
            "stderr_tail": stderr[-4000:],
        })
        return record
    record.update({
        "ok": result.returncode == 0,
        "timed_out": False,
        "returncode": result.returncode,
        "duration_seconds": round(time.time() - started, 3),
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    })
    record.update(_step_summary(step, result.stdout))
    return record


def run_steps(
    steps: list[Step],
    *,
    dry_run: bool,
    timeout_override: int | None = None,
    fail_fast: bool = False,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for index, step in enumerate(steps):
        result = run_step(step, dry_run=dry_run, timeout_override=timeout_override)
        results.append(result)
        if fail_fast and not result.get("ok"):
            for skipped in steps[index + 1:]:
                results.append({
                    "name": skipped.name,
                    "command": skipped.command,
                    "env": {"PYTHONDONTWRITEBYTECODE": "1", **skipped.env},
                    "timeout_seconds": int(timeout_override or skipped.timeout),
                    "dry_run": dry_run,
                    "ok": None,
                    "returncode": None,
                    "duration_seconds": 0.0,
                    "skipped": True,
                    "skip_reason": f"fail-fast after {step.name}",
                })
            break
    return results


def _aggregate_results(results: list[dict[str, object]]) -> dict[str, object]:
    counts: dict[str, int] = {}
    step_totals = {
        "total": len(results),
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "timed_out": 0,
        "dry_run": 0,
    }
    for result in results:
        if result.get("dry_run") and not result.get("skipped"):
            step_totals["dry_run"] += 1
        elif result.get("skipped"):
            step_totals["skipped"] += 1
        elif result.get("ok") is True:
            step_totals["passed"] += 1
        elif result.get("ok") is False:
            step_totals["failed"] += 1
        if result.get("timed_out"):
            step_totals["timed_out"] += 1
        for key, value in (result.get("counts") or {}).items():
            if isinstance(value, int):
                counts[str(key)] = counts.get(str(key), 0) + value
    return {"steps": step_totals, "counts": counts}


def _default_output_path(*, gates_selected: list[str], started_at: str) -> Path:
    stamp = (
        started_at.replace("+00:00", "Z")
        .replace(":", "")
        .replace("-", "")
        .replace(".", "")
    )
    gate_label = "-".join(gates_selected).replace("/", "-")
    return ROOT / ".aura" / "test-gates" / f"{stamp}-{gate_label}.json"


def _verify_payload(
    payload: dict[str, object],
    *,
    allow_dry_run: bool = False,
    require_live: bool = False,
) -> dict[str, object]:
    errors: list[str] = []
    if payload.get("schema") != "aura.test_gates.v1":
        errors.append("schema-mismatch")
    if payload.get("ok") is not True:
        errors.append("payload-not-ok")
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        errors.append("missing-results")
        results = []
    aggregate = payload.get("aggregate")
    if not isinstance(aggregate, dict):
        errors.append("missing-aggregate")
        aggregate = {}
    steps = aggregate.get("steps") if isinstance(aggregate, dict) else {}
    if not isinstance(steps, dict):
        errors.append("missing-aggregate-steps")
        steps = {}
    for key in ("failed", "timed_out", "skipped"):
        if int(steps.get(key) or 0) > 0:
            errors.append(f"{key}-steps-present")
    if int(steps.get("dry_run") or 0) > 0 and not allow_dry_run:
        errors.append("dry-run-steps-present")
    counts = aggregate.get("counts") if isinstance(aggregate, dict) else {}
    if isinstance(counts, dict):
        for key in ("failed", "errors"):
            if int(counts.get(key) or 0) > 0:
                errors.append(f"pytest-{key}-present")
    live_results: list[dict[str, object]] = []
    for result in results:
        if not isinstance(result, dict):
            errors.append("malformed-result")
            continue
        name = result.get("name") or "unknown"
        if name == "codex-hook-live":
            live_results.append(result)
        if result.get("ok") is False:
            errors.append(f"step-failed:{name}")
        if result.get("timed_out"):
            errors.append(f"step-timed-out:{name}")
        if result.get("skipped"):
            errors.append(f"step-skipped:{name}")
        if result.get("dry_run") and not allow_dry_run:
            errors.append(f"step-dry-run:{name}")
    if require_live:
        if payload.get("include_live") is not True:
            errors.append("live-not-included")
        if not live_results:
            errors.append("live-step-missing")
        elif not any(_is_executed_live_pass(result) for result in live_results):
            errors.append("live-step-not-executed-pass")
    return {
        "ok": not errors,
        "schema": "aura.test_gates.verification.v1",
        "source_schema": payload.get("schema"),
        "source_ok": payload.get("ok"),
        "source_gates": payload.get("gates"),
        "allow_dry_run": allow_dry_run,
        "require_live": require_live,
        "errors": errors,
        "aggregate": aggregate,
    }


def _is_executed_live_pass(result: dict[str, object]) -> bool:
    counts = result.get("counts")
    passed = counts.get("passed") if isinstance(counts, dict) else 0
    try:
        passed_count = int(passed or 0)
    except (TypeError, ValueError):
        passed_count = 0
    return (
        result.get("ok") is True
        and result.get("dry_run") is False
        and result.get("timed_out") is False
        and not result.get("skipped")
        and result.get("returncode") == 0
        and passed_count > 0
    )


def verify_evidence(path: Path, *, allow_dry_run: bool = False, require_live: bool = False) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "ok": False,
            "schema": "aura.test_gates.verification.v1",
            "path": str(path),
            "allow_dry_run": allow_dry_run,
            "require_live": require_live,
            "errors": [f"read-error:{exc}"],
        }
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "schema": "aura.test_gates.verification.v1",
            "path": str(path),
            "allow_dry_run": allow_dry_run,
            "require_live": require_live,
            "errors": ["payload-not-object"],
        }
    result = _verify_payload(payload, allow_dry_run=allow_dry_run, require_live=require_live)
    result["path"] = str(path)
    return result


def latest_evidence_path(directory: Path | None = None, *, gate: str | None = None) -> Path | None:
    base = directory or (ROOT / ".aura" / "test-gates")
    if not base.is_dir():
        return None
    pattern = f"*-{gate}.json" if gate else "*.json"
    files = [path for path in base.glob(pattern) if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: (path.stat().st_mtime, path.name))


def select_steps(names: list[str], *, include_live: bool) -> list[Step]:
    available = gates()
    selected: list[Step] = []
    for name in names:
        if name not in available:
            raise KeyError(name)
        selected.extend(available[name])
    if include_live and "live-codex" not in names:
        selected.extend(available["live-codex"])
    return selected


def _positive_int(raw: str) -> int:
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return value


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Aura test confidence gates.")
    parser.add_argument(
        "--gate",
        action="append",
        choices=sorted(gates().keys()),
        help="Gate to run. May be passed multiple times. Default: confidence.",
    )
    parser.add_argument("--include-live", action="store_true", help="Also run live Codex/tmux hook smoke.")
    parser.add_argument("--dry-run", action="store_true", help="Print selected commands without running them.")
    parser.add_argument("--output", metavar="PATH", help="Write the JSON result envelope to PATH.")
    parser.add_argument("--save", action="store_true", help="Write JSON evidence to .aura/test-gates/.")
    parser.add_argument("--verify", metavar="PATH", help="Verify a saved JSON evidence packet and exit.")
    parser.add_argument("--verify-latest", action="store_true", help="Verify the newest .aura/test-gates/*.json packet.")
    parser.add_argument("--latest-gate", choices=sorted(gates().keys()), help="Restrict --verify-latest to one gate.")
    parser.add_argument("--allow-dry-run", action="store_true", help="Allow dry-run steps when verifying evidence.")
    parser.add_argument("--require-live", action="store_true", help="Require live Codex smoke evidence when verifying.")
    parser.add_argument("--timeout", type=_positive_int, help="Override the per-step timeout in seconds.")
    parser.add_argument("--fail-fast", action="store_true", help="Skip remaining steps after the first failure.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.verify and args.verify_latest:
        raise SystemExit("--verify and --verify-latest are mutually exclusive")
    if args.verify_latest:
        path = latest_evidence_path(gate=args.latest_gate)
        if path is None:
            result = {
                "ok": False,
                "schema": "aura.test_gates.verification.v1",
                "path": None,
                "latest_gate": args.latest_gate,
                "allow_dry_run": bool(args.allow_dry_run),
                "require_live": bool(args.require_live),
                "errors": ["no-saved-evidence"],
            }
            print(json.dumps(result, indent=2))
            return 1
        result = verify_evidence(
            path,
            allow_dry_run=bool(args.allow_dry_run),
            require_live=bool(args.require_live),
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    if args.verify:
        result = verify_evidence(
            Path(args.verify).expanduser(),
            allow_dry_run=bool(args.allow_dry_run),
            require_live=bool(args.require_live),
        )
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    started = time.time()
    started_at = datetime.now(timezone.utc).isoformat()
    names = args.gate or ["confidence"]
    steps = select_steps(names, include_live=args.include_live)
    results = run_steps(
        steps,
        dry_run=args.dry_run,
        timeout_override=args.timeout,
        fail_fast=bool(args.fail_fast),
    )
    ok = all(result.get("ok") is not False for result in results) and all(
        result.get("skipped") or result.get("ok") is True for result in results
    )
    aggregate = _aggregate_results(results)
    payload = {
        "ok": ok,
        "schema": "aura.test_gates.v1",
        "repo_root": str(ROOT),
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - started, 3),
        "gates": names,
        "include_live": bool(args.include_live),
        "dry_run": bool(args.dry_run),
        "timeout_override": args.timeout,
        "fail_fast": bool(args.fail_fast),
        "aggregate": aggregate,
        "results": results,
    }
    output_path = None
    if args.output and args.save:
        raise SystemExit("--output and --save are mutually exclusive")
    if args.output:
        output_path = Path(args.output).expanduser()
    elif args.save:
        output_path = _default_output_path(gates_selected=names, started_at=started_at)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload["output_path"] = str(output_path)
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    output = json.dumps(payload, indent=2)
    print(output)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

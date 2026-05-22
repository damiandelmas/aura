#!/usr/bin/env python3
"""Optional live smoke test for boxed Codex hooks under Aura.

This is intentionally not a normal pytest test: it starts a real Codex TUI in
tmux and requires local Codex auth. It creates an isolated Aura state directory,
materializes a disposable Codex runtime profile with hooks, spawns one seat,
then verifies hook context injection and hook-to-Aura reporting from durable
JSONL/report evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AURA = ROOT / "cli" / "aura"


HOOK_SCRIPT = r'''#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def emit(payload):
    sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")


def append(path, payload):
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n")


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else "Unknown"
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except Exception as exc:
        data = {"_parse_error": str(exc), "_raw": raw}

    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    log_dir = codex_home / "hook-smoke"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "events.jsonl"
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_arg": event,
        "hook_event_name": data.get("hook_event_name"),
        "session_id": data.get("session_id"),
        "turn_id": data.get("turn_id"),
        "cwd": data.get("cwd"),
        "model": data.get("model"),
        "source": data.get("source"),
        "transcript_path": data.get("transcript_path"),
        "raw": data,
    }
    append(log_path, record)

    if event == "Stop":
        aura_cli = os.environ.get("AURA_HOOK_SMOKE_AURA_CLI", "__AURA_CLI__")
        if aura_cli:
            report_env = os.environ.copy()
            if data.get("session_id") and not report_env.get("AURA_RUNTIME_SESSION_ID"):
                report_env["AURA_RUNTIME_SESSION_ID"] = data["session_id"]
            cmd = [
                sys.executable,
                aura_cli,
                "report",
                "complete",
                "--work",
                "Codex hook smoke Stop hook published to Aura",
                "--done",
                f"Observed Codex Stop hook for session {data.get('session_id', 'unknown')}",
                "--receipt",
                str(log_path),
                "--ack",
            ]
            try:
                result = subprocess.run(
                    cmd,
                    cwd=data.get("cwd") or os.getcwd(),
                    env=report_env,
                    text=True,
                    capture_output=True,
                    timeout=10,
                )
                append(log_path, {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event_arg": "AuraReportPublish",
                    "hook_event_name": event,
                    "session_id": data.get("session_id"),
                    "returncode": result.returncode,
                    "stdout": result.stdout.strip(),
                    "stderr": result.stderr.strip(),
                })
            except Exception as exc:
                append(log_path, {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event_arg": "AuraReportPublish",
                    "hook_event_name": event,
                    "session_id": data.get("session_id"),
                    "error": str(exc),
                })

    if event in {"SessionStart", "UserPromptSubmit"}:
        emit({
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": (
                    f"[AURA_HOOK_SMOKE] {event} observed. "
                    f"session={data.get('session_id', 'unknown')} log={log_path}"
                ),
            }
        })
    elif event in {"PreCompact", "PostCompact"}:
        emit({"systemMessage": f"Aura hook smoke observed {event}; durable event log updated."})
    else:
        emit({})


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"codex hook smoke failed: {exc}", file=sys.stderr)
        sys.exit(0)
'''


def run_json(cmd: list[str], *, env: dict[str, str], timeout: int) -> dict:
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"command did not return JSON: {' '.join(cmd)}\n{result.stdout}") from exc


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def wait_until(deadline: float, fn, description: str):
    last = None
    while time.time() < deadline:
        last = fn()
        if last:
            return last
        time.sleep(1.0)
    raise TimeoutError(f"timed out waiting for {description}")


def _trim_string(value: str, limit: int = 1200) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"... <trimmed {len(value) - limit} chars>"


def _trim_json(value, *, string_limit: int = 1200, list_limit: int = 12):
    if isinstance(value, str):
        return _trim_string(value, string_limit)
    if isinstance(value, list):
        items = [_trim_json(item, string_limit=string_limit, list_limit=list_limit) for item in value[:list_limit]]
        if len(value) > list_limit:
            items.append({"trimmed_items": len(value) - list_limit})
        return items
    if isinstance(value, dict):
        return {
            str(key): _trim_json(item, string_limit=string_limit, list_limit=list_limit)
            for key, item in value.items()
        }
    return value


def _spawn_diagnostics(spawn: dict | None) -> dict:
    if not spawn:
        return {}
    keys = (
        "ok",
        "error",
        "name",
        "fleet",
        "runtime",
        "command",
        "runtime_home",
        "codex_box_codex_home",
        "aura_launch_id",
        "runtime_session_binding",
        "runtime_session_id",
        "prompt_delivery",
        "session_observation",
        "startup_readiness",
    )
    return _trim_json({key: spawn.get(key) for key in keys if key in spawn})


def _safe_run_json(cmd: list[str], *, env: dict[str, str], timeout: int) -> dict:
    try:
        return run_json(cmd, env=env, timeout=timeout)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "command": cmd}


def _failure_summary(
    *,
    error: BaseException,
    phase: str,
    state_dir: Path,
    fleet: str,
    seat: str,
    spawn: dict | None,
    codex_home: Path | None,
    hook_log: Path | None,
    env: dict[str, str],
) -> dict:
    events = read_jsonl(hook_log) if hook_log else []
    inspect = _safe_run_json(
        [sys.executable, str(AURA), "inspect", f"{fleet}:{seat}", "--raw", "--lines", "220"],
        env=env,
        timeout=20,
    )
    output = [str(line) for line in (inspect.get("output") or [])]
    report = _safe_run_json(
        [sys.executable, str(AURA), "report", "latest", "--target", f"{fleet}:{seat}"],
        env=env,
        timeout=20,
    )
    return {
        "ok": False,
        "phase": phase,
        "error": f"{type(error).__name__}: {error}",
        "state_dir": str(state_dir),
        "fleet": fleet,
        "seat": seat,
        "runtime_home": spawn.get("runtime_home") if spawn else None,
        "codex_home": str(codex_home) if codex_home else None,
        "hook_log": str(hook_log) if hook_log else None,
        "hook_event_names": [row.get("event_arg") for row in events],
        "hook_event_count": len(events),
        "user_prompt_submit_count": sum(1 for row in events if row.get("event_arg") == "UserPromptSubmit"),
        "aura_report_publish_count": sum(1 for row in events if row.get("event_arg") == "AuraReportPublish"),
        "inspect": _trim_json({
            "ok": inspect.get("ok", True),
            "error": inspect.get("error"),
            "runtime_session_binding": inspect.get("runtime_session_binding"),
            "runtime_session_id": inspect.get("runtime_session_id"),
            "runtime_session_evidence": inspect.get("runtime_session_evidence"),
        }),
        "terminal_tail": output[-40:],
        "latest_report": _trim_json(report.get("record") or report),
        "spawn": _spawn_diagnostics(spawn),
    }


def write_profile(state_dir: Path, profile: str) -> Path:
    root = state_dir / "runtime-profiles" / "codex" / profile / "codex-home-template"
    hooks_dir = root / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "codex_hook_smoke.py"
    hook_path.write_text(HOOK_SCRIPT.replace("__AURA_CLI__", str(AURA)), encoding="utf-8")
    hook_path.chmod(0o755)
    (root / "config.toml").write_text("[features]\nhooks = true\n", encoding="utf-8")
    command = 'python3 "$CODEX_HOME/hooks/codex_hook_smoke.py"'
    hooks = {
        "hooks": {
            "SessionStart": [{"matcher": "startup|resume|clear", "hooks": [{"type": "command", "command": f"{command} SessionStart"}]}],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": f"{command} UserPromptSubmit"}]}],
            "PreCompact": [{"matcher": "manual|auto", "hooks": [{"type": "command", "command": f"{command} PreCompact"}]}],
            "PostCompact": [{"matcher": "manual|auto", "hooks": [{"type": "command", "command": f"{command} PostCompact"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": f"{command} Stop", "timeout": 20}]}],
        }
    }
    (root / "hooks.json").write_text(json.dumps(hooks, indent=2) + "\n", encoding="utf-8")
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an optional live Aura/Codex hook smoke test.")
    parser.add_argument("--state-dir", type=Path, help="Aura state dir to use. Defaults to a new /tmp directory.")
    parser.add_argument("--fleet", default=None, help="Fleet name. Defaults to a unique hook-smoke fleet.")
    parser.add_argument("--seat", default="hook-smoke", help="Seat name.")
    parser.add_argument("--profile", default="hook-smoke", help="Disposable Codex runtime profile name.")
    parser.add_argument("--timeout", type=int, default=120, help="Seconds to wait for the live smoke.")
    parser.add_argument(
        "--command",
        help=(
            "Optional Codex command override. Omit this to use Aura's native initial-prompt argv path; "
            "pass e.g. 'codex --dangerously-bypass-approvals-and-sandbox --no-alt-screen' "
            "to exercise terminal prompt delivery."
        ),
    )
    parser.add_argument("--skip-compact", action="store_true", help="Skip the compact continuity probe.")
    parser.add_argument("--keep-seat", action="store_true", help="Leave the tmux seat running.")
    args = parser.parse_args()

    if shutil.which("tmux") is None:
        raise SystemExit("tmux is required for this live smoke")
    if shutil.which("codex") is None:
        raise SystemExit("codex is required for this live smoke")

    state_dir = (args.state_dir or Path(tempfile.mkdtemp(prefix="aura-codex-hook-smoke-"))).expanduser().resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    fleet = args.fleet or f"hook-smoke-{os.getpid()}-{int(time.time())}"
    seat = args.seat
    write_profile(state_dir, args.profile)

    env = {
        **os.environ,
        "AURA_STATE_DIR": str(state_dir),
        "AURA_REGISTRY_PATH": str(state_dir / "registry" / "seats.json"),
        "AURA_DELIVERY_LOG": str(state_dir / "registry" / "deliveries.jsonl"),
        "AURA_HOOK_SMOKE_AURA_CLI": str(AURA),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    prompt = (
        "HOOK SMOKE PROBE: do not edit files. Reply exactly once with "
        "HOOK_SMOKE_READY and state whether AURA_HOOK_SMOKE context is present. Do not run tools."
    )
    spawn_cmd = [
        sys.executable,
        str(AURA),
        "spawn",
        seat,
        "--fleet",
        fleet,
        "--runtime",
        "codex",
        "--runtime-profile",
        f"codex/{args.profile}",
        "--boxed",
        "--cwd",
        str(ROOT.parent),
        "--prompt",
        prompt,
        "--as-pane",
        "--wait",
        "--timeout",
        str(args.timeout),
    ]
    if args.command:
        spawn_cmd[spawn_cmd.index("--prompt"):spawn_cmd.index("--prompt")] = ["--command", args.command]

    stopped = False
    phase = "spawn"
    spawn = None
    codex_home = None
    hook_log = None
    try:
        spawn = run_json(spawn_cmd, env=env, timeout=args.timeout + 30)
        codex_home = Path(spawn["codex_box_codex_home"])
        hooks_path = codex_home / "hooks.json"
        hook_log = codex_home / "hook-smoke" / "events.jsonl"
        deadline = time.time() + args.timeout

        def read_publish_events():
            rows = read_jsonl(hook_log)
            return rows if any(row.get("event_arg") == "AuraReportPublish" for row in rows) else None

        phase = "wait-aura-report-publish"
        events = wait_until(deadline, read_publish_events, "hook log with AuraReportPublish")
        phase = "wait-hook-bound-inspect"
        inspect = wait_until(
            deadline,
            lambda: (
                row
                if (row := run_json([sys.executable, str(AURA), "inspect", f"{fleet}:{seat}", "--raw", "--lines", "180"], env=env, timeout=20))
                and row.get("runtime_session_binding") == "bound"
                else None
            ),
            "hook-bound Aura inspect result",
        )

        compact_write = None
        after_compact_send = None
        if not args.skip_compact:
            target = f"{fleet}:{seat}"
            phase = "write-compact"
            compact_write = run_json(
                [sys.executable, str(AURA), "write", target, "/compact", "--enter", "--as", "codex-hook-smoke"],
                env=env,
                timeout=20,
            )
            def read_compact_events():
                rows = read_jsonl(hook_log)
                names = {row.get("event_arg") for row in rows}
                return rows if {"PreCompact", "PostCompact"} <= names else None

            phase = "wait-compact-hooks"
            wait_until(
                deadline,
                read_compact_events,
                "PreCompact and PostCompact hook events",
            )
            after_compact_prompt = (
                "AFTER COMPACT HOOK SMOKE: reply exactly once with AFTER_COMPACT_SMOKE_READY "
                "and state whether AURA_HOOK_SMOKE context is present. Do not run tools."
            )
            phase = "send-after-compact-prompt"
            after_compact_send = run_json(
                [sys.executable, str(AURA), "send", target, after_compact_prompt, "--as-service", "codex-hook-smoke"],
                env=env,
                timeout=20,
            )
            def read_second_publish_events():
                rows = read_jsonl(hook_log)
                publish_count = sum(1 for row in rows if row.get("event_arg") == "AuraReportPublish")
                return rows if publish_count >= 2 else None

            phase = "wait-second-aura-report-publish"
            events = wait_until(
                deadline,
                read_second_publish_events,
                "second AuraReportPublish after compact",
            )
            phase = "wait-after-compact-assistant"
            inspect = wait_until(
                deadline,
                lambda: (
                    row
                    if (row := run_json([sys.executable, str(AURA), "inspect", target, "--raw", "--lines", "220"], env=env, timeout=20))
                    and any("AFTER_COMPACT_SMOKE_READY" in str(line) for line in row.get("output") or [])
                    else None
                ),
                "after-compact assistant response",
            )

        phase = "read-latest-report"
        report = run_json(
            [sys.executable, str(AURA), "report", "latest", "--target", f"{fleet}:{seat}"],
            env=env,
            timeout=20,
        )
        phase = "evaluate-checks"
        hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
        trusted_labels = {
            key.split(":")[-3]
            for key, value in hooks.get("state", {}).items()
            if key.startswith(str(hooks_path)) and isinstance(value, dict) and str(value.get("trusted_hash", "")).startswith("sha256:")
        }
        output_lines = [str(line) for line in inspect.get("output") or []]
        event_names = [row.get("event_arg") for row in events]
        user_prompts = [row for row in events if row.get("event_arg") == "UserPromptSubmit"]
        publish_events = [row for row in events if row.get("event_arg") == "AuraReportPublish"]
        publish = publish_events[-1]
        record = report.get("record") or {}

        checks = {
            "hook_trust_preseeded": {"session_start", "user_prompt_submit", "stop"} <= trusted_labels,
            "no_hook_review_gate": not any("Hooks need review" in line for line in output_lines),
            "context_injected": any("AURA_HOOK_SMOKE" in line for line in output_lines),
            "assistant_observed_context": any("HOOK_SMOKE_READY" in line for line in output_lines),
            "expected_user_prompt_submit_count": len(user_prompts) == (1 if args.skip_compact else 2),
            "stop_hook_seen": "Stop" in event_names,
            "aura_report_publish_succeeded": publish.get("returncode") == 0,
            "aura_report_recorded": record.get("work") == "Codex hook smoke Stop hook published to Aura",
            "report_session_matches_hook": record.get("session_id") == publish.get("session_id"),
            "inspect_bound_by_hook": inspect.get("runtime_session_binding") == "bound",
        }
        if not args.skip_compact:
            checks.update({
                "compact_write_ok": bool((compact_write or {}).get("ok")),
                "pre_compact_seen": "PreCompact" in event_names,
                "post_compact_seen": "PostCompact" in event_names,
                "after_compact_send_ok": bool((after_compact_send or {}).get("ok")),
                "after_compact_context_observed": any("AFTER_COMPACT_SMOKE_READY" in line for line in output_lines)
                and any("AURA_HOOK_SMOKE" in line for line in output_lines),
                "second_report_published": len(publish_events) >= 2,
            })
        ok = all(checks.values())
        summary = {
            "ok": ok,
            "state_dir": str(state_dir),
            "fleet": fleet,
            "seat": seat,
            "runtime_home": spawn.get("runtime_home"),
            "codex_home": str(codex_home),
            "hook_log": str(hook_log),
            "transcript_path": inspect.get("runtime_session_evidence", {}).get("transcript_path"),
            "report_id": record.get("report_id"),
            "session_id": inspect.get("runtime_session_id"),
            "checks": checks,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0 if ok else 1
    except Exception as exc:
        summary = _failure_summary(
            error=exc,
            phase=phase,
            state_dir=state_dir,
            fleet=fleet,
            seat=seat,
            spawn=spawn,
            codex_home=codex_home,
            hook_log=hook_log,
            env=env,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 1
    finally:
        if not args.keep_seat:
            subprocess.run(
                [sys.executable, str(AURA), "stop", f"{fleet}:{seat}"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                timeout=20,
            )
            stopped = True
        if stopped:
            pass


if __name__ == "__main__":
    raise SystemExit(main())

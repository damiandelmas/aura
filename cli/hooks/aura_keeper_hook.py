#!/usr/bin/env python3
"""Quiet Aura keeper-memory lifecycle hook for durable package agents."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Codex/Aura package hooks run on Unix.
    fcntl = None


CLI = Path(__file__).resolve().parents[1] / "aura"
DEFAULT_THRESHOLDS = (25, 50, 75)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_payload() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _first_string(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _event(payload: dict[str, Any]) -> str:
    return _first_string(
        sys.argv[1] if len(sys.argv) > 1 else None,
        payload.get("hook_event_name"),
        payload.get("hookEventName"),
        payload.get("event"),
        os.environ.get("CODEX_HOOK_EVENT"),
    ) or ""


def _target() -> str | None:
    fleet = _first_string(os.environ.get("AURA_FLEET"), os.environ.get("AURA_TMUX_SESSION"))
    seat = _first_string(os.environ.get("AURA_SEAT"), os.environ.get("AURA_AGENT_NAME"))
    return f"{fleet}:{seat}" if fleet and seat else None


def _package_id() -> str | None:
    return _first_string(os.environ.get("AURA_AGENT_PACKAGE_ID"), os.environ.get("AURA_IDENTITY_ID"))


def _package_root() -> Path | None:
    value = _first_string(os.environ.get("AURA_AGENT_PACKAGE_ROOT"), os.environ.get("AURA_RUNTIME_CAPSULE_REF"))
    if not value:
        return None
    root = Path(value).expanduser()
    return root if (root / "manifest.json").is_file() and (root / ".codex").is_dir() else None


def _session_id(payload: dict[str, Any]) -> str | None:
    return _first_string(
        payload.get("session_id"),
        payload.get("sessionId"),
        payload.get("thread_id"),
        payload.get("threadId"),
        os.environ.get("CODEX_THREAD_ID"),
        os.environ.get("AURA_RUNTIME_SESSION_ID"),
        os.environ.get("AURA_SESSION_ID"),
    )


def _direct_percent(payload: dict[str, Any]) -> int | None:
    for key in ("context_percent", "token_percent"):
        value = payload.get(key)
        if isinstance(value, (int, float)):
            return max(0, min(100, int(value)))
        if isinstance(value, str) and value.strip().isdigit():
            return max(0, min(100, int(value.strip())))
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _usage_percent(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    for key in ("percent", "context_percent", "used_percent", "percent_used"):
        percent = value.get(key)
        if isinstance(percent, (int, float)):
            return max(0, min(100, int(percent)))
    total = None
    for key in ("total_tokens", "totalTokens", "total_tokens_used", "input_tokens", "inputTokens"):
        candidate = value.get(key)
        number = _number(candidate)
        if number is not None:
            total = number
            break
    if total is None:
        for key in ("total_token_usage", "totalTokenUsage"):
            candidate = value.get(key)
            if isinstance(candidate, dict):
                total = _number(candidate.get("total_tokens") or candidate.get("totalTokens"))
            else:
                total = _number(candidate)
            if total is not None:
                break
    window = None
    for key in ("context_window", "context_window_tokens", "model_context_window", "modelContextWindow", "max_tokens"):
        candidate = value.get(key)
        number = _number(candidate)
        if number is not None and number > 0:
            window = number
            break
    if total is not None and window:
        return max(0, min(100, int((total / window) * 100)))
    return None


def _token_count_percent(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    payload = value.get("payload") if isinstance(value.get("payload"), dict) else value
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None
    return _usage_percent(payload.get("info"))


def _payload_usage_percent(payload: dict[str, Any]) -> int | None:
    percent = _token_count_percent(payload)
    if percent is not None:
        return percent
    for key in ("usage", "tokens", "token_count", "info"):
        percent = _usage_percent(payload.get(key))
        if percent is not None:
            return percent
    return None


def _context_percent(payload: dict[str, Any]) -> int | None:
    percent = _direct_percent(payload)
    if percent is not None:
        return percent
    percent = _payload_usage_percent(payload)
    if percent is not None:
        return percent
    transcript = payload.get("transcript_path")
    if not transcript:
        return None
    path = Path(str(transcript)).expanduser()
    if not path.is_file():
        return None
    latest: int | None = None
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if "usage" not in line and "token" not in line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                percent = _payload_usage_percent(row)
                if percent is not None:
                    latest = percent
    except Exception:
        return None
    return latest


def _thresholds() -> tuple[int, ...]:
    raw = os.environ.get("AURA_KEEPER_MEMORY_THRESHOLDS")
    if not raw:
        return DEFAULT_THRESHOLDS
    values: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            values.append(max(1, min(100, int(part))))
    return tuple(sorted(set(values))) or DEFAULT_THRESHOLDS


def _state_path(root: Path) -> Path:
    return root / "memories" / ".hook-state" / "aura-keeper-hook.json"


def _log_path(root: Path) -> Path:
    return root / "memories" / ".hook-state" / "keeper-hook.jsonl"


def _lock_path(root: Path) -> Path:
    return root / "memories" / ".hook-state" / "aura-keeper-hook.lock"


@contextmanager
def _state_lock(root: Path):
    path = _lock_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _load_state(path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": "aura.keeper_hook_state.v1", "sessions": {}}
    if not isinstance(parsed, dict):
        return {"schema": "aura.keeper_hook_state.v1", "sessions": {}}
    if not isinstance(parsed.get("sessions"), dict):
        parsed["sessions"] = {}
    return parsed


def _write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _audit(root: Path | None, status: str, **fields: object) -> None:
    if root is None:
        return
    try:
        path = _log_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ts": _now(), "status": status}
        payload.update({key: value for key, value in fields.items() if value is not None})
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    except Exception:
        pass


def _session_state(root: Path, session_id: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    path = _state_path(root)
    state = _load_state(path)
    session = state["sessions"].setdefault(session_id, {})
    if not isinstance(session.get("fired_boundaries"), list):
        session["fired_boundaries"] = []
    return path, state, session


def _launch_keeper(root: Path, *, target: str, boundary: str) -> int | None:
    log_path = _log_path(root).with_name("keeper-launch.log")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command_override = _first_string(os.environ.get("AURA_KEEPER_HOOK_COMMAND"))
    cmd = shlex.split(command_override) if command_override else [sys.executable, str(CLI), "keeper", "run", "memory", "--target", target, "--boundary", boundary]
    try:
        proc = subprocess.run(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=float(os.environ.get("AURA_KEEPER_HOOK_TIMEOUT", "25")),
        )
    except Exception as exc:
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"ok": False, "error": "keeper-launch-exception", "detail": str(exc)}) + "\n")
        return None
    output = (proc.stdout or "").strip()
    with log_path.open("a", encoding="utf-8") as handle:
        if output:
            handle.write(output + ("\n" if not output.endswith("\n") else ""))
        handle.write(json.dumps({"returncode": proc.returncode, "target": target, "boundary": boundary}) + "\n")
    if proc.returncode != 0:
        return None
    try:
        receipt = json.loads(output.splitlines()[-1]) if output else {}
    except Exception:
        return None
    if not isinstance(receipt, dict) or not receipt.get("ok"):
        return None
    pid = receipt.get("pid")
    return int(pid) if isinstance(pid, int) else 0


def _handle_stop(root: Path, payload: dict[str, Any], target: str, session_id: str) -> int | None:
    percent = _context_percent(payload)
    if percent is None:
        _audit(root, "skip", event="Stop", reason="missing-context-percent", target=target, session_id=session_id)
        return None
    with _state_lock(root):
        path, state, session = _session_state(root, session_id)
        fired = {int(value) for value in session.get("fired_boundaries", []) if str(value).isdigit()}
        crossed = [value for value in _thresholds() if percent >= value]
        due = [value for value in crossed if value not in fired]
        if not due:
            _audit(root, "skip", event="Stop", reason="already-fired", target=target, session_id=session_id, percent=percent)
            return None
        boundary = max(due)
        pid = _launch_keeper(root, target=target, boundary=str(boundary))
        if pid is None:
            session["last_stop_percent"] = percent
            session["last_launch_failed_boundary"] = boundary
            session["updated_at"] = _now()
            _write_state(path, state)
            _audit(root, "launch-failed", event="Stop", target=target, session_id=session_id, boundary=boundary, percent=percent)
            return None
        session["fired_boundaries"] = sorted(fired | {value for value in crossed if value <= boundary})
        session["last_stop_percent"] = percent
        session["updated_at"] = _now()
        _write_state(path, state)
    _audit(root, "launched", event="Stop", target=target, session_id=session_id, boundary=boundary, percent=percent, pid=pid)
    return pid


def _handle_precompact(root: Path, target: str, session_id: str) -> int | None:
    with _state_lock(root):
        path, state, session = _session_state(root, session_id)
        pid = _launch_keeper(root, target=target, boundary="precompact")
        if pid is None:
            session["last_precompact_launch_failed_at"] = _now()
            session["updated_at"] = _now()
            _write_state(path, state)
            _audit(root, "launch-failed", event="PreCompact", target=target, session_id=session_id, boundary="precompact")
            return None
        session["precompact_count"] = int(session.get("precompact_count") or 0) + 1
        session["updated_at"] = _now()
        _write_state(path, state)
    _audit(root, "launched", event="PreCompact", target=target, session_id=session_id, boundary="precompact", pid=pid)
    return pid


def main() -> int:
    payload = _read_payload()
    event = _event(payload)
    root = _package_root()
    package_id = _package_id()
    target = _target()
    session_id = _session_id(payload)

    if root is None or not package_id or not target:
        _audit(root, "skip", event=event, reason="not-durable-aura-package")
        return 0
    if not session_id:
        _audit(root, "skip", event=event, reason="missing-session-id", target=target)
        return 0
    if event == "Stop":
        _handle_stop(root, payload, target, session_id)
        return 0
    if event == "PreCompact":
        _handle_precompact(root, target, session_id)
        return 0
    _audit(root, "skip", event=event, reason="unsupported-event", target=target, session_id=session_id)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit(0)

"""Background keeper jobs for package-backed Aura agents."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib import agent_packages, registry, state


REQUEST_SCHEMA = "aura.keeper_job_request.v1"
STATUS_SCHEMA = "aura.keeper_job_status.v1"
KEEPER_ADDRESS = "aura:keepers:context"
SDK_RUNNER = Path("/home/axp/.codex/skills/_codex-sdk-runner/runner.mjs")
FLEX_BIN = Path("/home/axp/projects/flexsearch/main/venv/bin/flex")
DEFAULT_TRACE_OVERLAP_MESSAGES = 2
RECENT_MEMORY_LIMIT = 5
DEFAULT_STARTER_MESSAGES = 250


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def keeper_jobs_root() -> Path:
    return state.state_root() / "keeper-jobs"


def job_dir(job_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", job_id)
    return keeper_jobs_root() / safe


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing keeper artifact: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid keeper artifact: {path}")
    return payload


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _session_id(record: dict[str, Any]) -> str | None:
    value = record.get("runtime_session_id") or record.get("session_id")
    return str(value) if value else None


def _seat_ref(record: dict[str, Any], fallback: str | None = None) -> str | None:
    if record.get("seat_ref"):
        return str(record["seat_ref"])
    seat = record.get("seat") or record.get("name")
    if seat:
        fleet = record.get("fleet")
        return f"{fleet}:{seat}" if fleet else str(seat)
    return fallback


def _agent_id_from_record(record: dict[str, Any]) -> str | None:
    value = record.get("agent_package_id")
    if value:
        return str(value)
    if record.get("identity_provider") == "aura-agent" and record.get("identity_id"):
        return str(record["identity_id"])
    return None


def _record_matches_agent(record: dict[str, Any], agent_id: str) -> bool:
    if record.get("agent_package_id") == agent_id:
        return True
    return record.get("identity_provider") == "aura-agent" and record.get("identity_id") == agent_id


def _latest_registry_record_for_agent(agent_id: str) -> dict[str, Any] | None:
    rows = [row for row in registry.read_registry().values() if _record_matches_agent(row, agent_id)]
    if not rows:
        return None
    rows.sort(
        key=lambda row: str(
            row.get("runtime_session_updated_at_ms")
            or row.get("updated_at")
            or row.get("last_seen")
            or row.get("created_at")
            or ""
        )
    )
    return rows[-1]


def resolve_target(ref: str) -> dict[str, Any]:
    raw = str(ref or "").strip()
    if not raw:
        raise ValueError("target is required")

    row = registry.get_agent(raw)
    package: dict[str, Any] | None = None
    agent_id = _agent_id_from_record(row or {}) if row else None

    if agent_id:
        package = agent_packages.resolve(agent_id)
    else:
        package = agent_packages.resolve(raw)
        agent_id = str(package["agent_id"])
        row = _latest_registry_record_for_agent(agent_id)

    if not row:
        raise FileNotFoundError(f"target has no live registry row: {raw}")
    if not agent_id:
        raise ValueError(f"target is not package-backed by an Aura agent: {raw}")
    if package is None:
        package = agent_packages.resolve(agent_id)

    session_id = _session_id(row)
    if not session_id:
        raise ValueError(f"target has no runtime session id: {raw}")

    return {
        "ref": _seat_ref(row, fallback=raw),
        "agent_id": agent_id,
        "fleet": row.get("fleet"),
        "seat": row.get("seat") or row.get("name"),
        "runtime": row.get("runtime") or package.get("runtime"),
        "cwd": row.get("cwd") or row.get("workdir") or package.get("cwd"),
        "session_id": session_id,
        "package_root": package["root"],
        "registry_row": row,
    }


def _flex_bin() -> str:
    configured = os.environ.get("AURA_FLEX_BIN")
    if configured:
        return configured
    if FLEX_BIN.exists():
        return str(FLEX_BIN)
    found = shutil.which("flex")
    if found:
        return found
    raise FileNotFoundError("flex CLI not found; set AURA_FLEX_BIN")


def _flex_query(sql: str) -> list[dict[str, Any]]:
    proc = subprocess.run(
        [_flex_bin(), "core", "search", "--cell", "codex", "--json", sql],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "flex query failed").strip())
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid flex JSON output: {proc.stdout[:500]}") from exc
    if not isinstance(payload, list):
        raise RuntimeError("invalid flex result: expected list")
    return [row for row in payload if isinstance(row, dict)]


def _sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _memory_index_path(target: dict[str, Any]) -> Path:
    return Path(str(target["package_root"])) / "memories" / "index.json"


def read_memory_index(target: dict[str, Any]) -> dict[str, Any]:
    path = _memory_index_path(target)
    if not path.exists():
        return {"schema": "aura.agent_memory_index.v1", "sessions": {}}
    return _read_json(path)


def _session_cursor(target: dict[str, Any], session_id: str) -> dict[str, Any]:
    index = read_memory_index(target)
    sessions = index.get("sessions") if isinstance(index.get("sessions"), dict) else {}
    value = sessions.get(session_id)
    return value if isinstance(value, dict) else {}


def _flex_bounds(session_id: str) -> dict[str, Any]:
    rows = _flex_query(
        "SELECT COUNT(*) AS rows, MIN(position) AS min_position, MAX(position) AS max_position "
        "FROM messages WHERE session_id = "
        + _sql_literal(session_id)
        + " LIMIT 1"
    )
    if not rows or int(rows[0].get("rows") or 0) <= 0:
        raise FileNotFoundError(f"no Flex codex messages found for session {session_id}")
    return rows[0]


def _position_by_offset(session_id: str, *, offset: int) -> int:
    rows = _flex_query(
        "SELECT position FROM messages WHERE session_id = "
        + _sql_literal(session_id)
        + " ORDER BY position ASC LIMIT 1 OFFSET "
        + str(max(0, offset))
    )
    if not rows:
        raise FileNotFoundError(f"no Flex position at offset {offset} for session {session_id}")
    return int(rows[0]["position"])


def _overlap_start_position(session_id: str, *, last_read_position: int | None, overlap_messages: int, total_rows: int) -> int:
    if last_read_position is None:
        return _position_by_offset(session_id, offset=max(0, total_rows - DEFAULT_STARTER_MESSAGES))
    rows = _flex_query(
        "WITH ordered AS ("
        " SELECT id, position, row_number() OVER (ORDER BY position) AS rn"
        " FROM messages WHERE session_id = "
        + _sql_literal(session_id)
        + "), cursor AS ("
        " SELECT rn FROM ordered WHERE position <= "
        + str(int(last_read_position))
        + " ORDER BY position DESC LIMIT 1"
        + ") SELECT position AS start_position FROM ordered, cursor"
        + " WHERE ordered.rn = MAX(1, cursor.rn - "
        + str(max(0, overlap_messages))
        + ") LIMIT 1"
    )
    if not rows:
        return _position_by_offset(session_id, offset=max(0, total_rows - DEFAULT_STARTER_MESSAGES))
    return int(rows[0]["start_position"])


def _flex_slice(session_id: str, *, start_position: int, target_position: int) -> list[dict[str, Any]]:
    return _flex_query(
        "SELECT id, position, type, tool_name, target_file,"
        " CASE WHEN file_body IS NOT NULL AND length(file_body) > length(content)"
        " THEN file_body ELSE content END AS body"
        " FROM messages WHERE session_id = "
        + _sql_literal(session_id)
        + " AND position >= "
        + str(int(start_position))
        + " AND position <= "
        + str(int(target_position))
        + " ORDER BY position ASC"
    )


def _seed_keeper_codex_home(codex_home: Path) -> None:
    codex_home.mkdir(parents=True, exist_ok=True)
    source = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    for name in ("auth.json", "credentials.json", "config.toml"):
        src = source / name
        dest = codex_home / name
        if src.exists() and not dest.exists():
            shutil.copy2(src, dest)


def ensure_keeper_profile(cwd: str | None = None) -> dict[str, Any]:
    try:
        record = agent_packages.resolve(KEEPER_ADDRESS)
    except FileNotFoundError:
        created = agent_packages.create(
            address=KEEPER_ADDRESS,
            runtime="codex",
            profile=None,
            cwd=cwd or str(Path.cwd()),
            fleet="aura-keepers",
            seat="context",
            alias="aura-keeper-context",
        )
        record = created["agent"]
    codex_home = Path(record["root"]) / ".codex"
    _seed_keeper_codex_home(codex_home)
    return {
        "address": KEEPER_ADDRESS,
        "agent_id": record["agent_id"],
        "root": record["root"],
        "codex_home": str(codex_home),
    }


def _job_id(kind: str, agent_id: str, session_id: str, boundary: str) -> str:
    return ".".join(
        re.sub(r"[^A-Za-z0-9_.-]+", "_", part)
        for part in (kind, agent_id, session_id, boundary)
    )


def _memory_job_id(kind: str, agent_id: str, session_id: str, boundary: str, target_position: int) -> str:
    return _job_id(kind, agent_id, session_id, boundary) + f".p{int(target_position)}"


def _memory_path(target: dict[str, Any], *, boundary: str, session_id: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    short_session = re.sub(r"[^A-Za-z0-9_.-]+", "_", session_id)[:18]
    safe_boundary = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(boundary))
    return Path(str(target["package_root"])) / "memories" / f"{stamp}-{safe_boundary}-{short_session}.md"


def _memory_prompt_kind(boundary: str) -> str:
    return "state" if str(boundary).lower() == "precompact" else "trace"


def _recent_memory_paths(target: dict[str, Any], *, limit: int = RECENT_MEMORY_LIMIT) -> list[str]:
    root = Path(str(target["package_root"])) / "memories"
    if not root.is_dir():
        return []
    candidates = [
        path
        for path in root.glob("*.md")
        if path.is_file() and not path.name.startswith(".")
    ]
    candidates.sort(key=lambda path: (path.stat().st_mtime_ns, path.name), reverse=True)
    return [str(path) for path in candidates[: max(0, limit)]]


def _prompt_from_request(request: dict[str, Any]) -> str:
    memory_path = request["output"]["memory_path"]
    evidence = request["evidence"]
    recent_memories = evidence.get("recent_memory_paths") or []
    recent_memory_list = "\n".join(f"- {path}" for path in recent_memories) if recent_memories else "- none"
    prompt_kind = request.get("prompt_kind") or _memory_prompt_kind(str(request["boundary"]))
    if prompt_kind == "state":
        raw_prompt = """# TASK

You are capturing your working state.

Read your last 5 memories.
Read the new slice.

Capture the full working state before compaction.

Goal: make sure the next agent can recover the current work without relying on chat history.

LETS IMAGINE OUR ENTIRE SYSTEM / WORKFLOW / SOP.

DRAW IT OUT.

MARK WHERE WE ARE.

Write here:"""
    else:
        raw_prompt = """You are capturing your working state.

Read your last 5 memories.
Read the new slice.

Capture a trace of your working state.

Must have a 5 sentence overview.

Write here:"""

    return f"""{raw_prompt}
{memory_path}

Last 5 memories:
{recent_memory_list}

New slice:
- {evidence["slice_path"]}
- last read position: {evidence.get("last_read_position")}
- start position: {evidence["start_position"]}
- target position: {evidence["target_position"]}
- overlap messages: {evidence.get("overlap_messages")}
"""


def _launch_worker(*, job_path: Path, request: dict[str, Any]) -> dict[str, Any]:
    status_path = job_path / "status.json"
    events_path = job_path / "events.jsonl"
    result_path = job_path / "result.json"
    log_path = job_path / "log.txt"
    runner = Path(os.environ.get("AURA_KEEPER_SDK_RUNNER") or SDK_RUNNER)
    if not runner.exists():
        raise FileNotFoundError(f"missing Codex SDK runner: {runner}")
    cmd = [
        "node",
        str(runner),
        "memory",
        "--request",
        str(job_path / "request.json"),
        "--status",
        str(status_path),
        "--events",
        str(events_path),
        "--result",
        str(result_path),
        "--codex-home",
        request["keeper"]["codex_home"],
    ]
    job_script = job_path / "job.sh"
    job_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"exec {' '.join(shlex_quote(part) for part in cmd)}\n",
        encoding="utf-8",
    )
    job_script.chmod(0o755)
    log = log_path.open("ab")
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log.close()
    return {"pid": proc.pid, "job": str(job_script), "log": str(log_path)}


def shlex_quote(value: str) -> str:
    import shlex

    return shlex.quote(str(value))


def run_memory(*, target_ref: str, boundary: str, force: bool = False) -> dict[str, Any]:
    if not boundary:
        raise ValueError("boundary is required")
    target = resolve_target(target_ref)
    session_id = str(target["session_id"])
    cursor = _session_cursor(target, session_id)
    last_read_position = cursor.get("last_read_position")
    try:
        last_read_position = int(last_read_position) if last_read_position is not None else None
    except (TypeError, ValueError):
        last_read_position = None
    bounds = _flex_bounds(session_id)
    total_rows = int(bounds["rows"])
    target_position = int(bounds["max_position"])
    overlap_messages = DEFAULT_TRACE_OVERLAP_MESSAGES
    start_position = _overlap_start_position(
        session_id,
        last_read_position=last_read_position,
        overlap_messages=overlap_messages,
        total_rows=total_rows,
    )
    slice_rows = _flex_slice(session_id, start_position=start_position, target_position=target_position)
    if not slice_rows:
        raise FileNotFoundError(f"Flex returned no messages for session {session_id} slice {start_position}..{target_position}")
    keeper = ensure_keeper_profile(cwd=target.get("cwd"))
    job_id = _memory_job_id("memory", str(target["agent_id"]), session_id, str(boundary), target_position)
    path = job_dir(job_id)
    result_path = path / "result.json"
    if result_path.exists() and not force:
        return {
            "ok": True,
            "deduped": True,
            "job_id": job_id,
            "job_dir": str(path),
            "result": _read_json(result_path),
        }

    memory_path = _memory_path(target, boundary=str(boundary), session_id=session_id)
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    slice_path = path / "slice.json"
    index_path = _memory_index_path(target)
    prior_memory_path = cursor.get("latest_memory_path")
    recent_memory_paths = _recent_memory_paths(target)
    prompt_kind = _memory_prompt_kind(str(boundary))
    request = {
        "schema": REQUEST_SCHEMA,
        "job_id": job_id,
        "kind": "memory",
        "boundary": str(boundary),
        "prompt_kind": prompt_kind,
        "created_at": now_iso(),
        "target": {
            key: value
            for key, value in {
                "ref": target.get("ref"),
                "agent_id": target.get("agent_id"),
                "fleet": target.get("fleet"),
                "seat": target.get("seat"),
                "session_id": session_id,
                "runtime": target.get("runtime"),
                "cwd": target.get("cwd"),
                "package_root": target.get("package_root"),
            }.items()
            if value
        },
        "evidence": {
            "source": "flex:sessions:codex",
            "last_read_position": last_read_position,
            "last_read_message_id": cursor.get("last_read_message_id"),
            "overlap_messages": overlap_messages,
            "start_position": start_position,
            "target_position": target_position,
            "total_rows": total_rows,
            "slice_path": str(slice_path),
            "recent_memory_paths": recent_memory_paths,
            **({"prior_memory_path": prior_memory_path} if prior_memory_path else {}),
        },
        "output": {"memory_path": str(memory_path), "index_path": str(index_path)},
        "keeper": keeper,
    }

    path.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(path / "request.json", request)
    _atomic_write_json(
        slice_path,
        {
            "schema": "aura.keeper_memory_slice.v1",
            "session_id": session_id,
            "start_position": start_position,
            "target_position": target_position,
            "rows": slice_rows,
        },
    )
    _write_text(path / "prompt.md", _prompt_from_request(request))
    _atomic_write_json(
        path / "status.json",
        {
            "schema": STATUS_SCHEMA,
            "ok": True,
            "job_id": job_id,
            "state": "queued",
            "created_at": request["created_at"],
        },
    )
    launch = _launch_worker(job_path=path, request=request)
    status = {
        "schema": STATUS_SCHEMA,
        "ok": True,
        "job_id": job_id,
        "state": "running",
        "pid": launch["pid"],
        "started_at": now_iso(),
        "request": str(path / "request.json"),
        "events": str(path / "events.jsonl"),
        "result": str(result_path),
        "log": launch["log"],
    }
    _atomic_write_json(path / "status.json", status)
    return {
        "ok": True,
        "job_id": job_id,
        "job_dir": str(path),
        "pid": launch["pid"],
        "status": str(path / "status.json"),
        "events": str(path / "events.jsonl"),
        "result": str(result_path),
        "log": launch["log"],
        "memory_path": str(memory_path),
        "slice": str(slice_path),
        "start_position": start_position,
        "target_position": target_position,
        "last_read_position": last_read_position,
    }


def read_status(job_id: str) -> dict[str, Any]:
    return {"ok": True, "job_id": job_id, "status": _read_json(job_dir(job_id) / "status.json")}


def read_result(job_id: str) -> dict[str, Any]:
    return {"ok": True, "job_id": job_id, "result": _read_json(job_dir(job_id) / "result.json")}


def tail_log(job_id: str, *, lines: int = 80) -> dict[str, Any]:
    path = job_dir(job_id) / "log.txt"
    if not path.exists():
        return {"ok": True, "job_id": job_id, "path": str(path), "lines": []}
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"ok": True, "job_id": job_id, "path": str(path), "lines": content[-max(0, lines):]}

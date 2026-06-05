"""Background keeper jobs for package-backed Aura agents."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib import agent_packages, registry, state


REQUEST_SCHEMA = "aura.keeper_job_request.v1"
STATUS_SCHEMA = "aura.keeper_job_status.v1"
KEEPER_ADDRESS = "aura:keepers:context"
SDK_RUNNER = Path("/home/axp/.codex/skills/_codex-sdk-runner/runner.mjs")
FLEX_BIN = Path("/home/axp/projects/flexsearch/main/venv/bin/flex")
PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
TRACE_PROMPT_TEMPLATE = PROMPT_DIR / "keeper-memory-trace.md"
STATE_PROMPT_TEMPLATE = PROMPT_DIR / "keeper-memory-state.md"
DEFAULT_TRACE_OVERLAP_MESSAGES = 2
RECENT_MEMORY_LIMIT = 5
DEFAULT_STARTER_MESSAGES = 40
MAX_SLICE_BODY_CHARS = 4000
CODEX_AUTH_FILES = ("auth.json", "credentials.json")
CODEX_CONFIG_FILES = ("config.toml",)
AUTH_REFRESH_ERROR = "Your access token could not be refreshed because your refresh token was already used"
KEEPER_WORKER_ENV_STRIP = {
    "AURA_AGENT_NAME",
    "AURA_AGENT_PACKAGE_ID",
    "AURA_AGENT_PACKAGE_ROOT",
    "AURA_CODEX_BOX",
    "AURA_FLEET",
    "AURA_IDENTITY_ID",
    "AURA_RUNTIME",
    "AURA_RUNTIME_CAPSULE_REF",
    "AURA_RUNTIME_SESSION_ID",
    "AURA_SEAT",
    "AURA_SEAT_INSTANCE_ID",
    "AURA_SESSION_ID",
    "AURA_TMUX_SESSION",
    "CODEX_THREAD_ID",
}


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


def _last_read_position(cursor: dict[str, Any]) -> int | None:
    value = cursor.get("last_read_position")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


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


def _slice_speaker(row: dict[str, Any]) -> str:
    row_type = str(row.get("type") or "").strip() or "message"
    tool_name = str(row.get("tool_name") or "").strip()
    if tool_name:
        return f"{row_type} / {tool_name}"
    return row_type


def _slice_body(row: dict[str, Any]) -> str:
    body = row.get("body")
    if body is None:
        body = row.get("content")
    text = str(body or "").strip()
    if not text:
        return "[empty]"
    if len(text) <= MAX_SLICE_BODY_CHARS:
        return text
    omitted = len(text) - MAX_SLICE_BODY_CHARS
    return text[:MAX_SLICE_BODY_CHARS].rstrip() + f"\n\n[truncated {omitted} chars from this row]"


def _markdown_slice(*, session_id: str, start_position: int, target_position: int, rows: list[dict[str, Any]]) -> str:
    parts = [
        "# Conversation Slice",
        "",
        f"Session: `{session_id}`",
        f"Positions: `{start_position}` to `{target_position}`",
        "",
    ]
    for row in rows:
        position = row.get("position")
        speaker = _slice_speaker(row)
        target_file = row.get("target_file")
        parts.append(f"## {position} - {speaker}")
        if target_file:
            parts.append("")
            parts.append(f"Target file: `{target_file}`")
        parts.append("")
        parts.append(_slice_body(row))
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _keeper_source_codex_home() -> Path:
    configured = os.environ.get("AURA_KEEPER_CODEX_SOURCE_HOME") or os.environ.get("AURA_KEEPER_AUTH_SOURCE_HOME")
    return Path(configured or Path.home() / ".codex").expanduser()


def _backup_existing_auth(dest: Path) -> Path:
    backup_dir = dest.parent / ".auth-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    target = backup_dir / f"{dest.name}.{stamp}"
    counter = 1
    while target.exists():
        target = backup_dir / f"{dest.name}.{stamp}.{counter}"
        counter += 1
    shutil.move(str(dest), str(target))
    return target


def _link_auth_file(src: Path, dest: Path) -> dict[str, Any] | None:
    if not src.exists():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink():
        current = os.readlink(dest)
        if Path(current) == src:
            return {"file": dest.name, "mode": "symlink", "source": str(src), "changed": False}
        dest.unlink()
    elif dest.exists():
        try:
            if dest.samefile(src):
                return {"file": dest.name, "mode": "same-file", "source": str(src), "changed": False}
        except OSError:
            pass
        _backup_existing_auth(dest)
    dest.symlink_to(src)
    return {"file": dest.name, "mode": "symlink", "source": str(src), "changed": True}


def _refresh_config_file(src: Path, dest: Path) -> dict[str, Any] | None:
    if not src.exists():
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
        shutil.copy2(src, dest)
        return {"file": dest.name, "mode": "copy", "source": str(src), "changed": True}
    return {"file": dest.name, "mode": "copy", "source": str(src), "changed": False}


def _seed_keeper_codex_home(codex_home: Path) -> dict[str, Any]:
    codex_home.mkdir(parents=True, exist_ok=True)
    source = _keeper_source_codex_home()
    auth: list[dict[str, Any]] = []
    config: list[dict[str, Any]] = []
    for name in CODEX_AUTH_FILES:
        result = _link_auth_file(source / name, codex_home / name)
        if result:
            auth.append(result)
    for name in CODEX_CONFIG_FILES:
        result = _refresh_config_file(source / name, codex_home / name)
        if result:
            config.append(result)
    return {
        "source_codex_home": str(source),
        "codex_home": str(codex_home),
        "auth": auth,
        "config": config,
    }


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
    auth_seed = _seed_keeper_codex_home(codex_home)
    return {
        "address": KEEPER_ADDRESS,
        "agent_id": record["agent_id"],
        "root": record["root"],
        "codex_home": str(codex_home),
        "auth_seed": auth_seed,
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


def _prompt_template_path(prompt_kind: str) -> Path:
    env_name = "AURA_KEEPER_STATE_PROMPT" if prompt_kind == "state" else "AURA_KEEPER_TRACE_PROMPT"
    configured = os.environ.get(env_name)
    if configured:
        return Path(configured).expanduser()
    return STATE_PROMPT_TEMPLATE if prompt_kind == "state" else TRACE_PROMPT_TEMPLATE


def _load_prompt_template(prompt_kind: str) -> str:
    path = _prompt_template_path(prompt_kind)
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"missing keeper prompt template: {path}") from exc
    if not text:
        raise ValueError(f"empty keeper prompt template: {path}")
    return text


def _prompt_from_request(request: dict[str, Any]) -> str:
    memory_path = request["output"]["memory_path"]
    evidence = request["evidence"]
    recent_memories = evidence.get("recent_memory_paths") or []
    recent_memory_list = "\n".join(f"- {path}" for path in recent_memories) if recent_memories else "- none"
    prompt_kind = request.get("prompt_kind") or _memory_prompt_kind(str(request["boundary"]))
    raw_prompt = _load_prompt_template(prompt_kind)

    return f"""{raw_prompt}

WRITE HERE:
{memory_path}

Last 5 memories:
{recent_memory_list}

Conversation excerpt:
- {evidence.get("slice_markdown_path") or evidence["slice_path"]}
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
    unset_lines = "".join(f"unset {key}\n" for key in sorted(KEEPER_WORKER_ENV_STRIP))
    job_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"{unset_lines}"
        "export AURA_KEEPER_WORKER=1\n"
        f"export CODEX_HOME={shlex_quote(request['keeper']['codex_home'])}\n"
        f"exec {' '.join(shlex_quote(part) for part in cmd)}\n",
        encoding="utf-8",
    )
    job_script.chmod(0o755)
    log = log_path.open("ab")
    env = _keeper_worker_env(codex_home=str(request["keeper"]["codex_home"]))
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
    finally:
        log.close()
    return {"pid": proc.pid, "job": str(job_script), "log": str(log_path)}


def _keeper_worker_env(*, codex_home: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for key in KEEPER_WORKER_ENV_STRIP:
        env.pop(key, None)
    env["AURA_KEEPER_WORKER"] = "1"
    if codex_home:
        env["CODEX_HOME"] = codex_home
    return env


def shlex_quote(value: str) -> str:
    import shlex

    return shlex.quote(str(value))


def run_memory(*, target_ref: str, boundary: str, force: bool = False) -> dict[str, Any]:
    if not boundary:
        raise ValueError("boundary is required")
    target = resolve_target(target_ref)
    session_id = str(target["session_id"])
    bounds = _flex_bounds(session_id)
    total_rows = int(bounds["rows"])
    target_position = int(bounds["max_position"])
    cursor = _session_cursor(target, session_id)
    last_read_position = _last_read_position(cursor)
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

    slice_path = path / "slice.json"
    slice_markdown_path = path / "slice.md"
    index_path = _memory_index_path(target)
    prior_memory_path = cursor.get("latest_memory_path")
    recent_memory_paths = _recent_memory_paths(target)
    prompt_kind = _memory_prompt_kind(str(boundary))
    keeper = ensure_keeper_profile(cwd=target.get("cwd"))
    memory_path = _memory_path(target, boundary=str(boundary), session_id=session_id)
    memory_path.parent.mkdir(parents=True, exist_ok=True)
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
            "slice_markdown_path": str(slice_markdown_path),
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
    _write_text(
        slice_markdown_path,
        _markdown_slice(
            session_id=session_id,
            start_position=start_position,
            target_position=target_position,
            rows=slice_rows,
        ),
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
        "slice_markdown": str(slice_markdown_path),
        "start_position": start_position,
        "target_position": target_position,
        "last_read_position": last_read_position,
    }


def _classify_keeper_error(message: Any) -> dict[str, Any] | None:
    text = str(message or "")
    if not text:
        return None
    if AUTH_REFRESH_ERROR in text:
        return {
            "kind": "codex-auth-refresh",
            "severity": "critical",
            "summary": "Keeper Codex auth cannot refresh; memory jobs launch but cannot complete.",
            "recommended_action": "Refresh the keeper Codex auth home or relink it to the active user Codex auth.",
        }
    return {"kind": "keeper-error", "severity": "error", "summary": text}


def _job_status_path(path: Path) -> Path:
    return path / "status.json"


def _job_result_path(path: Path) -> Path:
    return path / "result.json"


def _read_status_with_diagnostics(path: Path) -> dict[str, Any]:
    status = _read_json(_job_status_path(path))
    diagnostic = _classify_keeper_error(status.get("error"))
    if diagnostic:
        status["diagnostic"] = diagnostic
    return status


def read_status(job_id: str) -> dict[str, Any]:
    path = job_dir(job_id)
    return {"ok": True, "job_id": job_id, "status": _read_status_with_diagnostics(path)}


def read_result(job_id: str) -> dict[str, Any]:
    return {"ok": True, "job_id": job_id, "result": _read_json(job_dir(job_id) / "result.json")}


def tail_log(job_id: str, *, lines: int = 80) -> dict[str, Any]:
    path = job_dir(job_id) / "log.txt"
    if not path.exists():
        return {"ok": True, "job_id": job_id, "path": str(path), "lines": []}
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"ok": True, "job_id": job_id, "path": str(path), "lines": content[-max(0, lines):]}


def _job_health_row(path: Path) -> dict[str, Any]:
    status_path = _job_status_path(path)
    result_path = _job_result_path(path)
    row: dict[str, Any] = {
        "job_id": path.name,
        "job_dir": str(path),
        "updated_at_ms": int(path.stat().st_mtime * 1000),
        "has_result": result_path.exists(),
    }
    if result_path.exists():
        row["state"] = "complete"
        return row
    if status_path.exists():
        try:
            status = _read_status_with_diagnostics(path)
            row["status"] = status
            row["state"] = status.get("state") or "unknown"
            if status.get("ok") is False:
                row["state"] = "failed"
            if status.get("diagnostic"):
                row["diagnostic"] = status["diagnostic"]
        except Exception as exc:
            row["state"] = "invalid-status"
            row["error"] = str(exc)
    else:
        row["state"] = "missing-status"
    return row


def health(*, limit: int = 50) -> dict[str, Any]:
    root = keeper_jobs_root()
    jobs = sorted(
        [path for path in root.glob("memory.*") if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[: max(0, int(limit))]
    rows = [_job_health_row(path) for path in jobs]
    counts: dict[str, int] = {}
    diagnostic_counts: dict[str, int] = {}
    for row in rows:
        state_name = str(row.get("state") or "unknown")
        counts[state_name] = counts.get(state_name, 0) + 1
        diagnostic = row.get("diagnostic")
        if isinstance(diagnostic, dict):
            kind = str(diagnostic.get("kind") or "unknown")
            diagnostic_counts[kind] = diagnostic_counts.get(kind, 0) + 1
    return {
        "ok": True,
        "schema": "aura.keeper_health.v1",
        "root": str(root),
        "limit": max(0, int(limit)),
        "counts": counts,
        "diagnostics": diagnostic_counts,
        "jobs": rows,
    }


def _request_target(request: dict[str, Any]) -> dict[str, Any]:
    target = request.get("target")
    return target if isinstance(target, dict) else {}


def _request_evidence(request: dict[str, Any]) -> dict[str, Any]:
    evidence = request.get("evidence")
    return evidence if isinstance(evidence, dict) else {}


def _candidate_from_job(path: Path, *, diagnostic: str, agent_id: str | None, session_id: str | None) -> dict[str, Any] | None:
    if _job_result_path(path).exists():
        return None
    request_path = path / "request.json"
    if not request_path.exists():
        return None
    try:
        request = _read_json(request_path)
        status = _read_status_with_diagnostics(path) if _job_status_path(path).exists() else {}
    except Exception:
        return None
    row = _job_health_row(path)
    row_diagnostic = row.get("diagnostic")
    diagnostic_kind = row_diagnostic.get("kind") if isinstance(row_diagnostic, dict) else None
    if diagnostic != "any" and diagnostic_kind != diagnostic:
        return None
    target = _request_target(request)
    evidence = _request_evidence(request)
    if agent_id and str(target.get("agent_id") or "") != str(agent_id):
        return None
    if session_id and str(target.get("session_id") or "") != str(session_id):
        return None
    output = request.get("output") if isinstance(request.get("output"), dict) else {}
    index_path = Path(str(output.get("index_path") or ""))
    target_session_id = str(target.get("session_id") or "")
    try:
        target_position = int(evidence.get("target_position"))
    except (TypeError, ValueError):
        target_position = None
    if index_path and index_path.exists() and target_session_id and target_position is not None:
        try:
            index = _read_json(index_path)
            sessions = index.get("sessions") if isinstance(index.get("sessions"), dict) else {}
            cursor = sessions.get(target_session_id) if isinstance(sessions.get(target_session_id), dict) else {}
            last_read = cursor.get("last_read_position")
            if last_read is not None and int(last_read) >= target_position:
                return None
        except Exception:
            pass
    return {
        "job_id": path.name,
        "job_dir": str(path),
        "agent_id": target.get("agent_id"),
        "session_id": target.get("session_id"),
        "boundary": request.get("boundary"),
        "target_position": evidence.get("target_position"),
        "memory_path": (request.get("output") or {}).get("memory_path") if isinstance(request.get("output"), dict) else None,
        "index_path": (request.get("output") or {}).get("index_path") if isinstance(request.get("output"), dict) else None,
        "state": row.get("state"),
        "diagnostic": row_diagnostic,
        "status": status,
        "_path": path,
        "_request": request,
    }


def _backfill_candidates(
    *,
    diagnostic: str,
    agent_id: str | None,
    session_id: str | None,
    job_ids: list[str] | None,
) -> list[dict[str, Any]]:
    if job_ids:
        paths = [job_dir(job_id) for job_id in job_ids]
    else:
        root = keeper_jobs_root()
        paths = [path for path in root.glob("memory.*") if path.is_dir()]
    rows = [
        row
        for path in paths
        if (row := _candidate_from_job(path, diagnostic=diagnostic, agent_id=agent_id, session_id=session_id)) is not None
    ]

    def sort_key(row: dict[str, Any]) -> tuple[str, str, int, float]:
        target_position = row.get("target_position")
        try:
            position = int(target_position)
        except (TypeError, ValueError):
            position = -1
        return (
            str(row.get("agent_id") or ""),
            str(row.get("session_id") or ""),
            position,
            Path(str(row["job_dir"])).stat().st_mtime,
        )

    ordered = sorted(rows, key=sort_key)
    if job_ids:
        return ordered
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for row in ordered:
        key = (
            str(row.get("agent_id") or ""),
            str(row.get("session_id") or ""),
            str(row.get("target_position") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _public_backfill_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if not key.startswith("_") and key != "status"}


def _wait_for_job(path: Path, *, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + max(0, int(timeout_seconds))
    while True:
        if _job_result_path(path).exists():
            return {"state": "complete", "result": str(_job_result_path(path))}
        if _job_status_path(path).exists():
            try:
                status = _read_status_with_diagnostics(path)
            except Exception as exc:
                return {"state": "invalid-status", "error": str(exc)}
            if status.get("ok") is False or status.get("state") == "failed":
                return {"state": "failed", "status": status}
        if time.time() >= deadline:
            return {"state": "timeout", "status": _read_status_with_diagnostics(path) if _job_status_path(path).exists() else None}
        time.sleep(2)


def _refresh_request_cursor_from_index(request: dict[str, Any]) -> None:
    target = _request_target(request)
    evidence = _request_evidence(request)
    output = request.get("output") if isinstance(request.get("output"), dict) else {}
    index_path = Path(str(output.get("index_path") or ""))
    session_id = str(target.get("session_id") or "")
    if not index_path.exists() or not session_id:
        return
    try:
        index = _read_json(index_path)
    except Exception:
        return
    sessions = index.get("sessions") if isinstance(index.get("sessions"), dict) else {}
    cursor = sessions.get(session_id) if isinstance(sessions.get(session_id), dict) else {}
    if not cursor:
        return
    last_read = cursor.get("last_read_position")
    if last_read is None:
        return
    try:
        evidence["last_read_position"] = int(last_read)
    except (TypeError, ValueError):
        evidence["last_read_position"] = last_read
    if cursor.get("last_read_message_id"):
        evidence["last_read_message_id"] = cursor.get("last_read_message_id")
    if cursor.get("latest_memory_path"):
        evidence["prior_memory_path"] = cursor.get("latest_memory_path")
    request["evidence"] = evidence


def backfill(
    *,
    limit: int = 5,
    dry_run: bool = False,
    diagnostic: str = "codex-auth-refresh",
    agent_id: str | None = None,
    session_id: str | None = None,
    job_ids: list[str] | None = None,
    wait: bool = False,
    timeout_seconds: int = 600,
) -> dict[str, Any]:
    candidates = _backfill_candidates(
        diagnostic=str(diagnostic or "any"),
        agent_id=agent_id,
        session_id=session_id,
        job_ids=job_ids,
    )
    selected = candidates[: max(0, int(limit))]
    if dry_run:
        return {
            "ok": True,
            "schema": "aura.keeper_backfill.v1",
            "dry_run": True,
            "limit": max(0, int(limit)),
            "candidate_count": len(candidates),
            "selected": [_public_backfill_row(row) for row in selected],
        }

    launched: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in selected:
        path = Path(str(row["_path"]))
        request = dict(row["_request"])
        if _job_result_path(path).exists():
            skipped.append({"job_id": row["job_id"], "reason": "result-exists"})
            continue
        target = _request_target(request)
        keeper = ensure_keeper_profile(cwd=target.get("cwd"))
        request["keeper"] = keeper
        _refresh_request_cursor_from_index(request)
        request["backfill"] = {
            "requested_at": now_iso(),
            "source_status": str(_job_status_path(path)),
            "diagnostic": row.get("diagnostic"),
        }
        _atomic_write_json(path / "request.json", request)
        _atomic_write_json(
            path / "status.json",
            {
                "schema": STATUS_SCHEMA,
                "ok": True,
                "job_id": row["job_id"],
                "state": "queued",
                "backfill": True,
                "queued_at": now_iso(),
            },
        )
        launch = _launch_worker(job_path=path, request=request)
        status = {
            "schema": STATUS_SCHEMA,
            "ok": True,
            "job_id": row["job_id"],
            "state": "running",
            "backfill": True,
            "pid": launch["pid"],
            "started_at": now_iso(),
            "request": str(path / "request.json"),
            "events": str(path / "events.jsonl"),
            "result": str(_job_result_path(path)),
            "log": launch["log"],
        }
        _atomic_write_json(path / "status.json", status)
        launched_row = {
            **_public_backfill_row(row),
            "pid": launch["pid"],
            "status_path": str(path / "status.json"),
            "result_path": str(_job_result_path(path)),
            "log": launch["log"],
        }
        if wait:
            launched_row["wait"] = _wait_for_job(path, timeout_seconds=timeout_seconds)
        launched.append(launched_row)
    return {
        "ok": True,
        "schema": "aura.keeper_backfill.v1",
        "dry_run": False,
        "limit": max(0, int(limit)),
        "candidate_count": len(candidates),
        "launched": launched,
        "skipped": skipped,
        "counts": {"launched": len(launched), "skipped": len(skipped)},
    }


def _agent_manifest_paths() -> list[Path]:
    root = agent_packages.agents_root()
    if not root.is_dir():
        return []
    return sorted(root.glob("i_*/manifest.json"))


def _codex_profile_templates() -> list[Path]:
    root = state.state_root() / "runtime-profiles" / "codex"
    if not root.is_dir():
        return []
    return sorted(path / "codex-home-template" for path in root.iterdir() if path.is_dir())


def _omx_profile_templates() -> list[Path]:
    root = state.state_root() / "runtime-profiles" / "omx"
    if not root.is_dir():
        return []
    return sorted(path / "codex-home-template" for path in root.iterdir() if path.is_dir())


def _with_omx_probes_disabled(call):
    previous = os.environ.get("AURA_OMX_ADAPTER_PROBE")
    os.environ["AURA_OMX_ADAPTER_PROBE"] = "0"
    try:
        return call()
    finally:
        if previous is None:
            os.environ.pop("AURA_OMX_ADAPTER_PROBE", None)
        else:
            os.environ["AURA_OMX_ADAPTER_PROBE"] = previous


def install_hooks(*, agents: bool = True, profiles: bool = True, dry_run: bool = False) -> dict[str, Any]:
    """Refresh Aura keeper hook installation across durable homes/templates."""

    from lib import codex as codex_lib
    from lib import omx_adapter

    installed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    if agents:
        for manifest_path in _agent_manifest_paths():
            root = manifest_path.parent
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as exc:
                skipped.append({"scope": "agent", "root": str(root), "reason": "invalid-manifest", "detail": str(exc)})
                continue
            if not isinstance(manifest, dict):
                skipped.append({"scope": "agent", "root": str(root), "reason": "invalid-manifest"})
                continue
            runtime = str(manifest.get("runtime") or "")
            codex_home = root / ".codex"
            if not codex_home.is_dir():
                skipped.append({"scope": "agent", "root": str(root), "runtime": runtime, "reason": "missing-codex-home"})
                continue
            if dry_run:
                installed.append({"scope": "agent", "root": str(root), "runtime": runtime, "codex_home": str(codex_home), "dry_run": True})
            elif runtime == "codex":
                installed.append({"scope": "agent", "root": str(root), "runtime": runtime, **codex_lib.install_aura_package_hooks(codex_home)})
            elif runtime == "omx":
                adapter = _with_omx_probes_disabled(
                    lambda root=root, codex_home=codex_home: omx_adapter.apply_adapter(
                        root=root,
                        codex_home=codex_home,
                        runtime=root / "runtime",
                    )
                )
                if adapter.enabled:
                    installed.append({"scope": "agent", "root": str(root), "runtime": runtime, "codex_home": str(codex_home), **adapter.metadata()})
                else:
                    skipped.append({"scope": "agent", "root": str(root), "runtime": runtime, "reason": "omx-adapter-disabled", "detail": adapter.error})
            else:
                skipped.append({"scope": "agent", "root": str(root), "runtime": runtime, "reason": "unsupported-runtime"})

    if profiles:
        for codex_home in _codex_profile_templates():
            root = codex_home.parent
            if dry_run:
                installed.append({"scope": "profile", "runtime": "codex", "root": str(root), "codex_home": str(codex_home), "dry_run": True})
            else:
                installed.append({"scope": "profile", "runtime": "codex", "root": str(root), **codex_lib.install_aura_package_hooks(codex_home)})
        for codex_home in _omx_profile_templates():
            root = codex_home.parent
            hooks_path = codex_home / "hooks.json"
            if dry_run:
                installed.append({"scope": "profile", "runtime": "omx", "root": str(root), "codex_home": str(codex_home), "dry_run": True})
            elif not hooks_path.is_file():
                skipped.append({"scope": "profile", "runtime": "omx", "root": str(root), "reason": "missing-hooks-json"})
            else:
                adapter = _with_omx_probes_disabled(
                    lambda root=root, codex_home=codex_home: omx_adapter.apply_adapter(
                        root=root,
                        codex_home=codex_home,
                        runtime=root / "runtime-template",
                    )
                )
                if adapter.enabled:
                    installed.append({"scope": "profile", "runtime": "omx", "root": str(root), "codex_home": str(codex_home), **adapter.metadata()})
                else:
                    skipped.append({"scope": "profile", "runtime": "omx", "root": str(root), "reason": "omx-adapter-disabled", "detail": adapter.error})

    return {
        "ok": True,
        "schema": "aura.keeper_hooks.install.v1",
        "dry_run": dry_run,
        "agents": agents,
        "profiles": profiles,
        "installed": installed,
        "skipped": skipped,
        "counts": {"installed": len(installed), "skipped": len(skipped)},
    }

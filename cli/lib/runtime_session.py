"""Runtime session id discovery for terminal-backed seats."""

from __future__ import annotations

from pathlib import Path
import os
import re
import sqlite3
import subprocess


RUNTIME_SESSION_ENV = {
    "codex": ("CODEX_THREAD_ID",),
    "omx": ("CODEX_THREAD_ID",),
    "claude-code": ("CLAUDE_SESSION_ID", "AURA_SESSION_ID"),
    "claude": ("CLAUDE_SESSION_ID", "AURA_SESSION_ID"),
}
CODEX_BACKED_RUNTIMES = {"codex", "omx"}

UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
DEFAULT_CODEX_STATE_DB = Path.home() / ".codex" / "state_5.sqlite"
BOUND_SESSION_SOURCES = {
    "spawn:resume-session": "spawn-resume-session",
    "argv:codex-resume": "argv-resume",
    "codex-jsonl:nonce": "nonce-jsonl",
    "codex-hook:session-start": "codex-hook",
    "codex-hook:user-prompt-submit": "codex-hook",
    "codex-footer:capture": "footer-capture",
}


def binding_method_for_source(source: str | None) -> str | None:
    if not source:
        return None
    if source in BOUND_SESSION_SOURCES:
        return BOUND_SESSION_SOURCES[source]
    if source.startswith("codex-hook:"):
        return "codex-hook"
    if source.startswith("env:"):
        return "runtime-env"
    if source == "current-process":
        return "current-process"
    return None


def is_bound_session(session: dict | None) -> bool:
    if not session or not (session.get("runtime_session_id") or session.get("session_id")):
        return False
    if session.get("runtime_session_binding") == "bound":
        return True
    return bool(binding_method_for_source(session.get("runtime_session_source")))


def mark_binding(session: dict) -> dict:
    if not session:
        return session
    method = session.get("runtime_session_bind_method") or binding_method_for_source(session.get("runtime_session_source"))
    if method and (session.get("runtime_session_id") or session.get("session_id")):
        if not session.get("runtime_session_id") and session.get("session_id"):
            session["runtime_session_id"] = session["session_id"]
        session.setdefault("runtime_session_binding", "bound")
        session.setdefault("runtime_session_bind_method", method)
        session.setdefault("runtime_session_bind_source", session.get("runtime_session_source"))
    else:
        if session.get("runtime_session_source") == "codex-state:cwd-start":
            possible_id = session.pop("runtime_session_id", None) or session.pop("session_id", None)
            session.pop("session_id", None)
            if possible_id and not session.get("runtime_session_possible_matches"):
                evidence = session.get("runtime_session_evidence") or {}
                session["runtime_session_possible_matches"] = [{
                    "runtime_session_id": possible_id,
                    "source": "codex-state:cwd-start",
                    "reason": evidence.get("reason"),
                    "cwd": session.get("runtime_session_cwd") or session.get("cwd"),
                    "created_at_ms": session.get("runtime_session_created_at_ms"),
                    "updated_at_ms": session.get("runtime_session_updated_at_ms"),
                }]
            if session.get("runtime_session_evidence") and not session.get("runtime_session_diagnostics"):
                session["runtime_session_diagnostics"] = {
                    **(session.get("runtime_session_evidence") or {}),
                    "source": "codex-state:cwd-start",
                    "reason": "legacy-codex-state-possible-match",
                }
        session.setdefault("runtime_session_binding", "unbound")
    return session


def possible_match_from_codex_state(row: dict, selection: dict, *, cwd: str | None, started: float | None, launch_id: str | None) -> dict:
    return {
        "runtime_session_possible_matches": [{
            "runtime_session_id": row.get("id"),
            "source": "codex-state:cwd-start",
            "reason": selection.get("reason"),
            "candidate_count": selection.get("candidate_count"),
            "cwd": cwd,
            "pane_start_epoch": started,
            "created_at_ms": row.get("created_at_ms"),
            "updated_at_ms": row.get("updated_at_ms"),
            "title": row.get("title"),
            "first_user_message_preview": (row.get("first_user_message") or "")[:160],
            "aura_launch_id": launch_id,
        }],
        "runtime_session_diagnostics": {
            **selection,
            "source": "codex-state:cwd-start",
            "reason": "codex-state-possible-match",
            "cwd": cwd,
            "pane_start_epoch": started,
            "aura_launch_id": launch_id,
        },
        "runtime_session_source": "codex-state:cwd-start",
        "runtime_session_binding": "unbound",
        "runtime_session_pid": None,
        "runtime_session_cwd": cwd,
        "runtime_session_created_at_ms": row.get("created_at_ms"),
        "runtime_session_updated_at_ms": row.get("updated_at_ms"),
    }


def _read_process_environ(pid: int) -> dict[str, str]:
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return {}
    env: dict[str, str] = {}
    for item in raw.split(b"\0"):
        if not item or b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        try:
            env[key.decode()] = value.decode(errors="replace")
        except UnicodeDecodeError:
            continue
    return env


def _read_process_cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    parts = []
    for item in raw.split(b"\0"):
        if item:
            parts.append(item.decode(errors="replace"))
    return parts


def _process_ppid(pid: int) -> int | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    end = stat.rfind(")")
    if end < 0:
        return None
    parts = stat[end + 2 :].split()
    if len(parts) < 2:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def _process_start_epoch(pid: int) -> float | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8", errors="replace")
        boot_time = None
        for line in Path("/proc/stat").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("btime "):
                boot_time = int(line.split()[1])
                break
    except OSError:
        return None
    if boot_time is None:
        return None
    end = stat.rfind(")")
    if end < 0:
        return None
    parts = stat[end + 2 :].split()
    if len(parts) < 20:
        return None
    try:
        start_ticks = int(parts[19])
        ticks_per_second = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    except (ValueError, OSError, KeyError):
        return None
    return boot_time + (start_ticks / ticks_per_second)


def _process_cwd(pid: int) -> str | None:
    try:
        return str(Path(f"/proc/{pid}/cwd").resolve())
    except OSError:
        return None


def _descendant_pids(root_pid: int, *, limit: int = 256) -> list[int]:
    children: dict[int, list[int]] = {}
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        pid = int(proc.name)
        ppid = _process_ppid(pid)
        if ppid is None:
            continue
        children.setdefault(ppid, []).append(pid)

    ordered = [root_pid]
    queue = [root_pid]
    while queue and len(ordered) < limit:
        parent = queue.pop(0)
        for child in sorted(children.get(parent, [])):
            if child not in ordered:
                ordered.append(child)
                queue.append(child)
    return ordered


def _codex_state_threads(cwd: str, *, around_epoch: float | None = None) -> list[dict]:
    db_path = Path(os.environ.get("CODEX_STATE_DB") or DEFAULT_CODEX_STATE_DB)
    if not db_path.exists():
        return []
    window_ms = 45 * 60 * 1000
    params: list[object] = [cwd]
    where = ["cwd = ?"]
    if around_epoch is not None:
        center_ms = int(around_epoch * 1000)
        where.append("created_at_ms BETWEEN ? AND ?")
        params.extend([center_ms - window_ms, center_ms + window_ms])
    query = f"""
        SELECT id, cwd, created_at_ms, updated_at_ms, title, first_user_message, agent_nickname, agent_role, agent_path
        FROM threads
        WHERE {' AND '.join(where)}
        ORDER BY created_at_ms DESC, updated_at_ms DESC
        LIMIT 50
    """
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute(query, params)]
        conn.close()
    except sqlite3.Error:
        return []
    return rows


def _row_haystack(row: dict) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in ("title", "first_user_message", "agent_nickname", "agent_role", "agent_path")
    ).lower()


def _row_contains_launch_id(row: dict, launch_id: str | None) -> bool:
    if not launch_id:
        return False
    haystack = " ".join(
        str(row.get(key) or "")
        for key in ("title", "first_user_message")
    )
    return launch_id in haystack


def _row_identity_haystack(row: dict) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in ("agent_nickname", "agent_role", "agent_path")
    ).lower()


def _seat_identity_pattern_matches(row: dict, seat_name: str) -> bool:
    import re

    text = " ".join(
        str(row.get(key) or "")
        for key in ("title", "first_user_message")
    ).lower()
    escaped = re.escape(seat_name.lower())
    patterns = (
        rf"\byou are (?:the )?`?{escaped}`?\b",
        rf"\bseat(?: name)?\s*[:=]\s*`?{escaped}`?\b",
        rf"\bname\s*[:=]\s*`?{escaped}`?\b",
    )
    return any(re.search(pattern, text) for pattern in patterns)


def _seat_match_rows(rows: list[dict], seat_name: str | None) -> list[dict]:
    if not seat_name:
        return []
    lowered = seat_name.lower()
    identity_haystacks = [(row, _row_identity_haystack(row)) for row in rows]
    exact = [row for row, haystack in identity_haystacks if lowered and lowered in haystack]
    if exact:
        return exact
    prompted_identity = [row for row in rows if _seat_identity_pattern_matches(row, seat_name)]
    if prompted_identity:
        return prompted_identity
    tokens = [token for token in re.split(r"[-_:.\s]+", seat_name.lower()) if len(token) > 2]
    if len(tokens) < 2:
        return []
    haystacks = [(row, _row_haystack(row)) for row in rows]
    return [row for row, haystack in haystacks if all(token in haystack for token in tokens)]


def _select_codex_state_row(
    rows: list[dict],
    *,
    seat_name: str | None,
    started: float | None,
    launch_id: str | None = None,
) -> tuple[dict | None, dict]:
    if not rows:
        return None, {"confidence": "none", "reason": "no-codex-state-row"}

    launch_matches = [row for row in rows if _row_contains_launch_id(row, launch_id)]
    if len(launch_matches) == 1:
        return launch_matches[0], {
            "confidence": "exact",
            "reason": "aura-launch-id",
            "candidate_count": len(rows),
            "launch_id_matches": 1,
        }
    if len(launch_matches) > 1:
        newest = sorted(launch_matches, key=lambda row: int(row.get("updated_at_ms") or 0), reverse=True)
        return newest[0], {
            "confidence": "high",
            "reason": "aura-launch-id-multiple-candidates",
            "candidate_count": len(rows),
            "launch_id_matches": len(launch_matches),
        }

    seat_matches = _seat_match_rows(rows, seat_name)
    if seat_matches:
        if len(seat_matches) == 1:
            return seat_matches[0], {
                "confidence": "high",
                "reason": "cwd-start-seat-name",
                "candidate_count": len(rows),
                "seat_name_matches": 1,
            }
        newest = sorted(seat_matches, key=lambda row: int(row.get("updated_at_ms") or 0), reverse=True)
        if len(newest) > 1:
            updated_gap_ms = int(newest[0].get("updated_at_ms") or 0) - int(newest[1].get("updated_at_ms") or 0)
            if updated_gap_ms >= 60000:
                return newest[0], {
                    "confidence": "high",
                    "reason": "cwd-start-seat-name-currently-updated",
                    "candidate_count": len(rows),
                    "seat_name_matches": len(seat_matches),
                    "updated_gap_ms": updated_gap_ms,
                }
        rows = seat_matches

    if started is not None:
        start_ms = int(started * 1000)
        rows = sorted(rows, key=lambda row: abs(int(row.get("created_at_ms") or 0) - start_ms))
        nearest = rows[0]
        delta_ms = abs(int(nearest.get("created_at_ms") or 0) - start_ms)
        if delta_ms <= 600000 and (len(rows) == 1 or len(seat_matches) == 1):
            return nearest, {
                "confidence": "medium" if seat_name else "high",
                "reason": "cwd-start-nearest",
                "candidate_count": len(rows),
                "created_delta_ms": delta_ms,
            }
        if delta_ms <= 600000:
            return nearest, {
                "confidence": "medium",
                "reason": "cwd-start-nearest-multiple-candidates",
                "candidate_count": len(rows),
                "created_delta_ms": delta_ms,
                "seat_name_matches": len(seat_matches),
            }

    return rows[0], {
        "confidence": "low" if len(rows) > 1 else "medium",
        "reason": "cwd-latest" if len(rows) > 1 else "cwd-only",
        "candidate_count": len(rows),
        "seat_name_matches": len(seat_matches),
    }


def _discover_codex_state_thread(
    pane_pid: int,
    *,
    seat_name: str | None = None,
    launch_id: str | None = None,
) -> dict:
    cwd = _process_cwd(pane_pid)
    if not cwd:
        return {}
    started = _process_start_epoch(pane_pid)
    rows = _codex_state_threads(cwd, around_epoch=started)
    if not rows:
        rows = _codex_state_threads(cwd)
    if not rows:
        return {}
    row, selection = _select_codex_state_row(
        rows,
        seat_name=seat_name,
        started=started,
        launch_id=launch_id,
    )
    if not row:
        return {}
    diagnostic = possible_match_from_codex_state(row, selection, cwd=cwd, started=started, launch_id=launch_id)
    diagnostic["runtime_session_pid"] = pane_pid
    return diagnostic


def _session_env_names(runtime: str | None) -> tuple[str, ...]:
    names = RUNTIME_SESSION_ENV.get(runtime or "", ())
    return ("AURA_RUNTIME_SESSION_ID", "AURA_SESSION_ID", *names)


def _current_process_session_env_names(runtime: str | None) -> tuple[str, ...]:
    names = RUNTIME_SESSION_ENV.get(runtime or "", ())
    return (*names, "AURA_RUNTIME_SESSION_ID", "AURA_SESSION_ID")


def _discover_codex_runtime_argv(pid: int) -> dict:
    argv = _read_process_cmdline(pid)
    if not argv:
        return {}
    for index, part in enumerate(argv):
        if part not in {"resume", "fork"}:
            continue
        if index + 1 >= len(argv):
            continue
        match = UUID_RE.search(argv[index + 1])
        if match and part == "resume":
            return {
                "runtime_session_id": match.group(0),
                "runtime_session_source": "argv:codex-resume",
                "runtime_session_binding": "bound",
                "runtime_session_bind_method": "argv-resume",
                "runtime_session_bind_source": "argv:codex-resume",
                "runtime_session_confidence": "exact",
                "runtime_session_evidence": {
                    "reason": "codex-resume-argv",
                    "argv": argv,
                },
                "runtime_session_pid": pid,
            }
        if match and part == "fork":
            return {
                "source_session_id": match.group(0),
                "runtime_session_source": "argv:codex-fork",
                "runtime_session_binding": "pending-fork-child",
                "runtime_session_bind_method": "argv-fork-source",
                "runtime_session_bind_source": "argv:codex-fork",
                "runtime_session_confidence": "source-exact-child-pending",
                "runtime_session_evidence": {
                    "reason": "codex-fork-argv",
                    "source_session_id": match.group(0),
                    "argv": argv,
                },
                "runtime_session_pid": pid,
            }
    return {}


def _discover_codex_resume_argv(pid: int) -> dict:
    discovered = _discover_codex_runtime_argv(pid)
    if discovered.get("runtime_session_source") == "argv:codex-resume":
        return discovered
    return {}


def discover_from_pane_pid(
    runtime: str | None,
    pane_pid: int | None,
    *,
    seat_name: str | None = None,
    launch_id: str | None = None,
) -> dict:
    if not pane_pid:
        return {}
    pids = _descendant_pids(int(pane_pid))
    if runtime in CODEX_BACKED_RUNTIMES:
        for pid in pids:
            discovered = _discover_codex_runtime_argv(pid)
            if discovered:
                return discovered
        discovered = _discover_codex_state_thread(
            int(pane_pid),
            seat_name=seat_name,
            launch_id=launch_id,
        )
        if discovered:
            return discovered

    env_names = _session_env_names(runtime)
    for pid in pids:
        env = _read_process_environ(pid)
        for name in env_names:
            value = env.get(name)
            if value:
                if runtime in CODEX_BACKED_RUNTIMES and name == "CODEX_THREAD_ID":
                    # Codex does not reliably rewrite process environ after a
                    # new thread starts. In tmux-spawned seats this value is
                    # often inherited from the spawning Codex session, so using
                    # it would corrupt restore metadata for other seats.
                    continue
                return {
                    "runtime_session_id": value,
                    "runtime_session_env": name,
                    "runtime_session_source": f"env:{name}",
                    "runtime_session_binding": "bound",
                    "runtime_session_bind_method": "runtime-env",
                    "runtime_session_bind_source": f"env:{name}",
                    "runtime_session_confidence": "medium",
                    "runtime_session_evidence": {"reason": "runtime-env", "env": name},
                    "runtime_session_pid": pid,
                }
    return {}


def discover_for_target(
    runtime: str | None,
    terminal,
    target: str | None,
    *,
    seat_name: str | None = None,
    launch_id: str | None = None,
) -> dict:
    if not target or not hasattr(terminal, "pane_pid"):
        return {}
    try:
        pane_pid = terminal.pane_pid(target)
    except Exception:
        pane_pid = None
    return discover_from_pane_pid(runtime, pane_pid, seat_name=seat_name, launch_id=launch_id)


def merge(record: dict, session: dict) -> dict:
    if not session:
        return record
    record = mark_binding(dict(record))
    session = mark_binding(dict(session))
    if is_bound_session(record) and not is_bound_session(session):
        protected = {
            key: record.get(key)
            for key in (
                "session_id",
                "runtime_session_id",
                "runtime_session_source",
                "runtime_session_binding",
                "runtime_session_bind_method",
                "runtime_session_bind_source",
                "runtime_session_bound_at",
                "runtime_session_confidence",
                "runtime_session_evidence",
                "runtime_session_env",
                "runtime_session_cwd",
                "runtime_session_created_at_ms",
                "runtime_session_updated_at_ms",
            )
            if record.get(key) is not None
        }
        return {**record, **{k: v for k, v in session.items() if k not in protected}, **protected}
    if not is_bound_session(session):
        diagnostics = {
            key: session.get(key)
            for key in (
                "runtime_session_source",
                "runtime_session_binding",
                "runtime_session_bind_method",
                "runtime_session_bind_source",
                "runtime_session_confidence",
                "runtime_session_evidence",
                "source_session_id",
                "runtime_session_diagnostics",
                "runtime_session_possible_matches",
                "runtime_session_cwd",
                "runtime_session_created_at_ms",
                "runtime_session_updated_at_ms",
                "runtime_session_pid",
            )
            if session.get(key) is not None
        }
        return {**record, **diagnostics}
    if (
        is_bound_session(record)
        and is_bound_session(session)
        and record.get("runtime_session_id") != session.get("runtime_session_id")
        and str(record.get("runtime_session_bind_source") or record.get("runtime_session_source") or "").startswith("codex-hook:")
        and (session.get("runtime_session_bind_source") or session.get("runtime_session_source")) == "argv:codex-resume"
    ):
        protected = {
            key: record.get(key)
            for key in (
                "session_id",
                "runtime_session_id",
                "runtime_session_source",
                "runtime_session_binding",
                "runtime_session_bind_method",
                "runtime_session_bind_source",
                "runtime_session_bound_at",
                "runtime_session_confidence",
                "runtime_session_evidence",
                "runtime_session_env",
                "runtime_session_cwd",
                "runtime_session_created_at_ms",
                "runtime_session_updated_at_ms",
            )
            if record.get(key) is not None
        }
        diagnostics = {
            "runtime_session_stale_process_evidence": {
                key: session.get(key)
                for key in (
                    "runtime_session_id",
                    "runtime_session_source",
                    "runtime_session_bind_source",
                    "runtime_session_evidence",
                    "runtime_session_pid",
                )
                if session.get(key) is not None
            }
        }
        return {**record, **{k: v for k, v in session.items() if k not in protected}, **diagnostics, **protected}
    merged = {**record, **session}
    if is_bound_session(session):
        merged["session_id"] = session["runtime_session_id"]
    return merged


def process_metadata(pid: int | None) -> dict:
    if not pid:
        return {}
    return {
        "runtime_process_pid": pid,
        "runtime_process_cwd": _process_cwd(pid),
        "runtime_process_started_at_epoch": _process_start_epoch(pid),
        "runtime_process_argv": _read_process_cmdline(pid),
    }


def _tmux_current_pane_pid() -> int | None:
    pane = os.environ.get("TMUX_PANE")
    if not pane:
        return None
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", pane, "#{pane_pid}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return int(result.stdout.strip())
    except (TypeError, ValueError):
        return None


def _tmux_current_fleet_seat() -> tuple[str | None, str | None]:
    pane = os.environ.get("TMUX_PANE")
    if not pane:
        return None, None
    result = subprocess.run(
        ["tmux", "display-message", "-p", "-t", pane, "#{session_name}\t#{window_name}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None, None
    parts = result.stdout.strip().split("\t", 1)
    if len(parts) != 2:
        return None, None
    return parts[0] or None, parts[1] or None


def resolve_current_process(runtime: str | None = None) -> dict:
    """Resolve the current process' runtime session id with evidence tiers.

    This is different from resolving another Aura seat. It should only be used
    when the caller asks for *this process/session*.
    """
    runtime = runtime or os.environ.get("AURA_RUNTIME") or ("codex" if os.environ.get("CODEX_THREAD_ID") else None)
    fleet, seat = _tmux_current_fleet_seat()
    pane_pid = _tmux_current_pane_pid()
    evidence: list[dict] = []

    for env_name in _current_process_session_env_names(runtime):
        env_value = os.environ.get(env_name)
        if env_value:
            evidence.append({
                "source": f"env:{env_name}",
                "session_id": env_value,
                "confidence": "exact",
                "reason": "current-process-env",
            })
            break

    pane_discovery = discover_from_pane_pid(runtime, pane_pid, seat_name=seat) if pane_pid else {}
    if pane_discovery.get("runtime_session_id"):
        evidence.append({
            "source": pane_discovery.get("runtime_session_source"),
            "session_id": pane_discovery.get("runtime_session_id"),
            "confidence": pane_discovery.get("runtime_session_confidence"),
            "reason": (pane_discovery.get("runtime_session_evidence") or {}).get("reason"),
            "details": pane_discovery.get("runtime_session_evidence"),
        })

    env_ids = [item for item in evidence if str(item.get("source") or "").startswith("env:")]
    if env_ids:
        selected = env_ids[0]
    elif evidence:
        selected = sorted(evidence, key=lambda item: {"exact": 4, "high": 3, "medium": 2, "low": 1}.get(item.get("confidence") or "", 0), reverse=True)[0]
    else:
        selected = {}

    agreement = sorted({item.get("session_id") for item in evidence if item.get("session_id")})
    mismatch = len(agreement) > 1
    cross_check = "mismatch" if mismatch else ("confirmed" if len(agreement) == 1 and len(evidence) > 1 else "single-source")
    return {
        "ok": bool(selected),
        "runtime": runtime,
        "session_id": selected.get("session_id"),
        "runtime_session_id": selected.get("session_id"),
        "runtime_session_source": selected.get("source"),
        "runtime_session_binding": "bound" if selected.get("session_id") else "unbound",
        "runtime_session_bind_method": binding_method_for_source(selected.get("source")),
        "runtime_session_bind_source": selected.get("source"),
        "runtime_session_confidence": selected.get("confidence"),
        "runtime_session_reason": selected.get("reason"),
        "cross_check": cross_check,
        "warning": "current-process-env-disagrees-with-pane-evidence" if mismatch else None,
        "fleet": fleet,
        "seat": seat,
        "pane": os.environ.get("TMUX_PANE"),
        "pane_pid": pane_pid,
        "cwd": os.getcwd(),
        "evidence": evidence,
        "mismatch": mismatch,
    }

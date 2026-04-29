"""Runtime session id discovery for terminal-backed seats."""

from __future__ import annotations

from pathlib import Path


RUNTIME_SESSION_ENV = {
    "codex": ("CODEX_THREAD_ID",),
    "claude-code": ("CLAUDE_SESSION_ID", "AURA_SESSION_ID"),
    "claude": ("CLAUDE_SESSION_ID", "AURA_SESSION_ID"),
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


def _session_env_names(runtime: str | None) -> tuple[str, ...]:
    names = RUNTIME_SESSION_ENV.get(runtime or "", ())
    return ("AURA_RUNTIME_SESSION_ID", "AURA_SESSION_ID", *names)


def discover_from_pane_pid(runtime: str | None, pane_pid: int | None) -> dict:
    if not pane_pid:
        return {}
    env_names = _session_env_names(runtime)
    for pid in _descendant_pids(int(pane_pid)):
        env = _read_process_environ(pid)
        for name in env_names:
            value = env.get(name)
            if value:
                return {
                    "runtime_session_id": value,
                    "runtime_session_env": name,
                    "runtime_session_pid": pid,
                }
    return {}


def discover_for_target(runtime: str | None, terminal, target: str | None) -> dict:
    if not target or not hasattr(terminal, "pane_pid"):
        return {}
    try:
        pane_pid = terminal.pane_pid(target)
    except Exception:
        pane_pid = None
    return discover_from_pane_pid(runtime, pane_pid)


def merge(record: dict, session: dict) -> dict:
    if not session:
        return record
    merged = {**record, **session}
    if session.get("runtime_session_id") and not merged.get("session_id"):
        merged["session_id"] = session["runtime_session_id"]
    return merged

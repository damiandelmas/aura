"""Durable event scheduler state helpers."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

from lib import state


DEFAULT_SCRIPT_TIMEOUT = 120


def pid_is_daemon(pid: int | None, job_id: str | None) -> bool:
    """Compute whether ``pid`` is a LIVE daemon process for ``job_id``.

    Two-laws read discipline: liveness is computed from the process, never
    trusted from the stored ``daemon`` record. A dead/reused pid that still
    sits in the record reads HISTORICAL, not running — closing the gap that let
    ``event status`` report ``daemon=yes`` over corpse pids. The /proc cmdline
    check guards against pid reuse (a recycled pid running something else).
    """
    if not isinstance(pid, int):
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        # ESRCH (gone) or EPERM (alive but not ours) — either way not our daemon.
        return False
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            cmdline = fh.read().decode("utf-8", "replace").replace("\x00", " ")
    except OSError:
        # Signalable but cmdline unreadable: assume alive rather than kill it.
        return True
    if "event daemon" not in cmdline:
        return False
    if job_id and str(job_id) not in cmdline:
        return False
    return True


def daemon_alive(job: dict) -> bool:
    """Computed liveness for a job's daemon (see pid_is_daemon)."""
    daemon = job.get("daemon")
    if not isinstance(daemon, dict):
        return False
    return pid_is_daemon(daemon.get("pid"), job.get("job_id"))


def supervisor_lock_path() -> Path:
    return events_root() / "supervisor.lock"


@contextmanager
def supervisor_lock():
    """Serialize ensure-daemons runs so two supervisors can't double-spawn."""
    path = supervisor_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def new_job_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%y%m%d_%H%M%S")
    return f"evt_{stamp}_{uuid.uuid4().hex[:8]}"


def events_root() -> Path:
    return state.state_root() / "events"


def jobs_root() -> Path:
    return events_root() / "jobs"


def names_root() -> Path:
    return events_root() / "names"


def job_dir(job_id: str) -> Path:
    return jobs_root() / job_id


def state_path(job_id: str) -> Path:
    return job_dir(job_id) / "state.json"


def events_path(job_id: str) -> Path:
    return job_dir(job_id) / "events.jsonl"


def name_path(name: str) -> Path:
    safe = name.replace("/", "_")
    return names_root() / f"{safe}.json"


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def append_event(job_id: str, event: dict) -> dict:
    record = {
        "schema": "aura.event.v1",
        "job_id": job_id,
        "at": now_iso(),
        **event,
    }
    path = events_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def load_state(job_id: str) -> dict:
    path = state_path(job_id)
    if not path.exists():
        raise FileNotFoundError(f"event job not found: {job_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(job: dict) -> dict:
    job["updated_at"] = now_iso()
    atomic_write_json(state_path(job["job_id"]), job)
    return job


def index_name(name: str, job_id: str) -> None:
    atomic_write_json(name_path(name), {"schema": "aura.event.name.v1", "name": name, "job_id": job_id})


def remove_name(name: str) -> bool:
    path = name_path(name)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def resolve_job_id(ref: str) -> str:
    direct = state_path(ref)
    if direct.exists():
        return ref
    index = name_path(ref)
    if index.exists():
        data = json.loads(index.read_text(encoding="utf-8"))
        return data["job_id"]
    raise FileNotFoundError(f"event job not found: {ref}")


def iter_jobs() -> list[dict]:
    root = jobs_root()
    if not root.exists():
        return []
    jobs = []
    for path in sorted(root.glob("*/state.json")):
        try:
            jobs.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return jobs


def render_template(template: str, job: dict, tick: int, run_id: str) -> str:
    ticks = job.get("ticks")
    return template.format(
        job_id=job.get("job_id"),
        name=job.get("name") or "",
        tick=tick,
        ticks=ticks if ticks is not None else "",
        run_id=run_id,
        target=job.get("target"),
        sender=job.get("sender"),
    )


def scripts_root() -> Path:
    """Trusted root for ``no_agent`` event scripts.

    Override with ``AURA_EVENT_SCRIPTS_DIR``; defaults to ``<state>/event-scripts``.
    A script must resolve INSIDE this root — the same traversal guard the Hermes
    cron scheduler used, ported so an event job cannot run an arbitrary path.
    """
    override = os.environ.get("AURA_EVENT_SCRIPTS_DIR")
    if override:
        return Path(override).expanduser()
    return state.state_root() / "event-scripts"


def run_script(script_path: str, timeout: int = DEFAULT_SCRIPT_TIMEOUT) -> tuple[bool, str]:
    """Run a ``no_agent`` event script and capture stdout.

    Returns ``(success, output)``. On failure ``output`` carries the error so the
    caller can deliver it as an alert. ``.sh``/``.bash`` run under bash; everything
    else under the current Python interpreter. The script MUST live within
    ``scripts_root()`` — absolute and relative paths alike are resolved and
    validated against it (no traversal, no symlink escape).
    """
    root = scripts_root()
    root.mkdir(parents=True, exist_ok=True)
    root_resolved = root.resolve()

    raw = Path(script_path).expanduser()
    path = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    try:
        path.relative_to(root_resolved)
    except ValueError:
        return False, f"blocked: script resolves outside event-scripts dir ({root_resolved}): {script_path!r}"
    if not path.is_file():
        return False, f"script not found: {path}"

    suffix = path.suffix.lower()
    if suffix in {".sh", ".bash"}:
        bash = shutil.which("bash") or ("/bin/bash" if os.path.isfile("/bin/bash") else None)
        if not bash:
            return False, f"cannot run {path.name!r}: bash not found on PATH"
        argv = [bash, str(path)]
    else:
        argv = [sys.executable, str(path)]

    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(path.parent),
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired:
        return False, f"script timed out after {timeout}s: {path}"
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"script execution failed: {exc}"

    out = (result.stdout or "").strip()
    err = (result.stderr or "").strip()
    if result.returncode != 0:
        parts = [f"script exited with code {result.returncode}"]
        if err:
            parts.append(f"stderr:\n{err}")
        if out:
            parts.append(f"stdout:\n{out}")
        return False, "\n".join(parts)
    return True, out

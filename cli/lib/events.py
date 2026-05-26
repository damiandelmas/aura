"""Durable event scheduler state helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import uuid

from lib import state


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

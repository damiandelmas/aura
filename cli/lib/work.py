"""Work-claim pool — a flat task store and a dumb dispatcher.

A claim-queue, NOT a scheduler. The dispatcher's only state is one task -> seat map,
kept in an append-only snapshot log per queue (last write per ``task_id`` wins).

"Idle" comes from the idle-watcher's reports on the bus (sensed, not signed). A
fresh idle report for an assigned seat, dated after its assignment, RELEASES the
task — the seat is free again. Idle proves *freeness*, NOT *success*: a seat also
goes idle when it errors to a prompt, asks a question, or crashes to the shell. So a
released task is "turn ended, outcome unverified", never ``done``. Promotion to
done/failed is a receipt the worker writes or a separate verify pass — never
inferred from silence. A lease that elapses with no idle at all (a hung/dead worker
that never finished its turn) requeues. First outcome wins; ``task_id`` is the only
dedup key, held in the one map.

Boundary: single dispatcher, FIFO, no bin-packing, no autoscale. The moment this
grows resource-aware placement or a second control loop it has become the trunk
Aura refuses.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Callable
import uuid

from lib import idle_watcher, placements, reports, state


# pending -> assigned -> released (turn ended, outcome unverified).
# done/failed are reserved for a receipt/verify pass that promotes a released task;
# the pool itself never infers success from silence.
TASK_STATES = {"pending", "assigned", "released", "done", "failed"}
DISPATCH_SENDER = "work-dispatcher"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_epoch() -> float:
    return datetime.now(timezone.utc).timestamp()


def new_task_id() -> str:
    return f"task_{uuid.uuid4().hex[:12]}"


def work_root() -> Path:
    return state.state_root() / "work"


def queue_dir(queue: str) -> Path:
    return work_root() / str(queue).replace("/", "_")


def tasks_path(queue: str) -> Path:
    return queue_dir(queue) / "tasks.jsonl"


def append_task(queue: str, record: dict[str, Any]) -> dict[str, Any]:
    path = tasks_path(queue)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True))
        f.write("\n")
    return record


def fold_tasks(queue: str) -> dict[str, dict[str, Any]]:
    """Fold the append-only log to current state: last snapshot per task_id wins."""
    path = tasks_path(queue)
    if not path.exists():
        return {}
    folded: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = row.get("task_id")
            if tid:
                folded[tid] = row
    return folded


def list_tasks(queue: str, *, state_filter: str | None = None) -> list[dict[str, Any]]:
    rows = sorted(fold_tasks(queue).values(), key=lambda r: r.get("created_at") or "")
    if state_filter:
        rows = [r for r in rows if r.get("state") == state_filter]
    return rows


def submit(queue: str, body: str) -> dict[str, Any]:
    stamp = now_iso()
    return append_task(queue, {
        "schema": "aura.work.task.v1",
        "task_id": new_task_id(),
        "queue": queue,
        "body": body,
        "state": "pending",
        "seat": None,
        "assigned_at": None,
        "lease_until": None,
        "attempts": 0,
        "created_at": stamp,
        "updated_at": stamp,
    })


def update_task(queue: str, task: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return append_task(queue, {**task, **changes, "updated_at": now_iso()})


def pool_member_refs(placement_name: str) -> set[str]:
    record = placements.get_placement(placement_name)
    if not record:
        return set()
    return {m.get("seat_ref") for m in record.get("members", []) if m.get("seat_ref")}


def idle_reports_map() -> dict[str, str]:
    """seat_ref -> latest idle-watcher report timestamp (iso)."""
    out: dict[str, str] = {}
    for row in reports.iter_reports():
        if row.get("source") != idle_watcher.IDLE_SOURCE:
            continue
        ref = row.get("seat_ref")
        if not ref and row.get("seat"):
            ref = f"{row.get('fleet')}:{row.get('seat')}" if row.get("fleet") else row.get("seat")
        if not ref:
            continue
        ts = row.get("timestamp") or ""
        if ref not in out or ts > out[ref]:
            out[ref] = ts
    return out


def plan_dispatch(tasks: dict[str, dict[str, Any]], idle_map: dict[str, str], *, now_epoch_value: float) -> dict[str, list]:
    """Decide actions from current state. Pure — no I/O.

    release : an assigned task whose seat reported idle AFTER assignment -> the seat
              finished its turn and is free. The task is released (outcome
              unverified), NOT marked done — idle proves freeness, not success.
    requeue : an assigned task past its lease with no idle (a hung/dead worker that
              never finished its turn) -> back to pending.
    assign  : a pending task -> an idle seat not currently occupied (FIFO).
    """
    release: list[str] = []
    requeue: list[str] = []
    assign: list[tuple[str, str]] = []

    assigned_by_seat: dict[str, dict[str, Any]] = {}
    pending: list[dict[str, Any]] = []
    for task in tasks.values():
        if task.get("state") == "assigned":
            assigned_by_seat[task.get("seat")] = task
        elif task.get("state") == "pending":
            pending.append(task)

    for seat, task in list(assigned_by_seat.items()):
        idle_ts = idle_map.get(seat)
        assigned_at = task.get("assigned_at")
        if idle_ts and assigned_at and idle_ts > assigned_at:
            release.append(task["task_id"])
            assigned_by_seat.pop(seat, None)
        elif task.get("lease_until") is not None and now_epoch_value > float(task["lease_until"]):
            requeue.append(task["task_id"])
            assigned_by_seat.pop(seat, None)

    busy_seats = set(assigned_by_seat.keys())
    idle_seats = [ref for ref in sorted(idle_map.keys()) if ref not in busy_seats]
    for task in sorted(pending, key=lambda t: t.get("created_at") or ""):
        if not idle_seats:
            break
        seat = idle_seats.pop(0)
        assign.append((task["task_id"], seat))
    return {"release": release, "requeue": requeue, "assign": assign}


def _aura_bin() -> str:
    return os.environ.get("AURA_BIN") or str(Path(__file__).resolve().parents[1] / "aura")


def _send_task(seat_ref: str, body: str) -> dict[str, Any]:
    cmd = [_aura_bin(), "send", seat_ref, body, "--as-service", DISPATCH_SENDER]
    try:
        proc = subprocess.run(
            cmd, text=True, capture_output=True, timeout=60,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "error": str(exc)}
    ok = proc.returncode == 0
    try:
        parsed = json.loads(proc.stdout)
        if isinstance(parsed, dict):
            ok = ok and parsed.get("ok", ok) and not parsed.get("error")
    except Exception:
        pass
    return {"ok": bool(ok), "stdout": (proc.stdout or "")[-500:], "error": (proc.stderr or "")[-500:] if not ok else None}


def dispatch_tick(
    queue: str,
    placement: str,
    *,
    lease_seconds: float = 300.0,
    send_fn: Callable[[str, str], dict[str, Any]] | None = None,
    idle_map: dict[str, str] | None = None,
    now_epoch_value: float | None = None,
) -> dict[str, Any]:
    send_fn = send_fn or _send_task
    now_e = now_epoch() if now_epoch_value is None else now_epoch_value

    tasks = fold_tasks(queue)
    members = pool_member_refs(placement)
    raw_idle = idle_reports_map() if idle_map is None else idle_map
    scoped_idle = {ref: ts for ref, ts in raw_idle.items() if not members or ref in members}

    plan = plan_dispatch(tasks, scoped_idle, now_epoch_value=now_e)
    results: dict[str, Any] = {"released": [], "requeued": [], "assigned": [], "assign_failed": []}

    for tid in plan["release"]:
        # idle proves the seat is free, NOT that the task succeeded -> released,
        # never done. A receipt/verify pass promotes released -> done|failed.
        update_task(queue, tasks[tid], state="released", lease_until=None)
        results["released"].append(tid)
    for tid in plan["requeue"]:
        task = tasks[tid]
        update_task(queue, task, state="pending", seat=None, assigned_at=None,
                    lease_until=None, attempts=int(task.get("attempts", 0)) + 1)
        results["requeued"].append(tid)
    for tid, seat in plan["assign"]:
        task = tasks[tid]
        sent = send_fn(seat, task["body"])
        if sent.get("ok"):
            update_task(queue, task, state="assigned", seat=seat,
                        assigned_at=now_iso(), lease_until=now_e + float(lease_seconds))
            results["assigned"].append({"task": tid, "seat": seat})
        else:
            results["assign_failed"].append({"task": tid, "seat": seat, "error": sent.get("error")})

    return {"ok": True, "queue": queue, "placement": placement, **results}

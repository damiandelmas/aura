"""Create, inspect, and spawn package-native Aura agents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib import agent_history, agent_packages


def _profile_name(ref: str | None) -> str | None:
    if not ref:
        return None
    return ref.split("/", 1)[1] if "/" in ref else ref


def _resume_session(record: dict, args) -> str | None:
    requested = getattr(args, "resume_session", None)
    fresh = bool(getattr(args, "fresh", False))
    if fresh and requested:
        raise ValueError("use either --fresh or --resume-session, not both")
    if fresh:
        return None
    if not requested:
        requested = (record.get("resume") or {}).get("default")
    if not requested:
        return None
    if str(requested).strip().lower() not in {"latest", "last"}:
        return requested
    from lib import registry
    from lib import runtime_session

    agent_id = record.get("agent_id")
    runtime = record.get("runtime")
    candidates = []
    for row in registry.read_registry().values():
        if row.get("agent_package_id") != agent_id:
            continue
        if runtime and row.get("runtime") and row.get("runtime") != runtime:
            continue
        if not runtime_session.is_bound_session(row):
            continue
        session_id = row.get("runtime_session_id") or row.get("session_id")
        if session_id:
            candidates.append((_session_sort_key(row), session_id))
    if not candidates:
        raise FileNotFoundError(f"agent package has no latest runtime session in registry: {agent_id}")
    return str(sorted(candidates, key=lambda item: item[0])[-1][1])


def _session_sort_key(row: dict) -> tuple[int, float | str]:
    value = row.get("runtime_session_updated_at_ms")
    if value is not None:
        try:
            return (3, float(value))
        except (TypeError, ValueError):
            return (2, str(value))
    for key in ("updated_at", "registered_at"):
        value = row.get(key)
        if value is not None:
            return (1, str(value))
    return (0, "")


def _spawn_args(record: dict, args) -> argparse.Namespace:
    runtime = record["runtime"]
    profile = _profile_name(record.get("profile"))
    cwd = getattr(args, "cwd", None) or record["cwd"]
    fleet = getattr(args, "fleet", None) or record["fleet"]
    seat = getattr(args, "seat", None) or record["seat"]
    return argparse.Namespace(
        name=seat,
        manifest=None,
        role_home=None,
        fleet=fleet,
        fleet_id=None,
        knowledge=None,
        memory=None,
        resume_session=_resume_session(record, args),
        fork_session=None,
        identity_provider="aura-agent",
        identity_id=record["agent_id"],
        identity_label=record.get("address") or record.get("alias") or record["agent_id"],
        at=None,
        slice=None,
        prompt=getattr(args, "prompt", None),
        work=None,
        cwd=cwd,
        context=None,
        wait=getattr(args, "wait", False),
        timeout=getattr(args, "timeout", 30),
        model=getattr(args, "model", None),
        as_pane=getattr(args, "as_pane", False),
        silent=False,
        clone=False,
        runtime=runtime,
        profile=None,
        runtime_profile=record.get("profile"),
        boxed=runtime == "codex",
        omx_profile=None,
        launch_command=None,
        _agent_package={
            "agent_id": record["agent_id"],
            "address": record.get("address"),
            "alias": record.get("alias"),
            "root": record["root"],
        },
    )


def run(args):
    action = getattr(args, "agent_action", None)
    if action == "create":
        try:
            return agent_packages.create(
                address=args.address,
                runtime=args.runtime,
                profile=args.profile,
                cwd=args.cwd or str(Path.cwd()),
                fleet=args.fleet,
                seat=args.seat,
                alias=args.alias,
            )
        except Exception as exc:
            return {"ok": False, "error": "agent-create-failed", "detail": str(exc)}
    if action == "adopt-root":
        try:
            return agent_packages.adopt_root(
                root=args.root,
                address=args.address,
                alias=args.alias,
                agent_id=args.agent_id,
            )
        except Exception as exc:
            return {"ok": False, "error": "agent-adopt-root-failed", "detail": str(exc)}
    if action == "clone":
        try:
            return agent_packages.clone(
                args.ref,
                address=args.address,
                alias=args.alias,
                cwd=args.cwd,
                fleet=args.fleet,
                seat=args.seat,
            )
        except Exception as exc:
            return {"ok": False, "error": "agent-clone-failed", "detail": str(exc), "ref": args.ref}
    if action == "promote-seat":
        try:
            return agent_packages.promote_seat(
                args.target,
                address=args.address,
                alias=args.alias,
            )
        except Exception as exc:
            return {"ok": False, "error": "agent-promote-seat-failed", "detail": str(exc), "target": args.target}
    if action == "rename":
        try:
            return agent_packages.rename(
                args.ref,
                address=args.address,
                alias=args.alias,
                fleet=args.fleet,
                seat=args.seat,
            )
        except Exception as exc:
            return {"ok": False, "error": "agent-rename-failed", "detail": str(exc), "ref": args.ref}
    if action == "hooks":
        try:
            return agent_packages.hooks(args.ref, repair=args.repair)
        except Exception as exc:
            return {"ok": False, "error": "agent-hooks-failed", "detail": str(exc), "ref": args.ref}
    if action == "inspect":
        try:
            return agent_packages.inspect(args.ref)
        except Exception as exc:
            return {"ok": False, "error": "agent-inspect-failed", "detail": str(exc), "ref": args.ref}
    if action == "census":
        try:
            return agent_packages.census()
        except Exception as exc:
            return {"ok": False, "error": "agent-census-failed", "detail": str(exc)}
    if action == "history":
        try:
            if getattr(args, "write", False):
                path = agent_history.write(args.ref)
                history = json.loads(path.read_text(encoding="utf-8"))
                return {"ok": True, "path": str(path), "history": history}
            return {"ok": True, "history": agent_history.build(args.ref)}
        except Exception as exc:
            return {"ok": False, "error": "agent-history-failed", "detail": str(exc), "ref": args.ref}
    if action == "spawn":
        try:
            record = agent_packages.resolve(args.ref)
        except Exception as exc:
            return {"ok": False, "error": "agent-resolve-failed", "detail": str(exc), "ref": args.ref}
        from commands import spawn

        try:
            spawn_args = _spawn_args(record, args)
        except Exception as exc:
            return {"ok": False, "error": "agent-spawn-args-failed", "detail": str(exc), "ref": args.ref}
        result = spawn.run(spawn_args)
        if isinstance(result, dict) and result.get("ok"):
            result["agent_package_id"] = record["agent_id"]
            if record.get("address"):
                result["agent_package_address"] = record.get("address")
            result["agent_package_root"] = record["root"]
        return result
    return {"ok": False, "error": f"unknown agent action: {action}"}

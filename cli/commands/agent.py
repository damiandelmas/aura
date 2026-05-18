"""Create, inspect, and spawn package-native Aura agents."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib import agent_packages


def _profile_name(ref: str | None) -> str | None:
    if not ref:
        return None
    return ref.split("/", 1)[1] if "/" in ref else ref


def _resume_session(record: dict, args) -> str | None:
    requested = getattr(args, "resume_session", None)
    if not requested:
        return None
    if str(requested).strip().lower() not in {"latest", "last"}:
        return requested
    path = Path(record["root"]) / "runtime-session.json"
    if not path.exists():
        raise FileNotFoundError(f"agent package has no runtime-session.json: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    session_id = payload.get("runtime_session_id") or payload.get("session_id")
    if not session_id:
        raise ValueError(f"runtime-session.json has no session id: {path}")
    return str(session_id)


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
        identity_label=record["address"],
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
            "address": record["address"],
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
    if action == "inspect":
        try:
            return agent_packages.inspect(args.ref)
        except Exception as exc:
            return {"ok": False, "error": "agent-inspect-failed", "detail": str(exc), "ref": args.ref}
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
            agent_packages.append_spawn_history(
                record["agent_id"],
                {
                    "fleet": result.get("fleet"),
                    "seat": result.get("name"),
                    "runtime": result.get("runtime"),
                    "cwd": result.get("cwd") or result.get("workdir"),
                    "aura_launch_id": result.get("aura_launch_id"),
                    "seat_instance_id": result.get("seat_instance_id"),
                    "runtime_capsule_ref": result.get("runtime_capsule_ref"),
                },
            )
            result["agent_package_id"] = record["agent_id"]
            result["agent_package_address"] = record["address"]
            result["agent_package_root"] = record["root"]
        return result
    return {"ok": False, "error": f"unknown agent action: {action}"}

"""Operator CLI for the Aura event sidecar adapter."""

from __future__ import annotations

import json


def _json_arg(value: str | None) -> dict:
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("payload-json must decode to an object")
    return parsed


def run(args):
    from lib import event_sidecar, registry

    action = args.clawhip_action
    if action == "status":
        return event_sidecar.status()
    if action == "verify-bindings":
        return event_sidecar.verify_bindings(getattr(args, "scope", None))
    if action == "emit":
        return event_sidecar.emit_event(args.kind, _json_arg(getattr(args, "payload_json", None)))
    if action == "deliver":
        return event_sidecar.deliver_human_message(args.source, args.message, channel=getattr(args, "channel", None))
    if action == "register-seat":
        agent = registry.get_agent(args.seat)
        if not agent:
            return {"ok": False, "error": f"unknown seat: {args.seat}"}
        runtime = {
            "runtime": agent.get("runtime"),
            "runtime_session_id": agent.get("runtime_session_id"),
            "session_ref": agent.get("session_id"),
        }
        return event_sidecar.register_runtime(agent, runtime, channel=getattr(args, "channel", None))
    return {"ok": False, "error": f"unknown clawhip action: {action}"}

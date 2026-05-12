"""Evaluate or execute bounded seat-to-seat routing."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from commands import send, watch
from lib import delivery, registry, state


DEFAULT_POLICY = {
    "rules": [
        {
            "when": {"source_state": "done", "target_state": "ready"},
            "action": "send",
            "template": "Review output from {source_seat}.",
        }
    ]
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _route_dir(fleet: str) -> Path:
    return state.fleet_dir(fleet) / "route"


def _events_path(fleet: str) -> Path:
    return _route_dir(fleet) / "events.jsonl"


def _append_event(fleet: str, record: dict) -> dict:
    base = _route_dir(fleet)
    base.mkdir(parents=True, exist_ok=True)
    with _events_path(fleet).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def _load_policy(path: str | None) -> dict:
    if not path:
        return DEFAULT_POLICY
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("route policy must be a JSON object")
    rules = data.get("rules")
    if not isinstance(rules, list):
        raise ValueError("route policy must contain a rules list")
    return data


def _sample_state(sample: dict) -> str:
    sense_record = sample.get("sense") or {}
    return sense_record.get("state") or "unknown"


def _sample_seat(sample: dict) -> str:
    return sample.get("seat") or sample.get("name") or ""


def _matches(rule: dict, source: dict, target: dict) -> bool:
    when = rule.get("when") or {}
    source_state = when.get("source_state")
    target_state = when.get("target_state")
    if source_state and _sample_state(source) != source_state:
        return False
    if target_state and _sample_state(target) != target_state:
        return False
    return True


def _dedupe_key(fleet: str, source_seat: str, target_seat: str, action: str, message: str) -> str:
    raw = f"{fleet}|{source_seat}|{target_seat}|{action}|{message}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"route:{fleet}:{source_seat}:{target_seat}:{action}:{digest}"


def _render_template(template: str, *, fleet: str, source: dict, target: dict) -> str:
    return template.format(
        fleet=fleet,
        source_seat=_sample_seat(source),
        target_seat=_sample_seat(target),
        source_state=_sample_state(source),
        target_state=_sample_state(target),
    )


def evaluate(fleet: str, observation: dict, policy: dict, max_actions: int) -> list[dict]:
    samples = [sample for sample in observation.get("samples", []) if sample.get("ok")]
    actions = []
    for rule in policy.get("rules", []):
        action_type = rule.get("action", "send")
        if action_type != "send":
            actions.append({
                "action": action_type,
                "fleet": fleet,
                "status": "blocked",
                "reason": f"unsupported route action: {action_type}",
            })
            continue

        template = rule.get("template") or "Review output from {source_seat}."
        explicit_target = rule.get("target")
        for source_sample in samples:
            for target_sample in samples:
                source_seat = _sample_seat(source_sample)
                target_seat = _sample_seat(target_sample)
                if not source_seat or not target_seat or source_seat == target_seat:
                    continue
                if explicit_target and target_seat != explicit_target:
                    continue
                if not _matches(rule, source_sample, target_sample):
                    continue
                message = _render_template(template, fleet=fleet, source=source_sample, target=target_sample)
                actions.append({
                    "action": "send",
                    "source_seat": source_seat,
                    "target_seat": target_seat,
                    "fleet": fleet,
                    "message": message,
                    "reason": f"{source_seat} is {_sample_state(source_sample)} and {target_seat} is {_sample_state(target_sample)}",
                    "dedupe_key": _dedupe_key(fleet, source_seat, target_seat, "send", message),
                    "status": "proposed",
                })
                if len(actions) >= max_actions:
                    return actions
    return actions


def _execute_action(action: dict) -> dict:
    target = action.get("target_seat")
    if not target:
        return {**action, "status": "blocked", "reason": "missing target_seat"}

    if not registry.get_agent(target, fleet=action.get("fleet")):
        return {**action, "status": "blocked", "reason": "target is not registered in fleet"}

    previous = delivery.has_successful_dedupe(target, action["dedupe_key"])
    if previous:
        return {**action, "status": "skipped_duplicate", "previous_message_id": previous}

    send_args = argparse.Namespace(
        target=target,
        message=action.get("message", ""),
        sender=None,
        service_sender="aura-route",
        mode=None,
        nudge=False,
        transport="tmux",
        dedupe_key=action["dedupe_key"],
        force=False,
        allow_hidden=False,
        defer_if_busy=False,
        defer_ttl="15m",
        defer_retry_every="15s",
        no_deferred_daemon=False,
    )
    result = send.run(send_args)
    if result.get("skipped"):
        return {**action, "status": "skipped_duplicate", "send": result}
    if result.get("deferred"):
        return {**action, "status": "deferred", "send": result, "reason": result.get("reason")}
    if not result.get("ok"):
        return {**action, "status": "blocked", "send": result, "reason": result.get("error", "send failed")}
    return {**action, "status": "sent", "send": result}


def run(args):
    fleet = getattr(args, "fleet", None)
    if not fleet:
        return {"ok": False, "error": "route requires --fleet"}

    requested_max = getattr(args, "max_actions", None)
    live_send = bool(getattr(args, "send", False))
    if live_send and requested_max is None:
        return {"ok": False, "error": "route --send requires explicit --max-actions > 0", "fleet": fleet}

    max_actions = int(requested_max if requested_max is not None else 10)
    if max_actions <= 0:
        return {"ok": False, "error": "route requires --max-actions > 0", "fleet": fleet}

    policy = _load_policy(getattr(args, "policy", None))

    observation_args = argparse.Namespace(
        fleet=fleet,
        once=True,
        iterations=None,
        lines=getattr(args, "lines", 80),
        interval=0,
        no_sense=False,
        sense=True,
        question=None,
        features=None,
    )
    observation = watch.sample_fleet(observation_args)
    actions = evaluate(fleet, observation, policy, max_actions=max_actions)

    route_id = f"route_{_now().replace(':', '').replace('-', '').replace('.', '')}_{fleet}"
    response = {
        "ok": True,
        "schema": "aura.route.v1",
        "type": "route",
        "route_id": route_id,
        "fleet": fleet,
        "at": _now(),
        "dry_run": not live_send,
        "max_actions": max_actions,
        "observation": {
            "watch_id": observation.get("watch_id"),
            "at": observation.get("at"),
            "count": observation.get("count", 0),
            "summary": observation.get("summary", {}),
        },
        "actions": actions,
    }

    try:
        _append_event(fleet, response)
    except OSError as exc:
        if live_send:
            return {"ok": False, "error": f"route persistence failed before send: {exc}", "fleet": fleet}
        response["persistence_error"] = str(exc)
        return response

    if live_send:
        executed = []
        for action in actions[:max_actions]:
            executed.append(_execute_action(action))
        response["actions"] = executed
        response["sent"] = sum(1 for action in executed if action.get("status") == "sent")
        response["deferred"] = sum(1 for action in executed if action.get("status") == "deferred")
        response["skipped_duplicate"] = sum(1 for action in executed if action.get("status") == "skipped_duplicate")
        _append_event(fleet, {**response, "event": "route_execution"})

    return response

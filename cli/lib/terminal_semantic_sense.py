"""LLM-backed terminal sense for Aura seats."""

from __future__ import annotations

import json
import re
from typing import Any

from lib import local_llm, sense_contracts, terminal_perception


ALLOWED_STATES = {"ready", "busy", "stuck", "done", "needs_human", "error", "unknown"}
ALLOWED_ACTIONS = {"send", "wait", "capture", "inspect", "escalate"}
ACTION_BY_STATE = {
    "ready": "send",
    "busy": "wait",
    "stuck": "inspect",
    "done": "capture",
    "needs_human": "escalate",
    "error": "escalate",
    "unknown": "inspect",
}
MAX_TERMINAL_CHARS = 12000


SYSTEM_PROMPT = """You are Aura terminal sense.

Read a terminal capture from a tmux-backed AI seat. Return exactly one JSON
object and no prose. Infer what the seat is doing now and what Aura should do
next.

Allowed state values:
ready, busy, stuck, done, needs_human, error, unknown

Allowed next_action values:
send, wait, capture, inspect, escalate

Use "ready" only when the seat is clearly waiting for input.
Use "done" only when work is complete and output should be captured/reviewed.
Use "needs_human" when an approval, permission, trust prompt, or operator choice
is blocking progress.
Use "stuck" when output suggests no useful progress or repeated waiting.
Use "busy" when work is actively running or likely still thinking.

Schema:
{
  "state": "ready|busy|stuck|done|needs_human|error|unknown",
  "confidence": 0.0,
  "summary": "one short sentence",
  "next_action": "send|wait|capture|inspect|escalate",
  "evidence": ["short quoted or paraphrased evidence"],
  "role": null,
  "current_task": null,
  "last_meaningful_event": null,
  "blockers": [],
  "features": {},
  "contract_result": {}
}

If a custom contract is provided, fill `contract_result` exactly with the
requested contract fields. Do not invent fields outside the contract.
"""


def perceive_terminal(
    capture: dict[str, Any],
    request: dict[str, Any] | None = None,
    watch: dict[str, Any] | None = None,
    *,
    model: str = local_llm.DEFAULT_OLLAMA_MODEL,
    host: str = local_llm.DEFAULT_OLLAMA_HOST,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Return structured semantic terminal sense from a local LLM."""
    request = request or {}
    output = terminal_perception.normalize_output(capture.get("output", ""))
    output = _tail_text(output, MAX_TERMINAL_CHARS)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": _user_prompt(capture, request, watch, output)},
    ]
    text = local_llm.ollama_chat(messages, model=model, host=host, timeout=timeout)
    parsed = _extract_json_object(text)
    return _coerce_result(parsed, request.get("features"), request.get("contract"))


def _tail_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _user_prompt(
    capture: dict[str, Any],
    request: dict[str, Any],
    watch: dict[str, Any] | None,
    output: str,
) -> str:
    context = {
        "question": request.get("question") or "What is this seat doing and what should Aura do next?",
        "requested_features": request.get("features") or [],
        "custom_contract": request.get("contract_prompt") or sense_contracts.prompt_contract(request.get("contract")),
        "mechanical_status": capture.get("mechanical_status") or capture.get("status") or "unknown",
        "terminal": capture.get("terminal") or "missing",
        "watch": watch or None,
    }
    return (
        "Context JSON:\n"
        f"{json.dumps(context, indent=2, sort_keys=True)}\n\n"
        "Terminal capture:\n"
        "```text\n"
        f"{output}\n"
        "```"
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
        stripped = stripped.strip()
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end <= start:
            raise RuntimeError("llm sense response did not contain a JSON object")
        value = json.loads(stripped[start:end + 1])
    if not isinstance(value, dict):
        raise RuntimeError("llm sense response was not a JSON object")
    return value


def _coerce_result(value: dict[str, Any], requested_features: Any, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    state = str(value.get("state") or "unknown").strip().lower()
    if state not in ALLOWED_STATES:
        state = "unknown"

    next_action = str(value.get("next_action") or _default_action(state)).strip().lower()
    if next_action not in ALLOWED_ACTIONS:
        next_action = _default_action(state)
    elif not _action_matches_state(state, next_action):
        next_action = _default_action(state)

    try:
        confidence = float(value.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    evidence = value.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    elif not isinstance(evidence, list):
        evidence = []
    evidence = [str(item)[:240] for item in evidence[:8] if item is not None]

    blockers = value.get("blockers", [])
    if isinstance(blockers, str):
        blockers = [blockers]
    elif not isinstance(blockers, list):
        blockers = []

    features = value.get("features", {})
    if not isinstance(features, dict):
        features = {}
    requested = terminal_perception.normalize_feature_names(requested_features)
    for key in requested:
        features.setdefault(key, None)

    contract_payload = value.get("contract_result")
    if contract_payload is None:
        contract_payload = {
            key: value.get(key)
            for key in (contract or {}).get("fields", {})
            if key in value
        }
    contract_result = sense_contracts.coerce_contract_result(contract, contract_payload)

    result = {
        "state": state,
        "confidence": confidence,
        "summary": str(value.get("summary") or "").strip()[:500],
        "evidence": evidence,
        "next_action": next_action,
        "features": features,
        "role": _nullable_string(value.get("role")),
        "current_task": _nullable_string(value.get("current_task")),
        "last_meaningful_event": _nullable_string(value.get("last_meaningful_event")),
        "blockers": [str(item)[:200] for item in blockers[:8] if item is not None],
    }
    if contract_result is not None:
        result["contract_result"] = contract_result
    return result


def _nullable_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _default_action(state: str) -> str:
    return ACTION_BY_STATE.get(state, "inspect")


def _action_matches_state(state: str, action: str) -> bool:
    if state == "unknown":
        return action in {"inspect", "wait"}
    return action == _default_action(state)

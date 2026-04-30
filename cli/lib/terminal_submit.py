"""Submit verification helpers for terminal-backed seats."""

from __future__ import annotations


def _marker_indexes(capture: list[str]) -> dict[str, int]:
    indexes = {
        "busy": -1,
        "idle": -1,
        "pasted": -1,
        "active_input": -1,
    }
    busy_markers = (
        "working (",
        "esc to interrupt",
        "running tool",
        "running command",
        "thinking",
    )
    idle_markers = (
        "›",
        "❯",
    )
    idle_prompt_text = {
        "explain this codebase",
        "ready for input",
    }
    for idx, raw in enumerate(capture or []):
        line = str(raw)
        lower = line.lower()
        stripped = line.strip()
        lower_stripped = stripped.lower()
        if lower_stripped.startswith(("› [pasted content", "> [pasted content")):
            indexes["pasted"] = idx
            continue
        if any(marker in lower for marker in busy_markers):
            indexes["busy"] = idx
        prompt_text = None
        if stripped.startswith("› "):
            prompt_text = stripped[1:].strip()
        elif stripped.startswith("❯ "):
            prompt_text = stripped[1:].strip()

        if prompt_text is not None:
            if prompt_text.lower() in idle_prompt_text:
                indexes["idle"] = idx
            else:
                indexes["active_input"] = idx
            continue

        if stripped in idle_markers or lower.rstrip().endswith("$"):
            indexes["idle"] = idx
    return indexes


def needs_submit_retry(capture: list[str]) -> bool:
    """Detect terminal states where a pasted prompt is queued but unsubmitted."""
    lines = [str(line).lower() for line in (capture or [])]
    joined = "\n".join(lines)
    queued_markers = (
        "messages to be submitted after next tool call",
        "press enter to submit",
        "enter to submit",
    )
    if any(marker in joined for marker in queued_markers):
        return True

    indexes = _marker_indexes(capture)
    return indexes["pasted"] > max(indexes["busy"], indexes["idle"])


def has_active_composer_input(capture: list[str]) -> bool:
    """Detect a non-empty interactive prompt that Aura should not overwrite.

    Codex panes render the empty composer with placeholder text such as
    "Explain this codebase". Real typed text also appears after the prompt
    marker, so delivery must treat it as queued input instead of assuming the
    seat is idle.
    """
    indexes = _marker_indexes(capture)
    return indexes["active_input"] > max(indexes["busy"], indexes["idle"], indexes["pasted"])


def is_busy(capture: list[str]) -> bool:
    """Detect terminal states where the runtime is already processing work."""
    indexes = _marker_indexes(capture)
    return indexes["busy"] > indexes["idle"]


def has_message_marker(capture: list[str], message_id: str | None) -> bool:
    """Return true when the submitted Aura message id is visible in pane output."""
    if not message_id:
        return False
    return any(message_id in str(line) for line in (capture or []))


def submission_evidence(capture: list[str], message_id: str | None = None) -> tuple[bool, str]:
    """Classify whether a post-submit capture proves the input was entered.

    Absence of queued pasted text is not enough when we know the Aura message id.
    A verified semantic send needs either the message id visible in the pane or a
    fresh working marker after the prompt, which means Enter reached the runtime.
    """
    if needs_submit_retry(capture):
        return False, "queued-input"
    if has_message_marker(capture, message_id):
        return True, "message-id-visible"
    if has_active_composer_input(capture):
        return False, "target-input-active"
    if is_busy(capture):
        return True, "target-working"
    if message_id:
        return False, "missing-positive-submit-evidence"
    return True, "no-queued-input"


def delivery_blocker(capture: list[str]) -> str | None:
    """Return a reason delivery should not paste into this terminal now."""
    if needs_submit_retry(capture):
        return "target-input-queued"
    if has_active_composer_input(capture):
        return "target-input-active"
    if is_busy(capture):
        return "target-busy"
    return None


def retry_submit(name: str, terminal) -> dict:
    """Retry submit using a literal Enter key event."""
    return terminal.send_keys(name, "Enter", enter=False) or {}


def verify_submit(
    terminal,
    target: str,
    *,
    message_id: str | None = None,
    lines: int = 80,
    delay_seconds: float = 1.0,
    max_retries: int = 2,
    sleep=None,
) -> dict:
    """Capture a terminal target, retry Enter if queued, and report evidence."""
    if sleep is None:
        import time

        sleep = time.sleep

    verify_capture = []
    submitted_verified = False
    verify_reason = "not-checked"
    submit_retry = False
    retry_result = None
    retry_results = []

    for attempt in range(max_retries + 1):
        sleep(delay_seconds)
        verify_capture = terminal.capture_output(target, max(lines, 120))
        submitted_verified, verify_reason = submission_evidence(verify_capture, message_id=message_id)
        if submitted_verified:
            break
        if verify_reason not in {"queued-input", "missing-positive-submit-evidence"} or attempt >= max_retries:
            break
        retry_result = retry_submit(target, terminal)
        retry_results.append(retry_result)
        submit_retry = bool(retry_result.get("ok"))
        if not submit_retry:
            verify_reason = "retry-submit-failed"
            break

    return {
        "submitted_verified": submitted_verified,
        "verify_reason": verify_reason,
        "submit_retry": submit_retry,
        "retry_result": retry_result,
        "retry_results": retry_results,
        "capture": verify_capture,
    }

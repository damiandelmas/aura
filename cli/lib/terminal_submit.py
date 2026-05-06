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
    """Legacy compatibility hook.

    Codex panes often leave the last submitted prompt visible at the bottom of
    the transcript. Treating arbitrary prompt text as live composer input causes
    false delivery blocks, so Aura no longer blocks on this signal.
    """
    return False


def is_busy(capture: list[str]) -> bool:
    """Detect terminal states where the runtime is already processing work."""
    indexes = _marker_indexes(capture)
    return indexes["busy"] > indexes["idle"]


def has_message_marker(capture: list[str], message_id: str | None) -> bool:
    """Return true when the submitted Aura message id is visible in pane output."""
    if not message_id:
        return False
    return any(message_id in str(line) for line in (capture or []))


def has_aura_envelope(capture: list[str]) -> bool:
    """Return true when a compact Aura message envelope is visible."""
    for raw in capture or []:
        line = str(raw).strip()
        if line.startswith(("› ", "❯ ")):
            line = line[1:].strip()
        if line.startswith("[AURA MESSAGE ") and " from=" in line and " sent_at=" in line:
            return True
    return False


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
    if has_aura_envelope(capture):
        return True, "aura-envelope-visible"
    if is_busy(capture):
        return True, "target-working"
    if message_id:
        return False, "missing-positive-submit-evidence"
    return True, "no-queued-input"


def delivery_blocker(capture: list[str]) -> str | None:
    """Return a reason delivery should not paste into this terminal now."""
    if needs_submit_retry(capture):
        return "target-input-queued"
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
    """Capture a terminal target, retry Enter on uncertain submit, and report evidence."""
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
        if verify_reason != "queued-input" or attempt >= max_retries:
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

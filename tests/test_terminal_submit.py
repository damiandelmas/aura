import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_busy_detection_ignores_stale_working_before_idle_prompt():
    from lib import terminal_submit

    capture = [
        "• Working (4m 55s • esc to interrupt)",
        "",
        "› Explain this codebase",
        "",
        "  gpt-5.5 medium · ~/projects/aura/main",
    ]

    assert terminal_submit.is_busy(capture) is False
    assert terminal_submit.delivery_blocker(capture) is None


def test_busy_detection_honors_new_work_after_idle_prompt():
    from lib import terminal_submit

    capture = [
        "› Explain this codebase",
        "",
        "• Working (3s • esc to interrupt)",
    ]

    assert terminal_submit.is_busy(capture) is True
    assert terminal_submit.delivery_blocker(capture) == "target-busy"


def test_submit_retry_ignores_stale_pasted_prompt_before_idle():
    from lib import terminal_submit

    capture = [
        "› [Pasted Content 1024 chars] #38",
        "",
        "› Explain this codebase",
    ]

    assert terminal_submit.needs_submit_retry(capture) is False


def test_submission_evidence_accepts_visible_message_id_after_prompt():
    from lib import terminal_submit

    capture = [
        "› [AURA MESSAGE id=aura-msg-unit from=ops sent_at=2026-04-30T00:00:00Z]",
        "  do the thing",
        "  [/AURA MESSAGE]",
        "",
        "gpt-5.5 medium · ~/project",
    ]

    assert terminal_submit.submission_evidence(capture, message_id="aura-msg-unit") == (
        True,
        "message-id-visible",
    )


def test_submission_evidence_rejects_idle_without_positive_marker():
    from lib import terminal_submit

    capture = [
        "› Explain this codebase",
        "",
        "gpt-5.5 medium · ~/project",
    ]

    assert terminal_submit.submission_evidence(capture, message_id="aura-msg-unit") == (
        False,
        "missing-positive-submit-evidence",
    )


def test_verify_submit_retries_queued_input_until_message_visible():
    from lib import terminal_submit

    class FakeTerminal:
        captures = [
            ["› [Pasted Content 1024 chars]", "", "gpt-5.5 medium"],
            ["› [AURA MESSAGE id=aura-msg-unit from=ops sent_at=now]", "  body", "[/AURA MESSAGE]"],
        ]
        keys = []

        @classmethod
        def capture_output(cls, target, lines=80):
            return cls.captures.pop(0)

        @classmethod
        def send_keys(cls, target, text, enter=False):
            cls.keys.append((target, text, enter))
            return {"ok": True}

    result = terminal_submit.verify_submit(
        FakeTerminal,
        "fleet:seat",
        message_id="aura-msg-unit",
        sleep=lambda _: None,
    )

    assert result["submitted_verified"] is True
    assert result["verify_reason"] == "message-id-visible"
    assert result["submit_retry"] is True
    assert FakeTerminal.keys == [("fleet:seat", "Enter", False)]

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "scripts" / "codex-hook-smoke.py"


def live_smoke_enabled() -> bool:
    return os.environ.get("AURA_RUN_LIVE_CODEX_SMOKE", "").strip().lower() in {"1", "true", "yes", "on"}


pytestmark = pytest.mark.skipif(
    not live_smoke_enabled(),
    reason="set AURA_RUN_LIVE_CODEX_SMOKE=1 to run live Codex/tmux hook smoke tests",
)


def run_smoke(*args: str) -> dict:
    timeout = int(os.environ.get("AURA_LIVE_CODEX_SMOKE_TIMEOUT", "180"))
    result = subprocess.run(
        [sys.executable, str(SMOKE), *args, "--timeout", str(timeout)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout + 60,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {}
    assert result.returncode == 0, (
        f"smoke exited {result.returncode}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    assert payload.get("ok") is True, payload
    return payload


def test_live_codex_hook_smoke_default_compact_path():
    payload = run_smoke()

    checks = payload["checks"]
    assert checks["hook_trust_preseeded"] is True
    assert checks["context_injected"] is True
    assert checks["inspect_bound_by_hook"] is True
    assert checks["pre_compact_seen"] is True
    assert checks["post_compact_seen"] is True
    assert checks["after_compact_context_observed"] is True
    assert checks["second_report_published"] is True


def test_live_codex_hook_smoke_command_override_prompt_path():
    payload = run_smoke(
        "--command",
        "codex --dangerously-bypass-approvals-and-sandbox --no-alt-screen",
        "--skip-compact",
    )

    checks = payload["checks"]
    assert checks["hook_trust_preseeded"] is True
    assert checks["context_injected"] is True
    assert checks["assistant_observed_context"] is True
    assert checks["inspect_bound_by_hook"] is True
    assert checks["aura_report_publish_succeeded"] is True

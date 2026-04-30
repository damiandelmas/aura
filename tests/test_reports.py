import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
AURA = ROOT / "cli" / "aura"


def run_aura(args, env, cwd=None):
    result = subprocess.run(
        [sys.executable, str(AURA), *args],
        cwd=cwd or ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_report_appends_semantic_delta_with_inferred_context(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "AURA_FLEET": "unitfleet",
        "AURA_SEAT": "engineer",
        "AURA_RUNTIME": "codex",
        "CODEX_THREAD_ID": "019ddf5f-b386-7ef0-9f43-8329ab2019c7",
        "DESKS_ROLE_ID": "leader-engine",
        "DESKS_PRODUCT": "flex",
        "DESKS_UNIT": "engine",
        "DESKS_ROLE_HOME": "/tmp/roles/leader-engine",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    result = run_aura(
        [
            "report",
            "complete",
            "--work",
            "Simplified Aura report primitive",
            "--done",
            "Added global report ledger",
            "--done",
            "Kept agent-facing fields tiny",
            "--receipt",
            "focused tests passed",
            "--next",
            "Document report-first UX",
        ],
        env,
        cwd=tmp_path,
    )

    assert result["ok"] is True
    assert result["schema"] == "aura.report_ack.v1"
    assert result["state"] == "complete"
    assert result["work"] == "Simplified Aura report primitive"
    assert result["seat"] == "engineer"
    assert result["fleet"] == "unitfleet"
    assert result["warnings"] == []

    latest = run_aura(["report", "latest"], env)
    record = latest["record"]
    assert record["schema"] == "aura.report.v1"
    assert record["state"] == "complete"
    assert record["work"] == "Simplified Aura report primitive"
    assert record["done"] == ["Added global report ledger", "Kept agent-facing fields tiny"]
    assert record["receipts"] == ["focused tests passed"]
    assert record["next"] == "Document report-first UX"
    assert record["seat"] == "engineer"
    assert record["fleet"] == "unitfleet"
    assert record["runtime"] == "codex"
    assert record["session_id"] == "019ddf5f-b386-7ef0-9f43-8329ab2019c7"
    assert record["role"]["desks_role_id"] == "leader-engine"
    assert record["role"]["desks_product"] == "flex"
    assert record["role"]["desks_unit"] == "engine"
    assert record["role"]["desks_role_home"] == "/tmp/roles/leader-engine"

    ledger = tmp_path / ".aura" / "reports" / "reports.jsonl"
    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["report_id"] == result["report_id"]


def test_report_list_and_latest_read_global_ledger(tmp_path):
    env = {
        **os.environ,
        "AURA_STATE_DIR": str(tmp_path / ".aura"),
        "AURA_FLEET": "unitfleet",
        "AURA_SEAT": "worker",
        "AURA_RUNTIME": "codex",
        "CODEX_THREAD_ID": "019ddf5f-b386-7ef0-9f43-8329ab2019c7",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    run_aura(["report", "working", "--work", "First"], env)
    second = run_aura(["report", "blocked", "--work", "Second", "--blocker", "needs decision"], env)

    listed = run_aura(["report", "list", "--limit", "1"], env)
    assert listed["ok"] is True
    assert listed["count"] == 1
    assert listed["rows"][0]["report_id"] == second["report_id"]

    latest = run_aura(["report", "latest"], env)
    assert latest["ok"] is True
    assert latest["record"]["state"] == "blocked"
    assert latest["record"]["blockers"] == ["needs decision"]

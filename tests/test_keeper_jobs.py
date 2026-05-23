import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _create_target(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages, registry

    created = agent_packages.create(
        address="flexgraph:operations:chief-of-staff",
        runtime="codex",
        profile=None,
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-operations",
        seat="chief-of-staff",
        alias="chief-of-staff",
    )
    agent = created["agent"]
    registry.upsert_agent(
        {
            "name": "chief-of-staff",
            "seat": "chief-of-staff",
            "fleet": "flexgraph-operations",
            "runtime": "codex",
            "cwd": str(tmp_path / "unit"),
            "agent_package_id": agent["agent_id"],
            "runtime_session_id": "019e-target",
        }
    )
    return agent


def _mock_flex_slice(monkeypatch, *, rows=20, max_position=200, start_position=1):
    from lib import keeper_jobs

    monkeypatch.setattr(
        keeper_jobs,
        "_flex_bounds",
        lambda session_id: {"rows": rows, "min_position": 1, "max_position": max_position},
    )
    monkeypatch.setattr(
        keeper_jobs,
        "_overlap_start_position",
        lambda session_id, *, last_read_position, overlap_messages, total_rows: start_position,
    )
    monkeypatch.setattr(
        keeper_jobs,
        "_flex_slice",
        lambda session_id, *, start_position, target_position: [
            {
                "id": f"{session_id}-{start_position}",
                "position": start_position,
                "type": "user_prompt",
                "tool_name": None,
                "target_file": None,
                "body": "target evidence start",
            },
            {
                "id": f"{session_id}-{target_position}",
                "position": target_position,
                "type": "assistant_message",
                "tool_name": None,
                "target_file": None,
                "body": "target evidence end",
            },
        ],
    )


def test_run_memory_creates_deterministic_job(monkeypatch, tmp_path):
    agent = _create_target(monkeypatch, tmp_path)

    from lib import keeper_jobs

    _mock_flex_slice(monkeypatch, rows=20, max_position=200, start_position=1)
    launched = {}

    def fake_launch(*, job_path, request):
        launched["job_path"] = job_path
        launched["request"] = request
        return {"pid": 1234, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")}

    monkeypatch.setattr(keeper_jobs, "_launch_worker", fake_launch)

    result = keeper_jobs.run_memory(target_ref="flexgraph-operations:chief-of-staff", boundary="precompact")

    assert result["ok"] is True
    assert result["job_id"] == f"memory.{agent['agent_id']}.019e-target.precompact.p200"
    job_path = Path(result["job_dir"])
    request = json.loads((job_path / "request.json").read_text(encoding="utf-8"))
    slice_payload = json.loads((job_path / "slice.json").read_text(encoding="utf-8"))
    assert request["schema"] == "aura.keeper_job_request.v1"
    assert request["kind"] == "memory"
    assert request["boundary"] == "precompact"
    assert request["prompt_kind"] == "state"
    assert request["target"]["agent_id"] == agent["agent_id"]
    assert request["target"]["session_id"] == "019e-target"
    assert request["target"]["ref"] == "flexgraph-operations:chief-of-staff"
    assert request["evidence"]["source"] == "flex:sessions:codex"
    assert request["evidence"]["slice_path"] == str(job_path / "slice.json")
    assert request["evidence"]["last_read_position"] is None
    assert request["evidence"]["start_position"] == 1
    assert request["evidence"]["target_position"] == 200
    assert request["evidence"]["total_rows"] == 20
    assert request["evidence"]["overlap_messages"] == 2
    assert request["evidence"]["recent_memory_paths"] == []
    assert slice_payload["schema"] == "aura.keeper_memory_slice.v1"
    assert slice_payload["rows"][-1]["id"] == "019e-target-200"
    assert request["output"]["memory_path"].startswith(str(Path(agent["root"]) / "memories"))
    assert request["output"]["index_path"] == str(Path(agent["root"]) / "memories" / "index.json")
    assert request["keeper"]["address"] == "aura:keepers:context"
    assert launched["request"]["job_id"] == result["job_id"]
    status = json.loads((job_path / "status.json").read_text(encoding="utf-8"))
    assert status["state"] == "running"
    assert status["pid"] == 1234


def test_memory_prompt_uses_trace_contract_for_non_precompact(monkeypatch, tmp_path):
    _create_target(monkeypatch, tmp_path)

    from lib import keeper_jobs

    _mock_flex_slice(monkeypatch, rows=20, max_position=200, start_position=1)
    monkeypatch.setattr(
        keeper_jobs,
        "_launch_worker",
        lambda *, job_path, request: {"pid": 1234, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")},
    )

    result = keeper_jobs.run_memory(target_ref="chief-of-staff", boundary="75")
    prompt = (Path(result["job_dir"]) / "prompt.md").read_text(encoding="utf-8")

    assert "You are capturing your working state." in prompt
    assert "Read your last 5 memories." in prompt
    assert "Read the new slice." in prompt
    assert "Capture a trace of your working state." in prompt
    assert "Must have a 5 sentence overview." in prompt
    assert "Write here:" in prompt
    assert "Last 5 memories:" in prompt
    assert "New slice:" in prompt
    assert "target_agent_id:" not in prompt
    assert "target session" not in prompt
    assert "## Workflow Position" not in prompt
    assert "## What Actually Happened" not in prompt


def test_memory_prompt_uses_state_contract_for_precompact(monkeypatch, tmp_path):
    _create_target(monkeypatch, tmp_path)

    from lib import keeper_jobs

    _mock_flex_slice(monkeypatch, rows=20, max_position=200, start_position=1)
    monkeypatch.setattr(
        keeper_jobs,
        "_launch_worker",
        lambda *, job_path, request: {"pid": 1234, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")},
    )

    result = keeper_jobs.run_memory(target_ref="chief-of-staff", boundary="precompact")
    prompt = (Path(result["job_dir"]) / "prompt.md").read_text(encoding="utf-8")

    assert "You are capturing your working state." in prompt
    assert "Read your last 5 memories." in prompt
    assert "Read the new slice." in prompt
    assert "Capture the full working state before compaction" in prompt
    assert "Goal: make sure the next agent can recover the current work without relying on chat history." in prompt
    assert "LETS IMAGINE OUR ENTIRE SYSTEM / WORKFLOW / SOP" in prompt
    assert "DRAW IT OUT." in prompt
    assert "MARK WHERE WE ARE." in prompt
    assert "Write here:" in prompt
    assert "## System / Workflow / SOP Map" not in prompt


def test_run_memory_includes_last_five_memory_files(monkeypatch, tmp_path):
    agent = _create_target(monkeypatch, tmp_path)

    from lib import keeper_jobs

    memory_root = Path(agent["root"]) / "memories"
    memory_root.mkdir(parents=True, exist_ok=True)
    for index in range(7):
        path = memory_root / f"prior-{index}.md"
        path.write_text(f"# Prior {index}\n", encoding="utf-8")
        path.touch()

    _mock_flex_slice(monkeypatch, rows=20, max_position=200, start_position=1)
    monkeypatch.setattr(
        keeper_jobs,
        "_launch_worker",
        lambda *, job_path, request: {"pid": 1234, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")},
    )

    result = keeper_jobs.run_memory(target_ref="chief-of-staff", boundary="50")
    request = json.loads((Path(result["job_dir"]) / "request.json").read_text(encoding="utf-8"))
    prompt = (Path(result["job_dir"]) / "prompt.md").read_text(encoding="utf-8")

    assert len(request["evidence"]["recent_memory_paths"]) == 5
    assert all(path.endswith(".md") for path in request["evidence"]["recent_memory_paths"])
    assert "Last 5 memories:" in prompt
    assert request["evidence"]["recent_memory_paths"][0] in prompt


def test_run_memory_dedupes_completed_job(monkeypatch, tmp_path):
    agent = _create_target(monkeypatch, tmp_path)

    from lib import keeper_jobs

    _mock_flex_slice(monkeypatch, max_position=200)
    calls = []

    def fake_launch(*, job_path, request):
        calls.append(request)
        return {"pid": 1234, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")}

    monkeypatch.setattr(keeper_jobs, "_launch_worker", fake_launch)
    first = keeper_jobs.run_memory(target_ref="chief-of-staff", boundary="manual")
    result_path = Path(first["result"])
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text('{"ok": true, "thread_id": "keeper-thread"}\n', encoding="utf-8")

    second = keeper_jobs.run_memory(target_ref=agent["agent_id"], boundary="manual")

    assert second["ok"] is True
    assert second["deduped"] is True
    assert second["job_id"] == first["job_id"]
    assert second["result"]["thread_id"] == "keeper-thread"
    assert len(calls) == 1


def test_run_memory_force_relaunches_completed_job(monkeypatch, tmp_path):
    _create_target(monkeypatch, tmp_path)

    from lib import keeper_jobs

    _mock_flex_slice(monkeypatch, max_position=200)
    calls = []

    def fake_launch(*, job_path, request):
        calls.append(request)
        return {"pid": 5678, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")}

    monkeypatch.setattr(keeper_jobs, "_launch_worker", fake_launch)
    first = keeper_jobs.run_memory(target_ref="chief-of-staff", boundary="manual")
    Path(first["result"]).write_text('{"ok": true}\n', encoding="utf-8")
    second = keeper_jobs.run_memory(target_ref="chief-of-staff", boundary="manual", force=True)

    assert second["ok"] is True
    assert second["job_id"] == first["job_id"]
    assert second["pid"] == 5678
    assert len(calls) == 2


def test_status_result_and_tail(monkeypatch, tmp_path):
    _create_target(monkeypatch, tmp_path)

    from lib import keeper_jobs

    _mock_flex_slice(monkeypatch, max_position=200)

    def fake_launch(*, job_path, request):
        (job_path / "log.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
        return {"pid": 1234, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")}

    monkeypatch.setattr(keeper_jobs, "_launch_worker", fake_launch)
    result = keeper_jobs.run_memory(target_ref="chief-of-staff", boundary="manual")
    Path(result["result"]).write_text('{"ok": true, "thread_id": "keeper-thread"}\n', encoding="utf-8")

    status = keeper_jobs.read_status(result["job_id"])
    read_result = keeper_jobs.read_result(result["job_id"])
    tail = keeper_jobs.tail_log(result["job_id"], lines=2)

    assert status["status"]["state"] == "running"
    assert read_result["result"]["thread_id"] == "keeper-thread"
    assert tail["lines"] == ["two", "three"]


def test_keeper_command_envelope(monkeypatch, tmp_path):
    _create_target(monkeypatch, tmp_path)

    from commands import keeper as keeper_cmd
    from lib import keeper_jobs

    _mock_flex_slice(monkeypatch, max_position=200)
    monkeypatch.setattr(
        keeper_jobs,
        "_launch_worker",
        lambda *, job_path, request: {"pid": 999, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")},
    )

    result = keeper_cmd.run(
        argparse.Namespace(
            keeper_action="run",
            keeper_kind="memory",
            target="chief-of-staff",
            boundary="manual",
            force=False,
        )
    )

    assert result["ok"] is True
    assert result["pid"] == 999


def test_run_memory_uses_package_cursor_and_prior_memory(monkeypatch, tmp_path):
    agent = _create_target(monkeypatch, tmp_path)

    from lib import keeper_jobs

    prior_memory = Path(agent["root"]) / "memories" / "prior.md"
    prior_memory.parent.mkdir(parents=True, exist_ok=True)
    prior_memory.write_text("# Prior\n", encoding="utf-8")
    (Path(agent["root"]) / "memories" / "index.json").write_text(
        json.dumps(
            {
                "schema": "aura.agent_memory_index.v1",
                "sessions": {
                    "019e-target": {
                        "last_read_position": 120,
                        "last_read_message_id": "019e-target-120",
                        "latest_memory_path": str(prior_memory),
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    seen = {}

    monkeypatch.setattr(
        keeper_jobs,
        "_flex_bounds",
        lambda session_id: {"rows": 300, "min_position": 1, "max_position": 240},
    )

    def fake_start(session_id, *, last_read_position, overlap_messages, total_rows):
        seen["last_read_position"] = last_read_position
        seen["overlap_messages"] = overlap_messages
        seen["total_rows"] = total_rows
        return 90

    monkeypatch.setattr(keeper_jobs, "_overlap_start_position", fake_start)
    monkeypatch.setattr(
        keeper_jobs,
        "_flex_slice",
        lambda session_id, *, start_position, target_position: [
            {"id": "019e-target-90", "position": 90, "type": "user_prompt", "body": "overlap"},
            {"id": "019e-target-240", "position": 240, "type": "assistant_message", "body": "new"},
        ],
    )
    monkeypatch.setattr(
        keeper_jobs,
        "_launch_worker",
        lambda *, job_path, request: {"pid": 1234, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")},
    )

    result = keeper_jobs.run_memory(target_ref=agent["agent_id"], boundary="50")

    request = json.loads((Path(result["job_dir"]) / "request.json").read_text(encoding="utf-8"))
    assert seen == {"last_read_position": 120, "overlap_messages": 2, "total_rows": 300}
    assert result["job_id"] == f"memory.{agent['agent_id']}.019e-target.50.p240"
    assert request["evidence"]["last_read_position"] == 120
    assert request["evidence"]["last_read_message_id"] == "019e-target-120"
    assert request["evidence"]["prior_memory_path"] == str(prior_memory)
    assert request["evidence"]["start_position"] == 90
    assert request["evidence"]["target_position"] == 240

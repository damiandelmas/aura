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
    slice_markdown = (job_path / "slice.md").read_text(encoding="utf-8")
    assert request["schema"] == "aura.keeper_job_request.v1"
    assert request["kind"] == "memory"
    assert request["boundary"] == "precompact"
    assert request["prompt_kind"] == "state"
    assert request["target"]["agent_id"] == agent["agent_id"]
    assert request["target"]["session_id"] == "019e-target"
    assert request["target"]["ref"] == "flexgraph-operations:chief-of-staff"
    assert request["evidence"]["source"] == "flex:sessions:codex"
    assert request["evidence"]["slice_path"] == str(job_path / "slice.json")
    assert request["evidence"]["slice_markdown_path"] == str(job_path / "slice.md")
    assert request["evidence"]["last_read_position"] is None
    assert request["evidence"]["start_position"] == 1
    assert request["evidence"]["target_position"] == 200
    assert request["evidence"]["total_rows"] == 20
    assert request["evidence"]["overlap_messages"] == 2
    assert request["evidence"]["recent_memory_paths"] == []
    assert slice_payload["schema"] == "aura.keeper_memory_slice.v1"
    assert slice_payload["rows"][-1]["id"] == "019e-target-200"
    assert "# Conversation Slice" in slice_markdown
    assert "Session: `019e-target`" in slice_markdown
    assert "## 1 - user_prompt" in slice_markdown
    assert "target evidence start" in slice_markdown
    assert "## 200 - assistant_message" in slice_markdown
    assert "target evidence end" in slice_markdown
    assert request["output"]["memory_path"].startswith(str(Path(agent["root"]) / "memories"))
    assert request["output"]["index_path"] == str(Path(agent["root"]) / "memories" / "index.json")
    assert request["keeper"]["address"] == "aura:keepers:context"
    assert launched["request"]["job_id"] == result["job_id"]
    assert result["slice_markdown"] == str(job_path / "slice.md")
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

    assert "YOU ARE CODEX, AN AUTONOMOUS CODING AGENT" in prompt
    assert "as if this conversation is you talking to the user" in prompt
    assert "The conversation is the source of truth." in prompt
    assert "This is a working-state capture, not a final verdict." in prompt
    assert "Preserve the user's corrections as important signal." in prompt
    assert "Organize by concerns, not by strict chronology." in prompt
    assert "Start with a top-level `#` title." in prompt
    assert "Then write a 3-5 sentence overview directly under the title." in prompt
    assert "Do not write a job report." in prompt
    assert "WRITE HERE:" in prompt
    assert "Last 5 memories:" in prompt
    assert "Conversation excerpt:" in prompt
    assert "slice.md" in prompt
    assert "slice.json" not in prompt
    assert "You are capturing your working state." not in prompt
    assert "Read the new slice." not in prompt
    assert "Do not summarize the keeper machinery" not in prompt
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
    assert "Read the new conversation excerpt." in prompt
    assert "Capture the full working state before compaction" in prompt
    assert "Goal: make sure the next agent can recover the current work without relying on chat history." in prompt
    assert "LETS IMAGINE OUR ENTIRE SYSTEM / WORKFLOW / SOP" in prompt
    assert "DRAW IT OUT." in prompt
    assert "MARK WHERE WE ARE." in prompt
    assert "WRITE HERE:" in prompt
    assert "slice.md" in prompt
    assert "slice.json" not in prompt
    assert "## System / Workflow / SOP Map" not in prompt


def test_memory_prompt_can_load_trace_template_override(monkeypatch, tmp_path):
    _create_target(monkeypatch, tmp_path)

    from lib import keeper_jobs

    template = tmp_path / "trace-template.md"
    template.write_text("# Custom Trace\n\nKeep this experimental.\n", encoding="utf-8")
    monkeypatch.setenv("AURA_KEEPER_TRACE_PROMPT", str(template))
    _mock_flex_slice(monkeypatch, rows=20, max_position=200, start_position=1)
    monkeypatch.setattr(
        keeper_jobs,
        "_launch_worker",
        lambda *, job_path, request: {"pid": 1234, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")},
    )

    result = keeper_jobs.run_memory(target_ref="chief-of-staff", boundary="manual")
    prompt = (Path(result["job_dir"]) / "prompt.md").read_text(encoding="utf-8")

    assert prompt.startswith("# Custom Trace")
    assert "Keep this experimental." in prompt
    assert "WRITE HERE:" in prompt
    assert "Conversation excerpt:" in prompt


def test_run_memory_prompt_includes_previous_memory_files_when_present(monkeypatch, tmp_path):
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


def test_seed_keeper_codex_home_links_auth_and_refreshes_config(monkeypatch, tmp_path):
    from lib import keeper_jobs

    source = tmp_path / "source-codex"
    source.mkdir()
    (source / "auth.json").write_text('{"token": "fresh"}\n', encoding="utf-8")
    (source / "config.toml").write_text('model = "gpt-5"\n', encoding="utf-8")
    codex_home = tmp_path / "keeper" / ".codex"
    codex_home.mkdir(parents=True)
    (codex_home / "auth.json").write_text('{"token": "stale-copy"}\n', encoding="utf-8")
    monkeypatch.setenv("AURA_KEEPER_CODEX_SOURCE_HOME", str(source))

    result = keeper_jobs._seed_keeper_codex_home(codex_home)

    auth_path = codex_home / "auth.json"
    assert auth_path.is_symlink()
    assert auth_path.resolve() == source / "auth.json"
    assert (codex_home / "config.toml").read_text(encoding="utf-8") == 'model = "gpt-5"\n'
    assert list((codex_home / ".auth-backups").glob("auth.json.*"))
    assert result["source_codex_home"] == str(source)
    assert result["auth"][0]["mode"] == "symlink"


def test_read_status_classifies_codex_auth_refresh_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import keeper_jobs

    job_id = "memory.i_target.019e-session.m15.p100"
    path = keeper_jobs.job_dir(job_id)
    path.mkdir(parents=True)
    (path / "status.json").write_text(
        json.dumps(
            {
                "ok": False,
                "state": "failed",
                "error": "Your access token could not be refreshed because your refresh token was already used. Please log out and sign in again.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = keeper_jobs.read_status(job_id)

    diagnostic = result["status"]["diagnostic"]
    assert diagnostic["kind"] == "codex-auth-refresh"
    assert diagnostic["severity"] == "critical"


def test_keeper_health_counts_auth_refresh_failures(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import keeper_jobs

    failed = keeper_jobs.job_dir("memory.i_target.019e-session.m15.p100")
    failed.mkdir(parents=True)
    (failed / "status.json").write_text(
        json.dumps(
            {
                "ok": False,
                "state": "failed",
                "error": "Your access token could not be refreshed because your refresh token was already used. Please log out and sign in again.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    complete = keeper_jobs.job_dir("memory.i_target.019e-session.m30.p200")
    complete.mkdir(parents=True)
    (complete / "result.json").write_text('{"ok": true}\n', encoding="utf-8")

    result = keeper_jobs.health(limit=10)

    assert result["counts"]["failed"] == 1
    assert result["counts"]["complete"] == 1
    assert result["diagnostics"]["codex-auth-refresh"] == 1


def test_keeper_backfill_dry_run_selects_auth_failures_oldest_first(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import keeper_jobs

    for position in (200, 100):
        job_id = f"memory.i_target.019e-session.m{position}.p{position}"
        path = keeper_jobs.job_dir(job_id)
        path.mkdir(parents=True)
        (path / "request.json").write_text(
            json.dumps(
                {
                    "job_id": job_id,
                    "boundary": f"m{position}",
                    "target": {"agent_id": "i_target", "session_id": "019e-session", "cwd": str(tmp_path)},
                    "evidence": {"target_position": position},
                    "output": {
                        "memory_path": str(tmp_path / f"memory-{position}.md"),
                        "index_path": str(tmp_path / "index.json"),
                    },
                    "keeper": {"codex_home": str(tmp_path / "stale" / ".codex")},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (path / "status.json").write_text(
            json.dumps(
                {
                    "ok": False,
                    "state": "failed",
                    "error": "Your access token could not be refreshed because your refresh token was already used. Please log out and sign in again.",
                }
            )
            + "\n",
            encoding="utf-8",
        )

    result = keeper_jobs.backfill(limit=2, dry_run=True)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert [row["target_position"] for row in result["selected"]] == [100, 200]
    assert result["candidate_count"] == 2


def test_keeper_backfill_relaunches_stored_request_with_fresh_keeper(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import keeper_jobs

    job_id = "memory.i_target.019e-session.m100.p100"
    path = keeper_jobs.job_dir(job_id)
    path.mkdir(parents=True)
    memory_path = tmp_path / "memory.md"
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps(
            {
                "schema": "aura.agent_memory_index.v1",
                "sessions": {
                    "019e-session": {
                        "last_read_position": 90,
                        "last_read_message_id": "msg-90",
                        "latest_memory_path": str(tmp_path / "prior.md"),
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (path / "request.json").write_text(
        json.dumps(
            {
                "job_id": job_id,
                "boundary": "m100",
                "target": {"agent_id": "i_target", "session_id": "019e-session", "cwd": str(tmp_path)},
                "evidence": {"target_position": 100},
                "output": {"memory_path": str(memory_path), "index_path": str(index_path)},
                "keeper": {"codex_home": str(tmp_path / "stale" / ".codex")},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (path / "status.json").write_text(
        json.dumps(
            {
                "ok": False,
                "state": "failed",
                "error": "Your access token could not be refreshed because your refresh token was already used. Please log out and sign in again.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        keeper_jobs,
        "ensure_keeper_profile",
        lambda cwd=None: {
            "address": "aura:keepers:context",
            "agent_id": "i_keeper",
            "root": str(tmp_path / "keeper"),
            "codex_home": str(tmp_path / "keeper" / ".codex"),
        },
    )
    monkeypatch.setattr(
        keeper_jobs,
        "_launch_worker",
        lambda *, job_path, request: {"pid": 2468, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")},
    )

    result = keeper_jobs.backfill(limit=1)

    assert result["counts"] == {"launched": 1, "skipped": 0}
    assert result["launched"][0]["pid"] == 2468
    request = json.loads((path / "request.json").read_text(encoding="utf-8"))
    status = json.loads((path / "status.json").read_text(encoding="utf-8"))
    assert request["keeper"]["codex_home"] == str(tmp_path / "keeper" / ".codex")
    assert request["evidence"]["last_read_position"] == 90
    assert request["evidence"]["last_read_message_id"] == "msg-90"
    assert request["evidence"]["prior_memory_path"] == str(tmp_path / "prior.md")
    assert request["backfill"]["diagnostic"]["kind"] == "codex-auth-refresh"
    assert status["state"] == "running"
    assert status["backfill"] is True


def test_keeper_backfill_skips_jobs_already_covered_by_index(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import keeper_jobs

    job_id = "memory.i_target.019e-session.m100.p100"
    path = keeper_jobs.job_dir(job_id)
    path.mkdir(parents=True)
    index_path = tmp_path / "index.json"
    index_path.write_text(
        json.dumps({"schema": "aura.agent_memory_index.v1", "sessions": {"019e-session": {"last_read_position": 100}}})
        + "\n",
        encoding="utf-8",
    )
    (path / "request.json").write_text(
        json.dumps(
            {
                "job_id": job_id,
                "boundary": "m100",
                "target": {"agent_id": "i_target", "session_id": "019e-session", "cwd": str(tmp_path)},
                "evidence": {"target_position": 100},
                "output": {"memory_path": str(tmp_path / "memory.md"), "index_path": str(index_path)},
                "keeper": {"codex_home": str(tmp_path / "stale" / ".codex")},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (path / "status.json").write_text(
        json.dumps(
            {
                "ok": False,
                "state": "failed",
                "error": "Your access token could not be refreshed because your refresh token was already used. Please log out and sign in again.",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = keeper_jobs.backfill(limit=10, dry_run=True)

    assert result["candidate_count"] == 0
    assert result["selected"] == []


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


def test_keeper_worker_launch_scrubs_target_aura_binding_env(monkeypatch, tmp_path):
    from lib import keeper_jobs

    runner = tmp_path / "runner.mjs"
    runner.write_text("console.log('ok')\n", encoding="utf-8")
    monkeypatch.setenv("AURA_KEEPER_SDK_RUNNER", str(runner))
    monkeypatch.setenv("AURA_FLEET", "target-fleet")
    monkeypatch.setenv("AURA_SEAT", "target-seat")
    monkeypatch.setenv("AURA_AGENT_PACKAGE_ID", "i_target")
    monkeypatch.setenv("AURA_AGENT_PACKAGE_ROOT", str(tmp_path / "target-package"))
    monkeypatch.setenv("AURA_RUNTIME_CAPSULE_REF", str(tmp_path / "target-package"))
    monkeypatch.setenv("AURA_SEAT_INSTANCE_ID", "si_target")
    monkeypatch.setenv("CODEX_THREAD_ID", "target-thread")
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    captured = {}

    class FakePopen:
        pid = 4321

        def __init__(self, cmd, *, stdin, stdout, stderr, env, start_new_session):
            captured["cmd"] = cmd
            captured["env"] = env
            captured["start_new_session"] = start_new_session

    monkeypatch.setattr(keeper_jobs.subprocess, "Popen", FakePopen)

    job_path = tmp_path / "job"
    job_path.mkdir()
    result = keeper_jobs._launch_worker(
        job_path=job_path,
        request={"keeper": {"codex_home": str(tmp_path / "keeper" / ".codex")}},
    )

    assert result["pid"] == 4321
    assert captured["start_new_session"] is True
    assert captured["env"]["AURA_KEEPER_WORKER"] == "1"
    assert captured["env"]["CODEX_HOME"] == str(tmp_path / "keeper" / ".codex")
    assert captured["env"]["AURA_STATE_DIR"] == str(tmp_path / "state")
    for key in (
        "AURA_FLEET",
        "AURA_SEAT",
        "AURA_AGENT_PACKAGE_ID",
        "AURA_AGENT_PACKAGE_ROOT",
        "AURA_RUNTIME_CAPSULE_REF",
        "AURA_SEAT_INSTANCE_ID",
        "CODEX_THREAD_ID",
    ):
        assert key not in captured["env"]


def test_keeper_hooks_install_refreshes_agent_and_profile_homes(monkeypatch, tmp_path):
    agent = _create_target(monkeypatch, tmp_path)
    root = Path(agent["root"])
    (root / ".codex").mkdir(parents=True, exist_ok=True)
    profile_codex_home = tmp_path / "state" / "runtime-profiles" / "codex" / "dev" / "codex-home-template"
    profile_codex_home.mkdir(parents=True)

    from lib import keeper_jobs

    result = keeper_jobs.install_hooks()

    assert result["ok"] is True
    installed_roots = {row["root"] for row in result["installed"]}
    assert str(root) in installed_roots
    assert str(profile_codex_home.parent) in installed_roots
    agent_hooks = json.loads((root / ".codex" / "hooks.json").read_text(encoding="utf-8"))
    profile_hooks = json.loads((profile_codex_home / "hooks.json").read_text(encoding="utf-8"))
    assert "aura_keeper_hook.py Stop" in agent_hooks["hooks"]["Stop"][0]["hooks"][0]["command"]
    assert agent_hooks["hooks"]["Stop"][0]["hooks"][0]["timeout"] == 10
    assert "aura_keeper_hook.py PreCompact" in profile_hooks["hooks"]["PreCompact"][0]["hooks"][0]["command"]


def test_keeper_hooks_command_defaults_to_agents_and_profiles(monkeypatch, tmp_path):
    from commands import keeper as keeper_cmd
    from lib import keeper_jobs

    captured = {}
    monkeypatch.setattr(
        keeper_jobs,
        "install_hooks",
        lambda **kwargs: captured.update(kwargs) or {"ok": True},
    )

    result = keeper_cmd.run(
        argparse.Namespace(
            keeper_action="hooks",
            keeper_hooks_action="install",
            agents=False,
            profiles=False,
            dry_run=True,
        )
    )

    assert result["ok"] is True
    assert captured == {"agents": True, "profiles": True, "dry_run": True}


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


def test_run_memory_reads_cursor_after_flex_bounds(monkeypatch, tmp_path):
    agent = _create_target(monkeypatch, tmp_path)

    from lib import keeper_jobs

    memory_root = Path(agent["root"]) / "memories"
    memory_root.mkdir(parents=True, exist_ok=True)
    prior_memory = memory_root / "fresh.md"
    prior_memory.write_text("# Fresh\n", encoding="utf-8")
    seen = {}

    def fake_bounds(session_id):
        (memory_root / "index.json").write_text(
            json.dumps(
                {
                    "schema": "aura.agent_memory_index.v1",
                    "sessions": {
                        "019e-target": {
                            "last_read_position": 180,
                            "last_read_message_id": "019e-target-180",
                            "latest_memory_path": str(prior_memory),
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        return {"rows": 300, "min_position": 1, "max_position": 240}

    def fake_start(session_id, *, last_read_position, overlap_messages, total_rows):
        seen["last_read_position"] = last_read_position
        return 170

    monkeypatch.setattr(keeper_jobs, "_flex_bounds", fake_bounds)
    monkeypatch.setattr(keeper_jobs, "_overlap_start_position", fake_start)
    monkeypatch.setattr(
        keeper_jobs,
        "_flex_slice",
        lambda session_id, *, start_position, target_position: [
            {"id": "019e-target-170", "position": 170, "type": "assistant", "body": "overlap"},
            {"id": "019e-target-240", "position": 240, "type": "assistant", "body": "new"},
        ],
    )
    monkeypatch.setattr(
        keeper_jobs,
        "_launch_worker",
        lambda *, job_path, request: {"pid": 1234, "job": str(job_path / "job.sh"), "log": str(job_path / "log.txt")},
    )

    result = keeper_jobs.run_memory(target_ref=agent["agent_id"], boundary="75")
    request = json.loads((Path(result["job_dir"]) / "request.json").read_text(encoding="utf-8"))

    assert seen["last_read_position"] == 180
    assert request["evidence"]["last_read_position"] == 180
    assert request["evidence"]["prior_memory_path"] == str(prior_memory)


def test_markdown_slice_truncates_large_rows():
    from lib import keeper_jobs

    rendered = keeper_jobs._markdown_slice(
        session_id="019e-target",
        start_position=1,
        target_position=1,
        rows=[
            {
                "position": 1,
                "type": "assistant",
                "tool_name": None,
                "body": "x" * (keeper_jobs.MAX_SLICE_BODY_CHARS + 10),
            }
        ],
    )

    assert "## 1 - assistant" in rendered
    assert "[truncated 10 chars from this row]" in rendered
    assert len(rendered) < keeper_jobs.MAX_SLICE_BODY_CHARS + 500


def test_ensure_keeper_profile_is_idempotent(monkeypatch, tmp_path):
    # Regression: ensure_keeper_profile resolved by an un-indexed address, so a second
    # call re-created and collided on the existing 'aura-keeper-context' alias. It must
    # now resolve the existing keeper agent by alias and be safe to call repeatedly.
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    from lib import keeper_jobs

    monkeypatch.setattr(keeper_jobs, "_seed_keeper_codex_home", lambda codex_home: {"seeded": False})

    first = keeper_jobs.ensure_keeper_profile(cwd=str(tmp_path / "unit"))
    second = keeper_jobs.ensure_keeper_profile(cwd=str(tmp_path / "unit"))  # must NOT raise

    assert first["agent_id"] == second["agent_id"]
    assert first["address"] == keeper_jobs.KEEPER_ADDRESS

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


class RestartTerminal:
    SESSION_NAME = "unitfleet"
    BACKEND_NAME = "tmux"

    created = []
    killed = []
    sent = []
    respawned = []
    existing = {"tmux:unitfleet:%1": 111}
    next_pane = "%2"
    next_pid = 222
    launch_ok = True
    captures = []

    @classmethod
    def reset(cls):
        cls.created = []
        cls.killed = []
        cls.sent = []
        cls.respawned = []
        cls.existing = {"tmux:unitfleet:%1": 111}
        cls.next_pane = "%2"
        cls.next_pid = 222
        cls.launch_ok = True
        cls.captures = []

    @staticmethod
    def configure_session(name):
        RestartTerminal.SESSION_NAME = name
        return name

    @staticmethod
    def target_exists(target):
        return target in RestartTerminal.existing

    @staticmethod
    def pane_pid(target):
        return RestartTerminal.existing.get(target)

    @staticmethod
    def kill_window(target):
        RestartTerminal.killed.append(target)
        RestartTerminal.existing.pop(target, None)

    @staticmethod
    def create_window(name, workdir, detached=False, command=None, env=None, unset_env=None):
        RestartTerminal.created.append((name, workdir, detached, command, env, unset_env))
        if not RestartTerminal.launch_ok:
            return {"ok": False, "error": "simulated launch failure"}
        target = f"unitfleet:{name}"
        pane_ref = f"tmux:unitfleet:{RestartTerminal.next_pane}"
        RestartTerminal.existing[pane_ref] = RestartTerminal.next_pid
        return {"ok": True, "target": target, "pane_id": RestartTerminal.next_pane}

    @staticmethod
    def respawn_pane(target, workdir=None, command=None, env=None, unset_env=None):
        RestartTerminal.respawned.append((target, workdir, command, env, unset_env))
        if not RestartTerminal.launch_ok:
            return {"ok": False, "error": "simulated launch failure"}
        RestartTerminal.existing[target] = RestartTerminal.next_pid
        return {"ok": True, "target": "unitfleet:engineer", "pane_id": "%1", "pane_ref": target}

    @staticmethod
    def send_text(target, text, submit=True):
        RestartTerminal.sent.append((target, text, submit))
        return {"ok": True, "target": target, "submitted": submit}

    @staticmethod
    def capture_output(target, lines=80):
        if RestartTerminal.captures:
            return RestartTerminal.captures.pop(0)
        return ["› ready"]

    @staticmethod
    def send_keys(target, text, enter=False):
        RestartTerminal.sent.append((target, text, enter))
        return {"ok": True, "target": target}


def _args(**overrides):
    base = {
        "target": "unitfleet:engineer",
        "role_home": None,
        "manifest": None,
        "cwd": None,
        "runtime": None,
        "prompt": None,
        "force": True,
        "dry_run": False,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _record(tmp_path, **overrides):
    record = {
        "name": "engineer",
        "seat": "engineer",
        "fleet": "unitfleet",
        "runtime": "command",
        "command": "python tests/fixtures/fake_runtime.py --name engineer",
        "cwd": str(tmp_path),
        "terminal_ref": "unitfleet:engineer",
        "backend_ref": "unitfleet:engineer",
        "pane_ref": "tmux:unitfleet:%1",
        "runtime_session_id": "old-session",
        "runtime_session_source": "unit",
        "runtime_session_confidence": "exact",
        "aura_launch_id": "aura-launch-old",
        "status": "alive",
    }
    record.update(overrides)
    return record


def test_restart_preserves_seat_and_records_seat_history(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import seat
    from lib import registry

    RestartTerminal.reset()
    registry.upsert_agent(_record(
        tmp_path,
        seat_instance_id="si_oldrestart1",
        identity_provider="desks",
        identity_id="r_restart",
        identity_label="flex:engine:lead",
        desks_identity_id="r_restart",
    ))

    result = seat._restart(_args(prompt="fresh start"), registry, RestartTerminal)

    assert result["ok"] is True
    assert result["schema"] == "aura.seat_restart.v1"
    assert result["seat_ref"] == "unitfleet:engineer"
    assert result["old"]["runtime_session_id"] == "old-session"
    assert result["old"]["seat_instance_id"] == "si_oldrestart1"
    assert result["old"]["pid"] == 111
    assert result["new"]["pid"] == 222
    assert result["new"]["seat_instance_id"].startswith("si_")
    assert result["new"]["seat_instance_id"] != "si_oldrestart1"
    assert result["new"]["pane_ref"] == "tmux:unitfleet:%1"
    assert result["same_viewport"] is True
    assert RestartTerminal.killed == []
    assert RestartTerminal.created == []
    assert RestartTerminal.respawned[0][0:3] == (
        "tmux:unitfleet:%1",
        str(tmp_path),
        "python tests/fixtures/fake_runtime.py --name engineer",
    )
    env = RestartTerminal.respawned[0][3]
    assert env["AURA_SEAT"] == "engineer"
    assert env["AURA_FLEET"] == "unitfleet"
    assert env["AURA_LAUNCH_ID"].startswith("aura-launch-")
    assert env["AURA_IDENTITY_PROVIDER"] == "desks"
    assert env["AURA_IDENTITY_ID"] == "r_restart"
    assert env["AURA_IDENTITY_LABEL"] == "flex:engine:lead"
    assert RestartTerminal.respawned[0][4] == [
        "NO_COLOR",
        "AURA_RUNTIME_SESSION_ID",
        "AURA_SESSION_ID",
        "CODEX_THREAD_ID",
        "CODEX_CI",
        "CLAUDE_SESSION_ID",
    ]
    assert RestartTerminal.sent[0][0] == "tmux:unitfleet:%1"
    assert "fresh start" in RestartTerminal.sent[0][1]

    updated = registry.get_agent("engineer", fleet="unitfleet")
    assert updated["name"] == "engineer"
    assert updated["fleet"] == "unitfleet"
    assert updated["previous_runtime_session_id"] == "old-session"
    assert updated["restart_from_session_id"] == "old-session"
    assert updated["runtime_session_id"] is None
    assert updated["pane_ref"] == "tmux:unitfleet:%1"
    assert updated["terminal_ref"] == "unitfleet:engineer"
    assert updated["restart_count"] == 1
    assert updated["seat_instance_id"] == result["new"]["seat_instance_id"]
    assert updated["identity_provider"] == "desks"
    assert updated["identity_id"] == "r_restart"

    rows = [
        json.loads(line)
        for line in (tmp_path / "state" / "registry" / "session-ledger.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert any(row["event"] == "seat_restart" for row in rows)
    seat_history = [row for row in rows if row["event"] == "seat_restarted"][-1]
    assert seat_history["schema"] == "aura.seat_history.v1"
    assert seat_history["before"]["seat_instance_id"] == "si_oldrestart1"
    assert seat_history["after"]["seat_instance_id"] == result["new"]["seat_instance_id"]
    assert seat_history["evidence"]["old_runtime_session_id"] == "old-session"
    assert seat_history["evidence"]["new_pane_ref"] == "tmux:unitfleet:%1"
    assert seat_history["evidence"]["old_seat_instance_id"] == "si_oldrestart1"
    assert seat_history["evidence"]["new_seat_instance_id"] == result["new"]["seat_instance_id"]
    assert seat_history["evidence"]["identity_carried_forward"] is True


def test_restart_uses_native_resume_for_codex(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import seat
    from lib import registry

    RestartTerminal.reset()
    registry.upsert_agent(_record(
        tmp_path,
        runtime="codex",
        command="codex --dangerously-bypass-approvals-and-sandbox",
    ))

    result = seat._restart(_args(prompt="fresh start"), registry, RestartTerminal)

    assert result["ok"] is True
    assert RestartTerminal.respawned[0][2] == f"codex --cd {tmp_path} --dangerously-bypass-approvals-and-sandbox resume old-session"


def test_restart_resolves_codex_cwd_choice_in_same_viewport(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import seat
    from lib import registry

    session_dir = tmp_path / "legacy-role-home"
    current_dir = tmp_path / "unit-root"
    session_dir.mkdir()
    current_dir.mkdir()
    prompt = [
        "Choose working directory to resume this session",
        "",
        f"  1. Use session directory ({session_dir})",
        f"  2. Use current directory ({current_dir})",
        "",
        "  Press enter to continue",
    ]

    RestartTerminal.reset()
    RestartTerminal.captures = [prompt, ["› ready"]]
    registry.upsert_agent(_record(
        current_dir,
        runtime="codex",
        command="codex --dangerously-bypass-approvals-and-sandbox",
        cwd=str(current_dir),
    ))

    result = seat._restart(_args(), registry, RestartTerminal)

    assert result["ok"] is True
    assert result["same_viewport"] is True
    assert result["cwd_choice"]["ok"] is True
    assert result["cwd_choice"]["selected_number"] == "2"
    assert result["cwd_choice"]["verified"] is True
    assert ("tmux:unitfleet:%1", "2", True) in RestartTerminal.sent
    updated = registry.get_agent("engineer", fleet="unitfleet")
    assert updated["cwd_choice"]["selected_path"] == str(current_dir)


def test_restart_dry_run_does_not_mutate_registry_or_terminal(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import seat
    from lib import registry

    RestartTerminal.reset()
    registry.upsert_agent(_record(tmp_path))
    before = registry.get_agent("engineer", fleet="unitfleet")

    result = seat._restart(_args(dry_run=True), registry, RestartTerminal)

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert RestartTerminal.killed == []
    assert RestartTerminal.created == []
    assert registry.get_agent("engineer", fleet="unitfleet") == before


def test_restart_refuses_unreconstructable_command(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import seat
    from lib import registry

    RestartTerminal.reset()
    registry.upsert_agent(_record(tmp_path, command=None))

    result = seat._restart(_args(), registry, RestartTerminal)

    assert result["ok"] is False
    assert result["phase"] == "build_plan"
    assert "recorded command" in result["error"]
    assert RestartTerminal.killed == []


def test_restart_failed_relaunch_keeps_old_seat_history_and_marks_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))

    from commands import seat
    from lib import registry

    RestartTerminal.reset()
    RestartTerminal.launch_ok = False
    registry.upsert_agent(_record(tmp_path))

    result = seat._restart(_args(), registry, RestartTerminal)

    assert result["ok"] is False
    assert result["phase"] == "relaunch_failed"
    assert result["old"]["runtime_session_id"] == "old-session"
    updated = registry.get_agent("engineer", fleet="unitfleet")
    assert updated["status"] == "restart_failed"
    assert updated["runtime_session_id"] == "old-session"
    assert updated["restart_last_failure"]["phase"] == "relaunch_failed"


def test_restart_requires_report_boundary_without_force(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "agents.json"))
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from commands import seat
    from lib import registry

    RestartTerminal.reset()
    registry.upsert_agent(_record(tmp_path))

    result = seat._restart(_args(force=False), registry, RestartTerminal)

    assert result["ok"] is False
    assert result["phase"] == "handoff_missing"
    assert RestartTerminal.killed == []

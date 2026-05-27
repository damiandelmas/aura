import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_package_runtime_findings_report_residue_and_env_drift(tmp_path):
    from lib import runtime_hygiene

    root = tmp_path / "agents" / "i_pkg"
    (root / ".codex").mkdir(parents=True)
    (root / "runtime-session.json").write_text("{}\n", encoding="utf-8")
    (root / "agent.json").write_text("{}\n", encoding="utf-8")
    manifest = {
        "runtime": "omx",
        "env": {
            "CODEX_HOME": "/home/axp/.codex",
            "OMX_ROOT": ".",
            "OMX_TEAM_STATE_ROOT": "../shared-omx-state",
        },
    }

    findings = runtime_hygiene.package_runtime_findings(root, manifest)
    by_code = {}
    for finding in findings:
        by_code.setdefault(finding["code"], []).append(finding)

    assert by_code["package-runtime-residue"][0]["severity"] == "error"
    assert {finding["residue"] for finding in by_code["package-runtime-residue"]} == {
        "agent.json",
        "runtime-session.json",
    }
    assert {finding["env"] for finding in by_code["package-runtime-env-drift"]} == {
        "CODEX_HOME",
        "OMX_TEAM_STATE_ROOT",
    }
    assert [finding["code"] for finding in runtime_hygiene.severe_findings(findings)] == [
        "package-runtime-residue",
        "package-runtime-residue",
        "package-runtime-env-drift",
        "package-runtime-env-drift",
    ]


def test_codex_global_storage_pressure_reports_holders_and_checkpoint_readiness(monkeypatch, tmp_path):
    from lib import runtime_hygiene

    home = tmp_path / ".codex"
    home.mkdir()
    (home / "logs_2.sqlite").write_bytes(b"db")
    (home / "logs_2.sqlite-wal").write_bytes(b"x" * 20)
    (home / "logs_2.sqlite-shm").write_bytes(b"shm")
    monkeypatch.setenv("AURA_CODEX_WAL_WARN_BYTES", "10")
    monkeypatch.setenv("AURA_CODEX_WAL_CRITICAL_BYTES", "100")
    monkeypatch.setattr(runtime_hygiene.shutil, "which", lambda name: "/usr/bin/lsof" if name == "lsof" else None)

    def fake_run(argv, **_kwargs):
        assert argv[0] == "/usr/bin/lsof"
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout="p123\nccodex\nn%s\n" % (home / "logs_2.sqlite-wal"),
            stderr="",
        )

    monkeypatch.setattr(runtime_hygiene.subprocess, "run", fake_run)

    result = runtime_hygiene.codex_global_storage_pressure(home)

    assert result["level"] == "warning"
    assert result["files"]["wal"]["bytes"] == 20
    assert result["holder_check"] == "ok"
    assert result["holder_count"] == 1
    assert result["holders"] == [{"pid": "123", "command": "codex", "paths": [str(home / "logs_2.sqlite-wal")]}]
    assert result["checkpoint_ready"] is False
    assert "sqlite3" in result["safe_operator_hints"][1]


def test_agent_census_includes_runtime_hygiene_and_global_storage(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import agent_packages, runtime_hygiene

    monkeypatch.setattr(
        runtime_hygiene,
        "codex_global_storage_pressure",
        lambda: {"level": "ok", "holder_count": 0, "checkpoint_ready": True},
    )
    agent = agent_packages.create(
        address="flexgraph:chatbot:ops:manager",
        runtime="codex",
        profile="worker",
        cwd=str(tmp_path / "unit"),
        fleet="flexgraph-chatbot",
        seat="manager",
        alias=None,
    )["agent"]
    root = Path(agent["root"])
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["env"]["CODEX_HOME"] = str(tmp_path / "global-codex")
    (root / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    (root / "runtime-session.json").write_text("{}\n", encoding="utf-8")

    result = agent_packages.census()
    package = result["packages"][0]

    assert result["global_storage"]["codex"]["level"] == "ok"
    assert package["runtime_hygiene"][0]["code"] == "package-runtime-residue"
    assert {finding["code"] for finding in package["runtime_hygiene"]} == {
        "package-runtime-residue",
        "package-runtime-env-drift",
    }
    assert "package-runtime-residue" in package["findings"]
    assert "package-runtime-env-drift" in package["findings"]


def test_spawn_preflight_refuses_contaminated_agent_package_before_terminal(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")

    from commands import spawn
    from lib import codex as codex_lib

    unit = tmp_path / "unit"
    unit.mkdir()
    package = tmp_path / "state" / "agents" / "i_pkg"
    (package / ".codex").mkdir(parents=True)
    (package / "manifest.json").write_text(
        json.dumps({"runtime": "codex", "env": {"CODEX_HOME": str(tmp_path / "wrong")}}) + "\n",
        encoding="utf-8",
    )

    class FakeBox:
        root = package
        codex_home = package / ".codex"

        def launch_env(self, _workdir):
            return {"HOME": str(package), "CODEX_HOME": str(self.codex_home)}

        def metadata(self):
            return {"codex_isolation": "aura-agent-package"}

    monkeypatch.setattr(codex_lib, "prepare_box", lambda **_kwargs: FakeBox())

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(*_args, **_kwargs):
            raise AssertionError("preflight should refuse before create_window")

    args = argparse.Namespace(
        name="manager",
        runtime="codex",
        resume_session=None,
        fork_session=None,
        launch_command=None,
        profile=None,
        runtime_profile=None,
        boxed=True,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt=None,
        work=None,
        cwd=str(unit),
        context=None,
        _agent_package={"agent_id": "i_pkg", "root": str(package)},
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is False
    assert result["error"] == "spawn-preflight-failed"
    assert result["spawn_preflight"]["errors"][0]["code"] == "package-runtime-home-contamination"
    assert result["spawn_preflight"]["errors"][0]["finding"]["code"] == "package-runtime-env-drift"


def test_hermes_startup_prompt_is_refused_before_terminal(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(tmp_path / "state" / "registry" / "agents.json"))
    monkeypatch.setenv("AURA_FLEET", "unitfleet")
    home = tmp_path / "home"
    (home / ".hermes").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    from commands import spawn

    unit = tmp_path / "unit"
    unit.mkdir()

    class FakeTerminal:
        SESSION_NAME = "unitfleet"

        @staticmethod
        def create_window(*_args, **_kwargs):
            raise AssertionError("Hermes prompt guard should refuse before create_window")

    args = argparse.Namespace(
        name="hermes-seat",
        runtime="hermes",
        resume_session=None,
        fork_session=None,
        launch_command=None,
        profile=None,
        runtime_profile=None,
        boxed=False,
        omx_profile=None,
        model=None,
        as_pane=True,
        prompt="do work now",
        work=None,
        cwd=str(unit),
        context=None,
    )

    result = spawn._spawn_terminal_runtime(args, FakeTerminal, lambda x: x)

    assert result["ok"] is False
    assert result["error"] == "hermes-startup-prompt-disabled"
    assert result["prompt_requested"] is True


def test_omx_package_box_does_not_pollute_source_cwd(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AURA_OMX_BOX_SETUP", "0")

    from lib import omx, omx_adapter

    source = tmp_path / "source"
    (source / ".git" / "info").mkdir(parents=True)
    package = tmp_path / "state" / "agents" / "i_omx"
    monkeypatch.setattr(
        omx.omx_adapter,
        "apply_adapter",
        lambda **_: omx_adapter.OmxAdapterResult(enabled=True),
    )

    box = omx.prepare_box(
        fleet="fleet",
        seat="seat",
        source_cwd=str(source),
        profile=None,
        root_override=package,
        package_layout=True,
    )
    launch_env = box.launch_env(str(source))

    assert launch_env["CODEX_HOME"] == str(package / ".codex")
    assert launch_env["OMX_ROOT"] == str(package.resolve())
    assert launch_env["OMX_TEAM_STATE_ROOT"] == str(package / ".omx" / "state")
    assert not (source / ".codex").exists()
    assert not (source / ".omx").exists()
    assert not (source / ".git" / "info" / "exclude").exists()


def test_global_aura_view_fleets_runs_from_clean_env(tmp_path):
    home = tmp_path / "home"
    state = tmp_path / "state"
    env = {
        "HOME": str(home),
        "USER": "tester",
        "LOGNAME": "tester",
        "PATH": os.environ.get("PATH", ""),
        "AURA_STATE_DIR": str(state),
        "AURA_REGISTRY_PATH": str(state / "registry" / "seats.json"),
    }

    result = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "aura"), "view", "fleets"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["schema"] == "aura.view.fleets.v1"

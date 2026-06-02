import importlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _reload_modules(*names):
    for name in names:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
        else:
            importlib.import_module(name)
    return [sys.modules[name] for name in names]


def test_default_state_root_is_home_dot_aura(monkeypatch, tmp_path):
    monkeypatch.delenv("AURA_STATE_DIR", raising=False)
    monkeypatch.delenv("AURA_REGISTRY_PATH", raising=False)
    monkeypatch.delenv("AURA_DELIVERY_LOG", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    registry, delivery = _reload_modules("lib.registry", "lib.delivery")

    expected_root = (tmp_path / "home" / ".aura").resolve()
    assert registry.registry_path() == expected_root / "registry" / "seats.json"
    assert delivery.delivery_log_path() == expected_root / "registry" / "deliveries.jsonl"


def test_aura_state_dir_overrides_default_paths(monkeypatch, tmp_path):
    root = tmp_path / "custom-state"
    monkeypatch.setenv("AURA_STATE_DIR", str(root))
    monkeypatch.delenv("AURA_REGISTRY_PATH", raising=False)
    monkeypatch.delenv("AURA_DELIVERY_LOG", raising=False)

    registry, delivery = _reload_modules("lib.registry", "lib.delivery")

    assert registry.registry_path() == root / "registry" / "seats.json"
    assert delivery.delivery_log_path() == root / "registry" / "deliveries.jsonl"


def test_workspace_state_uses_global_state_root_with_stable_workspace_key(monkeypatch, tmp_path):
    root = tmp_path / "state"
    workdir = tmp_path / "projects" / "runway"
    workdir.mkdir(parents=True)
    monkeypatch.setenv("AURA_STATE_DIR", str(root))

    workspace_state = _reload_modules("lib.workspace_state")[0]

    key = workspace_state.workspace_key(workdir)
    assert key.startswith("runway-")
    assert workspace_state.workspace_state_dir(workdir) == root / "workspaces" / key
    assert workspace_state.workspace_session_log(workdir) == root / "workspaces" / key / "sessions.jsonl"
    assert workspace_state.latest_session_path(workdir) == root / "workspaces" / key / "latest-session.json"

    record = workspace_state.append_session_record(workdir, {"event": "spawn", "seat": "lead"})
    workspace_state.write_latest_session(workdir, record)

    rows = [
        json.loads(line)
        for line in workspace_state.workspace_session_log(workdir).read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["workspace_root"] == str(workdir)
    assert rows[-1]["workspace_key"] == key
    assert json.loads(workspace_state.latest_session_path(workdir).read_text(encoding="utf-8"))["seat"] == "lead"
    assert json.loads(workspace_state.workspace_metadata_path(workdir).read_text(encoding="utf-8"))["workspace_root"] == str(workdir)


def test_workspace_state_does_not_write_project_local_state(monkeypatch, tmp_path):
    root = tmp_path / "state"
    workdir = tmp_path / "projects" / "runway"
    workdir.mkdir(parents=True)
    monkeypatch.setenv("AURA_STATE_DIR", str(root))

    workspace_state = _reload_modules("lib.workspace_state")[0]

    record = workspace_state.append_session_record(workdir, {"event": "spawn", "seat": "lead"})
    workspace_state.write_latest_session(workdir, record)

    assert not (workdir / ".aura" / "state").exists()
    assert not (workdir / ".aura").exists()


def test_explicit_registry_and_delivery_overrides_still_win(monkeypatch, tmp_path):
    registry_path = tmp_path / "x" / "agents.json"
    delivery_path = tmp_path / "y" / "deliveries.jsonl"
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "custom-state"))
    monkeypatch.setenv("AURA_REGISTRY_PATH", str(registry_path))
    monkeypatch.setenv("AURA_DELIVERY_LOG", str(delivery_path))

    registry, delivery = _reload_modules("lib.registry", "lib.delivery")

    assert registry.registry_path() == registry_path
    assert delivery.delivery_log_path() == delivery_path


def test_sense_writes_under_default_home_dot_aura(monkeypatch, tmp_path):
    monkeypatch.delenv("AURA_STATE_DIR", raising=False)
    monkeypatch.delenv("AURA_REGISTRY_PATH", raising=False)
    monkeypatch.delenv("AURA_DELIVERY_LOG", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    sense_module = _reload_modules("commands.sense")[0]
    record = {"schema": "aura.sense.v1", "seat": "seat1", "type": "sense"}

    sense_module._write_sense_record("seat1", record)

    root = (tmp_path / "home" / ".aura").resolve()
    events = root / "seats" / "seat1" / "sense" / "events.jsonl"
    latest = root / "seats" / "seat1" / "sense" / "latest.json"
    assert events.exists()
    assert latest.exists()
    assert json.loads(latest.read_text(encoding="utf-8"))["seat"] == "seat1"

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_lifecycle_hook_injection_recovers_from_non_object_settings(tmp_path):
    from lib import hooks

    workdir = tmp_path / "work"
    settings_dir = workdir / ".claude"
    settings_dir.mkdir(parents=True)
    settings_path = settings_dir / "settings.json"
    settings_path.write_text(json.dumps(["not", "an", "object"]) + "\n", encoding="utf-8")

    result = hooks.inject(str(workdir))
    settings = json.loads(settings_path.read_text(encoding="utf-8"))

    assert result["hooks"] == "injected"
    assert set(result["events"]) == {"SessionStart", "Stop"}
    assert set(settings["hooks"]) == {"SessionStart", "Stop"}


def test_lifecycle_hook_injection_recovers_from_malformed_hooks_section(tmp_path):
    from lib import hooks

    workdir = tmp_path / "work"
    settings_dir = workdir / ".claude"
    settings_dir.mkdir(parents=True)
    settings_path = settings_dir / "settings.json"
    settings_path.write_text(json.dumps({"hooks": "bad", "keep": "value"}) + "\n", encoding="utf-8")

    result = hooks.inject(str(workdir))
    settings = json.loads(settings_path.read_text(encoding="utf-8"))

    assert result["hooks"] == "injected"
    assert settings["keep"] == "value"
    assert isinstance(settings["hooks"]["SessionStart"], list)
    assert isinstance(settings["hooks"]["Stop"], list)


def test_lifecycle_hook_injection_recovers_from_non_list_event_entries(tmp_path):
    from lib import hooks

    workdir = tmp_path / "work"
    settings_dir = workdir / ".claude"
    settings_dir.mkdir(parents=True)
    settings_path = settings_dir / "settings.json"
    settings_path.write_text(
        json.dumps({"hooks": {"SessionStart": {"hooks": []}, "Stop": None}}) + "\n",
        encoding="utf-8",
    )

    result = hooks.inject(str(workdir))
    settings = json.loads(settings_path.read_text(encoding="utf-8"))

    assert result["hooks"] == "injected"
    assert isinstance(settings["hooks"]["SessionStart"], list)
    assert isinstance(settings["hooks"]["Stop"], list)
    assert hooks.AURA_BIN in settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]


def test_lifecycle_hook_injection_is_idempotent_with_valid_settings(tmp_path):
    from lib import hooks

    workdir = tmp_path / "work"
    workdir.mkdir()

    first = hooks.inject(str(workdir))
    second = hooks.inject(str(workdir))
    settings = json.loads((workdir / ".claude" / "settings.json").read_text(encoding="utf-8"))

    assert first["hooks"] == "injected"
    assert second["hooks"] == "already-present"
    assert len(settings["hooks"]["SessionStart"]) == 1
    assert len(settings["hooks"]["Stop"]) == 1

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _fake_hooks_config(native_hook: Path) -> dict:
    command = f'{shlex.quote("/usr/bin/node")} {shlex.quote(str(native_hook))}'
    return {
        "state": {
            "custom-user-hook": {"trusted_hash": "sha256:user"},
        },
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup|resume|clear",
                    "hooks": [{"type": "command", "command": command}],
                }
            ],
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": command}],
                }
            ],
            "PostToolUse": [{"hooks": [{"type": "command", "command": command}]}],
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": command}]}],
            "PreCompact": [{"hooks": [{"type": "command", "command": command}]}],
            "PostCompact": [{"hooks": [{"type": "command", "command": command}]}],
            "Stop": [{"hooks": [{"type": "command", "command": command, "timeout": 30}]}],
        },
    }


def test_omx_adapter_rewrites_boxed_hooks_and_trust_state(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_OMX_ADAPTER_PROBE", "0")

    from lib import omx_adapter

    root = tmp_path / "box"
    codex_home = root / "codex-home"
    runtime = root / "runtime"
    package_root = tmp_path / "pkg"
    native_hook = package_root / "dist" / "scripts" / "codex-native-hook.js"
    native_hook.parent.mkdir(parents=True)
    native_hook.write_text("console.log('hook')\n", encoding="utf-8")
    codex_home.mkdir(parents=True)
    runtime.mkdir(parents=True)
    hooks_path = codex_home / "hooks.json"
    config_path = codex_home / "config.toml"
    hooks_path.write_text(json.dumps(_fake_hooks_config(native_hook), indent=2) + "\n", encoding="utf-8")
    config_path.write_text(
        "model = 'unit'\n\n"
        "# OMX-owned Codex hook trust state\n"
        "[hooks.state.\"old\"]\n"
        "trusted_hash = \"sha256:old\"\n"
        "# End OMX-owned Codex hook trust state\n",
        encoding="utf-8",
    )

    result = omx_adapter.apply_adapter(root=root, codex_home=codex_home, runtime=runtime)

    assert result.enabled is True
    assert result.error is None
    assert result.wrapper_path.name == "aura-omx-native-hook"
    assert result.wrapper_path.is_file()
    assert os.access(result.wrapper_path, os.X_OK)
    wrapper = result.wrapper_path.read_text(encoding="utf-8")
    assert "codex_bind_hook.py" in wrapper
    assert "aura_keeper_hook.py" in wrapper
    assert "payload_file" in wrapper
    assert "AURA_OMX_NATIVE_HOOK" in wrapper
    assert not (runtime / "bin" / "aura-omx-native-hook").exists()
    assert result.native_hook_path == native_hook
    assert result.hooks_rewritten is True
    assert result.trust_state_updated is True
    assert result.config_trust_updated is True
    assert result.native_probe == "skipped"
    assert result.hud_probe == "skipped"

    hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
    wrapper_command = f"AURA_OMX_NATIVE_HOOK={shlex.quote(str(native_hook))} {shlex.quote(str(result.wrapper_path))}"
    for entries in hooks["hooks"].values():
        for entry in entries:
            for hook in entry["hooks"]:
                assert hook["command"] == wrapper_command
    assert hooks["state"]["custom-user-hook"] == {"trusted_hash": "sha256:user"}
    managed_state = {key: value for key, value in hooks["state"].items() if key.startswith(str(hooks_path))}
    assert len(managed_state) == 7
    assert all(value["trusted_hash"].startswith("sha256:") for value in managed_state.values())

    config = config_path.read_text(encoding="utf-8")
    assert "# Aura OMX adapter-owned Codex hook trust state" in config
    assert "# OMX-owned Codex hook trust state" not in config
    assert str(hooks_path) in config
    assert "sha256:old" not in config
    assert not (root / "aura-omx-adapter.json").exists()

    second = omx_adapter.apply_adapter(root=root, codex_home=codex_home, runtime=runtime)

    assert second.enabled is True
    assert second.error is None
    assert second.hooks_rewritten is False
    assert second.native_hook_path == native_hook
    assert second.wrapper_path == result.wrapper_path


def test_omx_native_wrapper_derives_roots_from_codex_home(tmp_path):
    wrapper = ROOT / "cli" / "hooks" / "aura-omx-native-hook"
    home = tmp_path / "home"
    codex_home = tmp_path / "box" / "codex-home"
    native_hook = tmp_path / "native-hook.py"
    home.mkdir()
    codex_home.mkdir(parents=True)
    native_hook.write_text(
        "import json, os, sys\n"
        "sys.stdin.read()\n"
        "print(json.dumps({\n"
        "    'OMX_ROOT': os.environ.get('OMX_ROOT'),\n"
        "    'OMX_STATE_ROOT': os.environ.get('OMX_STATE_ROOT'),\n"
        "    'OMX_TEAM_STATE_ROOT': os.environ.get('OMX_TEAM_STATE_ROOT'),\n"
        "}))\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(wrapper)],
        input=json.dumps({"hook_event_name": "UserPromptSubmit"}),
        text=True,
        capture_output=True,
        timeout=10,
        env={
            "HOME": str(home),
            "PATH": os.environ.get("PATH", ""),
            "CODEX_HOME": str(codex_home),
            "AURA_OMX_NATIVE_HOOK": str(native_hook),
            "AURA_OMX_NODE": sys.executable,
        },
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "OMX_ROOT": str(codex_home / "omx-root"),
        "OMX_STATE_ROOT": str(codex_home / "omx-root"),
        "OMX_TEAM_STATE_ROOT": str(codex_home / "omx-root" / ".omx" / "state"),
    }


def test_omx_native_wrapper_preserves_existing_roots(tmp_path):
    wrapper = ROOT / "cli" / "hooks" / "aura-omx-native-hook"
    home = tmp_path / "home"
    existing_root = tmp_path / "existing-omx"
    native_hook = tmp_path / "native-hook.py"
    home.mkdir()
    native_hook.write_text(
        "import json, os, sys\n"
        "sys.stdin.read()\n"
        "print(json.dumps({\n"
        "    'OMX_ROOT': os.environ.get('OMX_ROOT'),\n"
        "    'OMX_STATE_ROOT': os.environ.get('OMX_STATE_ROOT'),\n"
        "    'OMX_TEAM_STATE_ROOT': os.environ.get('OMX_TEAM_STATE_ROOT'),\n"
        "}))\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [str(wrapper)],
        input=json.dumps({"hook_event_name": "UserPromptSubmit"}),
        text=True,
        capture_output=True,
        timeout=10,
        env={
            "HOME": str(home),
            "PATH": os.environ.get("PATH", ""),
            "CODEX_HOME": str(tmp_path / ".codex"),
            "OMX_ROOT": str(existing_root),
            "AURA_OMX_NATIVE_HOOK": str(native_hook),
            "AURA_OMX_NODE": sys.executable,
        },
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "OMX_ROOT": str(existing_root),
        "OMX_STATE_ROOT": None,
        "OMX_TEAM_STATE_ROOT": None,
    }


def test_omx_native_wrapper_triggers_keeper_for_stop_payload(tmp_path):
    wrapper = ROOT / "cli" / "hooks" / "aura-omx-native-hook"
    home = tmp_path / "home"
    codex_home = tmp_path / "agent" / ".codex"
    native_hook = tmp_path / "native-hook.py"
    keeper_hook_cmd = tmp_path / "keeper-hook-ok.py"
    package_root = codex_home.parent
    home.mkdir()
    codex_home.mkdir(parents=True)
    (package_root / "manifest.json").write_text('{"runtime":"omx"}\n', encoding="utf-8")
    native_hook.write_text("import sys\nsys.stdin.read()\nprint('{}')\n", encoding="utf-8")
    keeper_hook_cmd.write_text("print('{\"ok\": true, \"pid\": 12345}')\n", encoding="utf-8")

    result = subprocess.run(
        [str(wrapper)],
        input=json.dumps({"hook_event_name": "Stop", "session_id": "019e-session", "context_percent": 60}),
        text=True,
        capture_output=True,
        timeout=10,
        env={
            "HOME": str(home),
            "PATH": os.environ.get("PATH", ""),
            "CODEX_HOME": str(codex_home),
            "AURA_OMX_NATIVE_HOOK": str(native_hook),
            "AURA_OMX_NODE": sys.executable,
            "AURA_AGENT_PACKAGE_ID": "i_pkg",
            "AURA_AGENT_PACKAGE_ROOT": str(package_root),
            "AURA_FLEET": "fleet",
            "AURA_SEAT": "worker",
            "AURA_KEEPER_HOOK_COMMAND": f"{sys.executable} {keeper_hook_cmd}",
        },
    )

    assert result.returncode == 0, result.stderr
    state = json.loads((package_root / "memories" / ".hook-state" / "aura-keeper-hook.json").read_text(encoding="utf-8"))
    assert state["sessions"]["019e-session"]["fired_boundaries"] == [25, 50]
    launch_log = package_root / "memories" / ".hook-state" / "keeper-launch.log"
    assert launch_log.is_file()


def test_omx_adapter_path_prefix_keeps_path_unchanged(tmp_path):
    from lib import omx_adapter

    runtime = tmp_path / "runtime"
    assert omx_adapter.adapter_path_prefix(runtime, "/usr/bin") == "/usr/bin"


def test_omx_adapter_path_prefix_preserves_legacy_runtime_bin(tmp_path):
    from lib import omx_adapter

    runtime = tmp_path / "runtime"
    (runtime / "bin").mkdir(parents=True)

    assert omx_adapter.adapter_path_prefix(runtime, "/usr/bin") == f"{runtime / 'bin'}:/usr/bin"

import json
import os
import shlex
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
    assert result.wrapper_path == runtime / "bin" / "aura-omx-native-hook"
    assert result.wrapper_path.is_file()
    assert os.access(result.wrapper_path, os.X_OK)
    assert result.native_hook_path == native_hook
    assert result.hooks_rewritten is True
    assert result.trust_state_updated is True
    assert result.config_trust_updated is True
    assert result.native_probe == "skipped"
    assert result.hud_probe == "skipped"

    hooks = json.loads(hooks_path.read_text(encoding="utf-8"))
    wrapper_command = shlex.quote(str(result.wrapper_path))
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
    marker = json.loads((root / "aura-omx-adapter.json").read_text(encoding="utf-8"))
    assert marker["wrapper"] == str(result.wrapper_path)
    assert marker["native_hook"] == str(native_hook)

    second = omx_adapter.apply_adapter(root=root, codex_home=codex_home, runtime=runtime)

    assert second.enabled is True
    assert second.error is None
    assert second.hooks_rewritten is False
    assert second.native_hook_path == native_hook
    assert second.wrapper_path == result.wrapper_path


def test_omx_adapter_path_prefix_prepends_runtime_bin(tmp_path):
    from lib import omx_adapter

    runtime = tmp_path / "runtime"
    assert omx_adapter.adapter_path_prefix(runtime, "/usr/bin") == f"{runtime / 'bin'}:/usr/bin"

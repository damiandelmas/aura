import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))
HOOK_PATH = ROOT / "cli" / "hooks" / "aura_compact_recovery_hook.py"


def _load_hook():
    spec = importlib.util.spec_from_file_location("aura_compact_recovery_hook_test", HOOK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _write_doc(path: Path) -> None:
    path.write_text(
        "# Compact Recovery\n\n"
        "- Confirm compact recovery fired.\n"
        "- Read this document before continuing.\n",
        encoding="utf-8",
    )


def test_codex_postcompact_injects_aura_followup(monkeypatch, tmp_path, capsys):
    hook = _load_hook()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    doc = codex_home / "AURA_COMPACT_RECOVERY.md"
    _write_doc(doc)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"ok": True}) + "\n", stderr="")

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("AURA_RUNTIME", "codex")
    monkeypatch.setenv("AURA_FLEET", "compact-test")
    monkeypatch.setenv("AURA_SEAT", "codex-seat")
    monkeypatch.setenv("CODEX_THREAD_ID", "session-1")
    monkeypatch.setattr(hook.subprocess, "run", fake_run)

    assert hook._handle_postcompact({"compact_summary": "summary text"}) == 0

    output = json.loads(capsys.readouterr().out)
    assert "injected follow-up context" in output["systemMessage"]
    assert not (codex_home / "aura-compact-recovery" / "pending-post-compact.json").exists()
    injected = list((codex_home / "aura-compact-recovery").glob("injected-*.json"))
    assert injected
    command = calls[0][0]
    message = command[3]
    assert command[:3] == ["/home/axp/.local/bin/aura", "send", "compact-test:codex-seat"]
    assert "--as-service" in command
    assert "compact-recovery" in command
    assert "--force" in command
    assert "--defer-if-busy" not in command
    assert "AURA_COMPACT_RECOVERY" in message
    assert "Compact Recovery" in message
    assert "summary text" in message


def test_codex_postcompact_treats_deferred_aura_send_as_handled(monkeypatch, tmp_path, capsys):
    hook = _load_hook()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    doc = codex_home / "AURA_COMPACT_RECOVERY.md"
    _write_doc(doc)

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            1,
            stdout=json.dumps({
                "ok": True,
                "blocked": True,
                "deferred": True,
                "reason": "target-busy",
            }) + "\n",
            stderr="",
        )

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("AURA_RUNTIME", "codex")
    monkeypatch.setenv("AURA_FLEET", "compact-test")
    monkeypatch.setenv("AURA_SEAT", "codex-seat")
    monkeypatch.setenv("CODEX_THREAD_ID", "session-1")
    monkeypatch.setattr(hook.subprocess, "run", fake_run)

    assert hook._handle_postcompact({"compact_summary": "summary text"}) == 0

    output = json.loads(capsys.readouterr().out)
    assert "deferred follow-up context" in output["systemMessage"]
    assert not (codex_home / "aura-compact-recovery" / "pending-post-compact.json").exists()
    records = list((codex_home / "aura-compact-recovery").glob("deferred-*.json"))
    assert records
    record = json.loads(records[0].read_text(encoding="utf-8"))
    assert record["state"] == "deferred"
    assert record["aura_send"]["ok"] is True


def test_codex_userpromptsubmit_surfaces_pending_recovery_when_injection_disabled(monkeypatch, tmp_path, capsys):
    hook = _load_hook()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    doc = codex_home / "AURA_COMPACT_RECOVERY.md"
    _write_doc(doc)

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("AURA_RUNTIME", "codex")
    monkeypatch.setenv("AURA_FLEET", "compact-test")
    monkeypatch.setenv("AURA_SEAT", "codex-seat")
    monkeypatch.setenv("AURA_COMPACT_RECOVERY_INJECT", "0")

    assert hook._handle_postcompact({"compact_summary": "summary text"}) == 0
    stored = json.loads(capsys.readouterr().out)
    assert "stored pending context" in stored["systemMessage"]

    assert hook._handle_user_prompt_submit({}) == 0
    output = json.loads(capsys.readouterr().out)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert output["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "AURA_COMPACT_RECOVERY" in context
    assert "Compact Recovery" in context
    assert not (codex_home / "aura-compact-recovery" / "pending-post-compact.json").exists()
    assert list((codex_home / "aura-compact-recovery").glob("consumed-*.json"))


def test_codex_userpromptsubmit_preserves_pending_compact_summary(monkeypatch, tmp_path, capsys):
    hook = _load_hook()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    doc = codex_home / "AURA_COMPACT_RECOVERY.md"
    _write_doc(doc)

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("AURA_RUNTIME", "codex")
    monkeypatch.setenv("AURA_COMPACT_RECOVERY_INJECT", "0")

    assert hook._handle_postcompact({"compact_summary": "original compact summary"}) == 0
    capsys.readouterr()

    assert hook._handle_user_prompt_submit({"prompt": "next user prompt"}) == 0
    output = json.loads(capsys.readouterr().out)
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "original compact summary" in context


def test_codex_postcompact_without_aura_target_leaves_pending(monkeypatch, tmp_path, capsys):
    hook = _load_hook()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    doc = codex_home / "AURA_COMPACT_RECOVERY.md"
    _write_doc(doc)

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("AURA_RUNTIME", "codex")
    monkeypatch.delenv("AURA_FLEET", raising=False)
    monkeypatch.delenv("AURA_SEAT", raising=False)

    assert hook._handle_postcompact({"compact_summary": "summary text"}) == 0

    output = json.loads(capsys.readouterr().out)
    assert "stored pending context" in output["systemMessage"]
    pending = codex_home / "aura-compact-recovery" / "pending-post-compact.json"
    record = json.loads(pending.read_text(encoding="utf-8"))
    assert record["state"] == "pending"
    assert record["aura_send"]["reason"] == "missing-target"
    assert not list((codex_home / "aura-compact-recovery").glob("injected-*.json"))


def test_codex_postcompact_aura_send_exception_leaves_pending(monkeypatch, tmp_path, capsys):
    hook = _load_hook()
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    doc = codex_home / "AURA_COMPACT_RECOVERY.md"
    _write_doc(doc)

    def fake_run(command, **kwargs):
        raise RuntimeError("send failed")

    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.setenv("AURA_RUNTIME", "codex")
    monkeypatch.setenv("AURA_FLEET", "compact-test")
    monkeypatch.setenv("AURA_SEAT", "codex-seat")
    monkeypatch.setattr(hook.subprocess, "run", fake_run)

    assert hook._handle_postcompact({}) == 0

    output = json.loads(capsys.readouterr().out)
    assert "stored pending context" in output["systemMessage"]
    record = json.loads((codex_home / "aura-compact-recovery" / "pending-post-compact.json").read_text(encoding="utf-8"))
    assert record["state"] == "pending"
    assert record["aura_send"]["reason"] == "aura-send-exception"
    assert "send failed" in record["aura_send"]["error"]


def test_hook_main_ignores_malformed_stdin(monkeypatch, tmp_path, capsys):
    hook = _load_hook()
    state_dir = tmp_path / "state"

    monkeypatch.setenv("AURA_COMPACT_RECOVERY_STATE_DIR", str(state_dir))
    monkeypatch.setenv("AURA_COMPACT_RECOVERY_INJECT", "0")
    monkeypatch.setattr(hook.sys, "argv", ["hook", "PostCompact"])
    monkeypatch.setattr(hook.sys, "stdin", type("FakeStdin", (), {"read": lambda self: "{not-json"})())

    assert hook.main() == 0

    output = json.loads(capsys.readouterr().out)
    assert "stored pending context" in output["systemMessage"]
    assert (state_dir / "pending-post-compact.json").is_file()


def test_claude_compact_recovery_preserves_existing_settings(tmp_path):
    from lib import hooks

    workdir = tmp_path / "work"
    settings_dir = workdir / ".claude"
    settings_dir.mkdir(parents=True)
    doc = workdir / "AURA_COMPACT_RECOVERY.md"
    _write_doc(doc)
    settings = {
        "permissions": {"allow": ["Bash(pytest:*)"]},
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "startup",
                    "hooks": [{"type": "command", "command": "echo startup"}],
                },
                {
                    "matcher": "compact",
                    "hooks": [{"type": "command", "command": "echo existing compact"}],
                },
            ],
            "Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}],
        },
    }
    (settings_dir / "settings.json").write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")

    result = hooks.inject_compact_recovery(str(workdir), str(doc))
    merged = json.loads((settings_dir / "settings.json").read_text(encoding="utf-8"))

    assert result["hooks"] == "injected"
    assert merged["permissions"] == settings["permissions"]
    assert merged["hooks"]["Stop"] == settings["hooks"]["Stop"]
    compact_entries = [entry for entry in merged["hooks"]["SessionStart"] if entry.get("matcher") == "compact"]
    assert len(compact_entries) == 2
    assert compact_entries[0]["hooks"][0]["command"] == "echo existing compact"
    assert "aura_compact_recovery_hook.py" in compact_entries[1]["hooks"][0]["command"]


def test_claude_compact_handler_renders_unreadable_document(monkeypatch, tmp_path, capsys):
    hook = _load_hook()
    missing_doc = tmp_path / "missing.md"

    monkeypatch.setenv("AURA_COMPACT_RECOVERY_DOC", str(missing_doc))
    monkeypatch.setenv("AURA_RUNTIME", "claude-code")

    assert hook._handle_claude_compact({"compact_summary": "claude summary"}) == 0

    context = capsys.readouterr().out
    assert "Runtime: claude-code" in context
    assert "claude summary" in context
    assert "Recovery document was not readable" in context


def test_hook_event_detection_accepts_payload_variants(monkeypatch):
    hook = _load_hook()

    monkeypatch.setattr(hook.sys, "argv", ["hook"])
    monkeypatch.delenv("CODEX_HOOK_EVENT", raising=False)
    assert hook._event({"hook_event_name": "PostCompact"}) == "PostCompact"
    assert hook._event({"hookEventName": "UserPromptSubmit"}) == "UserPromptSubmit"
    assert hook._event({"event": "ClaudeCompact"}) == "ClaudeCompact"

    monkeypatch.setenv("CODEX_HOOK_EVENT", "PostCompact")
    assert hook._event({}) == "PostCompact"

    monkeypatch.setattr(hook.sys, "argv", ["hook", "UserPromptSubmit"])
    assert hook._event({"hook_event_name": "PostCompact"}) == "UserPromptSubmit"


def test_hook_compact_summary_detection_accepts_payload_variants():
    hook = _load_hook()

    assert hook._compact_summary({"compact_summary": "snake"}) == "snake"
    assert hook._compact_summary({"compactSummary": "camel"}) == "camel"
    assert hook._compact_summary({"summary": "plain"}) == "plain"
    assert hook._compact_summary({"payload": {"compact_summary": "nested snake"}}) == "nested snake"
    assert hook._compact_summary({"payload": {"summary": "nested plain"}}) == "nested plain"
    assert hook._compact_summary({"payload": "bad"}) is None


def test_compact_recovery_document_path_prefers_explicit_env(monkeypatch, tmp_path):
    from lib import compact_recovery

    explicit = tmp_path / "explicit.md"
    runtime_home = tmp_path / "runtime-home"
    codex_home = tmp_path / "codex-home"

    monkeypatch.setenv("AURA_COMPACT_RECOVERY_DOC", str(explicit))
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    assert compact_recovery.recovery_document_path(runtime_home=runtime_home) == explicit


def test_claude_compact_recovery_skips_missing_workdir(tmp_path):
    from lib import hooks

    result = hooks.inject_compact_recovery(str(tmp_path / "missing"), str(tmp_path / "doc.md"))

    assert result["hooks"] == "skipped"
    assert "workdir not a dir" in result["reason"]


def test_claude_compact_recovery_injects_sessionstart_compact_matcher(tmp_path):
    from lib import hooks

    workdir = tmp_path / "work"
    workdir.mkdir()
    doc = workdir / "AURA_COMPACT_RECOVERY.md"
    _write_doc(doc)

    result = hooks.inject_compact_recovery(str(workdir), str(doc))
    second = hooks.inject_compact_recovery(str(workdir), str(doc))

    settings = json.loads((workdir / ".claude" / "settings.json").read_text(encoding="utf-8"))
    entries = settings["hooks"]["SessionStart"]
    compact_entries = [entry for entry in entries if entry.get("matcher") == "compact"]
    assert result["hooks"] == "injected"
    assert second["hooks"] == "already-present"
    assert len(compact_entries) == 1
    command = compact_entries[0]["hooks"][0]["command"]
    assert "AURA_COMPACT_RECOVERY_DOC=" in command
    assert "aura_compact_recovery_hook.py" in command
    assert "ClaudeCompact" in command

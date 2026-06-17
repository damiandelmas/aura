"""Continuity fixes for claude-code: allocate-on-resume + statusline FK install.

Claude resume ROTATES the session id (it forks from a leaf), so binding the typed
--resume-session id binds one the process never runs. The fix resumes INTO a chosen
new id via the repo wrapper (`--session-id <new> --fork-session`), born-bound like a
fresh spawn. Codex (id-preserving) is unchanged. Separately, hooks.inject installs a
repo-owned statusline that writes the pane->session FK so fresh seats are resolvable.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))

from lib import runtimes, hooks  # noqa: E402


# --------------------------------------------------------------------------
# build_resume_command — allocate-on-resume for claude, unchanged for codex
# --------------------------------------------------------------------------

def test_claude_resume_allocates_into_new_id_via_fork():
    cmd = runtimes.build_resume_command("claude-code", "OLD-SID", fork_into="NEW-SID")
    assert "aura-claude-r.sh" in cmd          # repo-owned wrapper, not bare claude-r
    assert "OLD-SID" in cmd                    # resume from the old id
    assert "--session-id" in cmd and "NEW-SID" in cmd
    assert "--fork-session" in cmd             # the flag that makes resume-into-a-chosen-id work


def test_claude_plain_resume_has_no_fork_flags():
    cmd = runtimes.build_resume_command("claude-code", "OLD-SID")
    assert "aura-claude-r.sh" in cmd and "OLD-SID" in cmd
    assert "--fork-session" not in cmd and "--session-id" not in cmd


def test_codex_resume_unchanged_and_id_preserving():
    cmd = runtimes.build_resume_command("codex", "OLD-SID")
    assert "aura-claude-r.sh" not in cmd       # codex keeps its own resume path
    assert "resume" in cmd and "OLD-SID" in cmd


def test_resume_wrapper_is_shipped_and_executable():
    wrapper = ROOT / "cli" / "hooks" / "aura-claude-r.sh"
    assert wrapper.exists()
    assert os.access(wrapper, os.X_OK)


# --------------------------------------------------------------------------
# hooks.inject — installs the statusline FK writer, idempotent + non-clobbering
# --------------------------------------------------------------------------

def test_inject_installs_statusline_fk_writer():
    wd = tempfile.mkdtemp()
    try:
        res = hooks.inject(wd)
        assert res.get("statusline") is True
        settings = json.loads((Path(wd) / ".claude" / "settings.json").read_text())
        assert "aura-claude-statusline.sh" in settings["statusLine"]["command"]
    finally:
        import shutil
        shutil.rmtree(wd, ignore_errors=True)


def test_inject_statusline_is_idempotent_and_non_clobbering():
    wd = tempfile.mkdtemp()
    try:
        hooks.inject(wd)
        again = hooks.inject(wd)
        assert again.get("statusline") is False     # not re-written
        # an explicit project statusLine is preserved, never clobbered
        sp = Path(wd) / ".claude" / "settings.json"
        data = json.loads(sp.read_text())
        data["statusLine"] = {"type": "command", "command": "my-own-line"}
        sp.write_text(json.dumps(data))
        hooks.inject(wd)
        assert json.loads(sp.read_text())["statusLine"]["command"] == "my-own-line"
    finally:
        import shutil
        shutil.rmtree(wd, ignore_errors=True)

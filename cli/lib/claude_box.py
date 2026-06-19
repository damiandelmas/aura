"""Boxed claude-code home preparation for package-native agents.

The claude analog of ``codex.prepare_box``. A claude package body carries its
runtime state at ``<package>/.claude`` and launches with
``CLAUDE_CONFIG_DIR=<package>/.claude`` (set from the manifest env). That
relocates claude's config + ``projects/<encoded-cwd>/`` session transcripts +
statusline state under the package root, which is what makes the body durable
and lets ``bind_guard.body_gates`` hold (native_state_ref under the package
root).

This module owns only the per-seat seeding: ensure the box dir, symlink the
source auth so the boxed seat is authenticated, and install the statusline
FK-writer + lifecycle hooks into the box's own ``settings.json``. Session
binding itself is born-bound at spawn (allocated ``--session-id``); the
statusline pane->session map (keyed by ``%N``, AURA-state-rooted) resolves the
live id independently of the boxed home.
"""

from __future__ import annotations

import os
from pathlib import Path

# Auth material claude keeps at the config-dir root. Symlinked (not copied) so a
# token refresh in the source home stays current inside the box — the same
# discipline boxed Codex uses for its auth files.
_AUTH_FILES = (".credentials.json",)


def _source_claude_home() -> Path:
    return Path(
        os.environ.get("AURA_CLAUDE_SOURCE_CONFIG_DIR")
        or os.environ.get("CLAUDE_CONFIG_DIR")
        or (Path.home() / ".claude")
    ).expanduser()


def _seed_onboarding(claude_home: Path, source_home: Path, workdir: str | Path | None) -> dict[str, object]:
    """Pre-complete Claude Code's first-run onboarding in the boxed config.

    A fresh CLAUDE_CONFIG_DIR otherwise blocks on the theme picker, the login
    picker, the bypass-permissions acceptance, and the per-folder trust prompt —
    none of which a detached managed seat can answer, so the initial-argv prompt
    never lands. Seeding ``.claude.json`` preempts all four (the symlinked
    ``.credentials.json`` supplies the actual auth, so login is skipped once
    onboarding reads complete). Merge-only: never clobber a key claude already
    wrote, so a seat that has truly onboarded keeps its own state.
    """
    import json

    path = claude_home / ".claude.json"
    data: dict[str, object] = {}
    if path.exists():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            data = parsed if isinstance(parsed, dict) else {}
        except Exception:
            data = {}

    theme = data.get("theme")
    if not theme:
        try:
            src = json.loads((source_home / ".claude.json").read_text(encoding="utf-8"))
            theme = src.get("theme") if isinstance(src, dict) else None
        except Exception:
            theme = None
    defaults = {
        "hasCompletedOnboarding": True,
        "theme": theme or "dark",
        "bypassPermissionsModeAccepted": True,
    }
    seeded = []
    for key, value in defaults.items():
        if not data.get(key):
            data[key] = value
            seeded.append(key)

    # Per-folder trust: claude prompts once per project root. Preempt it for the
    # spawn cwd so the seat does not stall on "do you trust the files here?".
    if workdir:
        wd = str(Path(workdir).expanduser().resolve())
        projects = data.setdefault("projects", {})
        if isinstance(projects, dict):
            proj = projects.setdefault(wd, {})
            if isinstance(proj, dict) and not proj.get("hasTrustDialogAccepted"):
                proj["hasTrustDialogAccepted"] = True
                seeded.append(f"projects[{wd}].hasTrustDialogAccepted")

    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return {"path": str(path), "seeded": seeded}


def _apply_profile(claude_home: Path, profile: str | None) -> dict[str, object]:
    """Copy an Aura-owned claude profile template into the box (no-replace).

    A claude profile is a ``claude-home-template/`` dir under
    ``runtime-profiles/claude-code/<profile>/``; its contents (settings.json,
    skills/, agents/, …) map straight into the box's ``.claude``. Copy-no-replace
    so the seat's accumulated runtime state is never clobbered on respawn, and so
    the later hook/onboarding merge layers cleanly on top of the profile's
    settings.json rather than under it.
    """
    if not profile:
        return {"profile": None}
    from lib import runtime_boxes

    template = runtime_boxes.runtime_profile_root("claude-code", profile) / "claude-home-template"
    if not template.is_dir():
        return {"profile": profile, "applied": False, "reason": "template-missing", "template": str(template)}
    copied = runtime_boxes.copy_template_tree_no_replace(template, claude_home)
    return {"profile": profile, "applied": bool(copied), "template": str(template)}


# Repo-owned statusline FK-writer (the producer the pane->session resolvers read).
# Read-only to this lane per seam v2; profiles only references it from the box settings.
_STATUSLINE_SCRIPT = Path(__file__).resolve().parent.parent / "hooks" / "aura-claude-statusline.sh"


def _install_statusline(claude_home: Path) -> bool:
    """Merge the statusLine FK-writer into the box settings.json, if absent.

    Profiles owns the ``statusLine`` key (seam v2 c1): ``default_hooks_claude`` is
    hooks-key-only, and the FK-writer used to ride inside ``hooks.inject``. Never
    clobber a profile-supplied statusLine; idempotent (if-absent only).
    """
    import json

    if not _STATUSLINE_SCRIPT.exists():
        return False
    path = claude_home / "settings.json"
    data: dict = {}
    if path.exists():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
            data = parsed if isinstance(parsed, dict) else {}
        except Exception:
            data = {}
    if data.get("statusLine"):
        return False  # a profile (or a prior prep) already set one — leave it
    data["statusLine"] = {"type": "command", "command": f"bash {_STATUSLINE_SCRIPT}"}
    # Trailing newline matches default_hooks_claude's serialization so the box is
    # byte-idempotent regardless of which writer (hooks vs statusLine) lands last.
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def prepare_package_box(
    package_root: str | Path,
    workdir: str | Path | None = None,
    profile: str | None = None,
    seat_target: str | None = None,
) -> dict[str, object]:
    """Seed a package's ``.claude`` box. Idempotent; safe to re-run on respawn.

    Order is fixed by the braid seam contract (v2):
      1. profile template merge FIRST (a profile's settings.json/skills must survive),
      2. auth symlink + onboarding seed,
      3. ``default_hooks_claude`` (hooks lane owns the body — we only CALL it; it
         merges ONLY the ``hooks`` key of the box settings.json),
      4. statusLine FK-writer (this lane owns the ``statusLine`` key — seam v2 c1,
         because default_hooks_claude is hooks-key-only and the script is read-only).

    Returns a diagnostic dict (never raises for a missing-source auth — a seat
    may legitimately authenticate by other means).
    """
    from lib import codex as codex_lib  # reuse the auth-symlink helper (archive-safe)
    from lib import hooks as hooks_lib

    root = Path(package_root).expanduser().resolve()
    claude_home = root / ".claude"
    claude_home.mkdir(parents=True, exist_ok=True)

    # 1. profile template first, so the seam call + statusLine layer on top of it.
    profile_result = _apply_profile(claude_home, profile)

    source = _source_claude_home()
    auth_linked: list[str] = []
    for name in _AUTH_FILES:
        if codex_lib._link_auth_file(source / name, claude_home / name):
            auth_linked.append(name)

    onboarding = _seed_onboarding(claude_home, source, workdir)

    # 3. THE SEAM CALL. config_dir is the box's CLAUDE_CONFIG_DIR. Built to the FROZEN
    #    signature; tolerant of the parallel build window before hooks lands H1
    #    (getattr guard) — the box stays functional (auth/onboarding/statusLine) and
    #    the rich hooks block appears once hooks' body exists. We never edit hooks.py.
    config_dir = str(claude_home)
    _default_hooks_claude = getattr(hooks_lib, "default_hooks_claude", None)
    if _default_hooks_claude is not None:
        _default_hooks_claude(config_dir, seat_target=seat_target)
        hooks_state = "default_hooks_claude"
    else:
        hooks_state = "pending-h1"

    # 4. statusLine FK-writer — this lane's key (seam v2 c1); never clobber a profile's.
    statusline_installed = _install_statusline(claude_home)

    return {
        "ok": True,
        "claude_home": str(claude_home),
        "auth_source": str(source),
        "auth_linked": auth_linked,
        "profile": profile_result,
        "onboarding": onboarding,
        "seat_target": seat_target,
        "hooks": hooks_state,
        "statusline": statusline_installed,
    }

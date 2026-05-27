import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli" / "aura"
CONTEXT_CURRENT = ROOT.parent / "context" / "current"
DEFAULT_SKILLS_ROOT = Path(os.environ.get("AURA_PUBLIC_SURFACE_SKILLS_ROOT", "/home/axp/.codex/skills"))


FORBIDDEN_PUBLIC_TEXT = {
    "top-level check": re.compile(r"\baura\s+check\b"),
    "top-level ledger": re.compile(r"\baura\s+ledger\b"),
    "top-level rename": re.compile(r"\baura\s+rename\b"),
    "top-level start": re.compile(r"\baura\s+start\b"),
    "top-level stop": re.compile(r"\baura\s+stop\b"),
    "diagnostic sleep": re.compile(r"\baura\s+sleep\b"),
    "diagnostic set": re.compile(r"\baura\s+set\b"),
    "legacy rehome": re.compile(r"\baura\s+(?:seat\s+)?rehome\b|\brehome\b"),
    "register orphan": re.compile(r"\bregister-orphan\b"),
    "spawn clone flag": re.compile(r"\bspawn\b[^\n`]*\s--clone\b"),
    "spawn slice flag": re.compile(r"\bspawn\b[^\n`]*\s--slice\b"),
    "desks identity alias": re.compile(r"\bdesks_identity_id\b"),
}


def _run_aura(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def _markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [
        path
        for path in root.rglob("*.md")
        if ".git" not in path.parts
        and "__pycache__" not in path.parts
        and "ast" not in path.relative_to(root).parts
    ]


def _skill_markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [
        path
        for path in root.rglob("*.md")
        if ".git" not in path.parts and "__pycache__" not in path.parts
    ]


def _forbidden_hits(files: list[Path]) -> list[str]:
    hits: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in FORBIDDEN_PUBLIC_TEXT.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                hits.append(f"{path}:{line}: {label}: {match.group(0)!r}")
    return hits


def test_removed_public_commands_are_not_cli_entrypoints():
    for command in ("check", "ledger", "rename", "start", "stop", "sleep", "set", "rehome", "register-orphan"):
        result = _run_aura(command, "--help")
        assert result.returncode != 0, command
        assert "invalid choice" in result.stderr


def test_removed_public_subcommands_and_flags_are_not_exposed():
    seat_help = _run_aura("seat", "--help")
    assert seat_help.returncode == 0
    assert "rehome" not in seat_help.stdout

    old_rehome = _run_aura("seat", "rehome", "--help")
    assert old_rehome.returncode != 0
    assert "invalid choice" in old_rehome.stderr

    spawn_help = _run_aura("spawn", "--help")
    assert spawn_help.returncode == 0
    assert "--clone" not in spawn_help.stdout
    assert "--slice" not in spawn_help.stdout

    for flag in ("--clone", "--slice"):
        old_spawn = _run_aura("spawn", "worker", flag, "legacy")
        assert old_spawn.returncode != 0, flag
        assert "unrecognized arguments" in old_spawn.stderr


def test_current_docs_do_not_teach_removed_public_surfaces():
    hits = _forbidden_hits(_markdown_files(CONTEXT_CURRENT))

    assert hits == []


def test_local_aura_skills_do_not_teach_removed_public_surfaces():
    hits = _forbidden_hits(_skill_markdown_files(DEFAULT_SKILLS_ROOT))

    assert hits == []

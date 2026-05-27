import os
import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli" / "aura"
CONTEXT_CURRENT = ROOT.parent / "context" / "current"
DEFAULT_SKILLS_ROOT = Path(os.environ.get("AURA_PUBLIC_SURFACE_SKILLS_ROOT", "/home/axp/.codex/skills"))
CONTRACT_PATH = ROOT / "tests" / "fixtures" / "public_surface_contract.json"


def _load_contract() -> dict[str, object]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


CONTRACT = _load_contract()
FORBIDDEN_PUBLIC_TEXT = {
    label: re.compile(pattern)
    for label, pattern in CONTRACT["retired_forbidden_surfaces"].items()
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


def _top_level_commands(help_text: str) -> set[str]:
    match = re.search(r"\{([^}]+)\}", help_text)
    assert match, help_text
    return {command.strip() for command in match.group(1).split(",") if command.strip()}


def _skill_file(skill_name: str) -> Path:
    return DEFAULT_SKILLS_ROOT / skill_name / "SKILL.md"


def test_removed_public_commands_are_not_cli_entrypoints():
    for command in CONTRACT["removed_cli_entrypoints"]:
        result = _run_aura(command, "--help")
        assert result.returncode != 0, command
        assert "invalid choice" in result.stderr


def test_top_level_help_taxonomy_matches_public_surface_contract():
    result = _run_aura("--help")
    assert result.returncode == 0

    normalized_help = " ".join(result.stdout.split())
    agent_safe = ", ".join(CONTRACT["help"]["agent_safe_verbs"])
    operator_tools = ", ".join(CONTRACT["help"]["operator_tools"])
    assert f"Agent-safe verbs: {agent_safe}." in normalized_help
    assert f"Operator tools: {operator_tools}." in normalized_help

    categorized = set()
    for key, commands in CONTRACT["cli_categories"].items():
        if key in {"runtime_profile_names", "hidden_internal"}:
            continue
        categorized.update(commands)
    assert _top_level_commands(result.stdout) == categorized


def test_removed_public_subcommands_and_flags_are_not_exposed():
    seat_help = _run_aura("seat", "--help")
    assert seat_help.returncode == 0
    for command in CONTRACT["removed_seat_subcommands"]:
        assert command not in seat_help.stdout

        old_subcommand = _run_aura("seat", command, "--help")
        assert old_subcommand.returncode != 0
        assert "invalid choice" in old_subcommand.stderr

    spawn_help = _run_aura("spawn", "--help")
    assert spawn_help.returncode == 0
    for flag in CONTRACT["removed_spawn_flags"]:
        assert flag not in spawn_help.stdout

    for flag in CONTRACT["removed_spawn_flags"]:
        old_spawn = _run_aura("spawn", "worker", flag, "legacy")
        assert old_spawn.returncode != 0, flag
        assert "unrecognized arguments" in old_spawn.stderr


def test_current_docs_do_not_teach_removed_public_surfaces():
    hits = _forbidden_hits(_markdown_files(CONTEXT_CURRENT))

    assert hits == []


def test_local_aura_skills_do_not_teach_removed_public_surfaces():
    hits = _forbidden_hits(_skill_markdown_files(DEFAULT_SKILLS_ROOT))

    assert hits == []


def test_normal_aura_skills_do_not_teach_operator_cli_commands():
    if not DEFAULT_SKILLS_ROOT.exists():
        return

    operator_commands = "|".join(
        re.escape(command) for command in CONTRACT["skills"]["normal_forbidden_cli_commands"]
    )
    operator_cli = re.compile(rf"\baura\s+(?:{operator_commands})\b")
    hits: list[str] = []
    for skill_name in CONTRACT["skills"]["normal"]:
        path = _skill_file(skill_name)
        assert path.exists(), skill_name
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in operator_cli.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            hits.append(f"{path}:{line}: operator CLI in normal skill: {match.group(0)!r}")

    assert hits == []


def test_operator_skill_is_allowed_to_teach_operator_cli_commands():
    if not DEFAULT_SKILLS_ROOT.exists():
        return

    operator_skill = _skill_file(CONTRACT["skills"]["operator"][0])
    assert operator_skill.exists()
    text = operator_skill.read_text(encoding="utf-8", errors="ignore")

    for command in ("seat", "agent", "profile", "write"):
        assert re.search(rf"\baura\s+{re.escape(command)}\b", text), command

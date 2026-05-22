import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def make_agent(monkeypatch, tmp_path, *, runtime="codex", alias="skills-agent"):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    from lib import agent_packages

    result = agent_packages.create(
        address=f"unit:skills:{alias}",
        runtime=runtime,
        profile=None,
        cwd=str(tmp_path / "work"),
        fleet="unit-skills",
        seat=alias,
        alias=alias,
    )
    assert result["ok"] is True
    return result["agent"]


def make_skill(tmp_path, name="aura-operator"):
    root = tmp_path / "src" / name
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: Test skill {name}.\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return root


def test_dry_run_apply_does_not_mutate(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    skill = make_skill(tmp_path)
    from lib import skill_libraries

    result = skill_libraries.apply(agent["alias"], [str(skill)], dry_run=True)

    assert result["dry_run"] is True
    root = Path(agent["root"])
    assert not (root / ".codex" / "skills" / "aura-operator").exists()
    assert not (root / "skills.lock.json").exists()


def test_apply_symlink_and_list(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    skill = make_skill(tmp_path)
    from lib import skill_libraries

    result = skill_libraries.apply(agent["alias"], [str(skill)])

    assert result["ok"] is True
    target = Path(agent["root"]) / ".codex" / "skills" / "aura-operator"
    assert target.is_symlink()
    assert Path(os.readlink(target)) == skill.resolve()
    lock = json.loads((Path(agent["root"]) / "skills.lock.json").read_text())
    assert lock["schema"] == skill_libraries.LOCK_SCHEMA
    assert lock["agent_id"] == agent["agent_id"]
    listed = skill_libraries.list_skills(agent["alias"])
    assert listed["locked"][0]["name"] == "aura-operator"
    assert listed["actual"][0]["owned"] is True


def test_copy_apply_creates_directory(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    skill = make_skill(tmp_path)
    from lib import skill_libraries

    skill_libraries.apply(agent["alias"], [str(skill)], mode="copy")

    target = Path(agent["root"]) / ".codex" / "skills" / "aura-operator"
    assert target.is_dir()
    assert not target.is_symlink()
    assert (target / "SKILL.md").is_file()


def test_missing_skill_file_rejected(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    bad = tmp_path / "src" / "bad"
    bad.mkdir(parents=True)
    from lib import skill_libraries

    with pytest.raises(skill_libraries.SkillLibraryError) as exc:
        skill_libraries.apply(agent["alias"], [str(bad)], dry_run=True)
    assert exc.value.code == "skill-file-missing"


def test_unsafe_skill_path_rejected(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    bad = tmp_path / "_archive" / "bad"
    bad.mkdir(parents=True)
    (bad / "SKILL.md").write_text("---\nname: bad\ndescription: bad\n---\n", encoding="utf-8")
    from lib import skill_libraries

    with pytest.raises(skill_libraries.SkillLibraryError) as exc:
        skill_libraries.apply(agent["alias"], [str(bad)], dry_run=True)
    assert exc.value.code == "unsafe-path"


def test_unsafe_skill_content_rejected(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    skill = make_skill(tmp_path)
    (skill / "token.log").write_text("secret", encoding="utf-8")
    from lib import skill_libraries

    with pytest.raises(skill_libraries.SkillLibraryError) as exc:
        skill_libraries.apply(agent["alias"], [str(skill)], dry_run=True)
    assert exc.value.code == "unsafe-path"


def test_destination_collision_requires_replace(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    skill = make_skill(tmp_path)
    root = Path(agent["root"])
    target = root / ".codex" / "skills" / "aura-operator"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("manual", encoding="utf-8")
    from lib import skill_libraries

    with pytest.raises(skill_libraries.SkillLibraryError) as exc:
        skill_libraries.apply(agent["alias"], [str(skill)])
    assert exc.value.code == "destination-exists"
    result = skill_libraries.apply(agent["alias"], [str(skill)], replace=True)
    assert result["applied"][0]["archive_path"]
    assert target.is_symlink()


def test_corrupt_lock_fails_closed_without_deleting(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    skill = make_skill(tmp_path)
    root = Path(agent["root"])
    target = root / ".codex" / "skills" / "aura-operator"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("manual", encoding="utf-8")
    (root / "skills.lock.json").write_text("{not json", encoding="utf-8")
    from lib import skill_libraries

    with pytest.raises(skill_libraries.SkillLibraryError) as exc:
        skill_libraries.apply(agent["alias"], [str(skill)], replace=True)
    assert exc.value.code == "corrupt-provenance"
    assert target.read_text() == "manual"


def test_remove_deletes_only_owned_target(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    skill = make_skill(tmp_path)
    from lib import skill_libraries

    skill_libraries.apply(agent["alias"], [str(skill)])
    result = skill_libraries.remove(agent["alias"], "aura-operator")

    assert result["removed"]["name"] == "aura-operator"
    assert skill.exists()
    assert not (Path(agent["root"]) / ".codex" / "skills" / "aura-operator").exists()
    assert skill_libraries.list_skills(agent["alias"])["locked"] == []


def test_remove_refuses_unowned_skill(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    root = Path(agent["root"])
    target = root / ".codex" / "skills" / "manual"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("manual", encoding="utf-8")
    from lib import skill_libraries

    with pytest.raises(skill_libraries.SkillLibraryError) as exc:
        skill_libraries.remove(agent["alias"], "manual")
    assert exc.value.code == "skill-not-owned"
    assert target.exists()


def test_doctor_and_sync_repair_missing_owned_link(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    skill = make_skill(tmp_path)
    from lib import skill_libraries

    skill_libraries.apply(agent["alias"], [str(skill)])
    target = Path(agent["root"]) / ".codex" / "skills" / "aura-operator"
    target.unlink()

    doctor = skill_libraries.doctor(agent["alias"])
    assert {issue["kind"] for issue in doctor["issues"]} == {"lock-with-missing-link"}
    dry_run = skill_libraries.sync(agent["alias"], dry_run=True)
    assert dry_run["repairs"][0]["kind"] == "lock-with-missing-link"
    repaired = skill_libraries.sync(agent["alias"])
    assert repaired["repaired"][0]["name"] == "aura-operator"
    assert target.is_symlink()


def test_doctor_detects_broken_owned_link(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    skill = make_skill(tmp_path)
    from lib import skill_libraries

    skill_libraries.apply(agent["alias"], [str(skill)])
    skill.rename(tmp_path / "src" / "moved")

    result = skill_libraries.doctor(agent["alias"])
    assert {issue["kind"] for issue in result["issues"]} == {"broken-owned-link"}


def test_doctor_detects_missing_lock_and_unmanaged_file(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    skill = make_skill(tmp_path)
    root = Path(agent["root"])
    link = root / ".codex" / "skills" / "manual-link"
    file = root / ".codex" / "skills" / "manual-file"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(skill.resolve(), target_is_directory=True)
    file.write_text("manual", encoding="utf-8")
    from lib import skill_libraries

    result = skill_libraries.doctor(agent["alias"])
    assert {issue["kind"] for issue in result["issues"]} == {"owned-link-with-missing-lock", "unmanaged-file"}


def test_unsupported_runtime_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))
    from lib import agent_packages, skill_libraries

    root = tmp_path / "state" / "agents" / "i_bad"
    (root / ".codex").mkdir(parents=True)
    (root / "manifest.json").write_text(json.dumps({"runtime": "claude-code"}), encoding="utf-8")
    index = {"schema": agent_packages.INDEX_SCHEMA, "agents": {"i_bad": {"root": str(root), "alias": "bad"}}, "addresses": {}, "aliases": {"bad": "i_bad"}}
    agent_packages.write_index(index)
    with pytest.raises(skill_libraries.SkillLibraryError) as exc:
        skill_libraries.list_skills("bad")
    assert exc.value.code == "unsupported-runtime"


def test_cli_smoke_apply_list_doctor_remove(monkeypatch, tmp_path):
    agent = make_agent(monkeypatch, tmp_path)
    skill = make_skill(tmp_path)
    env = {**os.environ, "AURA_STATE_DIR": str(tmp_path / "state"), "PYTHONDONTWRITEBYTECODE": "1"}

    dry_run = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "aura"), "skills", "apply", "--agent", agent["alias"], "--skill", str(skill), "--dry-run"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(dry_run.stdout)["dry_run"] is True
    subprocess.run(
        [sys.executable, str(ROOT / "cli" / "aura"), "skills", "apply", "--agent", agent["alias"], "--skill", str(skill)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    listed = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "aura"), "skills", "list", "--agent", agent["alias"]],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(listed.stdout)["locked"][0]["name"] == "aura-operator"
    doctor = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "aura"), "skills", "doctor", "--agent", agent["alias"]],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(doctor.stdout)["issues"] == []
    removed = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "aura"), "skills", "remove", "--agent", agent["alias"], "aura-operator"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(removed.stdout)["removed"]["name"] == "aura-operator"

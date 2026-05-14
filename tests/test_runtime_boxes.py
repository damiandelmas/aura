import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_runtime_box_paths_use_safe_segments_and_legacy_omx(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / "state"))

    from lib import runtime_boxes

    assert runtime_boxes.safe_segment("../bad fleet!") == "bad-fleet"
    assert runtime_boxes.runtime_home_root("codex", "my fleet", "seat/one") == (
        tmp_path / "state" / "runtime-homes" / "codex" / "my-fleet" / "seat-one"
    )
    assert runtime_boxes.runtime_profile_root("codex", "dev profile") == (
        tmp_path / "state" / "runtime-profiles" / "codex" / "dev-profile"
    )
    assert runtime_boxes.runtime_home_root("omx", "my fleet", "seat/one", legacy_omx=True) == (
        tmp_path / "state" / "omx-homes" / "my-fleet" / "seat-one"
    )
    assert runtime_boxes.runtime_profile_root("omx", "dev", legacy_omx=True) == (
        tmp_path / "state" / "omx-profiles" / "dev"
    )


def test_runtime_box_templates_copy_without_overwrite(tmp_path):
    from lib import runtime_boxes

    source = tmp_path / "profile" / "codex-home-template"
    destination = tmp_path / "box" / "codex-home"
    source.mkdir(parents=True)
    destination.mkdir(parents=True)
    (source / "new.txt").write_text("new\n", encoding="utf-8")
    (source / "keep.txt").write_text("template\n", encoding="utf-8")
    (destination / "keep.txt").write_text("existing\n", encoding="utf-8")

    copied = runtime_boxes.copy_template_tree_no_replace(source, destination)

    assert copied is True
    assert (destination / "new.txt").read_text(encoding="utf-8") == "new\n"
    assert (destination / "keep.txt").read_text(encoding="utf-8") == "existing\n"


def test_runtime_box_apply_templates_reports_applied_names(tmp_path):
    from lib import runtime_boxes

    root = tmp_path / "profile"
    (root / "home-template").mkdir(parents=True)
    (root / "codex-home-template").mkdir(parents=True)
    (root / "home-template" / "note.txt").write_text("home\n", encoding="utf-8")
    (root / "codex-home-template" / "note.txt").write_text("codex\n", encoding="utf-8")

    applied, names = runtime_boxes.apply_templates(
        root,
        {
            "home-template": tmp_path / "box" / "home",
            "codex-home-template": tmp_path / "box" / "codex-home",
            "missing-template": tmp_path / "box" / "missing",
        },
    )

    assert applied is True
    assert names == ("home-template", "codex-home-template")
    assert (tmp_path / "box" / "home" / "note.txt").read_text(encoding="utf-8") == "home\n"
    assert (tmp_path / "box" / "codex-home" / "note.txt").read_text(encoding="utf-8") == "codex\n"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink unavailable")
def test_runtime_box_templates_reject_file_symlink(tmp_path):
    from lib import runtime_boxes

    outside = tmp_path / "outside.txt"
    outside.write_text("secret\n", encoding="utf-8")
    source = tmp_path / "profile" / "codex-home-template"
    source.mkdir(parents=True)
    os.symlink(outside, source / "leak.txt")

    with pytest.raises(ValueError, match="symlink rejected"):
        runtime_boxes.copy_template_tree_no_replace(source, tmp_path / "box")

    assert not (tmp_path / "box" / "leak.txt").exists()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlink unavailable")
def test_runtime_box_templates_reject_directory_symlink(tmp_path):
    from lib import runtime_boxes

    outside = tmp_path / "outside"
    outside.mkdir()
    source = tmp_path / "profile" / "codex-home-template"
    source.mkdir(parents=True)
    os.symlink(outside, source / "linked-dir")

    with pytest.raises(ValueError, match="symlink rejected"):
        runtime_boxes.apply_templates(
            tmp_path / "profile",
            {"codex-home-template": tmp_path / "box" / "codex-home"},
        )

    assert not (tmp_path / "box" / "codex-home" / "linked-dir").exists()

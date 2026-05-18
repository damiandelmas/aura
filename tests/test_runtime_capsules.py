"""Runtime capsule manifest contract tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def test_runtime_capsule_writes_launch_and_session_manifests(tmp_path):
    from lib import runtime_capsules

    capsule = tmp_path / "capsule"
    record = {
        "name": "builder",
        "fleet": "unitfleet",
        "runtime": "codex",
        "runtime_home": str(capsule),
        "codex_box_codex_home": str(capsule / "codex-home"),
        "cwd": str(tmp_path / "work"),
        "aura_launch_id": "aura-launch-test",
        "seat_instance_id": "si_test",
        "runtime_session_id": "session-test",
        "runtime_session_source": "codex-jsonl:nonce",
        "runtime_session_binding": "bound",
    }

    launch = runtime_capsules.write_aura_launch(
        record,
        env_roots={
            "CODEX_HOME": str(capsule / "codex-home"),
            "OMX_SECRET_SHOULD_NOT_APPEAR": "secret",
        },
    )
    session = runtime_capsules.write_runtime_session(record, extra={"jsonl": str(capsule / "codex-home" / "sessions" / "x.jsonl")})

    assert launch["ok"] is True
    assert session["ok"] is True
    assert (capsule / "receipts").is_dir()
    assert (capsule / "artifacts").is_dir()

    launch_body = json.loads((capsule / "aura-launch.json").read_text(encoding="utf-8"))
    session_body = json.loads((capsule / "runtime-session.json").read_text(encoding="utf-8"))
    assert launch_body["schema"] == "aura.runtime_capsule.launch.v1"
    assert launch_body["env_roots"] == {"CODEX_HOME": str(capsule / "codex-home")}
    assert session_body["schema"] == "aura.runtime_capsule.session.v1"
    assert session_body["runtime_session_id"] == "session-test"


def test_runtime_capsule_ignores_profile_only_records(tmp_path):
    from lib import runtime_capsules

    record = {
        "name": "profile-only",
        "fleet": "unitfleet",
        "runtime": "codex",
        "runtime_profile_ref": "codex/aura-operator",
        "codex_profile_root": str(tmp_path / "runtime-profiles" / "codex" / "aura-operator"),
    }

    result = runtime_capsules.write_aura_launch(record)

    assert result == {"ok": False, "reason": "no-capsule-root"}
    assert not (tmp_path / "runtime-profiles" / "codex" / "aura-operator" / "aura-launch.json").exists()

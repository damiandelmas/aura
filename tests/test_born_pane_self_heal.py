"""M4 — born-pane self-heal + reliable reverse resolution.

Covers the locked-plan §4 M4 cases:
  - _match_registry_row is exact-only (fixes inspect tmux:...:%N registered:false bug)
  - _resolve_from_birth_env complete thin-row schema, rejects incomplete + fork children
  - _bind_pane self-heals an orphan from birth env
  - sessions reconcile-orphans dry-run vs real, mirror-unavailable graceful
  - _heal skips an occupant-mismatch born pane
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


def _pane(pane_id="%26", session="flt", pid="1234", cmd="codex", cwd="/repo", window="scout"):
    return {
        "pane_id": pane_id,
        "tmux_session": session,
        "physical_fleet": session,
        "pane_pid": pid,
        "pane_current_command": cmd,
        "pane_current_path": cwd,
        "window_id": "@1",
        "window_name": window,
        "pane_ref": f"tmux:{session}:{pane_id}",
    }


def _install_mirror(monkeypatch, panes, ok=True):
    from lib import tmux_mirror

    result = {"ok": ok, "panes": panes} if ok else {"ok": False, "error": "tmux-down", "panes": []}
    monkeypatch.setattr(tmux_mirror, "list_physical_panes", lambda **kw: result)


def _install_birth_env(monkeypatch, env):
    """Patch the raw pane env so _read_birth_env / fork detection run for real."""
    from lib import pane_resolver

    monkeypatch.setattr(pane_resolver, "_pane_env", lambda pid: dict(env))


def _args(**kw):
    base = {
        "pane": None,
        "current": False,
        "target": None,
        "repair": False,
        "fleet": None,
        "all": False,
        "dry_run": False,
    }
    base.update(kw)
    return type("Args", (), base)()


# --- _match_registry_row exact-only ---------------------------------------


def test_match_registry_row_exact_only(monkeypatch, tmp_path):
    """A fleet-b pane %26 must NOT match a fleet-a:%26 registry row."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import pane_resolver, registry

    registry.upsert_agent({
        "fleet": "fleet-a",
        "name": "scout",
        "runtime": "codex",
        "pane_ref": "tmux:fleet-a:%26",
        "seat_instance_id": "si-a",
    })

    pane = _pane(pane_id="%26", session="fleet-b")
    assert pane_resolver._match_registry_row(pane) is None


def test_match_registry_row_exact_hit(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from lib import pane_resolver, registry

    registry.upsert_agent({
        "fleet": "fleet-a",
        "name": "scout",
        "runtime": "codex",
        "pane_ref": "tmux:fleet-a:%26",
        "seat_instance_id": "si-a",
    })

    pane = _pane(pane_id="%26", session="fleet-a")
    matched = pane_resolver._match_registry_row(pane)
    assert matched is not None
    assert matched.get("seat_instance_id") == "si-a"


# --- _resolve_from_birth_env ----------------------------------------------


def test_resolve_from_birth_env_complete_schema():
    from lib import pane_resolver

    pane = _pane(pane_id="%26", session="flt")
    birth = {
        "AURA_FLEET": "flt",
        "AURA_SEAT": "scout",
        "AURA_LAUNCH_ID": "L-1",
        "AURA_SEAT_INSTANCE_ID": "si-1",
    }
    thin = pane_resolver._resolve_from_birth_env(pane, birth)
    assert thin is not None
    assert thin["fleet"] == "flt"
    assert thin["seat"] == "scout"
    assert thin["name"] == "scout"
    assert thin["seat_ref"] == "flt:scout"
    assert thin["seat_instance_id"] == "si-1"
    assert thin["aura_launch_id"] == "L-1"
    assert thin["pane_ref"] == "tmux:flt:%26"
    assert thin["runtime"] == "codex"
    assert thin["registered"] is False
    assert thin["status"] == "born-unhealed"
    assert thin["_from_birth_env"] is True
    assert thin.get("last_seen")


def test_resolve_from_birth_env_rejects_incomplete():
    from lib import pane_resolver

    pane = _pane()
    # Missing seat.
    assert pane_resolver._resolve_from_birth_env(
        pane, {"AURA_FLEET": "flt", "AURA_SEAT_INSTANCE_ID": "si-1"}
    ) is None
    # Missing both launch id and seat instance id.
    assert pane_resolver._resolve_from_birth_env(
        pane, {"AURA_FLEET": "flt", "AURA_SEAT": "scout"}
    ) is None
    # Empty env.
    assert pane_resolver._resolve_from_birth_env(pane, {}) is None


def test_resolve_from_birth_env_rejects_fork_child(monkeypatch):
    """A fork child's birth env is empty, so it can never be reconstructed."""
    from lib import pane_resolver

    _install_birth_env(monkeypatch, {
        "AURA_FLEET": "flt",
        "AURA_SEAT": "scout",
        "AURA_SEAT_INSTANCE_ID": "si-parent",
        "AURA_FORK_SOURCE": "sess-parent",
    })
    birth = pane_resolver._read_birth_env(1234)
    assert birth == {}
    assert pane_resolver._resolve_from_birth_env(_pane(), birth) is None


def test_read_birth_env_filters_to_aura_keys(monkeypatch):
    from lib import pane_resolver

    _install_birth_env(monkeypatch, {
        "AURA_FLEET": "flt",
        "AURA_SEAT": "scout",
        "AURA_LAUNCH_ID": "L-1",
        "AURA_SEAT_INSTANCE_ID": "si-1",
        "PATH": "/bin",
        "HOME": "/home/x",
    })
    birth = pane_resolver._read_birth_env(1234)
    assert birth == {
        "AURA_FLEET": "flt",
        "AURA_SEAT": "scout",
        "AURA_LAUNCH_ID": "L-1",
        "AURA_SEAT_INSTANCE_ID": "si-1",
    }


# --- _bind_pane self-heal --------------------------------------------------


def test_bind_pane_self_heals_orphan(monkeypatch, tmp_path):
    """No registry row, but the pane is Aura-born: bind creates the row with si/pane."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions
    from lib import registry

    pane = _pane(pane_id="%26", session="flt")
    _install_mirror(monkeypatch, [pane])
    _install_birth_env(monkeypatch, {
        "AURA_FLEET": "flt",
        "AURA_SEAT": "scout",
        "AURA_LAUNCH_ID": "L-1",
        "AURA_SEAT_INSTANCE_ID": "si-1",
        "AURA_RUNTIME_SESSION_ID": "runtime-sess-1",
    })

    result = sessions._bind_pane(_args(pane="%26"))
    assert result.get("ok") is True, result

    row = registry.resolve_live("scout", fleet="flt")
    assert row is not None
    assert row.get("seat_instance_id") == "si-1"
    assert row.get("pane_ref") == "tmux:flt:%26"


def test_bind_pane_unmanaged_not_born_errors(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions

    pane = _pane(pane_id="%26", session="flt")
    _install_mirror(monkeypatch, [pane])
    _install_birth_env(monkeypatch, {"PATH": "/bin"})

    result = sessions._bind_pane(_args(pane="%26"))
    assert result.get("ok") is False
    assert result.get("error") == "no-target"
    assert "not Aura-born" in result.get("detail", "")


# --- reconcile-orphans -----------------------------------------------------


def test_reconcile_orphans_dry_run_no_write(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions
    from lib import registry

    pane = _pane(pane_id="%26", session="flt")
    _install_mirror(monkeypatch, [pane])
    _install_birth_env(monkeypatch, {
        "AURA_FLEET": "flt",
        "AURA_SEAT": "scout",
        "AURA_LAUNCH_ID": "L-1",
        "AURA_SEAT_INSTANCE_ID": "si-1",
    })

    result = sessions._reconcile_orphans(_args(all=True, dry_run=True))
    assert result.get("ok") is True
    assert result.get("dry_run") is True
    assert result.get("reconciled") == 1
    assert result["results"][0]["status"] == "would-reconcile"
    # No registry write happened.
    assert registry.resolve_live("scout", fleet="flt") is None


def test_reconcile_orphans_reconciles_then_present(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions
    from lib import registry

    pane = _pane(pane_id="%26", session="flt")
    _install_mirror(monkeypatch, [pane])
    _install_birth_env(monkeypatch, {
        "AURA_FLEET": "flt",
        "AURA_SEAT": "scout",
        "AURA_LAUNCH_ID": "L-1",
        "AURA_SEAT_INSTANCE_ID": "si-1",
    })

    result = sessions._reconcile_orphans(_args(all=True))
    assert result.get("ok") is True
    assert result.get("reconciled") == 1
    assert result["results"][0]["status"] == "reconciled"

    row = registry.resolve_live("scout", fleet="flt")
    assert row is not None
    assert row.get("seat_instance_id") == "si-1"
    assert row.get("pane_ref") == "tmux:flt:%26"

    # Already present: a second run skips it.
    again = sessions._reconcile_orphans(_args(all=True))
    assert again.get("reconciled") == 0
    assert again.get("skipped") == 1


def test_reconcile_orphans_skips_without_seat_instance_id(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions
    from lib import registry

    pane = _pane(pane_id="%26", session="flt")
    _install_mirror(monkeypatch, [pane])
    # launch id only, no seat instance id -> reconciliation requires si.
    _install_birth_env(monkeypatch, {
        "AURA_FLEET": "flt",
        "AURA_SEAT": "scout",
        "AURA_LAUNCH_ID": "L-1",
    })

    result = sessions._reconcile_orphans(_args(all=True))
    assert result.get("reconciled") == 0
    assert result.get("skipped") == 1
    assert registry.resolve_live("scout", fleet="flt") is None


def test_reconcile_orphans_requires_selector(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions

    result = sessions._reconcile_orphans(_args())
    assert result.get("ok") is False
    assert "requires" in result.get("error", "")


def test_reconcile_mirror_unavailable_graceful(monkeypatch, tmp_path):
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions

    _install_mirror(monkeypatch, [], ok=False)
    result = sessions._reconcile_orphans(_args(all=True))
    assert result.get("ok") is False
    assert result.get("error") == "tmux-mirror-unavailable"


# --- _heal occupant-mismatch precheck --------------------------------------


def test_heal_skips_occupant_mismatch_born_pane(monkeypatch, tmp_path):
    """Registry row si-old, but the live pane was born under si-new: skip, don't heal."""
    monkeypatch.setenv("AURA_STATE_DIR", str(tmp_path / ".aura"))
    from commands import sessions
    from lib import registry

    registry.upsert_agent({
        "fleet": "flt",
        "name": "scout",
        "runtime": "codex",
        "pane_ref": "tmux:flt:%26",
        "seat_instance_id": "si-old",
        "status": "unbound",
    })

    pane = _pane(pane_id="%26", session="flt")
    _install_mirror(monkeypatch, [pane])
    _install_birth_env(monkeypatch, {
        "AURA_FLEET": "flt",
        "AURA_SEAT": "scout",
        "AURA_SEAT_INSTANCE_ID": "si-new",
    })

    # Make the seat look alive so we reach the precheck.
    from lib import seat_status

    monkeypatch.setattr(
        seat_status,
        "build_from_record",
        lambda record, **kw: {"terminal": "alive"},
    )

    result = sessions._heal(_args(target="flt:scout"))
    assert result.get("ok") is True
    rows = result.get("results") or []
    assert len(rows) == 1
    assert rows[0]["status"] == "skipped"
    assert rows[0]["reason"] == "occupant-mismatch-born-pane"

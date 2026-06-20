"""Society container config — verbs over a tmp registry, resolution via the seam."""

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli"))


FAKE_FLEETS = {
    "f_chat": {"fleet_id": "f_chat", "current_name": "flexchat-sales"},
    "f_chat2": {"fleet_id": "f_chat2", "current_name": "flexchat-ops"},
    "f_aura": {"fleet_id": "f_aura", "current_name": "aura-engine"},
}


@pytest.fixture
def soc(tmp_path, monkeypatch):
    from lib import society, fleets
    monkeypatch.setattr(society, "registry_path", lambda: tmp_path / "registry.json")
    monkeypatch.setattr(fleets, "read_fleets", lambda: dict(FAKE_FLEETS))
    return society


def test_set_member_pins_durable_ids(soc):
    res = soc.set_member("flexchat", "flexchat-*")
    assert res["ok"] and set(res["pinned"]) == {"f_chat", "f_chat2"}
    assert res["members"] == ["fleet-id://f_chat", "fleet-id://f_chat2"]


def test_get_expands_ids_to_current_names(soc):
    soc.set_member("flexchat", "flexchat-*")
    got = soc.get("flexchat")
    names = {m["name"] for m in got["members"]}
    assert names == {"flexchat-sales", "flexchat-ops"}
    assert all(m["status"] == "live" for m in got["members"])


def test_stale_member_never_dropped(soc, monkeypatch):
    soc.set_member("flexchat", "flexchat-sales")  # pins f_chat
    from lib import fleets
    monkeypatch.setattr(fleets, "read_fleets", lambda: {"f_aura": FAKE_FLEETS["f_aura"]})  # f_chat gone
    got = soc.get("flexchat")
    assert got["members"][0]["status"] == "stale"
    assert got["members"][0]["fleet_id"] == "f_chat"


def test_of_reverse_lookup(soc):
    soc.set_member("flexchat", "flexchat-*")
    assert soc.of("flexchat-sales")["societies"] == ["flexchat"]
    assert soc.of("aura-engine")["societies"] == []


def test_config_resolve_passthrough(soc):
    soc.set_fields("flexchat", config={"LINEAR_API_KEY": "op://flex/Linear/getflex/api key",
                                       "AURA_LINEAR_TARGET": "placement:linear-getflex-eng"})
    one = soc.resolve_config("flexchat", "LINEAR_API_KEY")
    assert one["value"] == "op://flex/Linear/getflex/api key"   # raw passthrough today
    full = soc.resolve_config("flexchat")
    assert full["config"]["AURA_LINEAR_TARGET"] == "placement:linear-getflex-eng"


def test_resolves_to_stored_raw(soc):
    soc.set_fields("flexchat", resolves_to="runway://flex/eng")
    assert soc.get("flexchat")["resolves_to"] == "runway://flex/eng"


def test_remove_member_and_list(soc):
    soc.set_member("flexchat", "flexchat-*")
    rm = soc.remove_member("flexchat", "f_chat")
    assert rm["removed"] == 1
    assert soc.remove_member("flexchat", "fleet-id://f_chat2")["removed"] == 1
    rows = {r["name"]: r for r in soc.list_societies()["societies"]}
    assert rows["flexchat"]["members"] == 0


def test_no_match_is_error(soc):
    assert soc.set_member("flexchat", "nope-*")["ok"] is False
    assert soc.get("ghost")["ok"] is False

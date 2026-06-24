#!/usr/bin/env python3
"""Project Aura's live mesh onto a Discord category tree (society config × live state).

The desired tree is a function of the society config and the live fleet roster, and
the generator continuously reconciles the guild to it:
  - CATEGORY per society (flex, flexchat, aura) + "other" (society-less fleets) +
    "archive" (true legacy).
  - A society/known fleet WITH a live ``:manager`` seat -> an ACTIVE channel in its
    society category, base name (``flexchat-factory`` -> ``#factory``; society-less
    fleets keep their full name), bound ``<fleet>:manager`` (+ live-seat aliases).
  - A known fleet at 0 live seats -> its channel STAYS in place (same category, same
    id, binding kept) and is marked DORMANT with a ``💤`` name prefix. Revived (gains
    a seat) -> the ``💤`` is stripped. The category is the society lookup, so a dormant
    channel is NEVER moved — only re-labelled in place.
  - A channel whose (category, base name) maps to NO known fleet -> ARCHIVE (true
    legacy only). #general (bot home) and the #self channels and hand-bound lanes
    (e.g. #sales-ops) are protected.

Identity is ``(category, BASE name)`` — the ``💤`` is derived from liveness, never
stored, so a re-run against an already-projected guild is a no-op. Channel/category
CREATE, the dormant RENAME, and the archive MOVE go through the Discord bot API;
Aura only BINDS. DRY-RUN by default; ``--apply`` performs the delta (safe to re-run).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

DISCORD_API = "https://discord.com/api/v10"
USER_AGENT = "AuraSocietyTree (https://aura.local, 1.0)"
CT_CATEGORY, CT_TEXT = 4, 0
OTHER_CATEGORY = "other"
ARCHIVE_CATEGORY = "archive"
SELF_CATEGORY = "self"
DORMANT_MARK = "💤"          # in-place name prefix for a 0-seat (dormant) fleet channel
# Personal (non-fleet) channels — kept OUT of the archive sweep, the same protection
# #general (the bot home) has.
SELF_CHANNELS = frozenset({"assistant", "life", "spiritual"})
# Hand-bound channels that live in a society category but map to NO fleet (e.g. an
# operator's direct-to-human lane). Protected from archive. Dead SOCIETY fleets are
# NOT listed here — they are kept automatically as dormant by liveness.
PROTECTED_CHANNELS = frozenset({"sales-ops"})
BINDINGS_PATH = Path(os.path.expanduser("~/.aura/discord/channel-bindings.json"))
REPO = Path(__file__).resolve().parents[1]
AURA_CLI = REPO / "cli" / "aura"


# ---- Aura data sources (society config + live roster) ---------------------- #

def aura(*args) -> dict:
    out = subprocess.run([sys.executable, str(AURA_CLI), *args],
                         capture_output=True, text=True, timeout=60).stdout
    start = out.find("{")
    return json.loads(out[start:]) if start >= 0 else {}


def live_roster() -> dict[str, list[str]]:
    rows = aura("list").get("rows", [])
    fleets: dict[str, list[str]] = {}
    for r in rows:
        if r.get("terminal") == "alive" and not r.get("hidden"):
            fleets.setdefault(r["fleet"], []).append(r["seat"])
    return {f: sorted(set(s)) for f, s in fleets.items()}


def society_members() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for soc in aura("society", "list").get("societies", []):
        name = soc["name"]
        got = aura("society", "get", name)
        out[name] = [m["name"] for m in got.get("members", [])]
    return out


def known_fleets(members: dict[str, list[str]]) -> set[str]:
    """Every fleet the projection recognises: all society members + every fleet in
    the registry (alive OR historical). A channel whose name maps outside this set
    is true legacy and is archived; inside it, the fleet is dormant-kept when dead."""
    fleets: set[str] = set()
    for rows in members.values():
        fleets.update(rows)
    for r in aura("list").get("rows", []):
        if r.get("fleet"):
            fleets.add(r["fleet"])
    return fleets


def channel_name(fleet: str, society: str | None) -> str:
    prefix = f"{society}-"
    if society and fleet.startswith(prefix):
        return fleet[len(prefix):]
    return fleet


def _base_name(name: str) -> str:
    return name[len(DORMANT_MARK):] if name.startswith(DORMANT_MARK) else name


def _dormant_name(base: str) -> str:
    return f"{DORMANT_MARK}{base}"


def _fleet_from_channel(cat: str | None, base: str, society_names: set[str]) -> str | None:
    """Reverse of channel_name: (category, base) -> fleet."""
    if cat in society_names:
        return f"{cat}-{base}"
    if cat == OTHER_CATEGORY:
        return base
    return None


def compute_target(roster: dict[str, list[str]], members: dict[str, list[str]]) -> list[dict]:
    """One ACTIVE channel per manager-bearing fleet, in its society or 'other'."""
    manager_fleets = {f for f, seats in roster.items() if "manager" in seats}
    assigned: set[str] = set()
    plan: list[dict] = []
    for society, fleets in sorted(members.items()):
        for fleet in sorted(set(fleets) & manager_fleets):
            assigned.add(fleet)
            plan.append(_channel(fleet, society, roster))
    for fleet in sorted(manager_fleets - assigned):     # society-less -> 'other'
        plan.append(_channel(fleet, None, roster))
    return plan


def _channel(fleet: str, society: str | None, roster: dict[str, list[str]]) -> dict:
    others = [s for s in roster.get(fleet, []) if s != "manager"]
    return {
        "category": society or OTHER_CATEGORY,
        "channel": channel_name(fleet, society),
        "fleet": fleet,
        "default_target": f"{fleet}:manager",
        "aliases": {s: f"{fleet}:{s}" for s in others},
    }


# ---- Discord (read-only here; writes only under --apply) ------------------- #

def discord_env() -> dict[str, str]:
    return dict(l.strip().split("=", 1) for l in
                open(os.path.expanduser("~/.aura/discord/env")) if "=" in l)


def discord_api(method: str, path: str, token: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{DISCORD_API}{path}", data=data, method=method,
        headers={"Authorization": f"Bot {token}", "User-Agent": USER_AGENT,
                 "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=20).read() or b"{}")


def guild_id(env: dict[str, str]) -> str:
    ch = discord_api("GET", f"/channels/{env['DISCORD_CHANNEL_ID']}", env["DISCORD_TOKEN"])
    return ch["guild_id"]


def fetch_state(env: dict[str, str], gid: str) -> dict:
    chans = discord_api("GET", f"/guilds/{gid}/channels", env["DISCORD_TOKEN"])
    cats_by_name = {c["name"]: c["id"] for c in chans if c["type"] == CT_CATEGORY}
    cats_by_id = {v: k for k, v in cats_by_name.items()}
    text = [c for c in chans if c["type"] == CT_TEXT]
    # index by (category, BASE name) — the 💤 marker is not part of identity
    by_base = {(cats_by_id.get(c.get("parent_id")), _base_name(c["name"])): c for c in text}
    return {"cats_by_name": cats_by_name, "cats_by_id": cats_by_id, "text": text, "by_base": by_base}


def load_bindings() -> dict:
    try:
        return json.loads(BINDINGS_PATH.read_text()).get("channels", {})
    except Exception:
        return {}


def _binding_matches(current: dict | None, c: dict) -> bool:
    # Up to date when the default target matches and every DESIRED alias is present
    # (subset). Extra stored aliases are tolerated: bind-channel is additive and a
    # transiently-dead seat's alias is kept dormant rather than churned. Rebind only
    # when a desired alias is missing/wrong (a new or renamed live seat).
    if not current or current.get("default_target") != c["default_target"]:
        return False
    cur_aliases = dict(current.get("aliases") or {})
    return all(cur_aliases.get(name) == target for name, target in c["aliases"].items())


def build_plan(target: list[dict], state: dict, env: dict[str, str], bindings: dict,
               roster: dict[str, list[str]], society_names: set[str], known: set[str]) -> dict:
    """Diff the desired projection against the live guild. Identity is (category,
    BASE name); the 💤 prefix is derived from liveness, so a re-run is a no-op."""
    home = env.get("DISCORD_CHANNEL_ID")

    needed_cats = sorted({c["category"] for c in target}) + [ARCHIVE_CATEGORY]
    categories = [{"name": cat, "id": state["cats_by_name"].get(cat),
                   "action": "exists" if cat in state["cats_by_name"] else "create"}
                  for cat in needed_cats]

    channels: list[dict] = []
    archive: list[dict] = []
    handled: set[str] = set()

    # 1. ACTIVE targets (manager-bearing). Match existing by (category, base), so a
    #    revived dormant channel (💤base) matches and gets the 💤 stripped.
    for c in target:
        existing = state["by_base"].get((c["category"], c["channel"]))
        cid = existing["id"] if existing else None
        rename = c["channel"] if (existing and existing["name"] != c["channel"]) else None
        bind_ok = _binding_matches(bindings.get(str(cid)) if cid else None, c)
        channels.append({**c, "id": cid, "dormant": False,
                         "action": "exists" if existing else "create",
                         "rename": rename,
                         "bind_action": "current" if bind_ok else "bind"})
        if existing:
            handled.add(existing["id"])

    # 2. Existing channels not claimed by an active target.
    for ch in state["text"]:
        if ch["id"] in handled:
            continue
        name = ch["name"]
        cat = state["cats_by_id"].get(ch.get("parent_id"))
        base = _base_name(name)
        if ch["id"] == home or base in SELF_CHANNELS or base in PROTECTED_CHANNELS:  # protected non-fleet
            continue
        if cat == ARCHIVE_CATEGORY:                          # already archived — no-op
            continue
        fleet = _fleet_from_channel(cat, base, society_names)
        if fleet and fleet in known:
            # a known fleet channel with no live manager: KEEP in place, mark by liveness.
            live = roster.get(fleet, [])
            desired = base if live else _dormant_name(base)
            channels.append({
                "category": cat, "channel": base, "fleet": fleet, "id": ch["id"],
                "dormant": not live, "action": "exists",
                "rename": desired if name != desired else None,
                "default_target": f"{fleet}:manager", "aliases": {},
                "bind_action": "current",     # dormant / manager-less: binding kept, never rebind
            })
        else:
            archive.append({"id": ch["id"], "name": name, "from": cat or "(uncategorized)"})

    return {"categories": categories, "channels": channels, "archive": archive}


def deltas(plan: dict) -> dict:
    return {
        "categories": [c for c in plan["categories"] if c["action"] == "create"],
        "channels": [c for c in plan["channels"] if c["action"] == "create"],
        "renames": [c for c in plan["channels"] if c.get("rename")],
        "binds": [c for c in plan["channels"] if c["bind_action"] == "bind"],
        "archive": plan["archive"],
    }


# ---- Plan rendering -------------------------------------------------------- #

def render(plan: dict) -> str:
    by_cat: dict[str, list[dict]] = {}
    for c in plan["channels"]:
        by_cat.setdefault(c["category"], []).append(c)
    d = deltas(plan)
    lines = ["DISCORD LIVE PROJECTION — DRY RUN (nothing mutated)\n"]
    for cat in list(by_cat) + [ARCHIVE_CATEGORY]:
        cstate = next((x for x in plan["categories"] if x["name"] == cat), None)
        tag = "[create]" if cstate and cstate["action"] == "create" else "[exists]"
        lines.append(f"▸ #{cat}/   {tag}")
        if cat == ARCHIVE_CATEGORY:
            for a in plan["archive"]:
                lines.append(f"    ↳ archive  #{a['name']:<24} ({a['id']})  from #{a['from']}")
            if not plan["archive"]:
                lines.append("    (nothing to archive)")
            continue
        for c in sorted(by_cat.get(cat, []), key=lambda c: (c["dormant"], c["channel"])):
            disp = (_dormant_name(c["channel"]) if c["dormant"] else c["channel"])
            if c["action"] == "create":
                state_tag = "NEW"
            elif c.get("rename"):
                state_tag = "REVIVE" if not c["dormant"] else "DORMANT"
            else:
                state_tag = "dormant" if c["dormant"] else "active"
            bind = "bind" if c["bind_action"] == "bind" else "ok"
            lines.append(f"    ├─ #{disp:<16} ⇐ {c['fleet']}   [{state_tag}; binding:{bind}]")
            if not c["dormant"]:
                lines.append(f"    │     default → {c['default_target']}")
                if c["aliases"]:
                    lines.append("    │     aliases → " + ", ".join(f"@{k}→{v}" for k, v in c["aliases"].items()))
    lines.append(f"\nDELTA: +{len(d['categories'])} categories, +{len(d['channels'])} channels, "
                 f"{len(d['renames'])} renames (💤), {len(d['archive'])} to archive, {len(d['binds'])} (re)binds.")
    if not any(d.values()):
        lines.append("RE-RUN NO-OP ✓ — the guild already matches the live projection.")
    return "\n".join(lines)


# ---- Apply (gated; idempotent — only the delta) ---------------------------- #

def apply(plan: dict, env: dict[str, str], gid: str) -> dict:
    tok = env["DISCORD_TOKEN"]
    cats = {c["name"]: c["id"] for c in plan["categories"] if c["id"]}
    counts = {"categories": 0, "channels": 0, "renames": 0, "archived": 0, "binds": 0}
    for c in plan["categories"]:                            # skip-existing
        if c["action"] == "create":
            made = discord_api("POST", f"/guilds/{gid}/channels", tok, {"name": c["name"], "type": CT_CATEGORY})
            cats[c["name"]] = made["id"]; counts["categories"] += 1
            print(f"created category #{c['name']} ({made['id']})"); time.sleep(0.5)
    for a in plan["archive"]:                               # true-legacy only
        discord_api("PATCH", f"/channels/{a['id']}", tok, {"parent_id": cats[ARCHIVE_CATEGORY]})
        counts["archived"] += 1; print(f"archived #{a['name']} ({a['id']})"); time.sleep(0.5)
    for c in plan["channels"]:
        cid = c["id"]
        if c["action"] == "create":
            made = discord_api("POST", f"/guilds/{gid}/channels", tok,
                               {"name": c["channel"], "type": CT_TEXT, "parent_id": cats[c["category"]]})
            cid = made["id"]; counts["channels"] += 1
            print(f"created #{c['category']}/#{c['channel']} ({cid})"); time.sleep(0.5)
        elif c.get("rename"):                               # dormant<->active in place; id + category unchanged
            discord_api("PATCH", f"/channels/{cid}", tok, {"name": c["rename"]})
            counts["renames"] += 1; print(f"renamed #{cid} -> #{c['rename']}"); time.sleep(0.5)
        if c["bind_action"] == "bind":
            bind = [str(AURA_CLI), "discord", "bind-channel", cid,
                    "--fleet", c["fleet"], "--default-target", c["default_target"]]
            for name, tgt in c["aliases"].items():
                bind += ["--alias", f"{name}={tgt}"]
            subprocess.run([sys.executable, *bind], check=True, capture_output=True)
            counts["binds"] += 1; print(f"bound #{c['channel']} → {c['default_target']}"); time.sleep(0.3)
    return counts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Discord live-projection generator (dry-run default; safe to re-run).")
    ap.add_argument("--apply", action="store_true", help="Apply the delta (gated). A re-run against the projected guild is a no-op.")
    ap.add_argument("--json", action="store_true", help="Emit the plan + delta as JSON.")
    args = ap.parse_args(argv)

    roster, members = live_roster(), society_members()
    target = compute_target(roster, members)
    society_names = set(members)
    known = known_fleets(members)
    env = discord_env()
    gid = guild_id(env)
    state = fetch_state(env, gid)
    plan = build_plan(target, state, env, load_bindings(), roster, society_names, known)
    d = deltas(plan)

    if args.json:
        print(json.dumps({"guild_id": gid, "plan": plan, "delta": d}, indent=2, default=str))
    else:
        print(render(plan))

    if args.apply:
        if not any(d.values()):
            print("\n--apply: NO-OP — the guild already matches the live projection (0 changes).")
            return 0
        print("\n--apply: MUTATING DISCORD…\n")
        print(f"\napply complete: {apply(plan, env, gid)}")
    else:
        print("\n(dry-run — re-run with --apply only after operator approval; safe to re-run.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

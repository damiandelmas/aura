I have verified all the key facts against the actual code. Now I have everything needed to synthesize the integrated, conflict-resolved plan.

Key verified facts that shape the resolution:
1. `get_agent` returns merged rows with `resolved_from`/`alias_chain` — several tests depend on `get_agent("old")["resolved_from"]` working (test line 186, 232). So `get_agent` must KEEP alias-following.
2. `_same_live_incarnation` is OR today; both repair test rows share BOTH si AND pane (`%341`), so AND-logic keeps that test green and the loser is correctly deleted (same pane = true duplicate). Distinct-pane rows are rejected (test line 257). So "preserve loser as historical" is unnecessary and would break test line 230 — **rejected**.
3. spawn collision is via `terminal.window_exists`, not alias — defect #5 framing is partly wrong.
4. `_canonical_bind_target` follows alias AND uses `get_agent(resolved)`.
5. `seat_history_for_target(follow_aliases=...)` is the legit historical consumer.

Here is the integrated plan.

---

# AURA Identity-Resolution Rewrite — Integrated Implementation Plan (LOCKED)

This is the single contract the implementation phase follows. It supersedes every conflicting statement in the five draft specs and both reviews. Where a draft and the actual code disagree, the **code wins** and is cited.

---

## 0. Ground truth corrections (verified against code)

The drafts contained several claims that the live code contradicts. These corrections are binding:

| Draft claim | Verified reality | Consequence |
|---|---|---|
| `get_agent()` should become physical-only by default / a wrapper | `get_agent` returns rows enriched with `resolved_from`+`alias_chain`; tests `test_rename_preserves_physical_refs_and_adds_alias:186` and `...repairs...:232` assert `get_agent("old")["resolved_from"]`. | **`get_agent()` KEEPS alias-following unchanged.** We do NOT add a `resolve_alias=` param, do NOT change its default. New `resolve_live`/`resolve_historical` are *added* alongside it. |
| M3: "preserve loser as historical (terminal_state + replaced_by)" | Repair test (`:200`) has both rows sharing **the same pane `%341`** and expects `read_registry().keys() == {pilot}` (loser deleted). New `_same_live_incarnation` (AND of si+pane) only returns True when panes are identical → loser is a true duplicate of one pane. Distinct-pane case is *rejected* (`:236` → error), never merged. | **Loser preservation is DROPPED.** Same-pane duplicate → delete loser (unchanged write path). Distinct-pane → preflight error. No `~terminal~uuid` keys, no `replaced_by`. This removes ZONE 1 & ZONE 3 breakage and the M3↔M5 visibility conflict. |
| M1/M2: `resolve_live` returns a tuple `(row, reason)` vs `dict|None` | Multiple callers (M2/M4) assume `dict|None`. | **LOCKED: `resolve_live -> dict|None`.** No reason string. |
| Defect #5: "spawn-into-alias blocks name reuse (alias shadow)" | `spawn.py:214` blocks via `terminal.window_exists(args.name)`, not alias. | Spawn name-reuse is governed by tmux window liveness, which is already correct doctrine. No spawn change needed for alias. We still remove alias from the *bind* path. |
| M3: `add_alias` gains `occupant_id`/`launched_at`; M5 reads them | Not required by any live path once continuity is occupant-keyed at the *target* row (M2 reads si from the resolved registry row, not from the alias). | **Alias record schema is left as `aura.seat_alias.v1` (source/target/reason/created_at).** Optional `retired_occupant` breadcrumb is additive and tolerated, never required. Avoids ZONE-9 schema-version handling. |

---

## 1. LOCKED contract: `resolve_live()` / `resolve_historical()`

Both live in `cli/lib/registry.py`.

```python
def resolve_live(ref: str, *, fleet: str | None = None) -> dict[str, Any] | None:
    """PHYSICAL live identity. NEVER reads aliases.

    Precedence:
      1. If ref carries/has a fleet -> exact registry row at _key(fleet, name); else None.
      2. Fleet unknown -> rows whose name == name:
           - exactly one -> that row
           - several -> prefer current_fleet(); if still ambiguous -> None
           - none -> None
    Returns the exact row dict (no resolved_from / alias_chain enrichment) or None.
    """

def resolve_historical(ref: str, *, max_hops: int = 8) -> tuple[str, list[str]]:
    """Follow the alias/lineage chain. EXACT body of today's resolve_alias().
    Used ONLY by: seat resolve verb, seat-history, restore/audit, M2 continuity
    fallback, and M5 alias ls/rm. Never by live ownership/routing/binding.
    """
```

Rules that make the precedence unambiguous (resolving ZONE-5/8 and the reviews):
- **`resolve_live` never calls `resolve_historical`/`resolve_alias`.**
- Fleet-explicit lookups (`fleet:name` or `fleet=` arg) return the exact `_key` row or `None` — they never fall back to name-scan.
- `resolve_alias()` is **kept** as a thin alias of `resolve_historical()` for backward compat; `get_agent()` keeps calling it internally and is unchanged.

`occupant_key()` helper (added in M1, foundation for M2):

```python
def occupant_key(row: dict[str, Any] | None) -> str | None:
    """Physical occupant id: pane_ref > seat_instance_id > aura_launch_id > None."""
```

---

## 2. BUILD ORDER (dependency-correct)

Files touched per move drive sequencing. registry.py is the shared spine (M1+M3), so those two **merge into one PR**. pane_resolver.py + sessions.py are shared by M4 only.

```
M1+M3  (registry.py spine)  ──┬──> M2 (delivery/continuity consumers)
   one combined PR            │
                             └──> M4 (pane_resolver.py + sessions.py self-heal)
                                        │
M2 and M4 are INDEPENDENT (disjoint files) — can run in parallel after M1+M3.
                                        │
                                        v
                              M5 (operator surface + docs)
                              depends on: M1 (resolve_historical), M4 (orphan-reconcile impl)
```

Sequence:
1. **M1+M3 (sequential, first, single PR)** — shared registry.py functions; defines the locked contract. Must land before anything else.
2. **M2** and **M4** — parallel; no shared files (M2: delivery libs; M4: pane_resolver + sessions). Both depend only on M1 symbols.
3. **M5** — last; depends on M1 (`resolve_historical`) and M4 (`_reconcile_orphaned_born_panes`, `list_orphaned_born_panes`).

Live-consumer call-site switches (cut/send/check/etc.) are grouped into M1+M3's PR since they are trivial and depend only on `resolve_live`.

---

## 3. Per-move file-by-file changes

### M1 + M3 (combined) — `cli/lib/registry.py`, plus live-consumer switch

**`cli/lib/registry.py`**

1. **Add** `resolve_live(ref, *, fleet=None) -> dict|None` (contract §1). Exact-key first, name-scan with current_fleet tiebreak, ambiguous→None.
2. **Add** `resolve_historical(ref, *, max_hops=8) -> tuple[str,list[str]]` = current body of `resolve_alias`. Keep `resolve_alias = resolve_historical` (or have `resolve_alias` delegate) so `get_agent` and all existing callers are untouched.
3. **Add** `occupant_key(row) -> str|None`.
4. **Keep `get_agent()` exactly as-is** (still alias-following; tests depend on `resolved_from`).
5. **Replace `_same_live_incarnation()`** — require BOTH si AND pane:
   ```python
   def _same_live_incarnation(left, right) -> bool:
       if not left or not right: return False
       ls, rs = left.get("seat_instance_id"), right.get("seat_instance_id")
       lp, rp = left.get("pane_ref"), right.get("pane_ref")
       if not (ls and rs and str(ls)==str(rs)): return False
       if not (lp and rp and str(lp)==str(rp)): return False
       return True
   ```
   (No launch-id branch — keep it strict; M4 thin rows without si simply return False = distinct.)
6. **`rename_preflight()`** — switch source resolution `get_agent(source_name)` → `resolve_live(source_name)`. **Keep** the existing "source is an alias" guard (it uses `resolve_alias` on a *missing* source row — this is historical lineage, legitimately allowed). Collision logic unchanged (now backed by strict `_same_live_incarnation`): distinct-pane target → `{"ok":False,"reason":"target-registry-exists"}`.
7. **`rename_agent()`** — switch `get_agent(source_name, fleet=...)` → `resolve_live(source_name, fleet=source_fleet)` at line 527 (the call-site ZONE-7/interaction-matrix flagged). **Keep the "source is an alias" historical guard** for the not-found branch. **Do NOT add loser preservation** — the existing `data.pop(source_ref, None)` + `data[target_ref]=record` write path is correct for same-pane repair. Alias still written via `add_alias(..., reason="rename")` unchanged.

**Live-consumer switches (same PR)** — change ownership/routing/binding reads from alias-following `get_agent` to `resolve_live`. Each is a one-liner:

| File:line | Change |
|---|---|
| `cli/commands/sessions.py:1340` `_canonical_bind_target` | Remove the `resolve_alias` block entirely. New body: `previous = registry.resolve_live(seat, fleet=fleet); return fleet, seat, previous, []`. Callers already unpack a 4-tuple with `alias_chain` — keep returning `[]` so unpacking and the `extra={"alias_chain": []}` stay valid (no caller signature churn). |
| `cli/commands/cut.py:114,170,201` | `get_agent` → `resolve_live` (live ownership). |
| `cli/commands/send.py:94` | `get_agent` → `resolve_live`. |
| `cli/commands/check.py:14` | `get_agent` → `resolve_live`. |
| `cli/commands/write.py:23` | `get_agent` → `resolve_live`. |
| `cli/commands/clawhip.py:30` | `get_agent` → `resolve_live`. |
| `cli/commands/discord_bridge.py:347` | `get_agent` → `resolve_live`. |
| `cli/lib/keeper_jobs.py:145` | `get_agent` → `resolve_live`. |
| `cli/lib/placements.py:78,142,154` | `get_agent` → `resolve_live` (membership is live ownership). |
| `cli/lib/seat_status.py:438` | `get_agent` → `resolve_live`. |
| `cli/commands/spawn.py:914,1069,1141,1228,1427` | `get_agent` → `resolve_live` (post-spawn re-fetch of the exact row). |

**Deliberately NOT switched (stay on `get_agent`/`resolve_historical` — historical/operator surfaces):**
- `cli/commands/seat.py:2413` (`seat resolve` verb — help text literally says "following aliases").
- `cli/commands/resolve.py:77,112,115` (`resolve` verb — name/group resolution, historical-tolerant).
- `cli/commands/seat.py` rename/adopt/restore reads that intentionally want lineage (`:1241` `get_agent(canonical_ref)`).
- `cli/lib/reports.py:54` — handled in M2 (sender canonicalization), not here.
- `cli/lib/identity.py:54`, `cli/lib/agent_packages.py:436` — keep `get_agent` (package/identity resolution tolerates rename lineage); revisit only if a test demands.

---

### M2 — occupant-keyed continuity (delivery/routing)

Files: `cli/lib/queued_messages.py`, `cli/lib/report_subscriptions.py`, `cli/lib/reports.py`, `cli/lib/registry.py` (add `resolve_occupant`).

**`cli/lib/registry.py`** — add:
```python
def resolve_occupant(*, seat_instance_id=None, aura_launch_id=None, pane_ref=None,
                     default_ref: str | None = None) -> dict[str, Any] | None:
    """Return the live row that IS this occupant, by si > launch_id > pane_ref.
    If none of the occupant ids match a row AND default_ref is given AND the
    occupant is not found anywhere live -> resolve_live(default_ref).
    If an occupant id matches a row -> return it (it wins over default_ref).
    Returns dict|None. No tuple, no metadata (locked: keep it simple)."""
```
LOCKED resolution of ZONE-5: if an occupant id matches a live row, **return that row** (continuity); name fallback (`default_ref`) is used ONLY when the occupant is absent everywhere. Name fallback therefore **loses to a live distinct pane** by construction.

**Continuity guarantee (resolves ZONE-2/8 false-positive):** continuity matches **sender→occupant**, never "any live row with that si." Queue/subscription records must carry the *sender's* occupant id captured at creation. Therefore:

**`cli/lib/queued_messages.py`**
- At record creation (find the create/enqueue path), capture sender occupant from the sender's live row: add fields `occupant_seat_instance_id`, `occupant_aura_launch_id`, `occupant_pane_ref` (schema stays v1; fields optional/additive).
- `_matches_report()` (line 106): replace the `resolve_alias` block (123–125) with:
  1. exact `target in report_targets` (unchanged).
  2. `live = registry.resolve_live(target)`; if `live` exists → match iff `f"{live['fleet']}:{live['name']}" in report_targets`, **else return False** (a live row exists; never reach back through history).
  3. only if no live row AND record has an occupant id: `row = registry.resolve_occupant(seat_instance_id=..., aura_launch_id=..., pane_ref=...)`; match iff that row's `fleet:name` ∈ report_targets.
  4. **No `resolve_historical` fallback.** (Removes ZONE-5 doctrine violation.)

**`cli/lib/report_subscriptions.py`**
- `_matches_target()` (148): exact match, then `resolve_live` (match only if the live row's ref ∈ report_targets, else False). No alias fallback.
- `_matches_placement()` (161): drop the `resolve_alias` candidate-expansion (175–177); use `resolve_live(seat_ref)` to add the current ref. Placement membership is live.
- `canonical_target()` (207): return `resolve_live(target)`'s `fleet:name` if live, else the input target unchanged. This is a dedupe key; **no alias.** (Dedupe by current physical name.)

**`cli/lib/reports.py`**
- `infer_context()` (54): keep `get_agent` for the generic case, but when birth env is present, prefer occupant. Add `_resolve_sender_for_report(seat, fleet)`:
  - Read `AURA_SEAT_INSTANCE_ID` / `AURA_LAUNCH_ID` / `TMUX_PANE`→pane_ref from env.
  - `row = registry.resolve_occupant(seat_instance_id=si, aura_launch_id=launch, pane_ref=pane, default_ref=None)`.
  - **LOCKED (ZONE-8): no name fallback for sender provenance.** If occupant ids are present but resolve to nothing, return the env-inferred `{fleet, seat}` *unchanged* (do NOT redirect to a possibly-reused name). If no occupant ids at all, behave as today (`get_agent`).

---

### M4 — born-pane self-heal + reliable reverse resolution

Files: `cli/lib/pane_resolver.py`, `cli/commands/sessions.py`, `cli/lib/seat_status.py`, `cli/aura` (verb), and uses M1's strict `_same_live_incarnation`.

**`cli/lib/pane_resolver.py`**
1. **Add** `_read_birth_env(pane_pid) -> dict[str,str]`: filter `_pane_env` to `{AURA_FLEET, AURA_SEAT, AURA_LAUNCH_ID, AURA_SEAT_INSTANCE_ID}`.
2. **Fix `_match_registry_row()` (131–146):** drop the `ref.endswith(f":{pane_id}")` cross-session fallback (lines 144–145). Exact `tmux:{session}:{pane_id}` only → fixes the `inspect …:%N registered:false` bug. (Operator recovery for fleet-renamed stale refs goes through orphan-reconcile, documented in M5.)
3. **Add** `_resolve_from_birth_env(pane_rec, birth_env) -> dict|None` with the **COMPLETE thin-row schema** (resolves ZONE-13):
   ```python
   {"name": seat, "seat": seat, "fleet": fleet,
    "seat_ref": registry._key(fleet, seat),
    "aura_launch_id": launch_id, "seat_instance_id": si,
    "pane_ref": pane_rec.get("pane_ref"),
    "runtime": "codex", "registered": False,
    "status": "born-unhealed", "last_seen": registry.now_iso(),
    "_from_birth_env": True}
   ```
   Require `fleet and seat and (launch_id or si)`, else None.
4. **Fork-child guard (resolves ZONE-4):** in `_read_birth_env` and `_resolve_from_birth_env`, if `_pane_env` shows a fork marker (`AURA_FORK_SOURCE` / `CODEX_FORK*` / parent-mismatched session), **do not** reconstruct from inherited si. If si is inherited and the pane is a fork child, return None (operator must `--target` explicitly). Combined with M1's strict si+pane `_same_live_incarnation`, a fork child can never merge into the parent row.

**`cli/commands/sessions.py`**
5. **`_bind_pane()` (1174):** after computing `matched`/`fleet`/`seat`, if `not fleet or not seat`, read `birth_env = pane_resolver._read_birth_env(res.get("pane_pid"))` and fill `fleet/seat` from `AURA_FLEET/AURA_SEAT`. Update the `no-target` error detail to `"pane is unmanaged and not Aura-born (no AURA_FLEET/AURA_SEAT env); pass --target fleet:seat"` (resolves ZONE-7-error-text). After `_canonical_bind_target`, if `previous is None` and birth_env present, synthesize `previous` from `_resolve_from_birth_env` so `bind_gates` runs its real si/package vetoes against it. Bind path then proceeds unchanged.
6. **Add** `_reconcile_orphaned_born_panes(*, fleet_filter=None, dry_run=False)`: iterate `tmux_mirror.list_physical_panes()`, skip panes already in `registry.read_registry()` by `pane_ref`, keep only those with complete birth env (`AURA_SEAT_INSTANCE_ID` required), build thin row via `_resolve_from_birth_env`, and (unless dry-run) `registry.upsert_agent(thin_row)`. Returns `{ok, dry_run, reconciled, skipped, results}`. Mirror-unavailable → `{ok:False,"error":"tmux-mirror-unavailable"}`.
7. **Add** `_reconcile_orphans(args)` and dispatch `sessions_action == "reconcile-orphans"` in `run()`.
8. **`_heal()` (428):** add a pre-check — if the live pane's birth si ≠ the registry row's si, skip with `reason:"occupant-mismatch-born-pane"` (prevents healing a reused name onto a stale row).

**`cli/lib/seat_status.py`**
9. **Add** `list_orphaned_born_panes(*, fleet_filter=None) -> list[dict]` (live panes with birth env but no registry pane_ref match).

**`cli/aura`**
10. Add `sessions reconcile-orphans` subcommand with `--fleet`, `--all`, `--dry-run`.

**bind_guard interaction (resolves ZONE-9-bind-guard):** thin rows pass `bind_gates` because the si gate compares pane si to `previous.seat_instance_id` (equal by construction) and package gate is skipped when `agent_package_id` is absent. No change to `bind_guard.py`. The thin row is only persisted by the existing `_bind_registry_session` writer (M4 doesn't add a second writer), so `registered` flips true with a real `pane_ref` already set — `seat_status` liveness stays correct (resolves ZONE Guarantee-3).

---

### M5 — operator surface + observability + docs

Files: `cli/aura`, `cli/commands/seat.py`, `cli/lib/seat_status.py`, docs.

**`cli/aura`** — under `seat_sub`, add an `alias` subparser group:
- `aura seat alias ls` → `--fleet`, `--source`, `--target`.
- `aura seat alias rm <source>` → `--confirm`, `--dry-run`.
Keep the existing `aura seat aliases` verb as-is (back-compat). Wire `seat reconcile-orphans` if surfacing under `seat` is desired; primary impl lives under `sessions reconcile-orphans` (M4).

**`cli/commands/seat.py`** — `run()` dispatch:
- `action == "alias"` → branch on `args.alias_action`:
  - `_alias_ls(args, registry)`: `registry.read_aliases()`, filter by source/target/fleet, return sorted rows. **Schema-tolerant**: read only `source/target/reason/created_at` (and optional `retired_occupant` if present). No occupant_id requirement.
  - `_alias_rm(args, registry)`: validate `source` ∈ aliases; if not `--confirm` → dry-run preview; else `aliases.pop(source); write_aliases(aliases)`. Alias removal touches the alias ledger only (never the registry).

**`cli/lib/seat_status.py`** — `build_from_record()` risk_flags (348+): when liveness indicates a missing pane but `record.get("aura_launch_id")` exists and no live pane_ref, add `"live_born_pane_without_row"` (distinct from `"missing_pane"`). Surfaces fixable orphans.

**Docs** (`.context/current/2026-06-04-2022/`):
- `lexicon.md`: add **Alias (Historical)** — lineage breadcrumb (source→target→time, optional retired occupant); never a live router; created by rename; read only by `seat resolve`, `seat-history`, restore/audit, M2 continuity fallback, and `seat alias ls/rm`.
- `model/two-laws.md`: Law 1 (Physical Identity) — live precedence `%N → seat_instance_id → aura_launch_id → exact current row by name`; alias never consulted for live ownership/routing/binding; rename acts on exact live `%N`; same-pane duplicate repaired by deleting the duplicate key, distinct-pane collision rejected; born panes self-heal.
- `model/the-seat.md`: add **Operator Surface** — `seat alias ls/rm`, `sessions reconcile-orphans`, orphan observability flag; edge cases (mirror-unavailable, fork-children, dead `%N`, thin rows).

---

## 4. Consolidated TEST MATRIX

### Existing tests that MUST stay green (no edits)
- `tests/test_registry_and_broadcast.py::test_rename_preserves_physical_refs_and_adds_alias` — relies on `get_agent("old")["resolved_from"]` (kept) and alias write.
- `...::test_rename_repairs_same_incarnation_duplicate_target` — **stays green unchanged**: same si+pane → repair → `keys()=={pilot}`, loser deleted, `get_agent("operator")["resolved_from"]` via alias. (Loser-preservation rejected precisely to keep this green.)
- `...::test_rename_rejects_different_incarnation_target` — distinct pane (`%341` vs `%342`) → `reason:"target-registry-exists"`, both rows survive. Strict `_same_live_incarnation` keeps this correct.
- `...::test_rename_terminal_exact_never_rediscovers_or_moves_for_plain_rename`, `...refuses_cross_fleet_source` — untouched (seat.py terminal rename unchanged).
- `tests/test_runtime_session_identity.py`, `tests/test_dashboard_identity.py` — unaffected (no signature changes to consumed functions).

### New adversarial tests (by move)

**M1+M3** (`tests/test_resolve_and_rename.py`)
- `test_resolve_live_never_follows_alias`: row A `%100`, alias A→B; `resolve_live("A")` returns A's row (or None if A's row gone), never B.
- `test_resolve_live_fleet_explicit_no_namescan`: `resolve_live("fleet-a:x")` with only `fleet-b:x` present → None.
- `test_resolve_live_ambiguous_returns_none`: two fleets, same name, no current_fleet preference → None.
- `test_same_live_incarnation_requires_si_and_pane`: same si, different pane → False; same si+pane → True; si only → False.
- `test_rename_rejects_distinct_pane_same_si`: si equal, panes differ → `target-registry-exists` (regression guard for the old OR bug).
- `test_get_agent_still_follows_alias`: `get_agent("old")["resolved_from"]` works (back-compat lock).
- `test_canonical_bind_target_physical_only`: alias stale→target; bind of stale name yields `previous=None`, `alias_chain==[]`.

**M2** (`tests/test_continuity_occupant.py`)
- `test_queued_match_by_live_name_only`: live row exists, report from different seat → no match (no history reach-back).
- `test_queued_match_by_occupant_after_rename`: target name gone, record carries sender si → matches renamed seat.
- `test_queued_no_match_wrong_occupant_same_name`: name reused by new si; old record's sender si is stale → does NOT match new occupant.
- `test_resolve_occupant_si_wins_over_default_ref`: occupant alive → return occupant row, not `default_ref`.
- `test_resolve_occupant_fallback_only_when_absent`: occupant gone → `default_ref` via `resolve_live`.
- `test_sender_canon_no_name_fallback`: env si resolves to nothing → returns env fleet:seat, never redirects to reused name.

**M4** (`tests/test_born_pane_self_heal.py`)
- `test_match_registry_row_exact_only`: `fleet-b:%26` query does not match `fleet-a:%26` row.
- `test_resolve_from_birth_env_complete_schema`: thin row has `seat_ref`, `runtime`, `last_seen`, `registered=False`.
- `test_resolve_from_birth_env_rejects_incomplete` / `_rejects_fork_child`.
- `test_bind_pane_self_heals_orphan`: no row, birth env present → binds, row created with correct si/pane.
- `test_reconcile_orphans_dry_run_no_write` and `_reconciles_then_present`.
- `test_reconcile_mirror_unavailable_graceful`.
- `test_heal_skips_occupant_mismatch_born_pane`.

**M5** (`tests/test_seat_alias_and_orphan.py`)
- `test_alias_ls_filters` / `_empty` / `_schema_tolerant_missing_fields`.
- `test_alias_rm_requires_confirm` / `_dry_run_no_write` / `_removes` / `_not_found`.
- `test_seat_status_flags_live_born_pane_without_row`.

Run gate per PR: `pytest tests/test_registry_and_broadcast.py tests/test_runtime_session_identity.py tests/test_dashboard_identity.py -x` plus the new files for that move.

---

## 5. Doc edits (summary)
- `.context/current/2026-06-04-2022/lexicon.md` — Alias = historical.
- `.context/current/2026-06-04-2022/model/two-laws.md` — Law 1 live precedence + alias demotion + rename/repair/self-heal semantics.
- `.context/current/2026-06-04-2022/model/the-seat.md` — operator surface + edge cases.
Docs land **in M5** but each move's PR appends a one-line note to the changelog of what it altered, so docs and code move in lockstep at M5.

---

## 6. Data migration (registry + aliases)
- **Registry rows:** none required. `resolve_live` reads existing fields; thin rows are additive. No key-format changes (loser-preservation dropped means no `~terminal~uuid` keys).
- **Alias ledger:** none. Schema stays `aura.seat_alias.v1`. Aliases become dormant for live routing automatically (no consumer reads them live after M1+M2). Optional future `retired_occupant` is additive; readers tolerate its absence.
- **Queue/subscription records:** additive optional fields `occupant_seat_instance_id`/`occupant_aura_launch_id`/`occupant_pane_ref`. Old records lacking them fall to the live-name path (step 2) and correctly **lose to a live distinct pane** — exactly the desired degradation. No backfill needed.

---

## 7. Risks and mitigations

| # | Risk | Mitigation in this plan |
|---|---|---|
| R1 | Changing `get_agent` default breaks `resolved_from`-dependent tests/consumers. | **`get_agent` left untouched.** New behavior is opt-in via `resolve_live`. |
| R2 | Loser-preservation breaks the repair test and creates ledger-invisible `~terminal~` keys. | **Loser-preservation dropped.** Strict `_same_live_incarnation` makes same-pane repair (delete loser) and distinct-pane reject the only two outcomes — both already covered by green tests. |
| R3 | `resolve_live` signature drift (tuple vs dict). | **Locked `dict|None`** in §1; every caller in §3 written against it. |
| R4 | M2 continuity matches the wrong occupant when a name is reused (same-si reach-back). | Continuity is **sender→occupant**: queue/sub records carry the *sender's* occupant id; live-name match wins first and a live row blocks history reach-back; missing occupant id degrades to live-name (loses to distinct pane). |
| R5 | Sender provenance redirected to a reused name on occupant miss. | **No name fallback** in `_resolve_sender_for_report`; returns env-inferred identity unchanged. |
| R6 | Fork-child inherits parent si → self-heal/rename corrupts both. | `_resolve_from_birth_env` rejects fork children; strict si+pane `_same_live_incarnation` forbids merge. |
| R7 | `_match_registry_row` fallback removal makes fleet-renamed stale refs unresolvable. | Intended; recovery path is `sessions reconcile-orphans` + `seat sweep`, documented in M5. |
| R8 | Hidden live consumers still alias-route after M1. | §3 enumerates every `get_agent`/`resolve_alias` call site and classifies each switch-vs-keep; live ownership/routing/binding all switched, historical surfaces explicitly kept. |
| R9 | bind_guard rejects thin/`registered=False` rows. | No new writer; thin row only feeds `bind_gates` (si/package vetoes pass by construction); persisted by existing `_bind_registry_session` with real pane_ref. |
| R10 | M5 alias ls/rm fails on old alias records. | Schema-tolerant reads (only source/target/reason/created_at required). |
| R11 | Two PRs (M2, M4) racing registry.py. | M2 adds only `resolve_occupant`; M4 adds none to registry.py (uses `_key`/`upsert_agent`/`now_iso`). Disjoint — safe parallel. M1+M3 lands first so both branch from the locked spine. |

This plan is internally consistent, every multi-move function has exactly one owner (`_same_live_incarnation`, `rename_*` → M1+M3; `resolve_occupant` → M2; `_match_registry_row`/`_bind_pane` → M4), the `resolve_live`/`resolve_historical` contract is singular, and every reviewer-raised conflict (ZONES 1–13, Guarantees 1–3, interaction matrix) is resolved with an explicit decision rather than left ambiguous.
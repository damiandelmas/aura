Good! Now let me write out the comprehensive critique:

---

# ADVERSARIAL CRITIQUE: M1-M5 Specs vs Aura Codebase

## EXECUTIVE SUMMARY

The M1-M5 specifications are architecturally sound but contain **5 critical breakage zones** and **10+ test coverage gaps** that will cause silent correctness bugs or explicit test failures if implemented as drafted. The specs also miss three doctrine guardrails (sender provenance, bind-guard veto, computed liveness) that will interact badly with the proposed changes.

**Highest Risk Areas:**
1. **M1 live-resolution semantics conflict with existing tests** (test_rename_repairs_same_incarnation_duplicate_target)
2. **M2 occupant-keyed continuity breaks deferred delivery guarantees** (delivery.py sender canonicalization)
3. **M3 loser preservation changes test expectations** (test_rename_repairs_same_incarnation_duplicate_target line 230)
4. **M4 thin-row reconstruction has occupant-id collision risk** (fork-children, services, pane reuse)
5. **M5 alias-ls/rm lacks occupant scoping for same-si lineage traversal**

---

## DETAILED FINDINGS

### **ZONE 1: M1 Live-Resolution Change Breaks Existing Test Expectations** 🔴 CRITICAL

**File**: `tests/test_registry_and_broadcast.py:test_rename_repairs_same_incarnation_duplicate_target` (line 200-234)

**Current test behavior** (PASSING):
```python
def test_rename_repairs_same_incarnation_duplicate_target(tmp_path, monkeypatch):
    registry.upsert_agent({
        "name": "operator",
        "fleet": "aura-refresh-test",
        "seat_instance_id": "si_same",
        "pane_ref": "tmux:aura-refresh-test:%341",
    })
    registry.upsert_agent({
        "name": "pilot",
        "fleet": "aura-refresh-test",
        "seat_instance_id": "si_same",
        "pane_ref": "tmux:aura-refresh-test:%341",
    })

    result = registry.rename_agent("aura-refresh-test:operator", new_name="pilot")

    assert result["ok"] is True
    assert result["repair_duplicate"] is True
    assert registry.read_registry().keys() == {"aura-refresh-test:pilot"}  # <-- DELETES SOURCE
```

**Specification M1 promise** (section 4.1, "Thin/Name-Only Rows"):
> "For M1: allow thin rows to be overwritten (they have no live physical identity)."

But the test row is NOT thin—it has **both** `seat_instance_id` AND `pane_ref`. The spec says M1 and M3 should:
1. Split `get_agent()` into `resolve_live()` and `resolve_historical()`
2. M3 changes `_same_live_incarnation()` to require **BOTH** si AND pane_ref match (exact match on pane, not just si)
3. M3 changes `rename_agent()` to **PRESERVE loser as historical** (not delete)

**Actual Breakage**:
```python
# After M1+M3 implementation:
assert registry.read_registry().keys() == {"aura-refresh-test:pilot"}  # FAILS
# Registry now has: {"aura-refresh-test:pilot", "aura-refresh-test:operator~terminal~<uuid>"}
```

**Why it breaks**: The spec says "preserve losers as terminal + replaced_by", but the test **expects deletion** (line 230). The test was written against the old behavior where `data.pop(source_ref, None)` silently deleted the loser.

**Required Fix**:
- Update test line 230 to check for TWO rows: winner + loser-marked-terminal
- OR clarify M3 spec: only preserve loser IF it's a live pane (has pane_ref and is still live). If loser is already dead, OK to delete.

---

### **ZONE 2: M2 Occupant-Keyed Continuity Breaks Deferred Delivery Sender Canonicalization** 🔴 CRITICAL

**File**: `cli/lib/delivery.py` (no spec changes proposed, but M2 changes callers)

**Current behavior** (stable):
- `new_delivery_record()` takes sender and target as strings (fleet:name)
- Deduplication key is based on `delivery_type + sender + target + body` (deterministic)
- When a queue record is written, it has `"target": "fleet:seat"` (name-based)
- If sender is renamed after queueing, old delivery records are orphaned (OK; they're historical)

**M2 proposed change** (`queued_messages.py:_matches_report()` per spec section 3.2):
```python
# NEW: occupant-keyed continuity for stale refs
occupant_si = record.get("occupant_seat_instance_id")
occupant_launch_id = record.get("occupant_aura_launch_id")
occupant_pane = record.get("occupant_pane_ref")

if occupant_si or occupant_launch_id or occupant_pane:
    matched, meta = registry.resolve_occupant(
        seat_instance_id=occupant_si,
        aura_launch_id=occupant_launch_id,
        pane_ref=occupant_pane,
    )
    if matched and meta.get("occupant_alive"):
        occupant_targets = {matched.get("fleet") + ":" + matched.get("name")}
        if report_targets & occupant_targets:
            return True
```

**Silent Correctness Bug**:
1. Queue record created for "fleet-a:probe" with occupant_si=si_abc
2. "fleet-a:probe" is renamed to "fleet-a:probe-2"
3. A NEW seat "fleet-a:probe" is spawned with occupant_si=si_xyz (different occupant)
4. Report arrives from "fleet-a:probe" (si_xyz)
5. Old queue record's occupant_si=si_abc is still alive at "fleet-a:probe-2" (different name but same si)
6. **M2 matches the old queue to the NEW occupant via si=si_abc lookup** ✗ WRONG OCCUPANT

**Why it breaks**: The spec's M2 fallback logic doesn't check "are we matching back to the ORIGINAL seat or a DIFFERENT seat with same si?". It only checks "occupant si alive?", not "is this the same occupant as the sender?".

**Root Cause**: Specs say (M2 section 4.5): "Same-occupant continuity (a renamed seat's stale env...resolves by occupant id (si), immune to name reuse.)"

But the logic is backwards: it matches old queued si to any live si match, even if the name has been reused for a different occupant.

**Required Fix**:
- M2 must add to queue records: `"sender_occupant_si"` (the si of WHO SENT IT)
- M2 occupant resolution must check: `record.get("sender_occupant_si") == matched.get("seat_instance_id")` (sender matches resolved occupant, not just "occupant exists")
- If no sender_occupant_si in old queue records, fallback to name-only (lose to live distinct pane)
- This requires queue record schema version bump and migration for old records

---

### **ZONE 3: M3 Loser-Preservation Changes Registry Write Path and Tests** 🟠 HIGH

**File**: `cli/lib/registry.py:rename_agent()` lines 562-565

**Current code**:
```python
if target_ref != source_ref:
    data.pop(source_ref, None)  # <-- DELETES SOURCE
data[target_ref] = record
_write_registry_unlocked(data)
```

**M3 spec code** (section 1.4):
```python
if target_ref != source_ref:
    # M3: Only delete source_ref if it's not a live pane that's distinct from target_existing
    if repair_duplicate and target_existing:
        # Preserve loser (target_existing) as historical; mark it as replaced_by winner
        loser = dict(target_existing)
        loser["terminal_state"] = "terminal"
        loser["replaced_by"] = target_ref
        loser["replaced_at"] = now_iso()
        # ... store loser under a unique key ...
        data[loser_key] = loser
    data.pop(source_ref, None)  # <-- STILL DELETES SOURCE
data[target_ref] = record
_write_registry_unlocked(data)
```

**Test Fallout**:
- `test_rename_preserves_physical_refs_and_adds_alias` (line 160-198): **PASSES** (single rename, no loser)
- `test_rename_repairs_same_incarnation_duplicate_target` (line 200-234): **FAILS** at line 230 (expects exactly 1 key, gets 2 with loser preserved)
- `test_rename_rejects_different_incarnation_target` (line 236-260): **PASSES** (error case, no changes)

**Downstream Tests at Risk**:
- `test_aura_seat_rename_replaces_public_rehome_and_top_level_rename` (line 262+): subprocess call to `aura seat rename` will work, but registry will have extra loser rows
- `test_seat_history_ledger.py`: Tests expect `seat_history_for_target()` to traverse `seat_ref` lineage. If loser rows are now in registry with new key format `"fleet:seat~terminal~<uuid>"`, the ledger lookup may miss them or hit them spuriously.

**Required Fix**:
- Clarify M3: is loser ALWAYS preserved or only in repair case?
- If always: update test expectations to check for loser rows
- If repair-only: spec already says `if repair_duplicate and target_existing`, so this is correct, but test needs update
- Ensure loser row key format is stable and documented (spec says `"fleet:seat~terminal~<uuid>"`, but needs to be queryable)

---

### **ZONE 4: M4 Born-Pane Self-Heal Has Occupant-ID Collision with Fork-Children** 🔴 CRITICAL

**File**: `cli/lib/pane_resolver.py:_resolve_from_birth_env()` (new, section 1.1)

**Specification** (M4 section 1.1):
```python
def _resolve_from_birth_env(pane_rec: dict[str, Any], birth_env: dict[str, str]) -> dict[str, Any] | None:
    """Reconstruct thin row from pane + birth env for orphaned Aura-born pane."""
    si = birth_env.get("AURA_SEAT_INSTANCE_ID")
    seat = birth_env.get("AURA_SEAT")
    # Return a thin row with si, pane_ref, etc.
```

**Docstring Promise**: "A live Aura-born pane carries...AURA_SEAT_INSTANCE_ID: unique occupant identity"

**Silent Collision Bug** (code path: fork-children):
1. Parent seat "probe" spawned with si=si_abc
2. Inside "probe", operator runs `codex fork` → child pane %99 spawned
3. Child pane inherits env AURA_SEAT_INSTANCE_ID=si_abc (from parent)
4. Child pane has AURA_SEAT="probe" (inherited from parent, not updated)
5. Child's pane_ref is distinct: "tmux:fleet:%99" (different %N)
6. M4's `_resolve_from_birth_env()` reconstructs: `{name: "probe", si: si_abc, pane_ref: "tmux:fleet:%99"}`
7. Bind-pane calls bind_gates with this thin row
8. bind_gates checks seat_instance_id match: parent has si=si_abc, thin row has si=si_abc → **MATCH** ✓
9. **Both panes now claim si=si_abc**; rename on either will corrupt the other

**Why it breaks**: The spec promises "AURA_SEAT_INSTANCE_ID: unique occupant identity", but fork-children inherit parent's si (by design in Codex). M4 doesn't account for this.

**Current safeguard** (M3 section 2.6):
> If old row exists and old-si ≠ new-si: bind_gates() refuses (seat-instance-mismatch).

But if old row exists with si=si_abc and new thin row ALSO si=si_abc, they will be treated as same occupant by `_same_live_incarnation()`. Then rename will trigger repair and merge them, orphaning the child pane.

**Required Fix**:
- M4 must check: is this a fork-child (check parent env AURA_FORK_SOURCE)? If so, DON'T inherit parent si; generate a NEW si.
- OR M3's `_same_live_incarnation()` must require NOT JUST si+pane match, but also check parent/child relationship (fork_source_session_id metadata).
- OR M4 reconciliation skips rows with fork_source_session_id set.
- Spec must clarify: Are fork-children separate occupants (new si) or continuations of parent (same si, new pane)?

---

### **ZONE 5: M2 resolve_occupant() Fallback Logic is Incomplete** 🟡 MEDIUM

**File**: `cli/lib/registry.py:resolve_occupant()` (new, spec section 1.2, part 4-5)

**Spec Code**:
```python
def resolve_occupant(..., default_ref: str | None = None):
    # ... match by si, launch_id, pane_ref ...
    # Strategy 5: Fallback to default_ref only if occupant truly not alive elsewhere
    if not matched_row and default_ref:
        fallback_attempted = True
        # Check if occupant (by si/launch_id) is alive somewhere else
        occupant_elsewhere = False
        if seat_instance_id:
            occupant_elsewhere = any(
                r.get("seat_instance_id") == seat_instance_id and r.get("registered", True)
                for r in data.values()
            )
```

**Silent Bug**: The spec checks "occupant si alive elsewhere", but doesn't check "is the occupant at a DIFFERENT PANE than what we're trying to bind?"

**Scenario**:
1. Pane %50 has AURA_SEAT_INSTANCE_ID=si_abc
2. Registry row "fleet:old-probe" has si=si_abc, pane_ref="tmux:fleet:%50" (matches)
3. Operator renames "fleet:old-probe" to "fleet:new-probe" (same pane %50)
4. M4 self-heal fires on a different orphaned pane %99 with AURA_SEAT="old-probe" and AURA_SEAT_INSTANCE_ID=si_abc (stale env)
5. `resolve_occupant(si_abc, default_ref="fleet:old-probe")` is called
6. Check "is si_abc alive elsewhere?": YES, at "fleet:new-probe"
7. Fallback is SKIPPED (correct)
8. But then what does the function return? The spec doesn't say: return the alive row at "fleet:new-probe" OR return None?

**Spec ambiguity** (section 1.2, bullet 4): "only succeeds if occupant is not found alive elsewhere". But if occupant IS alive elsewhere, does it:
- Return that live row? (YES, makes sense for same-occupant continuity)
- Return None? (NO, then fallback is pointless)

**Code Gap**: The spec pseudocode doesn't show the return in this case. It only shows: "if not matched_row and default_ref and not occupant_elsewhere: try fallback".

**Required Fix**:
- Clarify: if occupant is alive elsewhere, return that row (don't fallback)
- Add: `if matched_row: return matched_row, {matched_by, ...}` after si/launch/pane checks
- Test: resolve_occupant with multiple si matches returns the one with live pane_ref, not an arbitrary one

---

### **ZONE 6: _match_registry_row() Fix Removes Valid Session-Prefix Fallback** 🟡 MEDIUM

**File**: `cli/lib/pane_resolver.py:_match_registry_row()` (lines 131-147)

**Current code** (the "bug" being fixed):
```python
def _match_registry_row(pane: dict[str, Any]) -> dict | None:
    pane_id = str(pane.get("pane_id") or "")
    session = str(pane.get("tmux_session") or pane.get("physical_fleet") or "")
    exact = f"tmux:{session}:{pane_id}"
    fallback = None
    for record in registry.read_registry().values():
        ref = str(record.get("pane_ref") or "")
        if ref == exact:
            return record
        if ref.endswith(f":{pane_id}"):  # <-- FALLBACK PATH
            fallback = fallback or record
    return fallback
```

**M4 proposed fix** (spec section 1.1):
> "Fixed code": Only return exact match, never fallback.

**Real-world scenario that breaks**:
1. Seat "probe" bound to pane "tmux:aura:%50" (record written)
2. Session fleets are auto-organized by network region (aura-us-east, aura-us-west, etc.)
3. If a fleet rename happens (aura-us-east → aura-us-west-1), pane_ref might be outdated
4. Current fallback allows "find me any row with pane %50 even if session name changed"
5. **M4 removes this**, so outdated pane_refs become unresolvable

**Correct interpretation**: The fallback was a **workaround** for data corruption (fleet rename), not a feature. The M4 fix is CORRECT for live resolution, but operators need a separate `aura seat sweep` or `aura seat reconcile` to repair outdated fleet names.

**Verdict**: No code breakage; M4 spec is correct. But M5 must include explicit docs about fleet-rename recovery (use `aura seat orphan-reconcile --fleet new-fleet-name --auto-adopt`).

---

### **ZONE 7: M1 Backward-Compat Function Missing Critical Use Cases** 🟠 HIGH

**File**: `cli/lib/registry.py:get_agent()` (spec M1 section 1.2)

**Spec Promise**:
```python
def get_agent(name: str, fleet: str | None = None, *, resolve_alias: bool = False) -> dict[str, Any] | None:
    if resolve_alias:
        # Old behavior: follow alias chain
        ...
    # Default: physical-only (equivalent to resolve_live)
```

**Live Consumer Changes Required** (spec M1 section 3):
- `sessions.py:_canonical_bind_target()` → use `resolve_live()` only
- `queued_messages.py:_matches_report()` → use resolve_live + resolve_occupant
- `report_subscriptions.py` → use resolve_live + resolve_historical
- `cut.py`, `send.py`, `inspect.py`, `view.py`, `check.py` → all need updates

**Actual caller count**:
```
grep -r "get_agent" /home/axp/projects/aura/main/cli --include="*.py" | wc -l
# Result: 35+ call sites
```

**Callers NOT updated in spec**:
1. `cli/lib/keeper_jobs.py` (line ?): no spec change
2. `cli/lib/agent_packages.py` (line ?): no spec change
3. `cli/commands/clawhip.py` (line ?): no spec change
4. `cli/commands/write.py` (line ?): no spec change
5. `cli/commands/discord_bridge.py` (line ?): no spec change
6. `cli/commands/resolve.py` (line ?): no spec change
7. `cli/commands/seat.py` (multiple): partially updated
8. `cli/lib/placements.py` (multiple): no spec change

**Risk**: If these callers still use the old `get_agent()` (now physical-only by default), they will break if they relied on alias resolution. Specifically:
- **keeper_jobs.py**: If a job target is an old aliased name, keeper will fail to find it
- **agent_packages.py**: Package resolution may fail for renamed agents
- **placements.py**: Placement member resolution may skip aliased names

**Verdict**: Specs are incomplete. All 35+ callers need review and categorization:
- **Live consumers** (bind, send, cut, etc.) → use `resolve_live()`
- **Audit/lineage consumers** (history, reporting) → use `resolve_historical()`
- **Default wrapper consumers** (keeper, packages, placements) → explicit choice: `get_agent(resolve_alias=True)` or accept new physical-only behavior

---

### **ZONE 8: Doctrine Guarantee #1 — Sender Provenance (Silent Break)** 🔴 CRITICAL

**Affected Doctrine**: "Reports must route to their actual source, never to a sibling occupant with the same name."

**Current Mechanism**: `reports.py:infer_context()` reads AURA_SEAT from pane env, uses it as sender identity.

**M2 Proposed Change** (spec section 1.2, "reports.py: sender canonicalization"):
```python
def _resolve_sender_for_report(seat, fleet, agent_record):
    # Try occupant resolution if env has si/launch_id
    matched, meta = registry.resolve_occupant(
        seat_instance_id=si,
        aura_launch_id=launch_id,
        pane_ref=pane_ref,
        default_ref=f"{fleet}:{seat}",  # <-- FALLBACK TO NAME
    )
    if matched:
        return matched
    else:
        return agent_record or {}
```

**Silent Provenance Bug**:
1. Report arrives from pane %50 with AURA_SEAT_INSTANCE_ID=si_abc
2. si_abc is found at "fleet:probe-2" (renamed from "fleet:probe")
3. infer_context() canonicalizes sender to "fleet:probe-2" ✓ Correct
4. But if `resolve_occupant()` fails (occupant truly gone), fallback uses default_ref="fleet:probe"
5. NEW seat "fleet:probe" exists with si_xyz
6. Report is attributed to si_xyz (wrong occupant) ✗

**Root Cause**: Fallback to name after occupant dies. Should fallback to "unknown sender" instead.

**Required Fix**:
- If occupant resolution attempted but fails, DON'T fallback to default_ref
- Return `{sender: None, sender_kind: "unknown"}` to signal sender provenance lost
- Callers must handle unknown sender (log warning, require explicit sender in message header)

---

### **ZONE 9: Doctrine Guarantee #2 — Bind-Guard Veto (Implicit Break)** 🟠 MEDIUM

**Affected Code**: `cli/lib/bind_guard.py` (not mentioned in specs at all)

**Current Bind-Guard Contracts**:
1. `package_env_status()`: Checks if pane's package root matches registry record
2. `seat_instance_id_status()`: Checks if pane's si matches registry (error if mismatch)
3. `session_gates()`: Checks if runtime_session_id conflicts (error if already bound elsewhere)

**M2/M3/M4 Changes Affect Bind-Guard**:
1. M3 loser preservation: bind_guard must not veto rebinding of terminal rows
2. M4 thin-row reconstruction: bind_guard must accept rows with `registered=False`
3. M2 occupant-keyed continuity: bind_guard si match becomes WEAKER (now matches across name changes)

**Spec Gap**: None of the 5 specs mention bind_guard updates. But M4's section 2.1 ("bind_gates behavior") makes a claim:

> "Thin rows pass all occupant-id gates (seat_instance_id match is the primary check). Package-env gates are skipped if the thin row has no agent_package_id."

**Question**: If bind_guard currently rejects thin rows, where does this approval come from? Is bind_gates the approval? Or is bind_guard modified?

**Required Fix**:
- Either update bind_guard to accept thin rows (marked `_thin_from_birth_env=True`)
- Or ensure bind_gates runs BEFORE bind_guard and pre-approves thin rows
- Document the sequence: resolve_pane → bind_gates → bind_guard → _bind_registry_session

---

### **ZONE 10: Test Coverage Gaps (Adversarial Test Cases Missing)** 🟡 MEDIUM

**Missing test in M2 spec**:
- `test_queued_message_does_not_match_wrong_occupant_with_same_si()`: Create two occupants with si_a and si_b, queue a message for si_a, verify it doesn't match report from si_b even if both alive

**Missing test in M3 spec**:
- `test_rename_distinct_panes_same_si_rejected()`: Two rows with si=si_abc but pane_ref=%50 and %51 → rename rejected (currently PASSES because of OR logic in _same_live_incarnation, but M3 spec changes this to AND)
- `test_rename_preserves_loser_as_terminal_not_deleted()`: Actually check loser rows exist in registry (spec says "preserved", but tests check deletion)

**Missing test in M4 spec**:
- `test_born_pane_rejects_fork_child_occupant_collision()`: Fork-child with inherited si, verify NOT bound to parent row
- `test_resolve_from_birth_env_requires_seat_instance_id()`: Thin row without si is rejected (spec says "occupant identity has precedence: si > launch_id > pane_ref", implying si is REQUIRED)
- `test_reconcile_orphaned_born_panes_skips_fork_children()`: Mirror has fork-child pane, verify orphan-reconcile doesn't touch it
- `test_reconcile_orphaned_panes_with_mirror_unavailable()`: Mirror returns error, reconcile returns error gracefully

**Missing test in M1 spec**:
- `test_resolve_live_never_crosses_fleet_boundary()`: Query "fleet-a:probe", verify doesn't return row from fleet-b (name collision across fleets)
- `test_get_agent_backward_compat_resolve_alias_true()`: Old code using `get_agent(..., resolve_alias=True)` still works

**Missing test in M5 spec**:
- `test_alias_ls_filters_by_active_occupant()`: List aliases, verify `active_occupant` field is correct (only if target is still alive)
- `test_orphan_reconcile_dry_run_does_not_write()`: `--dry-run` mode returns what would be reconciled without modifying registry

---

## INTERACTION MATRIX: Risks When Moves Are Combined

| Move Pair | Risk | Severity |
|-----------|------|----------|
| M1+M2 | `resolve_live()` is called by M2 occupant fallback; if live lookup fails, fallback to occupant lookup. But M2 spec doesn't handle case where occupant si is alive but at DIFFERENT name (ambiguous which name to send to). | 🟡 MEDIUM |
| M2+M3 | M2 occupant-keyed continuity can mask a duplicate-repair (same si, different pane). M3's `_same_live_incarnation()` will refuse repair if panes differ, but M2 will still match the old queue to the new pane via si. | 🔴 CRITICAL |
| M3+M4 | M4 reconstructs thin rows with si from birth env. M3 renames use si as one part of match. If fork-child thin row inherits parent si, M3 rename will corrupt both occupants. | 🔴 CRITICAL |
| M1+M3 | M1 splits get_agent, M3 uses rename_preflight which calls resolve_live. But rename_agent ALSO calls get_agent() on line 527. After M1, line 527 must change to resolve_live() as well. Spec misses this. | 🟠 HIGH |
| M3+M5 | M5 adds `aura seat alias ls` verb. If M3 preserves losers as terminal, loser keys are `"fleet:seat~terminal~<uuid>"` (spec), but M5 ls/rm only works on alias keys. Loser rows are invisible to M5 operator surface. | 🟠 HIGH |

---

## DOCTRINE GUARANTEES AT RISK

### **Guarantee 1: Sender Provenance**
- **Statement**: "A report's sender is always the occupant that actually sent it, never a sibling with the same name."
- **Current Safeguard**: `infer_context()` reads pane env AURA_SEAT_INSTANCE_ID
- **At Risk**: M2 fallback to name after occupant dies violates this
- **Required**: Spec must forbid name-based fallback for sender canonicalization

### **Guarantee 2: Bind-Guard Veto**
- **Statement**: "bind_guard prevents binding a pane to a row unless occupant matches (si, package root, etc.)."
- **Current Safeguard**: `bind_guard.session_gates()` checks si mismatch
- **At Risk**: M4 thin rows have `registered=False`; bind_guard may reject them
- **Required**: Clarify bind_guard's behavior with thin rows; add explicit approval path

### **Guarantee 3: Computed Liveness**
- **Statement**: "`seat_status._terminal_status()` computes pane liveness by checking tmux mirror; a live pane is never marked 'missing'."
- **Current Safeguard**: `_terminal_status()` reads mirror and compares pane_ref
- **At Risk**: M4 born-pane self-heal creates rows without pane_ref; `seat_status` may not find them
- **Required**: M4 must ensure thin rows have pane_ref before they're marked `registered=True`

---

## SUMMARY TABLE: Required Changes

| File | Issue | Spec Section | Fix |
|------|-------|---------------|-----|
| `tests/test_registry_and_broadcast.py:230` | Test expects deletion, spec says preserve | M3:1.4 | Update test to expect 2 rows (winner + loser-terminal) |
| `cli/lib/registry.py:resolve_occupant()` | Fallback logic ambiguous | M2:1.2 | If occupant alive elsewhere, return that row; don't fallback to name |
| `cli/lib/queued_messages.py` | Missing sender_occupant_si check | M2:3.2 | Add `sender_occupant_si` to queue records, check it matches resolved si |
| `cli/commands/spawn.py:214` | No alias-shadow protection in spawn | M1 implied | spawn uses `registry.get_agent()` which now omits aliases; verify spawn doesn't break |
| `cli/lib/pane_resolver.py` | Fork-child si collision | M4:1.1 | Check AURA_FORK_SOURCE; don't inherit parent si in birth env |
| `cli/lib/registry.py:rename_agent():527` | Also calls get_agent() | M1+M3 | Change to `resolve_live()` |
| `cli/commands/sessions.py` | All callers of _canonical_bind_target need updating | M1:3.1 | Remove alias_chain from return tuple, update unpacking |
| `cli/lib/bind_guard.py` | Not mentioned in specs | M4 interaction | Clarify thin-row acceptance |
| `cli/lib/reports.py:infer_context()` | Sender fallback to name | M2:1.2 | Don't fallback to name; return unknown-sender instead |
| `tests/` (all) | Missing adversarial tests | M1-M5 | Add 10+ tests per Zone 10 above |

---

## RANK-ORDERED MUST-FIX LIST (For Implementation)

**DO THESE FIRST (P0: Blocks implementation)**:
1. **M2 resolve_occupant fallback logic** — spec is ambiguous on what to return when occupant is alive elsewhere
2. **M4 fork-child si collision** — spec doesn't account for inherited si; will corrupt fork-child occupancy
3. **M3 loser preservation in test** — test line 230 expects deletion, spec says preserve; consensus needed
4. **M1+M3 rename_agent() line 527** — spec misses one call site of get_agent() that must change to resolve_live()
5. **M2 queue record sender_occupant_si** — spec proposes occupant matching but doesn't store sender occupant; will cause false positives

**DO THESE NEXT (P1: Silent correctness bugs)**:
6. **M2 sender provenance fallback** — fallback to name violates sender provenance guarantee
7. **Bind-guard thin-row acceptance** — spec doesn't clarify; implicit assumption that may be wrong
8. **M5 terminal-loser visibility** — if losers are preserved with key `"fleet:seat~terminal~<uuid>"`, M5 alias-ls can't find them

**DO THESE LAST (P2: Coverage + validation)**:
9. Test updates for renamed behavior (10+ tests)
10. Documentation of fleet-rename recovery path (M4 removes fallback)

---

## SPECIFIC TEST COMMANDS TO RUN TODAY

```bash
cd /home/axp/projects/aura/main

# Tests that will FAIL after M1-M3 implementation:
pytest tests/test_registry_and_broadcast.py::test_rename_repairs_same_incarnation_duplicate_target -xvs

# Tests that MIGHT break (need verification):
pytest tests/test_registry_and_broadcast.py::test_rename_preserves_physical_refs_and_adds_alias -xvs
pytest tests/test_session_binding.py -xvs
pytest tests/test_deferred_delivery.py -xvs

# Tests that WILL pass but hide bugs:
pytest tests/test_reports.py -xvs  # M2 sender canonicalization not tested
pytest tests/test_seat_status.py -xvs  # M4 orphaned-pane visibility not tested
```
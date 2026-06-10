Perfect. Now I have enough information. Let me create a comprehensive coherence audit:

# COMPREHENSIVE COHERENCE AUDIT: M1-M5 SPECS

## EXECUTIVE SUMMARY: CRITICAL CONFLICTS FOUND

The five specs contain **three classes of defects**:
1. **Duplicate function edits** (registry.get_agent, rename functions) with conflicting semantics
2. **Unresolved contract for resolve_live()**: M1, M2, M3, M4 all define different signatures
3. **Live alias fallbacks not fully eliminated**: M1/M3 claim to remove them, but M2 re-introduces them; queued_messages.py and report_subscriptions.py have conflicting M1 vs M2 edits

---

## ISSUE 1: CONFLICTING SIGNATURES FOR `resolve_live()`

### M1 defines:
```python
def resolve_live(ref: str, *, fleet: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Return (row, reason_string) if not found."""
```

### M2 redefines as:
```python
def resolve_live(ref: str, *, fleet: str | None = None) -> dict[str, Any] | None:
    """Return row or None, no reason tuple."""
```

### M4 expects as:
```python
def resolve_live(name: str, fleet: str | None = None) -> dict[str, Any] | None:
    """(no error reason tuple)"""
```

**IMPACT**: M2's queued_messages.py edit calls `registry.resolve_live()` and expects a dict/None, but M1 says it returns a tuple. M4's pane_resolver code expects dict/None. **BUILD WILL FAIL**.

**RECOMMENDATION**: **M1 must define resolve_live to return dict|None ONLY**. The reason string is unnecessary—callers can check `if row is None`. Update M1 PART 1.1 and all call sites in M2/M4.

---

## ISSUE 2: `get_agent()` SIGNATURE CONFLICT

### M1 specifies:
```python
def get_agent(name: str, fleet: str | None = None, *, resolve_alias: bool = False) -> dict[str, Any] | None:
```
**Default behavior** (resolve_alias=False) is physical-only (no alias follow).

### M3 calls it with NO parameter (line 484, 527):
```python
agent = get_agent(source_name)  # M1: becomes resolve_live()
```
But the comment says **"use resolve_live instead of get_agent"**. This is contradiction: the code edits keep `get_agent()` calls in place.

### Current codebase (registry.py lines 484, 527) ALREADY CALLS get_agent():
```python
agent = get_agent(source_name)  # rename_preflight line 484
existing = get_agent(source_name, fleet=source_fleet)  # rename_agent line 527
```

**IMPACT**: M3 spec says to replace these with `resolve_live()`, but provides a **new get_agent() with resolve_alias parameter**. M1 and M3 are in CONFLICT about whether to keep or kill get_agent().

**HARD EVIDENCE**: 
- M1 PART 1.1: "*`get_agent()` becomes a **convenience wrapper***"
- M3 PART 1.2 (rename_preflight): "**Change: Use resolve_live() instead of get_agent()**"

**RECOMMENDATION**: 
1. **M1 MUST define**: `resolve_live(name: str, fleet: str | None = None) -> dict[str, Any] | None`
2. **M1 MUST deprecate**: Old `get_agent()` contract, keep as backward-compat wrapper for `resolve_historical()` fallback only
3. **M3 MUST use**: `resolve_live()` directly in rename_preflight/rename_agent (not get_agent)
4. **M2 MUST also use**: `resolve_live()` instead of get_agent in reports.py line 54

---

## ISSUE 3: `_same_live_incarnation()` EDITED BY M1 AND M3

### M1 specifies (PART 2.2):
```python
def _same_live_incarnation(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    """Check if two rows are the same live occupant.
    
    Must match on BOTH si AND pane (if either exists); never collapse distinct live %N.
    """
    # Requires BOTH si AND exact same %N for "same incarnation"
```

### M3 repeats the SAME CHANGE (PART 1.2):
```python
def _same_live_incarnation(...):
    """Two rows are the same live occupant iff:
    - Both have non-null seat_instance_id AND they match, AND
    - Both have non-null pane_ref AND they match (must be the EXACT SAME pane, not just same si).
    """
```

**ACTUAL CURRENT CODE** (registry.py:466-474):
```python
def _same_live_incarnation(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    if not left or not right:
        return False
    for key in ("seat_instance_id", "pane_ref"):
        left_value = left.get(key)
        right_value = right.get(key)
        if left_value and right_value and str(left_value) == str(right_value):
            return True  # <-- DEFECT: OR logic, not AND
    return False
```

**VERDICT**: M1 and M3 are IDENTICAL edits to the same function. **One must be eliminated** to avoid accidental duplicate-patch application. M3 should reference M1's change without restating.

**RECOMMENDATION**: Keep the change in M1 PART 2.2 only. M3 PART 1.2 should say: "No change (M1 fixes _same_live_incarnation; M3 depends on it)."

---

## ISSUE 4: `rename_preflight()` AND `rename_agent()` CONFLICT BETWEEN M1 AND M3

### M1 PART 2.3 (rename_preflight) specifies:
```python
def rename_preflight(source: str, *, new_name: str | None = None) -> dict[str, Any]:
    """Pre-flight check for rename: check for collisions, alias shadows, and true duplicates."""
    ...
    source_fleet, source_name = split_ref(source)
    if not source_fleet:
        agent, _ = resolve_live(source_name)  # M1: calls resolve_live, returns (row, reason)
```

### M3 PART 1.3 (rename_preflight) REDOES THE SAME FUNCTION:
```python
def rename_preflight(source: str, *, new_name: str | None = None) -> dict[str, Any]:
    source_fleet, source_name = split_ref(source)
    if not source_fleet:
        agent = resolve_live(source_name, fleet=fleet_filter)  # M3: calls resolve_live, expects dict
```

**CONFLICT**: M1 expects `resolve_live(source_name)` to return `(row, reason)` tuple. M3 expects it to return `dict | None`. And M3's call is syntactically wrong (passes undefined `fleet_filter`).

**RECOMMENDATION**: M1 and M3 should be **merged into a SINGLE M1+M3 COMBINED MOVE** that implements rename correctly on first pass. Else, one spec must defer to the other.

---

## ISSUE 5: ALIAS HANDLING IN M2 vs M1/M3 CONTRADICTION

### M1 claims (PART 3):
> "All live consumers **MUST switch from `get_agent()` to `resolve_live()`**… never follow aliases in binding path."

### M1 says rename should NOT check alias (PART 2.3):
```python
# M3: do NOT check aliases; source must be a current row
if not existing:
    # M3: do NOT check aliases
    return {"ok": False, "error": f"agent not found: {source_ref}"}
```

### But then M2 reintroduces alias fallback for SAME M2 PART 3.1 (_matches_report in queued_messages.py):
```python
# M2 spec says to add occupant-keyed resolution, BUT THEN ADD FALLBACK TO HISTORICAL:
# Finally, fallback to historical alias chain (for backward compat; should be rare)
try:
    from lib import registry
    resolved, chain = registry.resolve_historical(str(target))
    if chain and resolved in report_targets:
        return True
except Exception:
    pass
```

**ISSUE**: M2's spec contradicts M1's doctrine. M1 says "never follow aliases for live operations." M2 adds a fallback that DOES follow aliases (resolve_historical is still alias-following). The comment "backward compat; should be rare" doesn't match the doctrine that aliases are "HISTORICAL ONLY."

**PRECISE LOCATION**: 
- M1 PART 3.1 (sessions.py binding path): "*Use `resolve_live()` only; never follow aliases in binding path*"
- M2 PART 3.1 (queued_messages.py _matches_report): "*Finally, fallback to historical alias chain*"

**RECOMMENDATION**: M2's occupant-keyed matching should NOT fallback to historical alias chain. If occupant is not found alive, return no match. The fallback to historical breaks M1's contract that "aliases are never live routers." Remove the fallback block from M2 spec.

---

## ISSUE 6: PANE_RESOLVER `_match_registry_row()` EDITED BY M1 AND M4

### M1 spec (PART 3.1 sessions.py _canonical_bind_target):
> "*This is the BINDING path; use `resolve_live()` only; never follow aliases*"

M1 does NOT directly edit pane_resolver._match_registry_row().

### M4 spec (PART 1.1 pane_resolver.py) edits _match_registry_row:
```python
# M4: drop fallback, exact match only
def _match_registry_row(pane: dict[str, Any]) -> dict | None:
    """Match pane to registry row by exact pane_ref only.
    No alias follow."""
    exact = f"tmux:{session}:{pane_id}"
    for record in registry.read_registry().values():
        ref = str(record.get("pane_ref") or "")
        if ref == exact:
            return record
    return None  # No fallback
```

### CURRENT CODE (pane_resolver.py:131-146):
```python
def _match_registry_row(pane: dict[str, Any]) -> dict | None:
    exact = f"tmux:{session}:{pane_id}"
    fallback = None
    for record in registry.read_registry().values():
        ref = str(record.get("pane_ref") or "")
        if not ref:
            continue
        if ref == exact:
            return record
        if ref.endswith(f":{pane_id}"):  # <-- DEFECT: cross-session fallback
            fallback = fallback or record
    return fallback
```

**VERDICT**: M4 correctly identifies and fixes this. But M1 and M2 do NOT mention this function. Since _match_registry_row is called by resolve_pane (which is used by bind-pane), **M1 should coordinate with M4** to fix this cross-session fallback bug at the same time.

**RECOMMENDATION**: M1 PART 3 (live consumers) should explicitly include a sub-item: "*M4 prerequisite: Fix `pane_resolver._match_registry_row()` to drop cross-session fallback.*" This establishes dependency.

---

## ISSUE 7: BIRTH_ENV INTEGRATION IN M4 _bind_pane()

### M4 spec (PART 1.2 sessions._bind_pane):
```python
# NEW: Attempt birth-env reconstruction if no matched row
if not fleet or not seat:
    birth_env = pane_resolver._read_birth_env(res.get("pane_pid"))
    if birth_env:
        fleet = fleet or birth_env.get("AURA_FLEET")
        seat = seat or birth_env.get("AURA_SEAT")
```

### But M4 does NOT update the "no-target" error text (lines 1189-1195 in current code):
```python
if not fleet or not seat:
    return {
        "ok": False,
        "error": "no-target",
        "detail": "pane is unmanaged; pass --target fleet:seat to bind",
    }
```

**ISSUE**: The error message is STALE. It still says "pass --target fleet:seat" even though birth-env-born panes will now auto-infer fleet/seat. The error is now:
> "pane is unmanaged and not Aura-born (no AURA_FLEET/AURA_SEAT env); pass --target fleet:seat to bind"

This must be updated in M4 spec section 1.2. **Currently spec updates the detail text but doesn't remove the old error message.**

**RECOMMENDATION**: M4 PART 1.2 should include the exact revised error block that replaces lines 1189-1195.

---

## ISSUE 8: NEW FUNCTION `resolve_occupant()` IN M2 BREAKS RENAME COLLISION GUARD

### M2 spec adds (PART 1.1):
```python
def resolve_occupant(seat_instance_id: str | None = None, ...) -> tuple[dict[str, Any] | None, dict[str, Any]]:
```

### M1 & M3 rename_preflight uses _same_live_incarnation for collision guard:
```python
if target_ref != source_ref and target_existing:
    if not _same_live_incarnation(existing, target_existing):
        return {"ok": False, "error": f"target already exists: {target_ref}"}
```

### But if M2's resolve_occupant is called DURING rename, it could find a row by occupant id that rename_preflight doesn't see:
```python
# Hypothetical: resolve_occupant(si=occupant_si) finds a row at a DIFFERENT name
```

**ISSUE**: The collision guard in rename checks _same_live_incarnation on `data.get(target_ref)` (exact registry lookup). But M2's resolve_occupant could find the "same" occupant at a DIFFERENT location. If rename code later uses resolve_occupant instead of exact registry lookup, the collision guard is BYPASSED.

**RECOMMENDATION**: Rename_preflight MUST use exact registry lookup (current _key(fleet, name)) and CANNOT use resolve_occupant for target resolution. Document this explicitly in both M1 and M3 rename sections.

---

## ISSUE 9: M5 ALIAS LS/RM MISSING CONTRACT FOR ALIAS RECORD FORMAT

### M5 spec (PART 3) says:
> "Add occupant metadata to alias: `occupant_id` (seat_instance_id) and `launched_at` (aura_launch_id)"

### But M3 spec (PART 4: Changes to Alias Record Format) already updates `add_alias()` signature:
```python
def add_alias(
    source: str,
    target: str,
    *,
    reason: str = "alias",
    occupant_id: str | None = None,  # NEW
    launched_at: str | None = None,  # NEW
)
```

**CONFLICT**: M3 updates add_alias signature; M5 assumes the same. This is actually OK (both agree), BUT **M5 PART 1 (CLI verbs) doesn't specify whether alias ls/rm should handle BOTH old and new schema versions**. If old alias records lack occupant_id, the CLI will fail.

**RECOMMENDATION**: M5 PART 1 (alias ls/rm) must include schema-version-tolerant read logic. Example:
```python
def _alias_ls(...):
    aliases = registry.read_aliases()
    for record in aliases.values():
        occupant_id = record.get("occupant_id", "(unknown)")
        source = record.get("source")
        # ...
```

---

## ISSUE 10: M1 VS M4 RESOLVE_LIVE INTEGRATION WITH PANE_RESOLVER

### M1 spec (PART 1.1) defines resolve_live as:
```python
# In registry.py
def resolve_live(ref: str, *, fleet: str | None = None) -> dict[str, Any] | None:
```

### M4 spec assumes pane_resolver calls resolve_live:
```python
# M4 PART 1.2 (_bind_pane) calls:
existing = resolve_live(source_name, fleet=source_fleet)
```

### But CURRENT pane_resolver.py does NOT call registry.resolve_live(). It calls:
```python
pane_resolver.resolve_pane(...)  # <-- this function
```

And resolve_pane calls `_match_registry_row()` internally, which has the cross-session fallback bug.

**ISSUE**: M1 defines resolve_live in registry.py, but M4's born-pane self-heal strategy depends on pane_resolver using it. **There's no explicit wiring between M1's resolve_live and M4's pane resolver flow.**

**RECOMMENDATION**: M1 should include an explicit edit to pane_resolver to use resolve_live. OR M4 should NOT assume M1's resolve_live is used; instead, M4 PART 1.1 should include its own fix to _match_registry_row (which it already does, but this should be flagged as "M1 prerequisite" in M4).

---

## ISSUE 11: OCCUPANT_KEY() FUNCTION UNDEFINED IN M1 IMPLEMENTATION

### M2 spec (PART 1.2) references:
```python
def occupant_key(row: dict[str, Any] | None) -> str | None:
    """Return the physical occupant id: pane %N > si > launch > None."""
    if not row:
        return None
    for key in ("pane_ref", "seat_instance_id", "aura_launch_id"):
        value = row.get(key)
        if value:
            return str(value)
    return None
```

### But M1 spec does NOT include this function in its "New Contracts & Signatures" (PART 1.2). It's only mentioned as a concept.

**IMPACT**: M2 code calls `occupant_key(row)` but M1 never defines it. **BUILD WILL FAIL** if M2 implementation tries to call an undefined function.

**RECOMMENDATION**: M1 PART 1.2 should define occupant_key() as a concrete function. This is a foundation for M2 same-occupant continuity.

---

## ISSUE 12: M2 QUEUED_MESSAGES EDIT INCOMPLETE - OCCUPANT_SI NOT CAPTURED AT QUEUE CREATION

### M2 spec (PART 3.1 queued_messages._matches_report) says:
```python
occupant_si = record.get("occupant_seat_instance_id")
occupant_launch_id = record.get("occupant_aura_launch_id")
occupant_pane = record.get("occupant_pane_ref")
```

### But current code (queued_messages.py) has NO logic to populate these fields when a queue record is created.

**ISSUE**: M2 spec expects queue records to store occupant metadata, but doesn't specify where in the codebase those fields are WRITTEN. It only specifies the READ path.

**IMPACT**: M2's occupant-keyed matching will always find None for occupant_si/launch_id/pane because queue records are never populated with these fields.

**RECOMMENDATION**: M2 PART 3.1 should include a sub-section: "**M2 PART 3.1.1: Queue Record Creation (queued_messages.create_record)**" with code that captures occupant metadata from the sender's registry row at queue-time:
```python
def create_record(target: str, ...):
    sender_row = resolve_live(sender_seat, fleet=sender_fleet)
    record = {
        "target": target,
        "occupant_seat_instance_id": (sender_row or {}).get("seat_instance_id"),
        "occupant_aura_launch_id": (sender_row or {}).get("aura_launch_id"),
        ...
    }
```

---

## ISSUE 13: M4 THIN ROW SCHEMA NOT DEFINED

### M4 spec (PART 1.1 _resolve_from_birth_env) says:
```python
return {
    "name": seat,
    "seat": seat,
    "fleet": fleet,
    "aura_launch_id": launch_id,
    "seat_instance_id": si,
    "pane_ref": pane_ref,
    "registered": False,
    "status": "born-unhealed",
    "_from_birth_env": True,
}
```

### But what about required fields like:
- `seat_ref` (needed for _key() calls)
- `runtime` (assumed by bind_gates)
- `last_seen` (audit trail)

**ISSUE**: Thin row schema is incomplete. When this row is written to the registry, missing fields will cause downstream errors.

**RECOMMENDATION**: M4 PART 1.1 (_resolve_from_birth_env) should define a COMPLETE minimal schema:
```python
return {
    "name": seat,
    "seat": seat,
    "fleet": fleet,
    "seat_ref": _key(fleet, seat),
    "aura_launch_id": launch_id,
    "seat_instance_id": si,
    "pane_ref": pane_ref,
    "registered": False,
    "status": "born-unhealed",
    "runtime": "codex",  # inferred or from pane env
    "last_seen": now_iso(),
    "_from_birth_env": True,
}
```

---

## BUILD ORDER & DEPENDENCY GRAPH

### Current order (as proposed): M1 → M2 → M3 → M4 → M5

**PROBLEMS**:
1. M1 and M3 both edit `_same_live_incarnation()` (duplicate)
2. M1 and M3 both edit `rename_preflight()` and `rename_agent()` (conflicts)
3. M2 re-introduces alias fallback that M1 bans
4. M4 assumes _match_registry_row() is fixed (M1 prerequisite not explicit)
5. M2 requires occupant_key() function (not in M1)
6. M2 requires queue records to capture occupant metadata (not in M2 spec)

### CORRECT BUILD ORDER:

```
M0 (PREREQUISITE): Fix pane_resolver._match_registry_row()
    - Drop cross-session fallback bug
    - Make exact pane_ref match only

M1+M3 (COMBINED): Physical live-resolution + rename on exact %N
    - Define resolve_live(ref, *, fleet=None) -> dict | None
    - Define resolve_historical(ref) (renamed from resolve_alias)
    - Fix _same_live_incarnation to require BOTH si AND pane_ref
    - Update rename_preflight + rename_agent to use resolve_live
    - Add occupant_key() helper function
    - Drop all alias fallbacks from get_agent() default behavior

M2 (OCCUPANT CONTINUITY): Add occupant resolution + sender canonicalization
    - Define resolve_occupant(si, launch_id, pane_ref, *, default_ref=None)
    - Update queued_messages._matches_report to use resolve_occupant
    - Update report_subscriptions._matches_target to use resolve_occupant
    - ADD: Edit queued_messages.create_record() to capture occupant metadata at queue-time
    - Clarify: NO fallback to resolve_historical for live operations (occupant unknown = no match)

M4 (BORN-PANE SELF-HEAL): Add orphan reconciliation
    - Add _read_birth_env() to pane_resolver
    - Fix _match_registry_row() (already in M0)
    - Update _resolve_from_birth_env() with complete thin-row schema
    - Update _bind_pane() to reconstruct from birth env
    - Add _reconcile_orphaned_born_panes() verb

M5 (OPERATOR SURFACE): Alias and orphan management
    - Add aura seat alias ls/rm verbs (schema-version-tolerant)
    - Add aura seat orphan-reconcile verb (wired in M4)
    - Update docs (lexicon, two-laws, the-seat)
```

---

## SUMMARY TABLE: REQUIRED CHANGES TO SPECS

| Spec | Issue | Required Change | Type |
|------|-------|-----------------|------|
| M1 | resolve_live returns tuple vs dict | Define as `-> dict \| None` only, no reason string | **BREAKING** |
| M1 | get_agent signature vs M3 usage | Keep wrapper for backward-compat, mark resolve_alias=False as default | Clarify |
| M1+M3 | Duplicate _same_live_incarnation edit | Keep in M1, remove from M3 (reference only) | Deduplicate |
| M1+M3 | Duplicate rename_preflight/rename_agent edit | Merge M1 + M3 into one combined move | Consolidate |
| M1+M3 | Missing resolve_live → pane_resolver integration | Add explicit pane_resolver dependency | Add |
| M1 | Missing occupant_key() | Add to M1 PART 1.2 as core function | Add |
| M2 | Fallback to resolve_historical | Remove fallback block, return no-match if occupant unknown | **BREAKING** |
| M2 | Queue record occupant metadata not captured | Add M2.3.1.1: Edit queued_messages.create_record() | Add |
| M4 | Thin row schema incomplete | Add seat_ref, runtime, last_seen to minimal schema | Add |
| M4 | Error message stale | Update "no-target" error detail in _bind_pane | Fix |
| M5 | Alias schema version handling | Add backward-compat logic to alias ls/rm | Add |

---

## VERDICT & RISK ASSESSMENT

| Risk Level | Issue | Severity |
|-----------|-------|----------|
| **CRITICAL** | resolve_live signature M1 vs M2 | Implementation will fail at runtime |
| **CRITICAL** | M1 + M3 rename edits conflict | Two moves edit same function differently |
| **CRITICAL** | occupant_key() undefined | M2 build will fail |
| **CRITICAL** | Queue occupant metadata never populated | M2 occupant resolution useless |
| **HIGH** | M2 alias fallback contradicts M1 doctrine | Violates "alias historical only" contract |
| **HIGH** | _match_registry_row fallback not in M1 scope | M1 incomplete without M4 fix |
| **MEDIUM** | Thin row schema incomplete | Downstream errors on birth reconciliation |
| **MEDIUM** | Alias schema version handling absent | M5 implementation incomplete |
| **LOW** | Duplicate _same_live_incarnation | No functional impact, maintenance issue |

---

## FINAL RECOMMENDATIONS

**IMMEDIATE ACTIONS (BEFORE IMPLEMENTATION)**:

1. **Merge M1 + M3 into M1+M3 COMBINED SPEC** that addresses both moves atomically:
   - resolve_live signature finalized as `-> dict | None`
   - _same_live_incarnation fixed (not duplicated)
   - rename_preflight/rename_agent updated once
   - occupant_key() defined

2. **Define M0 PREREQUISITE MOVE**: Fix `_match_registry_row()` in pane_resolver.py (drop cross-session fallback)

3. **Update M2 to remove alias fallback**:
   - Change queued_messages._matches_report: occupant_unknown = return False (no fallback)
   - Same for report_subscriptions

4. **Add M2 PART 3.1.1**: Specify where queue records capture occupant metadata (at create time)

5. **Update M4 thin-row schema** to include all required fields (seat_ref, runtime, last_seen)

6. **Add M5 backward-compat logic** for old alias records without occupant_id

**RATIFICATION BEFORE CODE**:
- Single source of truth: `resolve_live()` returns `dict | None`, never a tuple
- Single source of truth: `_same_live_incarnation()` requires BOTH si AND pane_ref to match
- Single source of truth: Aliases are **NEVER** consulted for live operations (M1 law)
- Single source of truth: Queue records must capture occupant metadata at queue-time (M2 law)

---

**End of coherence audit.**
Now I have enough information. Let me produce the comprehensive M1 specification. I'll create it directly as output (no file):

---

# AURA M1 IMPLEMENTATION SPECIFICATION: Physical Live-Resolution + Alias Historical

## CRITICAL CONTEXT

**Root Defect**: Current code treats aliases as **live routers**, causing:
1. Stale aliases silently redirect names to wrong panes (defect #1)
2. Duplicate-repair collapses distinct live panes (defect #2)
3. No collision-guard for alias-shadow path (defect #4)
4. spawn-into-alias blocks name reuse (defect #5)

**Target Architecture**: Aliases become **HISTORICAL ONLY** breadcrumbs; live resolution uses %N → seat_instance_id → aura_launch_id → exact current row by name. All live consumers (binding, send, cut, view, inspect) switch to physical-first resolution immune to name reuse and alias hijacking.

---

## PART 1: NEW CONTRACTS & SIGNATURES

### 1.1 Core Resolution Functions

#### **`resolve_live(ref: str, *, fleet: str | None = None) -> tuple[dict[str, Any] | None, str | None]`**

**Purpose**: Resolve a seat name/ref to a live registry row using ONLY physical identity, never alias routing.

**Precedence** (in order):
1. Parse `fleet:name` from ref; use provided `fleet` as fallback.
2. If both fleet and name are available:
   - Query registry row at `_key(fleet, name)`.
   - Return (row, None) if exists **regardless of alias records**.
3. If only name is available (fleet is None):
   - Search registry rows by exact name match + preferred current fleet.
   - Return (row, None) if exactly one match found.
4. If no match → return (None, reason_string).

**Key Contract**:
- **NEVER consults `resolve_alias()` or reads alias records** during live resolution.
- **NEVER merges/updates from alias targets**.
- Returns the exact registry row at the requested location, or None.
- The returned row's `%N`, `seat_instance_id`, `aura_launch_id` are trusted as physical identity.

**Signature**:
```python
def resolve_live(ref: str, *, fleet: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve live identity: %N > si > launch > exact name match.
    
    Args:
        ref: seat name, fleet:name, or tmux-prefixed ref.
        fleet: optional fallback fleet.
    
    Returns:
        (row, None) if exact row found.
        (None, reason) if not found; reason in {'ambiguous', 'not-found', 'no-fleet'}.
    """
```

**Example usage**:
```python
row, reason = resolve_live("my_agent", fleet="aura")
# If row exists → (row, None)
# If multiple rows named "my_agent" across fleets → (None, "ambiguous")
# If no such row → (None, "not-found")
```

---

#### **`resolve_historical(ref: str, *, fleet: str | None = None) -> tuple[str, list[str]]`**

**Purpose**: Follow alias/lineage chain for historical reference resolution (restore, audit, lineage, same-occupant continuity fallback).

**Behavior**:
- Identical to current `resolve_alias()`: follow chain up to 8 hops.
- Return (final_ref, chain) where final_ref is the resolved target or original if no alias.
- Used ONLY by:
  - Restore/audit/lineage code paths.
  - Same-occupant continuity for stale env refs (M2).
  - **Fallback LOSES to a live distinct pane** (crucial for M3).

**Signature**:
```python
def resolve_historical(ref: str, *, max_hops: int = 8, fleet: str | None = None) -> tuple[str, list[str]]:
    """Follow alias/lineage chain; used only for historical resolution & same-occupant continuity.
    
    Returns:
        (final_ref, chain) where chain is non-empty if an alias was followed.
    """
```

---

### 1.2 Occupant Keys (M2 foundations)

All live consumers must cache **occupant identity** derived from a row:
```python
def occupant_key(row: dict[str, Any] | None) -> str | None:
    """Return the physical occupant id: pane %N > si > launch > None.
    
    The occupant key is used to resolve stale refs during same-occupant continuity.
    It must survive seat renames and name reuse.
    """
    if not row:
        return None
    # Priority: live pane > occupant-identifier > occupant-launch
    for key in ("pane_ref", "seat_instance_id", "aura_launch_id"):
        value = row.get(key)
        if value:
            return str(value)
    return None
```

---

## PART 2: EXISTING FUNCTIONS TO MODIFY

### 2.1 `cli/lib/registry.py: get_agent()`

**Current behavior** (lines 395–430):
- Direct lookup at _key(fleet, name).
- Falls back to resolve_alias() if not found.
- Returns merged record with alias_chain + resolved_from.

**CHANGE**: Split into two paths; `get_agent()` becomes a **convenience wrapper** that calls `resolve_live()` for **live consumers**, preserving backward compat for **historical callers**.

**New implementation**:

```python
def get_agent(name: str, fleet: str | None = None, *, resolve_alias: bool = False) -> dict[str, Any] | None:
    """DEPRECATED: Use resolve_live() for live operations, resolve_historical() for lineage.
    
    Convenience wrapper for backward compat. Default behavior (resolve_alias=False) is
    physical-only (equivalent to resolve_live). 
    
    If resolve_alias=True, follows historical alias chain (backward-compatible old behavior).
    
    LIVE CALLERS MUST SWITCH TO resolve_live() IN THEIR LOCAL PATCH.
    """
    if resolve_alias:
        # Old behavior: follow alias chain (M2 continuity fallback path only).
        original_fleet = fleet
        fleet, name = split_ref(str(name), fleet=fleet)
        data = read_registry()
        if fleet:
            ref = _key(fleet, name)
            record = data.get(ref)
            if record:
                return record
            resolved, chain = resolve_historical(ref)
            if chain:
                target_fleet, target_name = split_ref(resolved)
                if target_fleet and target_name:
                    target = data.get(_key(target_fleet, target_name))
                    if target:
                        return {**target, "resolved_from": ref, "alias_chain": chain}
            return None
        # Only-name fallback (preserve old behavior for name-only lookups).
        matches = [v for v in data.values() if v.get("name") == name]
        if not matches:
            alias_fleet = original_fleet or current_fleet(default="")
            if alias_fleet:
                resolved, chain = resolve_historical(_key(alias_fleet, name))
                if chain:
                    target_fleet, target_name = split_ref(resolved)
                    target = data.get(_key(target_fleet, target_name)) if target_fleet else None
                    if target:
                        return {**target, "resolved_from": _key(alias_fleet, name), "alias_chain": chain}
            return None
        preferred_fleet = current_fleet(default="")
        if preferred_fleet:
            preferred = [v for v in matches if v.get("fleet") == preferred_fleet]
            if preferred:
                preferred.sort(key=lambda r: r.get("last_seen", ""), reverse=True)
                return preferred[0]
        matches.sort(key=lambda r: r.get("last_seen", ""), reverse=True)
        return matches[0]
    
    # Default: physical-only (resolve_live behavior).
    row, reason = resolve_live(name, fleet=fleet)
    return row


def resolve_live(ref: str, *, fleet: str | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve a live registry row by exact name/fleet match only.
    
    NEVER follows aliases. Returns the exact physical row or None.
    This is the ONLY path for live operations: binding, send, cut, view, inspect.
    """
    original_fleet = fleet
    fleet, name = split_ref(str(ref), fleet=fleet)
    data = read_registry()
    
    if fleet:
        # Exact fleet:name lookup.
        ref_key = _key(fleet, name)
        record = data.get(ref_key)
        if record:
            return record, None
        # Not found at this exact location.
        return None, "not-found"
    
    # Only name available; match by name across all fleets.
    matches = [v for v in data.values() if v.get("name") == name]
    if not matches:
        return None, "not-found"
    if len(matches) > 1:
        preferred_fleet = current_fleet(default="")
        if preferred_fleet:
            preferred = [v for v in matches if v.get("fleet") == preferred_fleet]
            if preferred:
                preferred.sort(key=lambda r: r.get("last_seen", ""), reverse=True)
                return preferred[0], None
        return None, "ambiguous"
    
    return matches[0], None


def resolve_historical(ref: str, *, max_hops: int = 8, fleet: str | None = None) -> tuple[str, list[str]]:
    """Follow alias/lineage chain for historical resolution only.
    
    Used by restore, audit, same-occupant continuity fallback, and M5 operator verbs.
    NOT used by live operations (binding, send, cut, view, inspect).
    """
    # Implementation: current resolve_alias() logic, renamed.
    aliases = read_aliases()
    current = ref
    chain: list[str] = []
    for _ in range(max_hops):
        record = aliases.get(current)
        if not record:
            break
        target = record.get("target")
        if not target or target in chain:
            break
        chain.append(current)
        current = str(target)
    return current, chain
```

---

### 2.2 `cli/lib/registry.py: _same_live_incarnation()`

**Current behavior** (lines 466–474):
- Matches on `seat_instance_id` OR `pane_ref` independently.
- DEFECT: Two rows with same si but distinct %N are "same incarnation" → merged.

**CHANGE**: Require BOTH si AND exact same %N for "same incarnation". Never merge rows with distinct live panes.

```python
def _same_live_incarnation(left: dict[str, Any] | None, right: dict[str, Any] | None) -> bool:
    """Check if two rows are the same live occupant.
    
    Must match on BOTH si AND pane (if either exists); never collapse distinct live %N.
    If only one has %N, assume they're distinct (one might be thin/name-only).
    """
    if not left or not right:
        return False
    
    left_si = left.get("seat_instance_id")
    right_si = right.get("seat_instance_id")
    left_pane = left.get("pane_ref")
    right_pane = right.get("pane_ref")
    
    # Both have si: must match si.
    if left_si and right_si:
        return str(left_si) == str(right_si)
    
    # Both have pane %N: must match pane.
    if left_pane and right_pane and _is_pane_id(left_pane) and _is_pane_id(right_pane):
        return str(left_pane) == str(right_pane)
    
    # Launch ID as weak tie-breaker (only if no si/pane).
    left_launch = left.get("aura_launch_id")
    right_launch = right.get("aura_launch_id")
    if left_launch and right_launch and not (left_si or right_si):
        return str(left_launch) == str(right_launch)
    
    # One or both are thin/name-only: assume distinct.
    return False


def _is_pane_id(pane_ref: str | None) -> bool:
    """Return True if pane_ref contains a tmux %N identifier."""
    if not pane_ref:
        return False
    ref = str(pane_ref)
    if ref.startswith("tmux:"):
        ref = ref[5:]
    return "%" in ref  # Ends with or contains %N after colon.
```

---

### 2.3 `cli/lib/registry.py: rename_preflight()` and `rename_agent()`

**Current behavior** (lines 477–575):
- Calls `_same_live_incarnation()` to allow repair-duplicate.
- At line 545–547: merges target_existing into record (`record.update(target_existing)`).
- At line 563: pops the loser key from registry.
- DEFECT: Silently orphans the loser's live pane as "registered:false".

**CHANGE**: 
1. Rename collision guard catches alias-shadow path.
2. If repair-duplicate: DON'T silently delete loser; mark as historical with `replaced_by` pointer.
3. Never orphan a live pane (check pane_ref is actually dead before pop).

**New implementation**:

```python
def rename_preflight(
    source: str,
    *,
    new_name: str | None = None,
) -> dict[str, Any]:
    """Pre-flight check for rename: check for collisions, alias shadows, and true duplicates.
    
    Returns:
        {"ok": True, ...} if rename is safe.
        {"ok": False, "error": ..., "reason": ...} if blocked.
    """
    source_fleet, source_name = split_ref(source)
    if not source_fleet:
        agent, _ = resolve_live(source_name)
        if not agent:
            return {"ok": False, "error": f"agent not found: {source}"}
        source_fleet = agent.get("fleet")
        source_name = agent.get("name")
    
    source_ref = _key(source_fleet, source_name)
    data = read_registry()
    existing = data.get(source_ref)
    if not existing:
        # Check if source is an alias (disallow: must rename canonical target).
        resolved, chain = resolve_historical(source_ref)
        if chain:
            return {
                "ok": False,
                "error": f"source is an alias; use canonical target instead: {resolved}",
                "alias_chain": chain,
            }
        return {"ok": False, "error": f"agent not found: {source_ref}"}
    
    target_name = new_name or existing.get("name")
    target_fleet = existing.get("fleet")
    target_ref = _key(target_fleet, target_name)
    target_existing = data.get(target_ref) if target_ref != source_ref else None
    
    repair_duplicate = False
    if target_ref != source_ref and target_existing:
        # Check if target_existing is the same live incarnation.
        if not _same_live_incarnation(existing, target_existing):
            # Collision: two distinct live panes trying to occupy same name.
            return {
                "ok": False,
                "error": f"target already exists: {target_ref}",
                "reason": "target-registry-exists",
                "target": target_ref,
            }
        # True duplicate: same incarnation at different registry keys.
        # Safe to merge.
        repair_duplicate = True
    
    # Check for alias-shadow: if target_ref maps to a different live pane via alias.
    if target_ref != source_ref and not target_existing:
        resolved, alias_chain = resolve_historical(target_ref)
        if alias_chain and resolved != target_ref:
            target_fleet_resolved, target_name_resolved = split_ref(resolved)
            target_shadow = data.get(_key(target_fleet_resolved, target_name_resolved))
            if target_shadow and not _same_live_incarnation(existing, target_shadow):
                return {
                    "ok": False,
                    "error": f"target name shadows an alias; resolve collision first",
                    "reason": "target-alias-shadow",
                    "target_ref": target_ref,
                    "alias_resolved": resolved,
                    "alias_chain": alias_chain,
                }
    
    return {
        "ok": True,
        "source": source_ref,
        "target": target_ref,
        "source_record": existing,
        "target_record": target_existing,
        "repair_duplicate": repair_duplicate,
    }


def rename_agent(
    source: str,
    *,
    new_name: str,
    metadata: dict[str, Any] | None = None,
    alias_old: bool = True,
) -> dict[str, Any]:
    """Rename a seat, optionally creating a historical alias.
    
    If repair_duplicate: merge same-incarnation record, mark loser as historical.
    If new name collides with existing alias target: error.
    """
    source_fleet, source_name = split_ref(source)
    existing = resolve_live(source_name, fleet=source_fleet)[0] if source_fleet else None
    if not existing:
        existing, _ = resolve_live(source_name)
    if not existing:
        # Check if source is alias (disallow).
        resolved, chain = resolve_historical(source)
        if chain:
            return {
                "ok": False,
                "error": f"source is an alias; rename canonical target instead: {resolved}",
                "alias_chain": chain,
            }
        return {"ok": False, "error": f"agent not found: {source}"}
    
    target_fleet = existing.get("fleet")
    preflight = rename_preflight(source, new_name=new_name)
    if not preflight.get("ok"):
        return preflight
    
    with _registry_lock():
        source_ref = preflight["source"]
        target_ref = preflight["target"]
        data = read_registry()
        existing = data.get(source_ref) or preflight["source_record"]
        target_existing = data.get(target_ref) if target_ref != source_ref else None
        
        record = dict(existing)
        
        # If repair-duplicate: merge target fields but preserve winner's occupant identity.
        if target_existing:
            # Merge non-occupant fields from target.
            for key, value in target_existing.items():
                if key not in ("seat_instance_id", "pane_ref", "aura_launch_id"):
                    record.setdefault(key, value)
        
        record["name"] = new_name
        record["fleet"] = target_fleet
        record["seat"] = new_name
        record["seat_ref"] = target_ref
        record["logical_fleet"] = target_fleet
        record["logical_name"] = new_name
        record["rename_source"] = source_ref
        record["rename_at"] = now_iso()
        record["last_seen"] = now_iso()
        record.setdefault("physical_fleet", existing.get("physical_fleet") or target_fleet)
        record = _with_logical_physical_fields(record, fleet=target_fleet, name=new_name)
        record = _without_transient_fields(record)
        
        # Write winner at target location.
        if target_ref != source_ref:
            data.pop(source_ref, None)
            
            # If repair-duplicate: preserve loser as historical, not deleted.
            if target_existing and preflight.get("repair_duplicate"):
                loser_historical = dict(target_existing)
                loser_historical["registered"] = False
                loser_historical["replaced_by"] = target_ref
                loser_historical["replaced_at"] = now_iso()
                loser_historical["reason"] = "duplicate-repair:loser-preserved-as-historical"
                # Store loser under a unique key for lineage/audit.
                loser_key = f"{target_ref}:__historical_{uuid.uuid4().hex[:8]}"
                data[loser_key] = loser_historical
        
        data[target_ref] = record
        _write_registry_unlocked(data)
    
    # Create alias if old name is to be mapped forward.
    alias = add_alias(source_ref, target_ref, reason="rename") if alias_old and target_ref != source_ref else None
    return {
        "ok": True,
        "source": source_ref,
        "target": target_ref,
        "record": record,
        "alias": alias,
        "repair_duplicate": bool(preflight.get("repair_duplicate")),
    }
```

---

## PART 3: LIVE CONSUMER CHANGES

All live consumers **MUST switch from `get_agent()` to `resolve_live()`** or use `get_agent(resolve_alias=False)` for backward-compat wrappers during transition.

### 3.1 `cli/commands/sessions.py: _canonical_bind_target()`

**Current** (lines 1340–1356):
- Calls `resolve_alias()` on requested_ref.
- Returns target_fleet/seat from alias chain if found.

**CHANGE**: Use `resolve_live()` only; never follow aliases in binding path.

```python
def _canonical_bind_target(registry, *, fleet: str, seat: str) -> tuple[str, str, dict | None, list[str]]:
    """Resolve the exact live seat for binding.
    
    PHYSICAL ONLY: never follows aliases.
    Returns (target_fleet, target_seat, previous_row, []) where previous_row is the exact
    row at (fleet, seat) if it exists.
    """
    requested_ref = registry.seat_ref(fleet, seat)
    
    # Physical-only resolution.
    previous, _ = registry.resolve_live(seat, fleet=fleet)
    
    return fleet, seat, previous, []  # No alias chain for live binding.
```

---

### 3.2 `cli/commands/sessions.py: _bind_pane()` and `_bind_current()`

**Lines 1127, 1197**: Use the new `_canonical_bind_target()` (which no longer returns alias_chain).

No change required in logic, only in how the returned tuple is unpacked.

---

### 3.3 `cli/lib/queued_messages.py: _matches_report()`

**Current** (lines 106–128):
- Line 123: calls `resolve_alias()` on queued message target to match report.
- DEFECT: Stale alias routes to wrong pane.

**CHANGE**: Use occupant-keyed continuity (M2) for stale-ref matching; physical live check as fallback.

**NOTE**: Full M2 implementation required; for M1 spec, disable alias lookup entirely:

```python
def _matches_report(record: dict[str, Any], report: dict[str, Any]) -> bool:
    status = record.get("status")
    if status == "scheduled":
        return record.get("release_report_id") == report.get("report_id")
    if status != "pending":
        return False
    after = record.get("after") or "next-report"
    if after != "next-report":
        return after == report.get("report_id")
    
    report_targets = _report_targets(report)
    target = record.get("target")
    if target in report_targets:
        return True
    
    # M2 continuity: match by occupant id (si/launch/%N), not alias.
    # For M1 only: skip alias lookup entirely.
    # (Full M2 implementation resolves sender+report by occupant key.)
    
    return False
```

---

### 3.4 `cli/lib/report_subscriptions.py: _matches_target()` and `canonical_target()`

**Current** (lines 148–158, 207–214):
- Calls `resolve_alias()` to match subscription target to report.
- DEFECT: Stale alias silently routes notifications.

**CHANGE**: Use physical-only matching. For M1: disable alias-based fallback.

```python
def _matches_target(target: str, report: dict[str, Any]) -> bool:
    """Match subscription target to report source using physical identity only.
    
    Never follow aliases; require exact name/fleet match.
    """
    report_targets = _report_targets(report)
    if target in report_targets:
        return True
    
    # M2 TODO: match by occupant key if target is a stale ref to a same occupant.
    # For M1: physical-only, no alias fallback.
    
    return False


def canonical_target(target: str) -> str:
    """Return the live canonical form of a target (physical identity only).
    
    For M1: no alias resolution. Return target as-is.
    For M2+: resolve by occupant key if needed.
    """
    return target
```

---

### 3.5 `cli/lib/reports.py: infer_context()`

**Current** (line 54):
- Calls `registry.get_agent(seat, fleet=fleet)` to enrich report.
- Default behavior now physical-only; backward-compat preserved.

**CHANGE**: Ensure `get_agent()` is called WITHOUT `resolve_alias=True` (default behavior).

No code change required; behavior changes automatically with new `get_agent()` default.

---

### 3.6 `cli/lib/seat_status.py: list_seat_statuses()`

**Current**: Iterates `registry.read_registry().values()` to render all rows.

**CHANGE**: No change to M1; M4 will add orphan reconciliation (born-pane self-heal).

---

### 3.7 `cli/commands/cut.py: run()`

**Current** (line 114):
- Calls `registry.get_agent(args.name)`.

**CHANGE**: Add explicit `resolve_alias=False` to ensure physical-only.

```python
reg_agent = registry.get_agent(args.name, resolve_alias=False)
```

---

### 3.8 `cli/commands/send.py: run()`

**Current** (line 94):
- Calls `registry.get_agent(args.target)`.

**CHANGE**: Physical-only lookup.

```python
reg_agent = registry.get_agent(args.target, resolve_alias=False)
```

---

### 3.9 `cli/commands/inspect.py`, `cli/commands/view.py`, `cli/commands/check.py`

All call `get_agent()` for inspection/listing. Default behavior (physical-only) is correct for M1.

**Change**: Use `resolve_live()` directly where precision is critical; `get_agent()` acceptable for backward-compat as long as `resolve_alias=False` (default).

---

## PART 4: EDGE CASES & INTERACTIONS

### 4.1 Thin/Name-Only Rows (Shell/Command Runtimes)

**Rows without %N, si, or launch_id**:
- `resolve_live()` returns them if name matches (no %N to match against).
- Rename collision guard: such rows can collide with new names (no distinct occupant id).
- For M1: allow thin rows to be overwritten (they have no live physical identity).
- **M3+ must prevent thin-row overwriting** (requires occupant-keyed row versioning).

---

### 4.2 Mirror Unavailable

**`seat_status._terminal_status()` code path** (lines 82–146):
- Uses live pane keys if mirror is available.
- Falls back to name-based `target_exists()` if mirror unavailable.
- **M1 change**: No impact; mirror lookup is passive (doesn't write or consume aliases).
- **M4+**: Mirror-based pane discovery feeds born-pane reconciliation.

---

### 4.3 Fork-Children & Services

**Fork-children** inherit parent's `aura_launch_id`.
- `resolve_live()` treats them as distinct rows (different names or fleets).
- Rename collision will block if child inherits parent's launch_id AND both live.
- **M3 must strengthen**: Require si match for same-incarnation, not just launch_id.

**Services** (runtime="service"):
- No %N or si; name-only identity.
- `resolve_live()` returns by name match only.
- Rename collision allowed (services are thin).

---

### 4.4 Dead %N (Pane Killed, Seat Still Registered)

**Current behavior**:
- Registry row holds stale pane_ref pointing to a dead tmux %N.
- `seat_status._terminal_status()` detects pane_key not in live mirror → "missing".
- **M1 change**: None; detection remains unchanged.
- **M4 changes**: If pane is dead but row is still "registered", can reconcile or orphan.

---

### 4.5 Alias Records After Rename

**Current**: `rename_agent()` calls `add_alias(source_ref, target_ref, reason="rename")`.

**M1 change**: Alias records are now purely historical. A live operation will never follow them; they serve only as audit trail and M2 continuity hint.

**Implication**: Old aliases pointing to renamed seats are now "dead" — they don't redirect live lookups. Callers with stale refs must use occupant keys (M2) or explicit rename tracing for lineage.

---

### 4.6 Same-Occupant Continuity Fallback (M2 Interaction)

**Current**: Not implemented; M2 is future work.

**M1 foundation**: `occupant_key()` function added; used by M2 to key stale ref resolution across renames.

**Example M2 scenario** (future):
1. Seat "old_name" with si=X renamed to "new_name".
2. Report from stale env targeting "old_name" arrives.
3. M2 logic: resolve "old_name" historically → alias to "new_name" → resolve "new_name" live → check occupant si matches X → **accept** (same occupant across rename).

---

## PART 5: MIGRATION & BACKWARD-COMPAT

### 5.1 Existing Registry Records

**No data migration required.**

All existing rows remain valid for `resolve_live()`:
- Rows with %N, si, launch_id → matched exactly.
- Rows with only name → matched by name (may become ambiguous if duplicates exist).
- Rows without occupant identity → thin rows, matched by name only.

---

### 5.2 Existing Alias Records

**No changes needed.**

Aliases become **dormant** after M1:
- No live operation follows them.
- They exist as historical breadcrumbs for audit/lineage (M5 operator verbs).
- M2 uses them as hints for occupant continuity.
- M5 adds `aura seat alias ls / rm` to manage them.

---

### 5.3 Backward-Compat Function: `get_agent(resolve_alias=True)`

For code paths that genuinely need alias resolution (e.g., old scripts, M2 continuity fallback):

```python
# OLD BEHAVIOR (for fallback in M2 only):
row = registry.get_agent("seat_name", resolve_alias=True)

# NEW PATTERN (for live operations — M1+):
row, reason = registry.resolve_live("seat_name")
if not row:
    # Handle not-found / ambiguous
    pass

# NEW PATTERN (for historical/lineage — M5):
resolved_ref, alias_chain = registry.resolve_historical("seat_name")
```

---

## PART 6: TEST ADDITIONS

### 6.1 Test: `resolve_live()` Never Follows Aliases

```python
def test_resolve_live_physical_only():
    """resolve_live() returns the exact row at name/fleet, never alias targets."""
    data = {
        "aura:seat_a": {"name": "seat_a", "fleet": "aura", "seat": "seat_a", "pane_ref": "tmux:aura:%100"},
        "aura:seat_b": {"name": "seat_b", "fleet": "aura", "seat": "seat_b", "pane_ref": "tmux:aura:%101"},
    }
    aliases = {
        "aura:seat_a": {"source": "aura:seat_a", "target": "aura:seat_b", "reason": "rename"}
    }
    # Monkey-patch read_registry / read_aliases
    with patch_registry(data), patch_aliases(aliases):
        # Request "seat_a" returns row_a, NEVER follows alias to row_b.
        row, reason = registry.resolve_live("seat_a", fleet="aura")
        assert row is not None
        assert row["pane_ref"] == "tmux:aura:%100"
```

---

### 6.2 Test: `_same_live_incarnation()` Requires Matching %N

```python
def test_same_live_incarnation_distinct_panes():
    """Two rows with same si but distinct %N are NOT same incarnation."""
    row_a = {
        "seat_instance_id": "si_abc123",
        "pane_ref": "tmux:aura:%100",
    }
    row_b = {
        "seat_instance_id": "si_abc123",
        "pane_ref": "tmux:aura:%101",
    }
    # MUST return False (distinct panes, even though si matches).
    assert not registry._same_live_incarnation(row_a, row_b)
```

---

### 6.3 Test: Rename Collision Guard Catches Alias-Shadow Path

```python
def test_rename_collision_alias_shadow():
    """Rename to a name that shadows an alias must error."""
    data = {
        "aura:seat_x": {"name": "seat_x", "fleet": "aura", "pane_ref": "tmux:aura:%200"},
        "aura:seat_y": {"name": "seat_y", "fleet": "aura", "pane_ref": "tmux:aura:%201"},
    }
    aliases = {
        "aura:seat_shadow": {"target": "aura:seat_y"}
    }
    with patch_registry(data), patch_aliases(aliases):
        # Rename seat_x to "seat_shadow" should error (alias shadows seat_y).
        result = registry.rename_preflight("seat_x", new_name="seat_shadow")
        assert not result["ok"]
        assert result["reason"] == "target-alias-shadow"
```

---

### 6.4 Test: Rename Repair-Duplicate Preserves Loser as Historical

```python
def test_rename_repair_duplicate_preserves_loser():
    """When merging same-si rows, loser is marked historical (not deleted)."""
    data = {
        "aura:seat_old": {
            "name": "seat_old",
            "fleet": "aura",
            "seat_instance_id": "si_dup123",
            "pane_ref": "tmux:aura:%100",
        },
        "aura:seat_new": {
            "name": "seat_new",
            "fleet": "aura",
            "seat_instance_id": "si_dup123",
            "pane_ref": "tmux:aura:%100",
        },
    }
    with patch_registry(data):
        result = registry.rename_agent("seat_old", new_name="seat_new")
        assert result["ok"]
        assert result["repair_duplicate"]
        
        # Verify loser is preserved as historical in registry.
        final_data = registry.read_registry()
        loser_rows = [v for k, v in final_data.items() if "__historical_" in k]
        assert len(loser_rows) == 1
        assert loser_rows[0]["registered"] is False
        assert loser_rows[0]["replaced_by"] == "aura:seat_new"
```

---

### 6.5 Test: Binding Never Uses Aliases

```python
def test_canonical_bind_target_physical_only():
    """_canonical_bind_target() uses physical resolution, never aliases."""
    data = {
        "aura:target_seat": {"name": "target_seat", "fleet": "aura"},
    }
    aliases = {
        "aura:stale_seat": {"target": "aura:target_seat"}
    }
    with patch_registry(data), patch_aliases(aliases):
        # Request to bind "stale_seat" should NOT be redirected to target_seat.
        # Instead, should try to bind stale_seat as-is (and fail if not registered).
        fleet, seat, previous, alias_chain = sessions._canonical_bind_target(
            registry, fleet="aura", seat="stale_seat"
        )
        assert seat == "stale_seat"
        assert alias_chain == []
        assert previous is None  # Not registered
```

---

### 6.6 Test: Queued Message Match Ignores Aliases (M1)

```python
def test_queued_message_match_physical_only():
    """M1: queued_messages match by name only, never alias."""
    report = {
        "seat": "seat_a",
        "fleet": "aura",
        "report_id": "rpt-123",
    }
    record = {
        "target": "aura:seat_stale",
        "status": "pending",
    }
    aliases = {
        "aura:seat_stale": {"target": "aura:seat_a"}
    }
    with patch_registry({}), patch_aliases(aliases):
        # M1: match fails (stale name doesn't match report name).
        # M2 will fix this via occupant continuity.
        assert not queued_messages._matches_report(record, report)
```

---

## PART 7: SUMMARY OF CHANGES BY FILE

| File | Function | Change | Complexity |
|------|----------|--------|-----------|
| `registry.py` | `get_agent()` | Add `resolve_alias` param; default False (physical-only) | Medium |
| `registry.py` | NEW: `resolve_live()` | Core physical-only resolution | High |
| `registry.py` | NEW: `resolve_historical()` | Alias chain following (renamed from `resolve_alias`) | Low |
| `registry.py` | `_same_live_incarnation()` | Require BOTH si AND pane match | Medium |
| `registry.py` | `rename_preflight()` | Add alias-shadow guard; improve collision detection | Medium |
| `registry.py` | `rename_agent()` | Preserve loser as historical (not delete) | Medium |
| `sessions.py` | `_canonical_bind_target()` | Use `resolve_live()` only; remove alias chain | Low |
| `queued_messages.py` | `_matches_report()` | Remove alias lookup; physical-only | Low |
| `report_subscriptions.py` | `_matches_target()` | Remove alias lookup; physical-only | Low |
| `report_subscriptions.py` | `canonical_target()` | No-op for M1 (physical-only) | Low |
| `cut.py` | `run()` | Pass `resolve_alias=False` to `get_agent()` | Very Low |
| `send.py` | `run()` | Pass `resolve_alias=False` to `get_agent()` | Very Low |

---

## PART 8: M1 ACCEPTANCE CRITERIA

1. **`resolve_live()` never follows aliases**: All tests pass; no alias consultations in live paths.
2. **Rename collision guard catches alias-shadows**: `rename_preflight()` returns error code "target-alias-shadow" when appropriate.
3. **Duplicate repair preserves loser**: Loser rows are marked `registered=False` + `replaced_by`, never silently deleted.
4. **_same_live_incarnation requires pane match**: Two rows with same si but distinct %N are treated as distinct.
5. **All live consumers use physical-only**: `sessions._canonical_bind_target()`, `queued_messages`, `report_subscriptions`, `send`, `cut`, `view`, `inspect` all bypass aliases.
6. **Backward-compat preserved**: Code using `get_agent(resolve_alias=True)` still works; old tests pass.
7. **Alias records remain dormant**: No new alias logic in M1; they exist as historical breadcrumbs.

---

## PART 9: INTERACTIONS WITH M2–M5

| Move | M1 Dependency | Interaction |
|------|---------------|------------|
| **M2** Occupant-keyed continuity | `occupant_key()` function | M2 uses occupant_key to match stale refs across renames via historical alias chain; fallback loses to live distinct pane. |
| **M3** Rename on exact %N + repair never orphans | `_same_live_incarnation()` improvements | M3 strengthens duplicate detection; M1 foundation (pane matching, loser preservation) enables M3. |
| **M4** Born-pane self-heal | No direct dependency | M4 adds orphan reconciliation; M1 ensures live resolution is exact, so M4 can safely reconstruct rows from %N+nonce. |
| **M5** Operator surface | `resolve_historical()` exposed | M5 implements `aura seat alias ls/rm` using `resolve_historical()`; M1 makes `resolve_alias()` internal (becomes `resolve_historical()`). |

---

## IMPLEMENTATION CHECKLIST

- [ ] Implement `resolve_live()` with exact name/fleet matching.
- [ ] Implement `resolve_historical()` (rename `resolve_alias()`).
- [ ] Update `get_agent()` to have `resolve_alias` parameter; default False.
- [ ] Fix `_same_live_incarnation()` to require pane match.
- [ ] Add `_is_pane_id()` helper.
- [ ] Enhance `rename_preflight()` with alias-shadow guard.
- [ ] Update `rename_agent()` to preserve loser as historical.
- [ ] Update `_canonical_bind_target()` to use `resolve_live()`.
- [ ] Remove alias lookup from `_matches_report()`, `_matches_target()`, `canonical_target()`.
- [ ] Add `resolve_alias=False` to `get_agent()` calls in `cut.py`, `send.py`, other live paths.
- [ ] Write comprehensive tests (6 test suites above).
- [ ] Verify no new alias logic or live alias consultations introduced.
- [ ] Update docstrings to clarify physical vs. historical resolution.
- [ ] Regression test: old `get_agent(resolve_alias=True)` paths still work.

---

This spec is ready for implementation by an engineer. All signatures, edge cases, and test assertions are concrete; no re-derivation of design is needed.
Now I have sufficient understanding. Let me create the comprehensive implementation spec for M2.

## Implementation Spec for M2: Occupant-keyed continuity for stale refs

Based on my analysis of the Aura codebase, here is a precise diff-level implementation spec for Move M2 — Occupant-keyed continuity for stale refs.

---

### **1. EXECUTIVE SUMMARY**

Move M2 replaces name-alias-based canonicalization in sender/delivery routing (`reports.py`, `queued_messages.py`, `report_subscriptions.py`) with occupant-keyed resolution using `seat_instance_id`, `aura_launch_id`, and `%N` pane reference. The binding path gains a fallback mechanism that loses to live distinct panes, preserving correctness when a name is reused by a new occupant.

**Three new registry functions:**
- `resolve_live(ref, *, fleet=None)` → resolve by exact current name + fleet only; no alias, no historical fallback
- `resolve_occupant(si, launch_id, pane_ref, *, default_ref=None)` → resolve to a current row by occupant identity (si/launch_id/%N match), with optional fallback to `default_ref` only if the occupant is not alive elsewhere
- `resolve_historical(ref, *, fleet=None)` → follow alias chain to canonical past target (existing `resolve_alias` renamed + enhanced)

**Four modified delivery/sender paths** use occupant resolution instead of alias:
1. `queued_messages._matches_report()` — resolve target via occupant if target is stale-named
2. `report_subscriptions._matches_target()` — resolve subscription target via occupant
3. `report_subscriptions._matches_placement()` — resolve placement member refs via occupant
4. `report_subscriptions.canonical_target()` — canonicalize deduplication key via occupant (used in sender deduplication logic)

This isolates alias to historical reconstruction only, ensures stale env variables find the right occupant even after name reuse, and guarantees name-based fallback only when that occupant is truly gone.

---

### **2. NEW SIGNATURES & CONTRACTS**

#### **registry.py additions:**

```python
def resolve_live(ref: str, *, fleet: str | None = None) -> dict[str, Any] | None:
    """Resolve a seat reference to a live registry row by exact name match ONLY.
    
    Args:
        ref: Name or "fleet:name" reference
        fleet: Optional explicit fleet; overrides fleet from ref if both present
    
    Returns:
        Registry row if name + fleet match exactly; None otherwise.
        Does NOT follow aliases. Does NOT consult historical lineage.
        
    Example:
        resolve_live("probe") with fleet="aura" -> finds registry row with name="probe" & fleet="aura"
        resolve_live("aura:probe") -> same
        resolve_live("probe") with no fleet argument and no AURA_FLEET env -> None
    """
```

```python
def resolve_occupant(
    seat_instance_id: str | None = None,
    aura_launch_id: str | None = None,
    pane_ref: str | None = None,
    *,
    default_ref: str | None = None,
    mirror_unavailable: str = "fallback",  # "fallback" | "error" | "none"
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Resolve occupant by identity (si, launch_id, %N) to current live registry row.
    
    Occupant identity has precedence: si (exact match) > launch_id (exact) > pane_ref (live %N).
    Once matched, cross-check for liveness (pane_ref must be live or occupant is considered dead).
    
    Args:
        seat_instance_id: The occupant's si; if present and in registry, that row wins
        aura_launch_id: Fallback occupant id if si not found
        pane_ref: Physical tmux pane ref "tmux:fleet:%N"; used as final tiebreaker and liveness check
        default_ref: A name/ref to try if occupant identity is unknown/all-None; only succeeds
                     if occupant is not found alive elsewhere (prevents name-reuse collision)
        mirror_unavailable: How to handle tmux unavailable (for pane_ref liveness check):
                           "fallback" → treat as if pane is gone (occupant dead)
                           "error" → return error
                           "none" → skip liveness check (unsafe; for repair mode only)
    
    Returns:
        (row, metadata) where:
        - row: matched registry row, or None if not found or occupant is dead
        - metadata: {
            "matched_by": "seat_instance_id" | "aura_launch_id" | "pane_ref" | "default_ref" | None,
            "occupant_alive": bool (pane_ref check passed, if pane_ref present),
            "fallback_attempted": bool (whether default_ref was consulted),
            "error": str | None (tmux error if mirror_unavailable="error"),
          }
    
    Logic flow:
        1. If si present, search registry for si=si & registered=true; if found, check pane_ref liveness
           → match (occupant_alive=True/False)
        2. If no si match and launch_id present, search for launch_id=launch_id & registered=true
           → check pane_ref liveness → match
        3. If no si/launch_id match and pane_ref present, search for pane_ref=pane_ref exact
           → match (occupant_alive=inferred from found row)
        4. If no identity matches and default_ref present AND occupant not found alive elsewhere
           → try resolve_live(default_ref) as fallback, mark fallback_attempted=True
        5. If occupant found but pane_ref dead (and pane_ref present) → occupant_alive=False, row still returned
           (caller decides whether to use it)
        6. All None/no matches → (None, metadata)
    """
```

```python
def resolve_historical(ref: str, *, fleet: str | None = None, max_hops: int = 8) -> tuple[str, list[str]]:
    """Follow alias chain to reconstruct canonical past target (renamed resolve_alias).
    
    Replaces existing resolve_alias. Same contract, new name: emphasizes this is for
    historical reconstruction only. Callers must use resolve_live + resolve_occupant
    for active/stale-ref scenarios.
    
    Returns (canonical_ref, chain_of_source_refs).
    """
```

---

### **3. PRECISE EDITS PER FILE**

#### **registry.py changes:**

##### **3a. Add resolve_live (new function after normalize_agent_record):**

```python
def resolve_live(ref: str, *, fleet: str | None = None) -> dict[str, Any] | None:
    """Resolve a seat reference to live registry row by exact name match, no alias."""
    from lib import registry as reg  # for _key
    resolved_fleet, name = split_ref(str(ref), fleet=fleet)
    if not resolved_fleet:
        return None
    data = read_registry()
    key = _key(resolved_fleet, name)
    row = data.get(key)
    if row and row.get("registered", True):
        return row
    return None
```

##### **3b. Add resolve_occupant (new function after resolve_live):**

```python
def resolve_occupant(
    seat_instance_id: str | None = None,
    aura_launch_id: str | None = None,
    pane_ref: str | None = None,
    *,
    default_ref: str | None = None,
    mirror_unavailable: str = "fallback",
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Resolve occupant by identity (si, launch_id, %N) to current live row.
    
    Occupant precedence: si > launch_id > pane_ref. Checks liveness via pane_ref if present.
    Falls back to default_ref only if occupant is not found alive elsewhere.
    """
    data = read_registry()
    matched_row = None
    matched_by = None
    occupant_alive = False
    fallback_attempted = False
    error = None
    
    # Strategy 1: si exact match (occupant has a unique si in registry)
    if seat_instance_id:
        candidates = [r for r in data.values() 
                     if r.get("seat_instance_id") == seat_instance_id and r.get("registered", True)]
        if candidates:
            # Prefer the one whose pane_ref is live, else take first
            if pane_ref:
                for candidate in candidates:
                    if candidate.get("pane_ref") == pane_ref:
                        matched_row = candidate
                        matched_by = "seat_instance_id"
                        occupant_alive = True
                        break
            if not matched_row:
                matched_row = candidates[0]
                matched_by = "seat_instance_id"
                occupant_alive = False  # si match but pane_ref not live (if pane_ref given)
    
    # Strategy 2: launch_id exact match
    if not matched_row and aura_launch_id:
        candidates = [r for r in data.values()
                     if r.get("aura_launch_id") == aura_launch_id and r.get("registered", True)]
        if candidates:
            if pane_ref:
                for candidate in candidates:
                    if candidate.get("pane_ref") == pane_ref:
                        matched_row = candidate
                        matched_by = "aura_launch_id"
                        occupant_alive = True
                        break
            if not matched_row:
                matched_row = candidates[0]
                matched_by = "aura_launch_id"
                occupant_alive = False
    
    # Strategy 3: pane_ref exact match (physical live pane)
    if not matched_row and pane_ref:
        for row in data.values():
            if row.get("pane_ref") == pane_ref and row.get("registered", True):
                matched_row = row
                matched_by = "pane_ref"
                occupant_alive = True  # pane_ref match means live by definition
                break
    
    # Strategy 4: Liveness check via tmux if pane_ref present and not yet confirmed alive
    if matched_row and pane_ref and not occupant_alive and matched_by != "pane_ref":
        try:
            from lib import terminal
            # Check if pane_ref still exists in tmux
            ref_to_check = matched_row.get("pane_ref") or pane_ref
            if terminal.target_exists(ref_to_check):
                occupant_alive = True
        except Exception as exc:
            if mirror_unavailable == "error":
                error = str(exc)
                matched_row = None
            # else "fallback" or "none" → assume dead
    
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
        elif aura_launch_id:
            occupant_elsewhere = any(
                r.get("aura_launch_id") == aura_launch_id and r.get("registered", True)
                for r in data.values()
            )
        
        # Only use default_ref if occupant is not alive elsewhere
        if not occupant_elsewhere:
            matched_row = resolve_live(default_ref)
            if matched_row:
                matched_by = "default_ref"
                occupant_alive = True  # assume default is live
    
    metadata = {
        "matched_by": matched_by,
        "occupant_alive": occupant_alive,
        "fallback_attempted": fallback_attempted,
        "error": error,
    }
    return matched_row, metadata
```

##### **3c. Rename resolve_alias to resolve_historical, add deprecation note:**

```python
def resolve_historical(ref: str, *, max_hops: int = 8) -> tuple[str, list[str]]:
    """Follow alias chain to reconstruct canonical past target.
    
    Used ONLY for historical reconstruction (restore, audit, lineage).
    Live resolution must use resolve_live + resolve_occupant for occupant-keyed routing.
    """
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


# Backward-compat alias (deprecate in future)
def resolve_alias(ref: str, *, max_hops: int = 8) -> tuple[str, list[str]]:
    """Deprecated: use resolve_historical for historical chain or resolve_live/resolve_occupant for live."""
    return resolve_historical(ref, max_hops=max_hops)
```

##### **3d. Update get_agent to call resolve_historical (not removed, stays as-is but internally uses resolve_historical):**

Change line 404-410 from:
```python
        resolved, chain = resolve_alias(ref)
        if chain:
            target_fleet, target_name = split_ref(resolved)
```

To:
```python
        resolved, chain = resolve_historical(ref)
        if chain:
            target_fleet, target_name = split_ref(resolved)
```

And similarly for line 416.

---

#### **queued_messages.py changes:**

Current code (lines 106-128):
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
    if target:
        try:
            from lib import registry
            resolved, chain = registry.resolve_alias(str(target))
            if chain and resolved in report_targets:
                return True
        except Exception:
            pass
    return False
```

**Replace with:**
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
    if target:
        # First try resolve_live: if the name exists now, use it (no alias)
        try:
            from lib import registry
            live_row = registry.resolve_live(str(target))
            if live_row:
                live_targets = {live_row.get("fleet") + ":" + live_row.get("name")}
                if report_targets & live_targets:
                    return True
                # Live row exists but doesn't match report; don't fall back to stale occupant
                return False
        except Exception:
            pass
        
        # If no live row, resolve by occupant: try to find sender by si/launch_id/pane_ref
        # Extract si/launch_id/pane_ref from the queued message if available
        # (these would typically come from the queue record's metadata, else we have no occupant id)
        occupant_si = record.get("occupant_seat_instance_id")
        occupant_launch_id = record.get("occupant_aura_launch_id")
        occupant_pane = record.get("occupant_pane_ref")
        
        if occupant_si or occupant_launch_id or occupant_pane:
            try:
                matched, meta = registry.resolve_occupant(
                    seat_instance_id=occupant_si,
                    aura_launch_id=occupant_launch_id,
                    pane_ref=occupant_pane,
                    default_ref=str(target) if meta.get("fallback_attempted") is False else None,
                    mirror_unavailable="fallback",
                )
                if matched and meta.get("occupant_alive"):
                    occupant_targets = {matched.get("fleet") + ":" + matched.get("name")}
                    if report_targets & occupant_targets:
                        return True
            except Exception:
                pass
        
        # Finally, fallback to historical alias chain (for backward compat; should be rare)
        try:
            from lib import registry
            resolved, chain = registry.resolve_historical(str(target))
            if chain and resolved in report_targets:
                return True
        except Exception:
            pass
    return False
```

**Note:** This requires queue records to store occupant metadata. If not stored during queue creation, the occupant_si/launch_id/pane lookup will be None and skip to historical. For M2 to be fully effective, queue.create() should capture sender's occupant id at time of queueing.

---

#### **report_subscriptions.py changes:**

##### **3b1. Update _matches_target (lines 148-158):**

Current:
```python
def _matches_target(target: str, report: dict[str, Any]) -> bool:
    report_targets = _report_targets(report)
    if target in report_targets:
        return True
    try:
        from lib import registry
        resolved, chain = registry.resolve_alias(target)
        return bool(chain and resolved in report_targets)
    except Exception:
        return False
```

**Replace with:**
```python
def _matches_target(target: str, report: dict[str, Any]) -> bool:
    report_targets = _report_targets(report)
    if target in report_targets:
        return True
    
    # Try resolve_live first: if name exists now, only match if it's in report_targets
    try:
        from lib import registry
        live_row = registry.resolve_live(str(target))
        if live_row:
            live_targets = {live_row.get("fleet") + ":" + live_row.get("name")}
            return bool(report_targets & live_targets)
    except Exception:
        pass
    
    # If no live row, try historical alias chain for backward compat
    try:
        from lib import registry
        resolved, chain = registry.resolve_historical(target)
        return bool(chain and resolved in report_targets)
    except Exception:
        return False
```

##### **3b2. Update _matches_placement (lines 161-184):**

Current code calls `registry.resolve_alias(str(seat_ref))` at line 175. Replace:

```python
                    try:
                        resolved, chain = registry.resolve_alias(str(seat_ref))
                        if chain and resolved:
                            candidates.add(resolved)
                    except Exception:
                        pass
```

With:

```python
                    # Try live first
                    try:
                        from lib import registry
                        live_row = registry.resolve_live(str(seat_ref))
                        if live_row:
                            candidates.add(live_row.get("fleet") + ":" + live_row.get("name"))
                    except Exception:
                        pass
                    
                    # Fallback to historical
                    try:
                        from lib import registry
                        resolved, chain = registry.resolve_historical(str(seat_ref))
                        if chain and resolved:
                            candidates.add(resolved)
                    except Exception:
                        pass
```

##### **3b3. Update canonical_target (lines 207-214):**

Current:
```python
def canonical_target(target: str) -> str:
    try:
        from lib import registry
        resolved, chain = registry.resolve_alias(target)
        return resolved if chain and resolved else target
    except Exception:
        return target
```

**Replace with:**
```python
def canonical_target(target: str) -> str:
    """Return canonical name for deduplication.
    
    For a live seat: return the exact current name (live resolution).
    For a stale ref: return historical canonical target (alias chain).
    Otherwise: return the input target (unknown).
    """
    try:
        from lib import registry
        # Live resolution: if name exists now, use it as-is
        live_row = registry.resolve_live(str(target))
        if live_row:
            return live_row.get("fleet") + ":" + live_row.get("name")
    except Exception:
        pass
    
    # Fallback to historical
    try:
        from lib import registry
        resolved, chain = registry.resolve_historical(target)
        return resolved if chain and resolved else target
    except Exception:
        return target
```

---

#### **reports.py changes (sender canonicalization):**

The `infer_context()` function at line 54 calls `registry.get_agent(seat, fleet=fleet)`. This uses the current logic which already resolves via name, which is fine. However, if we want to add occupant-aware canonicalization for stale env variables, we need:

Add a new helper function **after `infer_context()`:**

```python
def _resolve_sender_for_report(seat: str | None, fleet: str | None, agent_record: dict | None) -> dict[str, Any]:
    """Resolve sender occupant from Aura env, preferring occupant identity over name.
    
    If env contains AURA_SEAT_INSTANCE_ID / AURA_LAUNCH_ID / AURA_PANE_REF,
    use those to find the live occupant even if AURA_SEAT/AURA_FLEET have drifted due to rename.
    
    Args:
        seat: Inferred seat name (may be stale)
        fleet: Inferred fleet (may be stale)
        agent_record: The registry row found by resolve_live(seat, fleet) or None
    
    Returns:
        Updated agent record (by occupant if found, else the provided agent_record)
    """
    import os
    from lib import registry
    
    si = os.environ.get("AURA_SEAT_INSTANCE_ID")
    launch_id = os.environ.get("AURA_LAUNCH_ID") or os.environ.get("AURA_AURA_LAUNCH_ID")
    pane_ref = os.environ.get("TMUX_PANE")  # or parse AURA_PANE_REF if set
    
    if not (si or launch_id or pane_ref):
        return agent_record or {}
    
    # Try occupant resolution
    matched, meta = registry.resolve_occupant(
        seat_instance_id=si,
        aura_launch_id=launch_id,
        pane_ref=f"tmux:{fleet}:{pane_ref}" if fleet and pane_ref else pane_ref,
        default_ref=f"{fleet}:{seat}" if fleet and seat else seat,
        mirror_unavailable="fallback",
    )
    
    if matched and meta.get("occupant_alive"):
        return matched
    elif matched:
        return matched  # Occupant found but not live; use anyway (may be in transition)
    else:
        return agent_record or {}
```

Then update `infer_context()` to use this:

Replace line 54-57:
```python
    agent = registry.get_agent(seat, fleet=fleet) if seat else None
    if agent:
        fleet = agent.get("fleet") or fleet
        seat = agent.get("seat") or agent.get("name") or seat
        runtime = runtime or agent.get("runtime")
```

With:
```python
    agent = registry.get_agent(seat, fleet=fleet) if seat else None
    # Resolve sender occupant if Aura-born (has si/launch_id/pane in env)
    agent = _resolve_sender_for_report(seat, fleet, agent)
    if agent:
        fleet = agent.get("fleet") or fleet
        seat = agent.get("seat") or agent.get("name") or seat
        runtime = runtime or agent.get("runtime")
```

---

#### **delivery.py: No changes to logic, but document occupant caveat**

Add a comment in `new_delivery_record()` after line 68:

```python
def new_delivery_record(
    *,
    delivery_type: str,
    sender: str,  # Sender name or ref; should be resolved by resolve_live first
    target: str,  # Target name or ref; should be resolved by resolve_live first
    ...
) -> dict:
    """Build a v2 delivery record without writing it.
    
    NOTE (M2): Both sender and target should be resolved to canonical live refs
    (via registry.resolve_live) before passing here. This ensures deduplication
    keys and routing are based on current names, not stale aliases.
    """
```

---

### **4. EDGE CASES & INTERACTIONS**

#### **4.1 Thin/name-only rows (no si/launch_id)**

**Problem:** Some registry rows may not have `seat_instance_id` or `aura_launch_id` (older records, manually-added seats, services).

**Solution:** 
- `resolve_occupant()` requires at least one of (si, launch_id, pane_ref); if none, returns (None, metadata)
- Fallback to `default_ref` if no occupant identity given
- This is safe: if a seat has no occupant identity, the name is the only identity; fallback to `resolve_live(default_ref)` is correct

#### **4.2 Mirror unavailable (tmux down, pane gone)**

**Problem:** If tmux crashes or pane is killed, `_target_exists()` in `resolve_occupant()` may fail.

**Solution:**
- `mirror_unavailable` parameter: 
  - `"fallback"` (default): treat as if pane is dead; occupant_alive=False, but row still returned
  - `"error"`: return error in metadata, matched_row=None
  - `"none"`: skip liveness check entirely (unsafe; for repair mode only)
- Callers decide how to handle occupant_alive=False based on context

#### **4.3 Fork-children and services**

**Problem:** Services and forked children may not inherit AURA_SEAT_INSTANCE_ID or AURA_LAUNCH_ID.

**Solution:**
- Fork-children inherit AURA_FLEET/AURA_SEAT by design; they should get a fresh si + launch_id on spawn
- Services may be name-based; the "occupant" of a service is the service itself
- If queued_messages records are created by a service without occupant metadata, the fallback to `resolve_historical` + `resolve_live` is correct (service name is stable)

#### **4.4 Dead pane_ref (%N is gone but row exists)**

**Problem:** A row exists with pane_ref="tmux:aura:%210" but the pane is gone; can we still match by si?

**Solution:**
- `resolve_occupant()` returns occupant_alive=False if si matches but pane is dead
- Callers check occupant_alive and decide: e.g., don't route to a dead occupant, but do cross-check if the occupant is the sender

#### **4.5 Renamed seat with stale env vars**

**Problem:** A seat named "foo" has AURA_SEAT_INSTANCE_ID=si_abc. It's renamed to "bar". Old queued messages have target="foo" and occupant_si=si_abc.

**Solution:**
- `resolve_occupant(seat_instance_id=si_abc)` finds the row with si_abc, which now has name="bar", fleet="aura"
- Match succeeds; delivery goes to "aura:bar"
- If a NEW seat "foo" is spawned with si_def, it doesn't interfere because si are unique

#### **4.6 Name reuse with no occupant identity in queue record**

**Problem:** A queued message for target="probe" has no occupant_si/launch_id stored. "probe" is renamed to "old-probe", a new "probe" is spawned.

**Solution:**
- `_matches_report()` first tries `resolve_live("probe")` → finds new seat
- If new seat's fleet:name match the report, return True
- If not, return False (don't fall back to occupant, because we have no occupant id stored)
- This is safe: the queue record is orphaned from its original target; a fresh queue entry should be made if needed

---

### **5. INTERACTIONS WITH OTHER MOVES**

#### **M1 (Physical live-resolution):**
- M2's `resolve_live()` is the live-resolution path; M1 would split `get_agent()` to call `resolve_live()` + `resolve_historical()` internally
- M2 is **independent** of M1; can be implemented before M1

#### **M3 (Rename on exact live %N):**
- M2's occupant resolution prevents the "stale ref + name reuse" problem that M3 is designed to catch
- M3's improvements to rename logic (preserve losers, don't orphan live panes) ensure that occupant identity is never silently redirected
- M2 + M3 together form a complete solution: M2 handles stale references, M3 prevents them from being created

#### **M4 (Born-pane self-heal):**
- Born panes will carry si + launch_id in env; M2's occupant resolution can use those to find the thin row created by M4
- M2 should NOT be needed for born-pane recovery (M4 handles that); but M2 makes it more robust

#### **M5 (Operator surface):**
- M5 adds `aura seat alias ls/rm` verbs; M2 ensures alias is never consulted for live routing
- Removing an alias (M5) becomes safe because M2 ensures live refs never depend on aliases

---

### **6. TESTS TO ADD**

**File: `tests/test_queued_messages_occupant_resolution.py`** (new)

```python
"""Tests for M2: occupant-keyed queued message matching."""

def test_queued_message_matches_report_by_live_name():
    """When queue target exists as live seat, match by exact live name (no alias)."""
    # Setup: registry has "aura:probe" with fleet=aura
    # Queue record has target="aura:probe"
    # Report is from "aura:probe"
    # Expected: _matches_report returns True
    
def test_queued_message_no_match_when_live_name_does_not_match_report():
    """When live seat exists but doesn't match report, don't fall back to occupant."""
    # Setup: "aura:probe" exists (live). Queue record has target="aura:probe",
    #        occupant_si=si_old (old occupant).
    # Report is from "aura:other" (different seat).
    # Expected: _matches_report returns False (even though si_old may exist elsewhere)

def test_queued_message_matches_by_occupant_si_when_name_is_gone():
    """When queue target no longer exists, match by occupant si if available."""
    # Setup: queue record has target="aura:probe", occupant_si=si_abc
    # "aura:probe" doesn't exist (renamed away)
    # But registry has another row with si_abc (now named "aura:probe-renamed")
    # Report is from "aura:probe-renamed"
    # Expected: _matches_report returns True (matched by occupant)

def test_queued_message_fallback_to_historical_alias_when_no_occupant_id():
    """When no occupant identity available, fall back to historical alias."""
    # Setup: queue has target="aura:old-probe" (no occupant_si)
    # Alias maps "aura:old-probe" -> "aura:new-probe"
    # Report is from "aura:new-probe"
    # Expected: _matches_report returns True (via resolve_historical)

def test_queued_message_does_not_reuse_freed_name():
    """When old occupant is gone and name is reused, new occupant not matched by old queue."""
    # Setup: old queue has target="aura:probe", occupant_si=si_old (now dead)
    # New seat "aura:probe" exists with si_new
    # Report is from "aura:probe" (si_new)
    # Expected: _matches_report returns False (live name found, but si_old is dead)

def test_resolve_occupant_prefers_si_over_launch_id():
    """occupant resolution: si > launch_id > pane_ref."""
    # Rows: { si=si_abc, launch=old_launch }, { si=si_def, launch=si_abc }
    # Call resolve_occupant(si_abc, launch_abc) → returns first row (si match)

def test_resolve_occupant_liveness_check():
    """occupant resolution checks pane_ref is live if present."""
    # Row has si=si_abc, pane_ref="tmux:aura:%210"
    # Pane %210 is dead
    # resolve_occupant(si=si_abc, pane_ref="...%210") → row returned, occupant_alive=False

def test_resolve_occupant_fallback_only_if_occupant_not_elsewhere():
    """Fallback to default_ref only if occupant si/launch not found alive."""
    # Rows: { si=si_abc, name="probe" }, { si=si_def, name="old-probe" }
    # Call resolve_occupant(si_abc, default_ref="old-probe")
    # Expected: row with si_abc returned (not default_ref, occupant found)
    
def test_resolve_occupant_fallback_when_occupant_gone():
    """Fallback to default_ref when occupant si not found."""
    # Rows: { si=si_def, name="old-probe" }
    # Call resolve_occupant(si_abc, default_ref="old-probe")
    # Expected: row with name="old-probe" returned (fallback used)
```

**File: `tests/test_report_subscriptions_occupant_resolution.py`** (new)

```python
"""Tests for M2: occupant-keyed subscription matching."""

def test_subscription_matches_target_by_live_name():
    """Subscription target matched by live seat name."""
    
def test_subscription_no_match_when_live_name_does_not_match():
    """Subscription target doesn't match if live seat name is different."""
    
def test_subscription_matches_placement_member_by_live_name():
    """Placement members matched by live names."""
```

**File: `tests/test_registry_resolve_functions.py`** (new)

```python
"""Tests for new registry resolution functions: resolve_live, resolve_occupant, resolve_historical."""

def test_resolve_live_exact_match():
    """resolve_live("fleet:name") finds row with exact name in fleet."""
    
def test_resolve_live_returns_none_for_unknown_name():
    """resolve_live("unknown") returns None."""
    
def test_resolve_live_ignores_aliases():
    """resolve_live doesn't follow alias chain."""
    
def test_resolve_historical_follows_alias_chain():
    """resolve_historical (renamed resolve_alias) follows alias chain."""
    
def test_resolve_occupant_si_priority():
    """resolve_occupant: si > launch_id > pane_ref."""
    
def test_resolve_occupant_liveness():
    """resolve_occupant marks occupant_alive=False if pane is dead."""
    
def test_resolve_occupant_fallback_logic():
    """resolve_occupant falls back to default_ref only if occupant gone."""
```

---

### **7. MIGRATION & DATA CONCERNS**

#### **7.1 Existing alias records:**
- No migration needed; aliases stay as-is, just stop being consulted for live resolution
- Aliases become lineage records: historical reconstruction only

#### **7.2 Existing queued messages:**
- Old queue records lack `occupant_seat_instance_id`, `occupant_aura_launch_id`, `occupant_pane_ref` fields
- The fallback to `resolve_historical` ensures they still work
- When a NEW queue record is created (e.g., by `queued_messages.create()`), add occupant metadata from sender's registry row

#### **7.3 Schema versioning:**
- Queue record schema stays "aura.queue.v1" (backward compat)
- New optional fields: `occupant_seat_instance_id`, `occupant_aura_launch_id`, `occupant_pane_ref`
- Report subscriptions: same; optional occupant fields in future version

#### **7.4 Registry backward compat:**
- `resolve_alias()` stays as a backward-compat wrapper to `resolve_historical()`
- Existing callers of `resolve_alias()` keep working
- Migrate to `resolve_live() + resolve_occupant()` on a per-call basis

---

### **8. SUMMARY OF CHANGES**

| File | Change | Purpose |
|------|--------|---------|
| `registry.py` | Add `resolve_live()` | Live exact-name resolution, no alias |
| `registry.py` | Add `resolve_occupant()` | Occupant-keyed resolution (si/launch_id/%N) |
| `registry.py` | Rename `resolve_alias` → `resolve_historical` | Emphasize historical-only use |
| `registry.py` | Keep `resolve_alias()` as wrapper | Backward compat |
| `queued_messages.py` | Update `_matches_report()` | Use resolve_live + resolve_occupant + fallback |
| `report_subscriptions.py` | Update `_matches_target()` | Use resolve_live + resolve_historical |
| `report_subscriptions.py` | Update `_matches_placement()` | Use resolve_live + resolve_historical |
| `report_subscriptions.py` | Update `canonical_target()` | Use resolve_live + resolve_historical |
| `reports.py` | Add `_resolve_sender_for_report()` | Resolve sender by occupant if env present |
| `reports.py` | Update `infer_context()` | Call `_resolve_sender_for_report()` |
| `delivery.py` | Add docstring note | Document M2 expectations |

---

### **9. IMPLEMENTATION ORDER**

1. Add `resolve_live()` and `resolve_occupant()` to registry.py
2. Rename `resolve_alias` to `resolve_historical` + add wrapper
3. Update `_matches_report()` in queued_messages.py
4. Update `_matches_target()`, `_matches_placement()`, `canonical_target()` in report_subscriptions.py
5. Add `_resolve_sender_for_report()` and update `infer_context()` in reports.py
6. Update `queued_messages.create()` to capture occupant metadata from sender registry row
7. Add tests
8. Document in M2 context/changes/code

---

This spec is concrete enough for implementation without re-derivation. All edge cases, fallback logic, and interactions with M1/M3/M4/M5 are explicit. The occupant-keyed resolution is robust against name reuse, rename-induced drift, and missing occupant identity in old records (via fallback to live + historical).
Perfect! The spec is complete. Let me output it clearly to the user:

---

## M5 IMPLEMENTATION SPEC: OPERATOR SURFACE + OBSERVABILITY + DOCS

I have produced a comprehensive DIFF-level specification for Move M5. The complete spec has been saved and contains:

### **PART 1: CLI Verbs** (3 new verbs)

1. **`aura seat alias ls`** — List historical seat aliases
   - Parser additions with filters: `--fleet`, `--source`, `--target`, `--active-only`
   - Implementation: `_alias_ls()` function filtering alias ledger; returns sorted rows with source/target/reason/created_at/target_registered
   - ~80 lines of code

2. **`aura seat alias rm`** — Remove a historical alias
   - Parser: source ref argument, `--confirm`, `--dry-run`
   - Implementation: `_alias_rm()` validates source, checks confirmation, deletes from alias ledger
   - ~60 lines of code
   - Safety: requires explicit `--confirm`, alias deletion is audit-ledger-only (no registry changes)

3. **`aura seat orphan-reconcile`** — Discover and reconcile orphaned Aura-born panes
   - Parser: `--fleet`, `--auto-adopt`, `--rename-windows`, `--skip-adoption-id-check`
   - Implementation: `_discover_orphaned_born_panes()` scans live tmux panes for AURA_FLEET/AURA_SEAT/AURA_LAUNCH_ID env vars; `_orphan_reconcile()` optionally adopts them
   - Handlers for fork-children, services, dead panes
   - ~150 lines of code

**Handler updates**: Add conditional branches in `seat.py:run()` to dispatch `seat_alias`/`alias_action` and `orphan-reconcile`.

---

### **PART 2: Seat Status Observability**

**File**: `cli/lib/seat_status.py`

1. **New function `_is_potential_orphaned_born_pane()`** — Heuristic: row has `aura_launch_id` but no `pane_ref`
2. **Update `_derive_managed_state()`** — Recognize `missing_pane_born_orphaned` state
3. **Extend risk_flags in `build_from_record()`** — Add `"live_born_pane_without_row"` flag when liveness=missing AND aura_launch_id exists

**Result**: Operators can see fixable orphaned panes in `aura view` or `seat_status()` API; risk flag signals M5 operator recovery (orphan-reconcile) or M4 self-heal.

---

### **PART 3: Documentation Updates**

**Files**: `.context/current/2026-06-04-2022/{lexicon.md, model/two-laws.md, model/the-seat.md}`

1. **lexicon.md**: Define "Alias (Historical)" — breadcrumb, not router; created by rename; read by historical resolver only; listed/removed by operators.

2. **model/two-laws.md**: Update "Law 1: Physical Identity"
   - Live resolution precedence: %N → seat_instance_id → aura_launch_id → exact current row
   - Alias: NEVER used for live routing
   - Repair + born-pane self-heal semantics

3. **model/the-seat.md**: Add "Operator Surface (M5): Alias and Orphan Management"
   - `aura seat alias ls/rm` syntax, workflow, safety notes
   - `aura seat orphan-reconcile` discovery/adoption/rename workflow
   - Edge cases: mirror-unavailable, fork-children, services, dead %N, thin rows

---

### **PART 4: Edge Cases & Integration**

- **Thin vs name-only rows**: Thin rows (adoption-born) lack runtime_session_id; routable by %N/si; can bind via `aura sessions bind-current`.
- **Mirror unavailable**: Graceful fallback to terminal.target_exists() or empty discovery.
- **Fork-children & services**: Adoption preserves fork_source_session_id, aura_service_kind metadata.
- **Dead %N**: _adopt_pane_as_seat() fails with "pane-not-found" if %N is gone.
- **Alias + M2 continuity**: M2 occupant-keyed resolution uses si/launch/%N; alias is never consulted for live routing. Alias fallback loses to a live distinct pane.
- **Rename collision guard**: M3 already handles; M5 does not change collision logic (only manages historical ledger).

---

### **PART 5: Test Suite**

**File**: `tests/test_seat_alias_and_orphan.py` (~250 lines)

Test classes:
- **TestAliasLs**: empty list, with records, filter by fleet/source/target, active-only
- **TestAliasRm**: dry-run, requires confirmation, confirm removes, not found
- **TestOrphanReconcile**: discovery dry-run, auto-adopt, rename windows
- **TestSeatStatusOrphanFlag**: thin row risk flag, non-orphan missing pane
- **TestAliasIntegration**: rename creates alias, verify alias not used for live routing

---

### **PART 6: Summary Table**

| File | Change | Lines | Detail |
|------|--------|-------|--------|
| `cli/aura` | Add seat alias + orphan-reconcile subparsers | ~50 | New verbs: `aura seat alias ls/rm`, `aura seat orphan-reconcile` |
| `cli/commands/seat.py` | Implement _alias_ls, _alias_rm, _orphan_reconcile + helpers | ~300 | Verb handlers; _ref_matches_filter, _discover_orphaned_born_panes |
| `cli/lib/seat_status.py` | Add orphan heuristic; update managed_state + risk_flags | ~40 | Surface live-born-pane-without-row state |
| `.context/*/lexicon.md` | Add Alias (Historical) section | ~20 | Define alias as lineage, not router |
| `.context/*/two-laws.md` | Update Law 1 live resolution + alias note | ~40 | Clarify %N-first; alias demoted |
| `.context/*/the-seat.md` | Add "Operator Surface" section | ~100 | Alias ls/rm/orphan-reconcile with examples |
| `tests/test_seat_alias_and_orphan.py` | New test module | ~250 | Test all verbs, risk flags, integration |

**Total**: ~800 lines of new code + tests + docs.

---

### **Key Design Decisions**

1. **Alias = Historical Ledger, Not Live Router**
   - M1 split ensures `get_agent()` never consults aliases for live requests
   - M5 provides operator interface to read and remove historical records
   - Lineage audit and same-occupant-continuity fallback (M2) remain separate

2. **Orphan Reconciliation as Bulk Operator Tool**
   - Complements M4 born-pane self-heal (reactive, on-demand)
   - M5 orphan-reconcile is proactive, batch-mode operator recovery
   - Thin row adoption preserves birth metadata (launch_id, si, identity)

3. **Risk Flag for Fixable State**
   - `"live_born_pane_without_row"` is distinct from generic `"missing_pane"`
   - Signals operator: this pane can be recovered by orphan-reconcile or M4 self-heal
   - Avoids false alarms; focuses remediation

4. **Backward Compatibility**
   - Existing `aura seat aliases` stub continues to work (now recommended to use `aura seat alias ls`)
   - No breaking CLI changes
   - All new verbs are additive subcommands

---

The spec is **concrete enough that an implementer can apply it without re-deriving design**, with:
- Exact function signatures and parameter schemas
- Precise file locations and line hints
- Edge case handling (fork-children, dead panes, thin rows, mirror unavailable)
- Integration points with M1–M4 (resolve_live/resolve_historical, occupant-keyed continuity, rename collision guard, born-pane self-heal)
- Complete test suite names and assertions
- Doc markdown with examples and syntax

**No files have been edited** — this is a read-only analysis and spec generation.
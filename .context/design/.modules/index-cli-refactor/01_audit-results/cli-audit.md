# IMEM CLI Architecture Audit
**Date:** 2025-10-29  
**Project:** /home/axp/projects/fleet/hangar/code/aura/main  
**File:** imem/src/imem/cli.py (1167 lines)

---

## 1. COMMAND STRUCTURE OVERVIEW

### Current Pattern: MIXED (Noun-Verb Groups + Verb-First)

The CLI exhibits **inconsistent command patterns**:

| Command | Pattern | Type | Location |
|---------|---------|------|----------|
| `imem develop search` | Noun-Verb-Group | Phase-based | cli.py:41-89 |
| `imem conversations search` | Noun-Verb-Group | Source-based | cli.py:92-142 |
| `imem compose` | Verb-First | Composition | cli.py:215-285 |
| `imem init` | Verb-First | Setup | cli.py:288-440 |
| `imem search` | Verb-First | Main search | cli.py:443-586 |
| `imem update` | Verb-First | Incremental | cli.py:589-604 |
| `imem dedupe` | Verb-First | Maintenance | cli.py:607-669 |
| `imem status` | Verb-First | Status | cli.py:672-704 |
| `imem service start/stop/status` | Verb-First + Subgroup | Service | cli.py:707-773 |
| `imem index-conversation` | Verb-Noun-Hyphenated | Indexing | cli.py:877-1004 |
| `imem index-all-conversations` | Verb-Noun-Hyphenated | Batch Indexing | cli.py:1007-1162 |

---

## 2. CLICK DECORATORS & GROUP STRUCTURE

### Click Groups (@click.group)

```python
@click.group()
def imem():                          # cli.py:31-34 (ROOT GROUP)
    """IMEM - Vector search for institutional memory"""
    
@imem.group()
def develop():                       # cli.py:41-44 (PHASE GROUP)
    """Search develop phase (what we built)"""
    
@imem.group()
def conversations():                 # cli.py:92-95 (SOURCE GROUP)
    """Search conversations (how we got there)"""
    
@imem.group()
def service():                       # cli.py:707-710 (SERVICE GROUP)
    """Manage the global Qdrant service"""
```

### Click Commands (@click.command)

**Under `develop` group:**
- `develop.command(name='search')` → cli.py:47-89

**Under `conversations` group:**
- `conversations.command(name='search')` → cli.py:98-142

**Under `service` group:**
- `service.command()` → cli.py:713-734 (start)
- `service.command()` → cli.py:737-749 (stop)
- `service.command(name='status')` → cli.py:752-773 (status)

**Direct under `imem` root:**
- `@imem.command()` for: compose, init, search, update, dedupe, status
- `@imem.command()` for: index-conversation, index-all-conversations

---

## 3. COMMAND CATALOG WITH SIGNATURES

### Phase-Based Search Commands

#### `imem develop search <query>`
**Location:** cli.py:47-89  
**Decorator:** `@develop.command(name='search')`  
**Parameters:**
```python
def develop_search(query, decisions, constraints, failures, patterns, 
                   implementation, pattern, impl, limit, after):
```
**Options:**
- `--decisions` (flag) → Filter section_type='Decisions'
- `--constraints` (flag) → Filter section_type='Constraints'
- `--failures` (flag) → Filter section_type='Failures'
- `--patterns` (flag) → Filter section_type='Patterns'
- `--implementation` (flag) → Filter section_type='Implementation'
- `--pattern` (flag) → Filter layer='pattern'
- `--impl` (flag) → Filter layer='implementation'
- `--limit` (int, default=5)
- `--after` (date, YYYY-MM-DD)

**Helper:** Uses `_execute_search(query, filters, limit, after)` → cli.py:145-212

#### `imem conversations search <query>`
**Location:** cli.py:98-142  
**Decorator:** `@conversations.command(name='search')`  
**Parameters:**
```python
def conversations_search(query, limit, after, session, messages_only, 
                         patches_only, user_only, assistant_only, file):
```
**Options:**
- `--limit` (int, default=5)
- `--after` (date, YYYY-MM-DD)
- `--session` (str) → Filter session_id
- `--messages-only` (flag) → Filter chunk_type='message'
- `--patches-only` (flag) → Filter chunk_type='patch'
- `--user-only` (flag) → Filter chunk_type='message', role='user'
- `--assistant-only` (flag) → Filter chunk_type='message', role='assistant'
- `--file` (str) → Filter patches by file_path

**Helper:** Uses `_execute_search(query, filters, limit, after)` → cli.py:145-212

### Main Search Command

#### `imem search <query> [<query> ...]`
**Location:** cli.py:443-586  
**Decorator:** `@imem.command()`  
**Parameters:**
```python
def search(query, limit, sort_by, show_metadata, after, split_terms, 
           operator, phase_filter, layer, section, session):
```
**Options:**
- `--limit` (int, default=5)
- `--sort-by` (choice: similarity|date|hybrid, default=similarity)
- `--show-metadata` (flag)
- `--after` (date, YYYY-MM-DD)
- `--split-terms` (flag) → Enable multi-term search
- `--operator` (choice: AND|OR, default=AND)
- `--in` (choice: develop|designate|document|conversations|all, default=develop)
- `--layer` (choice: implementation|pattern|both, default=implementation)
- `--section` (str) → Filter by section type (e.g., "Decisions")
- `--session` (str) → Filter by conversation session

---

## 4. INDEXING COMMANDS

### Conversation Indexing (Single)

#### `imem index-conversation <conversation_id>`
**Location:** cli.py:877-1004  
**Decorator:** `@imem.command()`  
**Parameters:**
```python
def index_conversation(conversation_id, collection):
```
**Arguments:**
- `<conversation_id>` → Session ID (full/partial) or path to JSONL
- `--collection` (default='institutional_memory')

**Process:**
1. Determine input: Session ID or JSONL path → cli.py:918-944
2. Find conversation file using ConversationFinder
3. Export to structured markdown → cli.py:948-975
4. Ingest with chunking → cli.py:987-993
5. Store in Qdrant

**Issue:** Uses hardcoded global collection `institutional_memory` (should be per-project)

### Batch Conversation Indexing

#### `imem index-all-conversations`
**Location:** cli.py:1007-1162  
**Decorator:** `@imem.command()`  
**Parameters:**
```python
def index_all_conversations(limit, recent, min_size, collection, dry_run):
```
**Options:**
- `--limit` (int) → Process only first N
- `--recent` (int) → Process only N most recent
- `--min-size` (int, default=2) → Skip < N KB
- `--collection` (default='institutional_memory')
- `--dry-run` (flag)

**Process:**
1. Find all conversations → cli.py:1052-1053
2. Filter by size → cli.py:1056-1063
3. Apply limit/recent filters → cli.py:1069-1072
4. For each conversation:
   - Export to markdown → cli.py:1110-1119
   - Prepare metadata → cli.py:1127-1133
   - Ingest using `EnhancedModularIngest.ingest_conversation_chunked()` → cli.py:1136-1141

**Issue:** Same hardcoded global collection problem + no per-project separation

### Project Initialization & Full Indexing

#### `imem init [--force] [--vscode] [--include-design]`
**Location:** cli.py:288-440  
**Decorator:** `@imem.command()`  
**Parameters:**
```python
def init(force, vscode, include_design):
```
**Options:**
- `--force` (flag) → Re-index from scratch
- `--vscode` (flag) → Setup VS Code integration
- `--include-design` (flag) → Include design phase (default excluded)

**Process:**
1. Ensure Qdrant running → cli.py:313-316
2. Get project root → cli.py:319-324
3. Detect .context folder structure → cli.py:327-343
4. Register project → cli.py:354-357
5. Create collection with E5-Large-v2 config → cli.py:373-396
6. Index phases: develop, designate, document (+ design if flag) → cli.py:406-430
7. Update registry with doc count → cli.py:432
8. Setup VS Code if requested → cli.py:437-438

**Key:** Indexes **only changelogs**, not conversations

### Incremental Re-indexing

#### `imem update`
**Location:** cli.py:589-604  
**Decorator:** `@imem.command()`  
**Parameters:** None (uses context.invoke)  
**Function:** Delegates to `init(force=False, vscode=False)`

---

## 5. PHASE INDEXING IMPLEMENTATION

### Where Phase Indexing Happens

**In `imem init` → cli.py:401-430:**
```python
indexed_phases = ['develop', 'designate', 'document']
if include_design:
    indexed_phases.append('design')

for phase in indexed_phases:
    phase_dir = context_root / phase
    if not phase_dir.exists():
        continue
    
    md_files = list(phase_dir.rglob("*.md"))
    
    for md_file in md_files:
        ingester.ingest_markdown_chunked(
            md_file,
            phase=phase,
            collection_name=collection_name
        )
```

### IngestModularIngest Methods for Phase Indexing

**Location:** imem/src/imem/ingest.py

#### `ingest_markdown_chunked(file_path, phase, collection_name)`
**Location:** ingest.py:626-787  
**Purpose:** Index individual markdown files with section-level chunking

**Key Responsibilities:**
1. Auto-detect phase from path if not provided → ingest.py:635-636
2. Detect layer (implementation/pattern) → ingest.py:639, 611-624
3. Parse with LlamaIndex (section-level) → ingest.py:658
4. Build rich metadata:
   - `source`: 'changelog'
   - `phase`: 'develop'|'design'|'designate'|'document'
   - `layer`: 'implementation'|'pattern'
   - `section_type`: H2 parent (e.g., "Decisions")
   - `section_name`: H3 title
   - `header_path`: Full path for debugging
   - Structured field flags: `has_context`, `has_solution`, `has_rationale`, etc.

5. Filter H3+ sections only (skip H1/H2 noise) → ingest.py:699-701
6. Batch encode with E5-Large-v2 → ingest.py:670
7. Upsert to Qdrant → ingest.py:773-776

#### `_extract_phase(file_path)` 
**Location:** ingest.py:585-598  
**Purpose:** Auto-detect phase from file path

```python
'/design/' → 'design'
'/designate/' → 'designate'
'/develop/' → 'develop'
'/document/' → 'document'
else → 'unknown'
```

#### `_detect_layer(file_path, phase)`
**Location:** ingest.py:611-624  
**Purpose:** Detect implementation vs pattern layer

- Only develop phase has pattern layers
- Check `.pattern.md` in filename → 'pattern', else 'implementation'

---

## 6. CONVERSATION INDEXING IMPLEMENTATION

### Where Conversation Indexing Happens

**Two separate commands:**
1. `imem index-conversation <id>` → cli.py:877-1004 (single)
2. `imem index-all-conversations` → cli.py:1007-1162 (batch)

### EnhancedModularIngest Methods for Conversations

#### `ingest_conversation_chunked(markdown_path, session_id, metadata, collection_name)`
**Location:** ingest.py:823-907  
**Purpose:** Index conversations with H2-level chunking

**Key Responsibilities:**
1. Parse TRACE-formatted markdown → ingest.py:840-845
2. Parse H2 section headers to extract metadata:
   - Message sections: Extract role (user|assistant) → ingest.py:789-821
   - Code patch sections: Extract file_path → ingest.py:789-821
3. Batch encode with E5-Large-v2 → ingest.py:857
4. Build rich metadata:
   - `source`: 'conversation'
   - `session_id`: UUID
   - `section_type`: "Message 1: USER", "Code Patch 1: src/cli.py"
   - `chunk_type`: 'message'|'patch'
   - `role`: 'user'|'assistant' (for messages)
   - `file_path`: Path (for patches)
   - Metadata: start_time, duration_minutes, message_count, has_changelog, changelog_path

5. Upsert to Qdrant → ingest.py:901-904

#### `parse_conversation_section(section_name)`
**Location:** ingest.py:789-821  
**Purpose:** Parse TRACE H2 headers into structured metadata

**Returns:**
```python
"Message 1: USER" → {'chunk_type': 'message', 'role': 'user'}
"Message 2: ASSISTANT" → {'chunk_type': 'message', 'role': 'assistant'}
"Code Patch 1: src/cli.py" → {'chunk_type': 'patch', 'file_path': 'src/cli.py'}
```

---

## 7. HELPER FUNCTIONS FOR INDEXING

### In cli.py

#### `_execute_search(query, filters, limit, after_date)`
**Location:** cli.py:145-212  
**Purpose:** Shared search execution logic for phase and conversation searches

**Process:**
1. Ensure Qdrant running
2. Get project info from registry
3. Create EnhancedQdrantSearch instance
4. Execute search with filters
5. Format and display results

**Note:** Used by both `develop search` and `conversations search`

#### `setup_vscode_integration(project_root)`
**Location:** cli.py:776-875  
**Purpose:** Configure VS Code settings and install IMEM Auto-Sync extension

**Tasks:**
1. Create/update `.vscode/settings.json`
2. Set IMEM configuration (autoSync, syncOnSave, changelogPath)
3. Auto-install VS Code extension from bundled .vsix
4. Print setup instructions

### In ingest.py

#### `_extract_frontmatter(content)`
**Location:** ingest.py:600-609  
**Purpose:** Extract YAML frontmatter from markdown

#### `get_existing_file_paths(collection_name)`
**Location:** ingest.py:68-107  
**Purpose:** Get set of already-indexed file paths for incremental ingestion

#### `get_existing_content_hashes(collection_name)`
**Location:** ingest.py:109-156  
**Purpose:** Get MD5 hash mapping for content-based deduplication

#### `update_file_path(collection_name, point_id, new_file_path)`
**Location:** ingest.py:158-216  
**Purpose:** Update file_path when same content found at new location (avoids duplication)

#### `deduplicate_collection(collection_name, dry_run)`
**Location:** ingest.py:218-332  
**Purpose:** Remove duplicate content based on file hashes

---

## 8. IDENTIFIED INCONSISTENCIES & ISSUES

### 1. **Inconsistent Command Patterns**

| Pattern | Commands | Issue |
|---------|----------|-------|
| Noun-Verb Group | `imem develop search`, `imem conversations search` | Backwards English, hard to extend |
| Verb-First | `imem init`, `imem search`, `imem compose` | Natural but inconsistent with groups |
| Verb-Noun Hyphenated | `imem index-conversation`, `imem index-all-conversations` | Mixed with groups above |

**Impact:** Users don't know which syntax to use; documentation confusing; hard to extend

### 2. **Global Collection Hardcoding**

**Problem:** Conversation indexing uses hardcoded `'institutional_memory'` collection:
- cli.py:879 (default parameter)
- cli.py:1011 (default parameter)
- Never created with proper E5-Large-v2 vector schema

**Impact:**
- All projects share same global conversation collection
- No project isolation
- Collection may not exist or have wrong schema (the actual bug)
- Registry doesn't track conversation collections

### 3. **Missing Registry Tracking**

**Current registry (registry.py:36-46):**
```python
self.data["projects"][project_key] = {
    "collection": collection_name,           # SINGLE collection name
    "indexed_at": datetime.now().isoformat(),
    "doc_count": 0
}
```

**Problem:** Only tracks ONE collection per project
- Should track: `changelog` and `conversation` separately
- Currently: Can't tell which collection stores what

### 4. **No Per-Project Conversation Separation**

**Current behavior:**
- All projects' conversations go to global `institutional_memory`
- No way to search conversations for specific project
- No way to delete project's conversations without affecting others

### 5. **Duplication of Search Logic**

**Three separate search entry points:**
1. `imem develop search` → cli.py:47-89
2. `imem conversations search` → cli.py:98-142
3. `imem search` → cli.py:443-586

**All three use `_execute_search()` helper, but:**
- Develop/conversations versions very limited (no sort, no multi-term)
- Main search version has more features
- Code duplication for filter building

### 6. **Inconsistent Collection Naming**

- Changelog: `imem_{hash}` (8-char hash)
- Conversation: `institutional_memory` (hardcoded global)

**Should be:**
- Changelog: `imem_{hash}_changelog`
- Conversation: `imem_{hash}_conversation`

### 7. **Metadata Metadata Confusion**

Conversation metadata has two sources:
1. **Stored in Qdrant (payload):** chunk_type, role, file_path, session_id, etc.
2. **Passed at ingestion time (metadata dict):** start_time, duration_minutes, message_count, has_changelog

These aren't always synchronized properly.

### 8. **Phase Filter Inconsistency**

**In main `imem search`:**
- Supports 5 values: develop, designate, document, conversations, all
- But `designate` is never actually indexed by default (only created in init as option)

**In phase-based searches:**
- `develop` has its own search command
- `conversations` has its own search command
- But `designate` and `document` don't have dedicated commands

### 9. **No Design Phase by Default**

**In `imem init`:**
- Design phase EXCLUDED by default
- Requires `--include-design` flag
- But other phases indexed unconditionally
- No explanation in CLI help why design is special

---

## 9. CURRENT COMMAND TREE (ASCII)

```
imem (root @click.group())
├── develop (@imem.group())
│   └── search (noun-verb)
├── conversations (@imem.group())
│   └── search (noun-verb)
├── service (@imem.group())
│   ├── start (verb-first)
│   ├── stop (verb-first)
│   └── status (verb-first)
├── compose (verb-first, complex config)
├── init (verb-first, full project setup)
├── search (verb-first, main search)
├── update (verb-first, incremental)
├── dedupe (verb-first, maintenance)
├── status (verb-first, project status)
├── index-conversation (verb-noun, single)
└── index-all-conversations (verb-noun, batch)
```

**Problems visible:**
- 3 different patterns at root level
- develop/conversations feel like first-class phases, but design/document don't
- index-* commands don't fit pattern
- No `imem index develop` parallel to `imem search develop`

---

## 10. RECOMMENDED REFACTOR PATTERN

### Target State (Verb-Noun, Consistent)

```
imem (root)
├── index
│   ├── develop [--force]
│   ├── design [--force]
│   ├── document [--force]
│   ├── conversations [--limit] [--recent] [--min-size]
│   └── context [--force] [--include-design]  # Convenience: all phases
├── search
│   ├── <query> [options]  # Default: develop
│   └── --in [develop|design|document|conversations|context]
├── service
│   ├── start
│   ├── stop
│   └── status
├── compose (complex, keep as-is)
├── update (convenience)
├── dedupe (maintenance)
└── status (project status)
```

**Key improvements:**
- ✅ Consistent verb-noun at all levels
- ✅ Discoverable: `imem index` lists all phases
- ✅ Extensible: Easy to add new phases or sources
- ✅ Per-project: Separate collections by data type
- ✅ Backwards compatible: `imem search` still works

---

## 11. SUMMARY TABLE: FILE LOCATIONS & LINE NUMBERS

| Artifact | Location | Lines |
|----------|----------|-------|
| Root group | cli.py | 31-34 |
| develop group | cli.py | 41-44 |
| develop search | cli.py | 47-89 |
| conversations group | cli.py | 92-95 |
| conversations search | cli.py | 98-142 |
| _execute_search helper | cli.py | 145-212 |
| compose command | cli.py | 215-285 |
| init command | cli.py | 288-440 |
| main search command | cli.py | 443-586 |
| update command | cli.py | 589-604 |
| dedupe command | cli.py | 607-669 |
| status command | cli.py | 672-704 |
| service group | cli.py | 707-710 |
| service.start | cli.py | 713-734 |
| service.stop | cli.py | 737-749 |
| service.status | cli.py | 752-773 |
| setup_vscode_integration | cli.py | 776-875 |
| index-conversation | cli.py | 877-1004 |
| index-all-conversations | cli.py | 1007-1162 |
| EnhancedModularIngest.__init__ | ingest.py | 37-66 |
| ingest_markdown_chunked | ingest.py | 626-787 |
| _extract_phase | ingest.py | 585-598 |
| _detect_layer | ingest.py | 611-624 |
| parse_conversation_section | ingest.py | 789-821 |
| ingest_conversation_chunked | ingest.py | 823-907 |
| get_existing_file_paths | ingest.py | 68-107 |
| get_existing_content_hashes | ingest.py | 109-156 |
| update_file_path | ingest.py | 158-216 |
| deduplicate_collection | ingest.py | 218-332 |
| SimpleRegistry.register_project | registry.py | 36-46 |
| SimpleRegistry.get_project_info | registry.py | 53-55 |
| EnhancedQdrantSearch.search | enhanced.py | 95-212 |

---

## 12. KEY FINDINGS

### What Works
- ✅ Basic search across phases (develop, conversations)
- ✅ Phase-aware metadata (section_type, layer)
- ✅ Section-level chunking with LlamaIndex
- ✅ E5-Large-v2 embeddings
- ✅ Batch ingestion with deduplication
- ✅ Incremental updates
- ✅ Compositional retrieval (`imem compose`)

### What's Broken
- ❌ Conversation indexing (wrong global collection)
- ❌ No per-project conversation isolation
- ❌ Inconsistent CLI command patterns
- ❌ Registry doesn't track multiple collections
- ❌ Design phase excluded by default with no explanation

### What Needs Refactor
- **Priority 1 (Phase 1):** CLI consistency (verb-noun)
- **Priority 2 (Phase 1):** Collection architecture (separate changelog/conversation per project)
- **Priority 3 (Phase 2):** Graph intelligence layer (topology detection)
- **Priority 4 (Phase 3):** BRAIN persistence (months away)

---

## 13. IMPLEMENTATION ROADMAP (From Design Doc)

### Phase 1: CLI Refactor + Conversation Indexing (~2-3 hours)

1. **Extract `_index_phase(phase_name, force)` helper** (~30 min)
2. **Refactor CLI to verb-noun** (~1 hour)
   - New commands: `imem index develop|design|document|conversations|context`
   - New search: `imem search [develop|design|...]`
   - Remove: `index-conversation`, `index-all-conversations`, noun-verb groups
3. **Fix collection architecture** (~30 min)
   - Create: `{project}_changelog` and `{project}_conversation` collections
   - Update registry to track both
4. **Test conversation indexing** (~30 min)
   - Verify metadata includes chunk_type, role, file_path

### Phase 2: Graph Intelligence Layer (~3-4 hours, NEXT SESSION)

1. **Build graph from chunks** (topology detection)
2. **Enrich metadata** (position, confidence)
3. **Adapt templates** (different renderings per topology)

### Phase 3: BRAIN Persistence (~2-3 hours, MONTHS LATER)

1. Requires 3-6 months usage data
2. Don't build yet

---

## 14. CHECKLIST FOR REFACTOR SUCCESS

- [ ] Verb-noun pattern applied at all CLI levels
- [ ] `imem index <source>` works for: develop, design, document, conversations, context
- [ ] `imem search [source] <query>` consistent interface
- [ ] Two collections per project: `{hash}_changelog`, `{hash}_conversation`
- [ ] Registry tracks both collections
- [ ] Conversation indexing creates proper per-project collection
- [ ] All metadata properly enriched (chunk_type, role, file_path, phase, layer)
- [ ] `imem compose` still works (no breaking changes)
- [ ] Old commands removed
- [ ] No redundant search implementations

---

## References

**Design Document:** `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/.modules/flex-graph/index-cli-refactor/251029-1437.md`

**Architecture Docs:**
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/document/architecture_imem-i2.md`
- `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/.modules/flex-graph/02_current/imem-architecture.md`


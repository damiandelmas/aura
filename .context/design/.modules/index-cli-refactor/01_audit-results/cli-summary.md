# IMEM CLI Structure - Quick Reference

**Complete audit available:** `/home/axp/projects/fleet/hangar/code/aura/main/.context/design/.modules/flex-graph/index-cli-refactor/cli-audit.md`

---

## Problem Statement

**Current State:** Mixed command patterns (noun-verb groups + verb-first + verb-noun-hyphenated)
- `imem develop search` (noun-verb group)
- `imem init` (verb-first)
- `imem index-conversation` (verb-noun-hyphenated)

**Blocker:** Conversation indexing broken due to hardcoded global collection + inconsistent CLI

**Solution:** Refactor to consistent verb-noun pattern with proper per-project collection architecture

---

## Command Patterns (CURRENT)

| Pattern | Examples | Issue |
|---------|----------|-------|
| **Noun-Verb Groups** | `imem develop search`, `imem conversations search` | Backwards English, hard to extend |
| **Verb-First** | `imem init`, `imem search`, `imem compose` | Natural but inconsistent |
| **Verb-Noun-Hyphenated** | `imem index-conversation`, `imem index-all-conversations` | Mixed with groups |

---

## Key Commands at a Glance

### Search Commands
| Command | Location | Purpose | Pattern |
|---------|----------|---------|---------|
| `imem develop search <query>` | cli.py:47-89 | Search develop phase | noun-verb |
| `imem conversations search <query>` | cli.py:98-142 | Search conversations | noun-verb |
| `imem search <query>` | cli.py:443-586 | Main search (most features) | verb-first |

### Index Commands
| Command | Location | Purpose | Pattern |
|---------|----------|---------|---------|
| `imem init` | cli.py:288-440 | Full project setup | verb-first |
| `imem index-conversation` | cli.py:877-1004 | Single conversation | verb-noun |
| `imem index-all-conversations` | cli.py:1007-1162 | Batch conversations | verb-noun |
| `imem update` | cli.py:589-604 | Incremental re-index | verb-first |

### Maintenance Commands
| Command | Location | Purpose | Pattern |
|---------|----------|---------|---------|
| `imem dedupe` | cli.py:607-669 | Remove duplicates | verb-first |
| `imem status` | cli.py:672-704 | Project status | verb-first |
| `imem service start/stop/status` | cli.py:707-773 | Service management | verb-first |

---

## Metadata & Filtering (CURRENT)

### Changelog Chunks (develop/design/document phases)
```python
{
    'source': 'changelog',
    'phase': 'develop'|'design'|'designate'|'document',
    'layer': 'implementation'|'pattern',
    'section_type': 'Decisions'|'Constraints'|etc,  # H2 parent
    'section_name': '...',  # H3 title
    'has_context': bool,
    'has_solution': bool,
    'has_rationale': bool,
    'has_alternatives': bool,
    'timestamp': str,  # Optional
    'session_id': str,  # Link to conversation
}
```

### Conversation Chunks
```python
{
    'source': 'conversation',
    'session_id': str,
    'chunk_type': 'message'|'patch',
    'role': 'user'|'assistant',  # For messages
    'file_path': str,  # For patches
    'section_type': 'Message 1: USER'|'Code Patch 1: src/cli.py',
    'start_time': str,
    'duration_minutes': int,
    'message_count': int,
}
```

---

## Collection Architecture (CURRENT PROBLEM)

### Issue
- Changelogs: `imem_{hash}` (per-project) ✅
- Conversations: `institutional_memory` (hardcoded global) ❌

### Should Be
- Changelogs: `imem_{hash}_changelog` (per-project)
- Conversations: `imem_{hash}_conversation` (per-project)

### Registry Tracking (CURRENT PROBLEM)
```python
# OLD (only tracks one collection)
{'collection': 'imem_1ba1fff1'}

# SHOULD BE (tracks both)
{'collections': {
    'changelog': 'imem_1ba1fff1_changelog',
    'conversation': 'imem_1ba1fff1_conversation'
}}
```

---

## Helper Functions (CURRENT)

### In cli.py

| Function | Location | Purpose |
|----------|----------|---------|
| `_execute_search()` | cli.py:145-212 | Shared search logic for all search commands |
| `setup_vscode_integration()` | cli.py:776-875 | VS Code setup + extension install |

### In ingest.py

| Function | Location | Purpose |
|----------|----------|---------|
| `ingest_markdown_chunked()` | ingest.py:626-787 | Index single markdown with LlamaIndex |
| `ingest_conversation_chunked()` | ingest.py:823-907 | Index conversation with H2 chunking |
| `_extract_phase()` | ingest.py:585-598 | Auto-detect phase from path |
| `_detect_layer()` | ingest.py:611-624 | Detect pattern vs implementation layer |
| `parse_conversation_section()` | ingest.py:789-821 | Parse TRACE H2 headers → metadata |
| `get_existing_file_paths()` | ingest.py:68-107 | For incremental indexing |
| `get_existing_content_hashes()` | ingest.py:109-156 | For content-based dedup |
| `update_file_path()` | ingest.py:158-216 | Update path when content moves |
| `deduplicate_collection()` | ingest.py:218-332 | Remove duplicate chunks |

---

## Phase Indexing Flow

```
imem init
├─ Detect .context folder structure
├─ Register project → imem_{hash}_changelog
├─ For each phase in [develop, designate, document, +design?]:
│  ├─ Find all .md files (recursive)
│  └─ For each file:
│     ├─ Call EnhancedModularIngest.ingest_markdown_chunked()
│     │  ├─ Parse with LlamaIndex (section-level)
│     │  ├─ Filter H3+ sections only
│     │  ├─ Build metadata (phase, layer, section_type, etc)
│     │  ├─ Batch encode with E5-Large-v2
│     │  └─ Upsert to {hash}_changelog collection
│     └─ Log progress
└─ Update registry with doc count
```

---

## Conversation Indexing Flow (BROKEN)

```
imem index-all-conversations
├─ Find all .claude/ conversations
├─ Filter by size, limit, recent
└─ For each conversation:
   ├─ Export to markdown via TRACE
   ├─ Call EnhancedModularIngest.ingest_conversation_chunked()
   │  ├─ Parse TRACE markdown
   │  ├─ Parse H2 headers → chunk_type, role, file_path
   │  ├─ Batch encode with E5-Large-v2
   │  └─ Upsert to HARDCODED "institutional_memory" ❌
   └─ Log progress
```

**Problems:**
- Collection never created with proper schema
- Global collection (no project isolation)
- Registry doesn't track it

---

## Click Decorator Groups

```python
@click.group()
def imem():                    # Root (cli.py:31-34)

@imem.group()
def develop():                 # Phase (cli.py:41-44)
    @develop.command(name='search')

@imem.group()
def conversations():           # Source (cli.py:92-95)
    @conversations.command(name='search')

@imem.group()
def service():                 # Service (cli.py:707-710)
    @service.command()
    @service.command()
    @service.command(name='status')

# Direct commands under @imem (scattered):
@imem.command()  # compose, init, search, update, dedupe, status
@imem.command()  # index-conversation, index-all-conversations
```

---

## Refactor Target (RECOMMENDED)

### New Command Tree
```
imem
├── index
│   ├── develop [--force]
│   ├── design [--force]
│   ├── document [--force]
│   ├── conversations [--limit] [--recent]
│   └── context [--force] [--include-design]
├── search [--in develop|design|document|conversations|context]
├── service
│   ├── start
│   ├── stop
│   └── status
├── compose
├── update
├── dedupe
└── status
```

### Benefits
- ✅ Consistent verb-noun everywhere
- ✅ `imem index` → list all phases
- ✅ `imem search` → list all options
- ✅ Parallel command families (search + index)
- ✅ Per-project collections
- ✅ Extensible for new phases/sources

---

## Inconsistencies Summary

| Issue | Location | Impact |
|-------|----------|--------|
| 3 different command patterns | Throughout CLI | Confusing, hard to learn |
| Hardcoded `institutional_memory` | cli.py:879, 1011 | Conversation indexing broken |
| Single collection in registry | registry.py:36-46 | Can't track changelog vs conversation |
| No per-project conversations | collection strategy | No isolation between projects |
| Duplicated search logic | cli.py:47, 98, 443 | Hard to maintain consistency |
| Design phase excluded by default | cli.py:402-404 | Unclear why it's different |
| Phase filter mismatch | cli.py:453 | Supports designate but doesn't index it |

---

## Implementation Phases

### Phase 1: Foundation (2-3 hours)
1. Extract `_index_phase()` helper (~30 min)
2. Refactor CLI to verb-noun (~1 hour)
3. Fix collection architecture (~30 min)
4. Test conversation indexing (~30 min)

### Phase 2: Intelligence (3-4 hours, NEXT SESSION)
1. Graph construction (topology detection)
2. Metadata enrichment (position, confidence)
3. Template adaptation

### Phase 3: Persistence (MONTHS LATER)
1. BRAIN layer (requires usage data)
2. Entity resolution
3. Reference counting

---

## Testing Checklist

After refactor:
- [ ] `imem index develop` creates changelog collection
- [ ] `imem index conversations --limit 10` creates conversation collection
- [ ] Two collections exist: `imem_{hash}_changelog`, `imem_{hash}_conversation`
- [ ] `imem search "query"` works with `--in` filter
- [ ] Conversation metadata includes: chunk_type, role, file_path
- [ ] Changelog metadata includes: phase, layer, section_type
- [ ] `imem compose` still works
- [ ] No breaking changes

---

## Files to Modify

- **cli.py** - CLI structure refactor (primary)
- **registry.py** - Track multiple collections per project
- **ingest.py** - Collection naming logic (minor, already flexible)

---

## Key Insights

> "The current CLI has three incompatible patterns at root level:
> noun-verb groups, verb-first, and verb-noun-hyphenated.
> This blocks intuitive discoverability and makes extension painful.
> Verb-noun throughout fixes this + enables per-project conversation isolation."

---


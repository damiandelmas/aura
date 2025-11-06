---
session_id: c5383e9c-9894-4584-9edd-1cf8aaebaca1
---

● CORRECTED Architecture

┌─ TIER 0: THE THINGS THEMSELVES ──────────────────┐
│ Heterogeneous formats:                           │
│ • URLs (https://docs.anthropic.com/hooks)        │
│ • Codebases (github.com/anthropic/claude-code)   │
│ • Local markdown (develop logs)                  │
│ • PDFs (research papers)                         │
│ • APIs (data endpoints)                          │
│ • Databases (SQL, Neo4j)                         │
│                                                  │
│ NO standard format at this layer                 │
└──────────────────────────────────────────────────┘
            ↓
┌─ TIER 1: OBJECTIVE GATEWAY ───────────────────────┐
│ STANDARDIZED as markdown + frontmatter           │
│                                                   │
│ Entry for URL:                                    │
│ ---                                               │
│ source: https://docs.anthropic.com/hooks         │
│ retrieval_method: webfetch                        │
│ authority: 1                                      │
│ tags: [official, documentation]                   │
│ ---                                               │
│ ## Summary                                        │
│ [150-250 words describing Tier 0 content]         │
│                                                   │
│ Entry for codebase:                               │
│ ---                                               │
│ source: https://github.com/user/repo             │
│ retrieval_method: git_clone                       │
│ authority: 4                                      │
│ tags: [code, reference]                           │
│ ---                                               │
│ ## Summary                                        │
│ [Description of what codebase contains]           │
│                                                   │
│ ALL Tier 1 = markdown files for uniform parsing  │
└───────────────────────────────────────────────────┘
            ↓
┌─ YOUR CUSTOM PARSER ───────────────────────────────┐
│                                                    │
│ 1. Parse Tier 1 (python-frontmatter)              │
│    post = frontmatter.load(tier1_entry)           │
│    metadata = post.metadata                       │
│    summary = post.content                         │
│                                                    │
│ 2. Decide: Use summary OR fetch Tier 0?           │
│    if need_full_content:                          │
│      tier0_content = fetch(metadata['source'],    │
│                           metadata['retrieval_method']) │
│    else:                                           │
│      tier0_content = summary                      │
│                                                    │
│ 3. Parse content (BRAIN intelligence)             │
│    - Schema evolution                             │
│    - Entity resolution                            │
│                                                    │
│ 4. Ingest to Qdrant                               │
│                                                    │
└────────────────────────────────────────────────────┘
            ↓
┌─ QDRANT ───────────────────────────────────────────┐
│ Vectorized content with metadata                   │
└────────────────────────────────────────────────────┘

---
The Key Insight

Tier 1 is the NORMALIZATION layer:

Tier 0: Heterogeneous (URL, code, MD, PDF, API...)
Tier 1: Homogeneous (always markdown + frontmatter)

Tier 1 = Universal adapter pattern

Every Tier 0 source gets wrapped in a Tier 1 markdown file that:
1. Points to it (source: field)
2. Describes how to fetch it (retrieval_method: field)
3. Summarizes it (markdown content)
4. Provides metadata (frontmatter)

---
python-frontmatter Usage

Only for Tier 1 entries (which are always markdown with frontmatter):

# Parse Tier 1 entry
tier1_file = "GLOBAL_REGISTRY/anthropic-hooks.md"
post = frontmatter.load(tier1_file)

# Extract metadata
source = post['source']              # "https://docs.anthropic.com/hooks"
retrieval_method = post['retrieval_method']  # "webfetch"
authority = post['authority']        # 1
tags = post['tags']                  # ["official", "documentation"]

# Extract summary (Tier 1 content)
summary = post.content  # "Official lifecycle hooks..."

# Fetch Tier 0 if needed
if need_full_content:
    if retrieval_method == 'webfetch':
        tier0_content = WebFetch(source)
    elif retrieval_method == 'git_clone':
        tier0_content = git_clone(source)
    elif retrieval_method == 'file_read':
        tier0_content = Path(source).read_text()

---
Example Flow

Tier 0: Anthropic Docs (URL)

https://docs.anthropic.com/en/docs/claude-code/hooks
[HTML content lives at URL]

Tier 1: Registry Entry (Markdown)

---
source: https://docs.anthropic.com/en/docs/claude-code/hooks
retrieval_method: webfetch
authority: 1
tags: [official, documentation, hooks]
created: 2024-10
---

## Anthropic Hooks Documentation

Official lifecycle hooks for Claude Code events including SessionStart,
PreToolUse, PostToolUse, and Stop. Enables blocking operations, context
injection, validation, and audit trails for AI coding workflows.

Parser Action

# 1. Parse Tier 1
post = frontmatter.load("GLOBAL_REGISTRY/anthropic-hooks.md")

# 2. Option A: Use summary only (fast)
summary = post.content
ingest_to_qdrant(summary, post.metadata)

# 2. Option B: Fetch full content (deep)
full_content = WebFetch(post['source'])
parsed = parse_with_brain_intelligence(full_content)
ingest_to_qdrant(parsed, post.metadata)

---
The Corrected Understanding

Tier 1 standardizes access to heterogeneous Tier 0 sources

- Tier 0 = diverse formats (URL, code, PDF, etc)
- Tier 1 = uniform format (markdown + frontmatter)
- Parser reads Tier 1 (always markdown)
- Fetches Tier 0 when needed (via retrieval_method)

python-frontmatter parses Tier 1 entries only.

Tier 1 = universal markdown interface to anything in Tier 0.
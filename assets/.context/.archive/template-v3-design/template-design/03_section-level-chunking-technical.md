# YES! Section-Level Chunking & Metadata Architecture

## 🎯 **The Vision**

**Slice and dice your corpus at the section level while preserving narrative context.**

```
Single Changelog (250927-2217.md)
        ↓
    Parse into sections
        ↓
┌─────────────────────────────────────┐
│ Section 1: Key Decisions            │ → Tag: DECISION
│ Section 2: Technical Implementation │ → Tag: IMPLEMENTATION
│ Section 3: File Operations          │ → Tag: AUDIT
│ Section 4: Knowledge Capture        │ → Tag: CONSTRAINT
│ Section 5: Replication Guide        │ → Tag: PATTERN
└─────────────────────────────────────┘
        ↓
    Vector DB stores EACH SECTION separately
        ↓
    But metadata links back to parent document
```

**Result:** Search finds specific sections, but you can always reconstruct full narrative.

---

## 📐 **Section-Level Chunking Architecture**

### **Current (Document-Level)**
```python
# Store entire changelog as one vector
{
  "content": "[entire 350-line changelog]",
  "metadata": {
    "file_path": "250927-2217.md",
    "timestamp": "2025-09-27T22:17:57-0700"
  }
}
```

**Problem:** Search returns whole changelog, Claude wades through 350 lines to find the constraint.

---

### **Enhanced (Section-Level)**
```python
# Store each section as separate vector
[
  {
    "content": "### Decision 1: File-Based Retrieval...",
    "metadata": {
      "file_path": "250927-2217.md",
      "section_type": "decision",
      "section_id": "DEC-FILE-RETRIEVAL",
      "section_title": "File-Based Retrieval Pattern",
      "parent_doc": "250927-2217.md",
      "section_number": 3,
      "timestamp": "2025-09-27T22:17:57-0700"
    }
  },
  {
    "content": "### Tool Output Limits (Critical Knowledge)...",
    "metadata": {
      "file_path": "250927-2217.md",
      "section_type": "constraint",
      "section_id": "CONS-BASH-TRUNCATE",
      "section_title": "Bash Output Truncation",
      "parent_doc": "250927-2217.md",
      "section_number": 8,
      "timestamp": "2025-09-27T22:17:57-0700"
    }
  }
]
```

**Benefit:** Search returns exact relevant section, not entire doc.

---

## 🔍 **Slice & Dice Queries**

### **Query 1: All Constraints Across Corpus**
```bash
imem search --section-type constraint "bash"
```

**Returns:**
```
1. CONS-BASH-TRUNCATE (from 250927-2217.md)
   "Bash tool truncates output at 30,000 characters hard limit..."

2. CONS-PORT-CONFLICT (from 250915-1430.md)
   "Port 6333 conflicted with internal tool..."

3. CONS-TILDE-EXPANSION (from 250927-2217.md)
   "Read/Write tools don't expand tilde (~)..."
```

---

### **Query 2: All Decisions About Tools**
```bash
imem search --section-type decision "tool"
```

**Returns:**
```
1. DEC-FILE-RETRIEVAL (from 250927-2217.md)
   "Use file-based retrieval for large output..."

2. DEC-NATIVE-TOOLS (from 250927-2217.md)
   "Use Read and Write tools directly instead of bash..."

3. DEC-E5-MODEL (from 250918-1422.md)
   "Standardize on E5-Large-v2 for all projects..."
```

---

### **Query 3: All Failures Related to Permissions**
```bash
imem search --section-type failure "permission"
```

**Returns:**
```
1. FAIL-ECHO-PERMISSIONS (from 250927-2217.md)
   "Using echo via Bash triggered permission prompts..."

2. FAIL-CAT-VARIABLE (from 250927-2217.md)
   "cat via Bash in variable assignment triggered prompts..."
```

---

### **Query 4: All Patterns About File Operations**
```bash
imem search --section-type pattern "file"
```

**Returns:**
```
1. PATTERN-FILE-BASED-RETRIEVAL (from 250927-2217.md)
   "For large output, save to file first, then use Read tool..."

2. PATTERN-ABSOLUTE-PATHS (from 250927-2217.md)
   "Always use absolute paths with Read/Write/Edit tools..."
```

---

## 🏗️ **Implementation Architecture**

### **Component 1: Section Parser**

```python
# src/imem/processing/section_parser.py

class SectionParser:
    """
    Parse markdown into sections based on headers and patterns
    """

    SECTION_PATTERNS = {
        'decision': r'##\s*Key Decision|##\s*Decision \d+',
        'constraint': r'##\s*Knowledge Capture|###\s*Tool Output Limits|###.*Constraint',
        'failure': r'##\s*Failed Approach|###.*didn\'t work',
        'pattern': r'##\s*Pattern:|##\s*Replication Guide',
        'implementation': r'##\s*Technical Implementation|##\s*Implementation',
        'audit': r'##\s*File Operations Audit'
    }

    def parse_changelog(self, content: str, file_path: str) -> List[Section]:
        """
        Split changelog into sections based on markdown headers
        """
        sections = []

        # Extract YAML frontmatter
        frontmatter = self._extract_frontmatter(content)

        # Split on ## headers
        chunks = re.split(r'\n##\s+', content)

        for i, chunk in enumerate(chunks):
            # Detect section type
            section_type = self._detect_section_type(chunk)

            # Extract section title
            title = self._extract_title(chunk)

            # Generate section ID
            section_id = self._generate_id(title, section_type)

            sections.append(Section(
                content=chunk,
                section_type=section_type,
                section_id=section_id,
                section_title=title,
                parent_doc=file_path,
                section_number=i,
                timestamp=frontmatter.get('timestamp')
            ))

        return sections

    def _detect_section_type(self, chunk: str) -> str:
        """
        Match section against known patterns
        """
        for section_type, pattern in self.SECTION_PATTERNS.items():
            if re.search(pattern, chunk, re.IGNORECASE):
                return section_type

        return 'general'  # Default type

    def _generate_id(self, title: str, section_type: str) -> str:
        """
        Generate unique ID for section
        """
        # Clean title for ID
        clean = re.sub(r'[^a-zA-Z0-9]+', '-', title.upper())
        prefix = section_type.upper()[:4]  # DECI, CONS, FAIL, PATT

        return f"{prefix}-{clean[:30]}"
```

---

### **Component 2: Section-Aware Ingestion**

```python
# src/imem/search/section_ingest.py

class SectionIngest:
    """
    Ingest sections as separate vectors while preserving relationships
    """

    def ingest_changelog(self, file_path: str):
        """
        Parse and ingest sections from a single changelog
        """
        # Read changelog
        content = self.read_file(file_path)

        # Parse into sections
        parser = SectionParser()
        sections = parser.parse_changelog(content, file_path)

        # Generate embeddings for each section
        vectors = []
        for section in sections:
            embedding = self.encoder.encode(section.content)

            vectors.append({
                'vector': embedding,
                'payload': {
                    'content': section.content,
                    'file_path': file_path,
                    'section_type': section.section_type,
                    'section_id': section.section_id,
                    'section_title': section.section_title,
                    'parent_doc': section.parent_doc,
                    'section_number': section.section_number,
                    'timestamp': section.timestamp,

                    # Enable reconstruction
                    'total_sections': len(sections),
                    'prev_section': sections[i-1].section_id if i > 0 else None,
                    'next_section': sections[i+1].section_id if i < len(sections)-1 else None
                }
            })

        # Store in Qdrant
        self.qdrant.upsert(collection_name, vectors)
```

---

### **Component 3: Section-Filtered Search**

```python
# src/imem/search/section_search.py

class SectionSearch:
    """
    Search with section-level filtering
    """

    def search(self, query: str, section_type: str = None, limit: int = 10):
        """
        Search with optional section type filter
        """
        # Generate query embedding
        query_vector = self.encoder.encode(query)

        # Build Qdrant filter
        filters = None
        if section_type:
            filters = Filter(
                must=[
                    FieldCondition(
                        key="section_type",
                        match=MatchValue(value=section_type)
                    )
                ]
            )

        # Search
        results = self.qdrant.search(
            collection_name=self.collection,
            query_vector=query_vector,
            query_filter=filters,
            limit=limit
        )

        return self._format_results(results)

    def get_all_by_type(self, section_type: str):
        """
        Retrieve all sections of a specific type
        """
        results = self.qdrant.scroll(
            collection_name=self.collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="section_type",
                        match=MatchValue(value=section_type)
                    )
                ]
            ),
            limit=1000
        )

        return self._format_results(results)
```

---

### **Component 4: Context Reconstruction**

```python
# src/imem/context/reconstructor.py

class ContextReconstructor:
    """
    Rebuild full document context from section results
    """

    def reconstruct_document(self, section_id: str):
        """
        Given a section, retrieve the full parent document
        """
        # Get section
        section = self.get_section(section_id)
        parent_doc = section.parent_doc

        # Get all sections from same parent
        all_sections = self.qdrant.scroll(
            collection_name=self.collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="parent_doc",
                        match=MatchValue(value=parent_doc)
                    )
                ]
            )
        )

        # Sort by section_number
        sorted_sections = sorted(
            all_sections,
            key=lambda x: x.payload['section_number']
        )

        # Reconstruct full content
        full_content = "\n\n".join([
            s.payload['content'] for s in sorted_sections
        ])

        return full_content

    def get_surrounding_context(self, section_id: str, context_window: int = 2):
        """
        Get N sections before and after a specific section
        """
        section = self.get_section(section_id)

        # Get prev/next sections
        prev_id = section.payload['prev_section']
        next_id = section.payload['next_section']

        context = [section]

        # Walk backwards
        current = prev_id
        for _ in range(context_window):
            if current:
                prev_section = self.get_section(current)
                context.insert(0, prev_section)
                current = prev_section.payload['prev_section']

        # Walk forwards
        current = next_id
        for _ in range(context_window):
            if current:
                next_section = self.get_section(current)
                context.append(next_section)
                current = next_section.payload['next_section']

        return context
```

---

## 🎨 **Enhanced CLI Commands**

### **New Search Modes**

```bash
# Search only constraints
imem search "bash" --type constraint

# Search only decisions
imem search "file" --type decision

# Search only failures
imem search "permission" --type failure

# Get all constraints (no query)
imem list --type constraint

# Get all decisions from last month
imem list --type decision --after 2025-09-01

# Search with context window
imem search "bash truncate" --type constraint --context 2
# Returns: 2 sections before + match + 2 sections after
```

---

### **New Analysis Commands**

```bash
# Show all constraint types
imem analyze constraints

# Output:
# Technical Constraints: 12
# Business Constraints: 5
# Integration Constraints: 8

# Show decision timeline
imem analyze decisions --timeline

# Output:
# 2025-09-15: Port 6334 standardization
# 2025-09-18: E5-Large-v2 model choice
# 2025-09-27: File-based retrieval pattern

# Show failure patterns
imem analyze failures --group-by pattern

# Output:
# Permission Issues: 3 failures
# Path Handling: 2 failures
# Tool Limitations: 4 failures
```

---

## 📊 **Storage Schema Evolution**

### **Current Schema**
```
Collection: memory_a3f2d8c1
└── Documents (1 per file)
    └── Full changelog content
```

### **Enhanced Schema**
```
Collection: memory_a3f2d8c1
├── Sections (N per file)
│   ├── Section metadata
│   ├── Section content
│   └── Parent linking
└── Indexes
    ├── By section_type
    ├── By section_id
    └── By parent_doc
```

---

## 🔗 **Cross-Referencing Example**

Your changelog already has:
```markdown
## Related Work
- 250927-1938_trace-conversation-extraction-cleanup.md
- 250927-1957_remove-redundant-find-command.md
```

Enhanced with section-level:
```markdown
## Related Work
- DECI-REMOVE-FIND (from 250927-1957.md)
  → Led to simplified CLI in this session

- CONS-CONVERSATION-SIZE (from 250927-1938.md)
  → Identified issue this session solved

- PATT-PERMISSION-FREE (discovered in this session)
  → Used in both bookmark commands
```

**Auto-detected by analyzing:**
1. Mentions of other file names
2. Shared constraint/decision IDs
3. Temporal relationships (sessions on same day)
4. Keyword overlap between sections

---

## 💡 **Killer Feature: Pattern Synthesis**

### **Auto-Detect Patterns Across Corpus**

```bash
imem synthesize patterns
```

**Output:**
```markdown
# Discovered Pattern: Permission-Free File Operations

Found in 3 sessions:
1. 250927-2217 (Decision: Use Read/Write tools)
2. 250920-1534 (Constraint: Echo triggers prompts)
3. 250918-0922 (Failure: Cat in variables fails)

Common Thread:
- Bash file operations trigger permission prompts
- Native tools (Read, Write) don't require permissions
- Solution: Always prefer native tools over Bash

Recommendation:
Create PATTERN-PERMISSION-FREE-OPS in standards doc.
```

---

## 🎯 **Implementation Phases**

### **Phase 1: Parser & Ingestion (1 week)**
- Build SectionParser
- Modify ingestion to store sections
- Maintain backward compatibility (store full docs too)
- Test with existing changelogs

### **Phase 2: Section Search (3 days)**
- Add --type filters to search
- Implement section-level retrieval
- Add context reconstruction

### **Phase 3: Analysis Commands (3 days)**
- `imem list --type X`
- `imem analyze constraints/decisions/failures`
- Timeline and grouping views

### **Phase 4: Auto-Synthesis (1 week)**
- Pattern detection across sections
- Cross-reference discovery
- Relationship mapping

---

## 📈 **Expected Impact**

| Capability | Before | After |
|------------|--------|-------|
| Find all constraints | Search → Read 20 docs | `--type constraint` → 5 exact sections |
| Find decision rationale | Grep through docs | `--type decision` → Instant |
| Pattern recognition | Manual | Auto-detected |
| Cross-references | Manual linking | Auto-discovered |
| Context retrieval | All or nothing | Surgical + expandable |

---

## 🚀 **Quick Start**

```bash
# Re-index with section parsing
imem reindex --enable-sections

# Search by section type
imem search "bash" --type constraint

# List all decisions
imem list --type decision

# Get full context for a section
imem context CONS-BASH-TRUNCATE

# Analyze patterns
imem analyze patterns
```

---

## TL;DR

**Section-level chunking = surgical precision + full context when needed.**

- **Parse** changelogs into sections (decisions, constraints, failures, patterns)
- **Store** each section as separate vector with rich metadata
- **Search** by section type: "show me ALL constraints about bash"
- **Reconstruct** full document when you need complete narrative
- **Synthesize** patterns across entire corpus automatically

**You get slice-and-dice queryability without losing narrative context.** 🎯

This is **exactly** what production RAG systems do (LlamaIndex, LangChain) but tuned for your institutional memory use case.

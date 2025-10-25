# LlamaIndex Chunking Visualization

## Original Markdown Structure

```markdown
# Conversation: 67f63a89-04a                    ← H1 title

**Duration:** 21min | **Messages:** 133

## User Messages                                 ← H2 section 1
- [Request interrupted by user]

## Assistant Responses                           ← H2 section 2
I'm ready to help you search...
[... 5464 chars of assistant messages ...]

## Code Changes                                  ← H2 section 3
### /path/to/file1.md                           ← H3 subsection
**Operation:** edit

### /path/to/file2.py                           ← H3 subsection
**Operation:** edit

## Tools Used                                    ← H2 section 4
- **Edit**: 17×
- **Read**: 11×
...

## Files Modified                                ← H2 section 5
- /path/to/file1.md (edit)
- /path/to/file2.py (edit)
...
```

---

## How LlamaIndex Chunks It

### Node 1 (Root)
```
Header Path: /
Level: H0
Content: "# Conversation: 67f63a89-04a\n\n**Duration:** 21min..."
```
**What it is:** The H1 title + metadata

---

### Node 2 (User Messages - Header Only)
```
Header Path: /Conversation: 67f63a89-04a/
Level: H0
Content: "## User Messages\n\n- [Request interrupted by user]"
```
**What it is:** User Messages section (49 chars)

---

### Node 3 (Assistant Responses - Content)
```
Header Path: /Conversation: 67f63a89-04a/
Level: H0
Content: "## Assistant Responses\n\nI'm ready to help you search... [5464 chars]"
```
**What it is:** Assistant Responses section (full content)

---

### Nodes 4-21 (Other H2 sections)
Each H2 section becomes 1-2 nodes depending on length

---

### Node 22 (Code Changes - Header)
```
Header Path: /Conversation: 67f63a89-04a/
Level: H0
Content: "## Code Changes"
```
**What it is:** Code Changes section header (15 chars)

---

### Nodes 23-39 (Code Changes - H3 subsections)
```
Header Path: /Conversation: 67f63a89-04a/Code Changes/
Level: H0
Content: "### /home/axp/.../file.py\n\n**Operation:** edit"
```
**What it is:** Each file edit becomes a separate node (~100 chars each)

---

### Node 40 (Tools Used)
```
Header Path: /Conversation: 67f63a89-04a/
Level: H0
Content: "## Tools Used\n\n- **Edit**: 17×\n- **Read**: 11×..."
```
**What it is:** Tools Used section (127 chars)

---

### Node 41 (Files Modified)
```
Header Path: /Conversation: 67f63a89-04a/
Level: H0
Content: "## Files Modified\n\n- /path/to/file1.md (edit)..."
```
**What it is:** Files Modified section (743 chars)

---

## What This Means for Search

### Query: "What tools were used?"

**Qdrant returns:** Node 40
```
## Tools Used
- **Edit**: 17×
- **Read**: 11×
- **Bash**: 8×
- **TodoWrite**: 7×
```

✅ **Perfect!** Just the relevant section.

---

### Query: "Show me code changes to cli.py"

**Qdrant returns:** Nodes 36-38 (3 separate nodes)
```
### /home/axp/.../imem/src/imem/cli.py
**Operation:** edit

### /home/axp/.../imem/src/imem/cli.py
**Operation:** edit

### /home/axp/.../imem/src/imem/cli.py
**Operation:** edit
```

✅ **Good!** Multiple relevant patches grouped together.

---

### Query: "What did the user ask?"

**Qdrant returns:** Node 2
```
## User Messages
- [Request interrupted by user]
```

✅ **Perfect!** Just user questions, not assistant responses.

---

## Conclusion: The Chunking is CORRECT

**Why the weird header_path values don't matter:**

1. ✅ **Sections ARE separated** - Each H2 becomes its own searchable node
2. ✅ **Node sizes are good** - Average 411 chars (not too big, not too small)
3. ✅ **Subsections work** - H3 under "Code Changes" create granular nodes
4. ✅ **Search will be precise** - "tools" query returns just Tools section

**The `header_path: /Conversation: 67f63a89-04a/` is fine because:**
- We're filtering by `source: 'conversation'` in metadata
- The actual section type will be in the content text
- Vector similarity will match the right nodes
- We can add custom `section_type` metadata when indexing

**This is exactly what we want for conversation archaeology!**

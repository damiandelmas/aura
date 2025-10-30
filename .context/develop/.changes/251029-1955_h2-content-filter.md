---
schema_version: "v3_adaptive"
type: "bug-fix.h2-chunking-filter"
status: "completed"
keywords: "ingest chunking filter h2 content markdown indexing llama-index"
timestamp: "2025-10-29T19:55:00-0700"
session_id: "f48360a7-9532-46b2-a6ec-cf9348226255"
---

# H2 Chunking Filter Fix

## Request
> "Fix the chunking filter to index H2 sections with content while skipping empty H2 parent headers"

## Overview
Changed the markdown chunking filter from header-level-based filtering to content-length-based filtering. Previously, all H1 and H2 sections were skipped regardless of content, which incorrectly excluded valuable H2 sections like Overview and Request that contain prose. The new approach examines actual content after the header line and only skips chunks with less than 20 characters of content. This allows substantive H2 sections to be indexed while still filtering out empty H2 parent containers that only serve as grouping headers.

## Decisions

### Content-Based Filter Over Header-Level Filter
- **Context**: Original filter skipped all H1/H2 headers, losing Overview and Request sections
- **Solution**: Check content length instead of header level
- **Rationale**: Empty parent headers (Decisions, Implementation) have no content, but prose sections (Overview, Request) have substantial text
- **Approach**: Extract content excluding header line, skip if less than 20 characters

### Threshold Selection
- **Context**: Needed minimum length to distinguish empty containers from real content
- **Solution**: 20 character threshold (approximately 3 words)
- **Rationale**: Substantive sections always exceed this, empty headers never do

## Implementation

### Architecture
1. Parse header level from markdown syntax → Detect H1-H6
2. Extract actual content after header line → Split on newline, take remainder
3. Measure content length → Count characters in extracted text
4. Filter based on content → Skip chunks with <20 chars of actual content
5. Allow H2 sections through → Now indexed if they have content

### Code Signatures

**Content-Based Chunking Filter** (`imem/src/imem/ingest.py` lines 699-711)
```python
# Extract actual content (excluding header line)
content_lines = content.split('\n')
actual_content = '\n'.join(content_lines[1:]).strip() if len(content_lines) > 1 else ''

# FILTER: Skip chunks with no actual content (empty H2 parent headers)
# This allows H2 sections with content (Overview, Request) while skipping
# empty H2 parent headers (Decisions, Implementation that only contain H3s)
if len(actual_content) < 20:  # Less than ~3 words of actual content
    continue  # Skip empty headers (H1 titles, H2 parent sections)

# Re-assign header_level for H2 sections now that we're allowing them
if header_level is None:
    continue  # Skip frontmatter/non-header chunks
```

## Patterns

### Content-Length Heuristic for Empty Containers
- **Pattern**: Measure actual content after header to distinguish containers from content
- **When**: Parsing hierarchical documents where headers serve dual purposes
- **Approach**: Extract text excluding the header line, apply character count threshold
- **Benefit**: Simple heuristic that works across different document structures

## Audit

### Modified
- `imem/src/imem/ingest.py` - Changed filter from `if header_level in [1, 2]: continue` to content-length check on lines 699-707
- `imem/src/imem/ingest.py` - Added `actual_content` extraction logic to separate header from body text
- `imem/src/imem/ingest.py` - Updated inline comments to explain new filter behavior

### Impact
- H2 sections with prose (Overview, Request, Constraints with description) now indexed
- Empty H2 parent containers (Decisions, Implementation with only H3 children) still filtered
- Improves search recall for top-level narrative content in changelogs

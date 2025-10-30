---
schema_version: "v3_adaptive"
type: "bug-fix.h2-chunking-filter"
status: "completed"
keywords: "document-chunking hierarchical-filtering content-analysis structural-heuristics empty-container-detection"
timestamp: "2025-10-29T19:55:00-0700"
session_id: "f48360a7-9532-46b2-a6ec-cf9348226255"
source_changelog: "251029-1955_h2-content-filter.md"
---

# Hierarchical Document Filtering Pattern

## Request
> "Fix the chunking filter to index secondary-level sections with content while skipping empty secondary-level parent headers"

## Overview
Changed the document chunking filter from structural-level-based filtering to content-length-based filtering. Previously, all primary and secondary structural levels were skipped regardless of content, which incorrectly excluded valuable secondary-level sections like Overview and Request that contain prose. The new approach examines actual content after the header and only skips chunks with less than 20 characters of content. This allows substantive secondary-level sections to be indexed while still filtering out empty secondary-level parent containers that only serve as structural grouping.

## Decisions

### Content-Based Filter Over Structural-Level Filter
- **Context**: Original filter skipped all structural levels, losing narrative sections with meaningful content
- **Solution**: Check content length instead of structural hierarchy level
- **Rationale**: Empty parent containers have no content, but prose sections have substantial text; structure alone cannot distinguish them
- **Approach**: Extract content excluding header line, skip if less than threshold characters

### Threshold Selection
- **Context**: Needed minimum length to distinguish empty containers from real content
- **Solution**: 20 character threshold (approximately 3 words)
- **Rationale**: Substantive sections consistently exceed this minimum, empty headers never do

## Implementation

### Architecture
1. Identify structural level from document syntax → Detect all header depths
2. Extract actual content after header → Split on line boundary, take remainder
3. Measure content length → Count characters in extracted text
4. Filter based on content → Skip chunks with insufficient content
5. Allow substantive secondary-level sections through → Now indexed if content exceeds threshold

### Code Signatures

**Content-Length Chunking Filter**
```pseudocode
1. Extract document structure: Parse header depth from document syntax
2. Separate header from body: Split header line from following content lines
3. Retrieve actual content: Join remaining lines and trim whitespace
4. Measure content size: Count characters in extracted content
5. Apply filtering logic:
   - IF content length < 20 characters THEN skip chunk
   - ELSE retain chunk for indexing
6. Re-evaluate structural classification: Adjust indexing strategy for secondary levels
```

## Patterns

### Content-Length Heuristic for Distinguishing Structural Containers
- **Pattern**: Measure actual content following structural markers to distinguish containers from content
- **When**: Processing hierarchical documents where headers serve dual purposes (both containers and content)
- **Approach**: Extract text excluding the structural marker, apply character count threshold
- **Benefit**: Universal heuristic applicable to any hierarchical document structure; simple to implement; language-independent

### Dual-Purpose Headers in Hierarchical Documents
- **Problem**: Structural markers (headers) serve both container and content roles
- **Challenge**: Distinguishing substantive sections from empty organizational containers
- **Solution**: Content-based classification rather than structure-based classification
- **Applicability**: Works for any document type with nested sections

## Audit

### Modified
- Document chunking filter - Changed from structural-level-based exclusion to content-length heuristic
- Content extraction logic - Added mechanism to separate structural markers from substantive content
- Filtering documentation - Updated to explain content-based filtering behavior

### Impact
- Secondary-level sections with prose content now indexed
- Empty secondary-level parent containers still filtered
- Improves search recall for narrative content in hierarchical documents

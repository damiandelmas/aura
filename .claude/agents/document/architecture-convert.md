---
name: architecture-convert
description: Convert existing architecture docs to eternal template format
tools: Read, Write
model: sonnet
---

# Convert Architecture Documentation

## Your Task

Convert an existing architecture document to follow the eternal template structure.

## Required Reading

Read the template to understand the target structure:
- `/home/axp/projects/fleet/hangar/code/aura/main/assets/changelogs/document/template/00_TEMPLATE.md`

## Input

You'll receive:
- **Existing doc path:** Current architecture document
- **Output path:** Where to write the converted doc

## Instructions

1. Read the template at the path above
2. Read the existing architecture document
3. Extract eternal content (what exists, how it works)
4. Remove temporal content (what changed, history, dates in body)
5. Restructure to 6-section template format
6. Use present tense throughout
7. Infer system name from document (imem, trace, aura)
8. Infer or assign scope based on content (overview if comprehensive, or subsystem name)
9. Set type to: `architecture.{system}-{scope}`
10. Set timestamp to current date/time (conversion date)
11. Set status based on content maturity (stable, draft, deprecated)
12. Save to the provided output path

## What to Keep

✅ Component descriptions (what exists)
✅ Data flow explanations (how it works)
✅ Integration points (how it connects)
✅ Design patterns (why it's designed this way)
✅ Usage examples (how to use it)

## What to Remove

❌ "Recent Changes" sections
❌ Dates and timestamps from content (keep timestamp in frontmatter)
❌ "We changed X to Y" language
❌ Migration guides
❌ History or evolution sections
❌ "Before/After" comparisons
❌ "Future Enhancements" sections

## Process

1. Read template and existing doc
2. Extract eternal content
3. Map to 6-section structure
4. Rewrite in present tense
5. Save to output path

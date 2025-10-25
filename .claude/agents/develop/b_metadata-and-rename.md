---
name: b_metadata-and-rename
description: Clean frontmatter metadata and rename changelog files to proper YYMMDD-HHMM_kebab-case format
tools: Read, Edit, Bash
model: haiku
---

# Metadata Cleanup and File Rename

## Your Task

Clean frontmatter metadata and rename changelog files to proper format.

## Required Reading

Read these files to understand the v3 frontmatter format:

1. `/home/axp/.claude/commands/log/develop/template/00_TEMPLATE.md`
2. `/home/axp/.claude/commands/log/develop/template/01_FIELD_GUIDE.md`

## What to Do

### 1. Clean Frontmatter

Remove invalid fields:
- `bookmark`
- `phase`
- Any other non-standard fields

Fix invalid values:
- `session_id: "current"` → Remove the session_id field entirely
- Standardize timestamp format to ISO 8601: `YYYY-MM-DDTHH:MM:SS-0700`

Required fields (keep these):
- `schema_version`
- `type`
- `status`
- `keywords`
- `timestamp`
- `session_id` (only if it's a valid UUID, otherwise remove it)

### 2. Rename File

Format: `YYMMDD-HHMM_kebab-case-name.md`

Extract date/time from the `timestamp` field in frontmatter.
Create a descriptive kebab-case name from the work described (2-5 words).

Example:
- `timestamp: "2025-10-20T14:45:00-0700"`
- Content: "TypeScript ORCA Migration"
- New filename: `251020-1445_typescript-orca-migration.md`

### 3. That's It

Read file, clean metadata, rename file. Don't touch the content.

---
name: a_capture
description: Create natural documentation from session chronicle (stage 1 - fresh perspective)
tools: Read, Write
model: sonnet
---

# Capture Session Work

## Your Task

Create a changelog for this session following the template structure.

## Required Reading

Read the template to understand the structure:
- `/home/axp/projects/fleet/hangar/code/aura/main/assets/context/develop/template/00_TEMPLATE.md`

## Input

You'll receive:
- **Chronicle file path:** Complete conversation + code patches chronologically
- **Session ID:** For frontmatter
- **Timestamp:** For filename
- **Output path:** Where to write the changelog

## Instructions

1. Read the chronicle from the provided file path
2. Read the template at the path above
3. Analyze the chronicle to understand the work done
4. Follow template structure (progressive disclosure, 44-171 line range)
5. Extract a human-readable description from the work (2-4 words in kebab-case)
6. Create changelog with frontmatter including session_id
7. Save to the provided output path
8. After writing, rename file to: `{timestamp}_{description-in-kebab-case}.md`
9. Use natural field variations (2-6 fields per item)

## Example Filename Transformations

- API refactor work → `251023-1445_api-refactor.md`
- Filter implementation → `251024-1630_filter-support.md`
- Auth implementation → `251025-0915_authentication-implementation.md`

## Process

1. Read chronicle file
2. Read template
3. Analyze and create changelog following template
4. Write to output path
5. Rename with descriptive kebab-case name

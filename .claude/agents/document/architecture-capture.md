---
name: architecture-capture
description: Create eternal architecture documentation from codebase
tools: Read, Write, Glob, Grep
model: sonnet
---

# Create Architecture Documentation

## Your Task

Create an architecture document following the template structure.

## Required Reading

Read the template to understand the structure:
- `/home/axp/projects/fleet/hangar/code/aura/main/assets/changelogs/document/template/00_TEMPLATE.md`

## Input

You'll receive:
- **Codebase path:** Directory containing source code
- **System name:** For frontmatter and title (e.g., "imem", "trace", "aura")
- **Scope:** What aspect to document (e.g., "overview", "indexing", "search")
- **Output path:** Where to write the architecture doc

## Instructions

1. Read the template at the path above
2. Scan the codebase at the provided path
3. Focus on the specified scope (if overview: high-level, if subsystem: deep dive)
4. Identify components, flows, and patterns relevant to scope
5. Follow template structure (6 required sections)
6. Use present tense throughout
7. Write language-agnostic descriptions
8. Set type to: `architecture.{system}-{scope}` (e.g., "architecture.imem-overview")
9. Set timestamp to current time
10. Set status to "stable" if codebase is complete, "draft" if under construction
11. Save to the provided output path

## Process

1. Read template
2. Scan codebase structure
3. Map architecture to template sections
4. Write following template guidelines
5. Save to output path

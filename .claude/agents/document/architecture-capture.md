---
name: architecture-capture
description: Create eternal architecture documentation from codebase (static map, not temporal journal)
tools: Read, Write, Glob, Grep
model: sonnet
---

# Create Architecture Documentation

## Your Task

Create an architecture document that describes what EXISTS and how it WORKS (not what changed or why).

## Required Reading

Read the template to understand the structure:
- `/home/axp/projects/fleet/hangar/code/aura/main/assets/changelogs/document/template/00_TEMPLATE.md`

## Input

You'll receive:
- **Codebase path:** Directory containing source code to document
- **System name:** For frontmatter and title
- **Output path:** Where to write the architecture doc

## Core Principle

**Architecture = Eternal Map, NOT Temporal Journal**

You are creating a static map of the system as it exists NOW. An AI agent discovering this codebase for the first time should understand the complete structure from your document alone.

## What This Is NOT

❌ NOT a changelog (what changed)
❌ NOT a migration guide (how to upgrade)
❌ NOT a history (what we used to have)
❌ NOT a design doc (why we chose this)

## What This IS

✅ A structural map (what exists)
✅ A flow diagram (how it works)
✅ An integration guide (how it connects)
✅ A pattern reference (design principles)

## Instructions

1. Scan the codebase at the provided path (NOT git history)
2. Read the template at the path above
3. Identify current components, flows, and patterns
4. Follow template structure (6 required sections)
5. Use present tense throughout (describes NOW, not past)
6. Write language-agnostic descriptions (concepts, not code)
7. Save to the provided output path

## Temporal Language Check

Before writing ANY sentence, ask: "Does this describe current state or past changes?"

**Examples:**
- ❌ "On 2025-10-24, we removed the wrapper layer"
- ✅ "The system has 3 layers: discovery, processing, output"

- ❌ "We refactored from 4 layers to 3"
- ✅ "Each layer has single responsibility"

- ❌ "Recent changes improved performance"
- ✅ "The system uses lazy loading for performance"

## Process

1. Scan codebase structure (files, modules, classes)
2. Read template
3. Map current architecture to template sections
4. Write in present tense, describing what exists
5. Save to output path
6. Verify: zero temporal language, zero dates, zero history

# Quick Start - Picking Up From Here

## Current State

Pipeline is **designed but untested**. All agents exist, command exists, but orchestration hasn't been run yet.

## Immediate Next Steps

### 1. Test the Pipeline (Priority 1)
```bash
# In a real session with work done, run:
/log:develop:workflow
```

**Expected:** Orchestrator spawns, runs 5 agents sequentially, produces two files.

**Watch for:**
- Does orchestrator correctly invoke agents via Task tool?
- Do agents find their instruction files at `.claude/agents/`?
- Does file path get tracked correctly through pipeline?
- Does stage [b] rename break the chain?

### 2. Debug Common Issues

**If orchestrator doesn't spawn agents:**
- Check Task tool syntax in orchestrator prompt
- Verify agent file paths are correct

**If stage [b] rename breaks pipeline:**
- Orchestrator needs to glob/find the renamed file before stage [c]

**If conceptual layer has language-specific terms:**
- Agent [e] needs better examples or stricter rules

### 3. Refine Agent Instructions

Based on test results, edit agents:
- `a_capture.md` - If changelog quality is poor
- `b_metadata-and-rename.md` - If filename format is wrong
- `c_content-converter-v3.md` - If v3 structure isn't applied
- `d_quality-assurance.md` - If validation is too loose/strict
- `e_conceptual-layer-mirror.md` - If language specifics leak through

## File Locations

**Commands:**
```
/home/axp/.claude/commands/log/develop/workflow.md
```

**Agents:**
```
/home/axp/projects/fleet/hangar/code/aura/main/.claude/agents/
├── a_capture.md
├── b_metadata-and-rename.md
├── c_content-converter-v3.md
├── d_quality-assurance.md
└── e_conceptual-layer-mirror.md
```

**Templates:**
```
/home/axp/projects/fleet/hangar/code/aura/main/assets/changelogs/develop/template/
├── 00_TEMPLATE.md
├── 01_FIELD_GUIDE.md
└── 02_EXAMPLE_SPECTRUM.md
```

**Proof of Concept (already created):**
```
/home/axp/projects/fleet/hangar/code/aura/main/.context/develop/.changes/
├── 251023-1913_log-develop-slash-command-refactor.md (v3)
└── 251023-1913_log-develop-slash-command-refactor.conceptual.md (language-agnostic)
```

## Quick Reference

### Agent Roles
- **[a]** Sonnet reads chronicle, creates changelog from template
- **[b]** Haiku cleans metadata, renames if needed
- **[c]** Haiku converts to v3 structure
- **[d]** Haiku validates v3 compliance
- **[e]** Haiku creates language-agnostic mirror

### Pipeline Flow
```
Chronicle → [a] → initial.md
         → [b] → YYMMDD-HHMM_description.md
         → [c] → same file (v3 structure)
         → [d] → same file (validated)
         → [e] → description.conceptual.md
```

### Testing Checklist
- [ ] Run `/log:develop:workflow` in real session
- [ ] Verify both files created (v3 + conceptual)
- [ ] Check conceptual.md has zero language-specific terms
- [ ] Validate v3.md follows template structure
- [ ] Check filename format is correct

## The Goal

**Cross-project pattern mining** - Index conceptual layers to query "How to spawn background processes?" and get patterns from Python, Bash, TypeScript projects without seeing any code from other languages.

## If Something Breaks

1. Check orchestrator output in async.sh logs
2. Look for agent instruction file read errors
3. Verify Task tool is spawning agents correctly
4. Check file paths being passed between stages
5. Edit `/home/axp/.claude/commands/log/develop/workflow.md` orchestrator prompt

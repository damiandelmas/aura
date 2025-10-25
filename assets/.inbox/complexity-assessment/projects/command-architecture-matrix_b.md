# Command Architecture Matrix

## Framework

**X-Axis: Coupling**
- MONO = Monolithic (single-file)
- MODU = Modular (component-based)
- MULT = Multi-agent (distributed)

**Y-Axis: Methodology**
- LEAN = Minimal viable
- ARCH = Architected/Engineered
- INTL = Intelligent/Adaptive

## 3×3 Matrix

| | MONO | MODU | MULT |
|---|---|---|---|
| **LEAN** | Template selection | Component imports | Agent specialization |
| **ARCH** | Workflow templates | Library assembly | Orchestrated pipelines |
| **INTL** | Smart single commands | Adaptive composition | Conversation compiler |

## Decision Logic

**Coupling Dimension:**
- MONO → Single developer, quick creation
- MODU → Team reuse, standardization  
- MULT → Complex workflows, intelligence required

**Methodology Dimension:**
- LEAN → Speed, proven patterns, minimal overhead
- ARCH → Reliability, repeatability, quality gates
- INTL → Adaptation, learning, context-awareness

## Evolution Paths

```
MONO-LEAN → MODU-LEAN → MULT-LEAN
    ↓           ↓           ↓
MONO-ARCH → MODU-ARCH → MULT-ARCH
    ↓           ↓           ↓
MONO-INTL → MODU-INTL → MULT-INTL
```

## Examples

- **MONO-LEAN**: 69-line template selector
- **MODU-ARCH**: @templates/security.md + @templates/testing.md
- **MULT-INTL**: 200+ line conversation analyzer
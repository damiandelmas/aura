# Command Architecture Framework - Complexity Assessment

## Matrix Dimensions

**X-Axis: Coupling**
- MONO (1-3): Single-file solutions
- MODU (4-6): Component-based systems  
- MULT (7-9): Multi-agent orchestration

**Y-Axis: Methodology**
- LEAN (+0): Speed over perfection
- ARCH (+3): Reliability gates required
- INTL (+6): Adaptive intelligence needed

## Scoring System

### Coupling Assessment

**MONO (1-3)**
- Score 1: Single function, no dependencies
- Score 2: Multiple functions, internal state
- Score 3: Complex logic, multiple concerns

**MODU (4-6)**
- Score 4: Simple component composition
- Score 5: Multiple interdependent components
- Score 6: Complex component ecosystem

**MULT (7-9)**
- Score 7: 2-3 agents, simple coordination
- Score 8: 4-6 agents, cross-validation
- Score 9: Complex orchestration, dynamic coordination

### Methodology Modifiers

**LEAN (+0)**
- ≤3 execution steps
- Basic error handling
- >10% acceptable failure rate

**ARCH (+3)**
- Multiple phases with gates
- Quality validation required
- <5% acceptable failure rate

**INTL (+6)**
- Context-aware behavior
- Learning/optimization
- <1% acceptable failure rate

## Complexity Thresholds

**Low (1-5)**
- Dev time: 15-60 min
- Testing: Basic functional
- Review: Optional

**Medium (6-10)**
- Dev time: 1-4 hours
- Testing: Functional + edge cases
- Review: Recommended

**High (11-15)**
- Dev time: 4+ hours
- Testing: Comprehensive
- Review: Mandatory

## Decision Matrix

| | MONO | MODU | MULT |
|---|---|---|---|
| **LEAN** | 1-3 | 4-6 | 7-9 |
| **ARCH** | 4-6 | 7-9 | 10-12 |
| **INTL** | 7-9 | 10-12 | 13-15 |

## Assessment Protocol

1. **Evaluate coupling needs** → Base score (1-9)
2. **Determine methodology requirements** → Add modifier (0/+3/+6)
3. **Calculate total complexity** → Apply thresholds
4. **Allocate resources** → Match complexity to effort

## Examples

**File Search**: MONO-1 + LEAN-0 = 1 (Low)
**Code Review Orchestrator**: MULT-8 + ARCH-3 = 11 (High)
**Adaptive Docs**: MODU-6 + INTL-6 = 12 (High)

Use this framework to assess before building. Match complexity to available resources.
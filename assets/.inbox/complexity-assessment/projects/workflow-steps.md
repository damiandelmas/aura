# Command Architecture Framework Workflow

## Phase 1: Assessment

### Step 1: Analyze Requirements
- Read task description
- Identify core functionality needed
- Determine quality/reliability requirements

### Step 2: Score Coupling Dimension (1-9)
- **MONO (1-3):** Count functions, dependencies, state complexity
- **MODU (4-6):** Count components, assess interfaces, setup overhead
- **MULT (7-9):** Count agents needed, coordination complexity, synthesis requirements

### Step 3: Score Methodology Modifier (0/+3/+6)
- **LEAN (+0):** Speed prioritized, basic validation acceptable
- **ARCH (+3):** Reliability required, systematic phases needed
- **INTL (+6):** Adaptive behavior, context awareness required

### Step 4: Calculate Total Complexity
- Add coupling score + methodology modifier
- Apply threshold:
    - **Low (1-5)**
    - **Medium (6-10)**
    - **High (11-15)**

---

## Phase 2: Component Selection

### Based on Matrix Position
- Select base template from 9-cell matrix
- Add required modules (validation, automation, state, error)
- Choose integration patterns

### Component Library
- **HEADER_MODULE:** Title, args, description
- **MISSION_MODULE:** Clear objectives
- **PROCESS_MODULE:** Execution steps (lean/arch/intl variants)
- **INTEGRATION_MODULE:** Tool usage (mono/modu/mult variants)
- Enhancement modules as needed

---

## Phase 3: Assembly

### Template Construction
1. Start with base template for matrix cell
2. Integrate `$ARGUMENTS` throughout
3. Add systematic phases if ARCH/INTL
4. Include agent orchestration if MULT
5. Add validation protocols if complexity >6

### Quality Gates by Complexity
- **Low:** Basic examples, minimal documentation
- **Medium:** Testing protocols, troubleshooting notes
- **High:** Comprehensive validation, team review required

---

## Phase 4: Implementation

### Development Process
1. Create `.claude/commands/[name].md`
2. Implement using selected components
3. Test at appropriate thoroughness level
4. Document according to complexity threshold
5. Add automation hooks if beneficial

### Resource Allocation
- **Low:** 15-60 minutes, solo development
- **Medium:** 1-4 hours, optional review
- **High:** 4+ hours, mandatory team review

---

> This workflow transforms subjective "this seems complex" into objective scoring, enabling consistent resource allocation and appropriate quality measures across the team.
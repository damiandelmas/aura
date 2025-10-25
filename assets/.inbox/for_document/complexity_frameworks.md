# Software Complexity Classification Frameworks

## Industry-Standard Complexity Models

### Cynefin Framework
Developed for sense-making and decision-making in complex environments, the Cynefin framework categorizes problems into five domains:

**Simple/Obvious Domain**
- Best practices apply
- Known solutions exist
- Cause and effect relationships are clear
- Appropriate response: Sense-Categorize-Respond

**Complicated Domain**
- Good practices apply
- Expertise required to analyze
- Multiple right answers may exist
- Appropriate response: Sense-Analyze-Respond

**Complex Domain**
- Emergent practices
- Experimentation needed
- Patterns only visible in retrospect
- Appropriate response: Probe-Sense-Respond

**Chaotic Domain**
- Novel practices required
- Immediate action necessary
- No clear cause-effect relationships
- Appropriate response: Act-Sense-Respond

**Disorder Domain**
- Unclear which domain applies
- Requires assessment before action

### Cyclomatic Complexity
McCabe's cyclomatic complexity measures code complexity through control flow:

**Calculation**: M = E - N + 2P
- E = number of edges in control flow graph
- N = number of nodes
- P = number of connected components

**Interpretation**:
- 1-10: Simple, low risk
- 11-20: Moderate complexity
- 21-50: High complexity
- 50+: Very high risk, untestable

### Cognitive Complexity
Measures mental effort required to understand code:

**Factors**:
- Nesting depth
- Structural complexity
- Flow breaks (break, continue, goto)
- Recursive calls

Unlike cyclomatic complexity, cognitive complexity penalizes nested structures more heavily as they increase mental load exponentially.

## Architectural Complexity Scales

### Coupling Dimension
**Monolithic**
- Single deployment unit
- Shared memory space
- Direct function calls
- Tight coupling between components

**Modular**
- Component-based architecture
- Well-defined interfaces
- Reusable building blocks
- Loose coupling within single deployment

**Distributed**
- Multiple deployment units
- Network communication
- Independent scaling
- Service boundaries and contracts

### Technical Debt Quantification
**Categories**:
- Code debt (poor structure, duplication)
- Architecture debt (wrong patterns)
- Test debt (inadequate coverage)
- Documentation debt (missing or outdated)

**Measurement approaches**:
- SQALE (Software Quality Assessment based on Lifecycle Expectations)
- Technical Debt Ratio = Remediation Cost / Development Cost
- Code smell density

## Maturity Models

### Capability Maturity Model Integration (CMMI)
**Level 1**: Initial (unpredictable, reactive)
**Level 2**: Managed (project-level processes)
**Level 3**: Defined (organizational standards)
**Level 4**: Quantitatively Managed (measured processes)
**Level 5**: Optimizing (continuous improvement)

### DORA Metrics for Software Delivery
**Elite performers**:
- Deployment frequency: Multiple per day
- Lead time: Less than one hour
- MTTR: Less than one hour
- Change failure rate: 0-15%

**High performers**:
- Deployment frequency: Weekly to monthly
- Lead time: One day to one week
- MTTR: Less than one day
- Change failure rate: 16-30%

## Application to Documentation

### Documentation Complexity Matrix

**Simple Documentation**:
- Single README file
- Installation + usage instructions
- Appropriate for: Libraries under 1000 LOC, single-purpose tools

**Moderate Documentation**:
- Multiple organized files
- Architecture overview
- API reference
- Appropriate for: Applications, frameworks, multi-component systems

**Complex Documentation**:
- Structured documentation system
- Multiple audience targets
- Generated components
- Appropriate for: Platforms, enterprise systems, public APIs

### Decision Criteria

**Assess by**:
- Number of integration points
- Team size and distribution
- User base diversity
- Regulatory requirements
- Change frequency
- System criticality

**Anti-pattern**: Applying enterprise documentation frameworks to simple projects or vice versa. Match documentation complexity to system complexity and organizational needs.
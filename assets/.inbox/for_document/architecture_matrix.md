# Software Architecture Classification Matrix

## Two-Dimensional Framework

### Dimension 1: Coupling (Architectural Organization)

**Monolithic**
- Single deployment unit
- Shared memory space
- Direct function calls between components
- Single process execution
- Examples: Traditional web applications, desktop applications, embedded systems

**Modular**
- Component-based within single deployment
- Well-defined interfaces and boundaries
- Plugin architecture or module system
- Single deployment with logical separation
- Examples: Plugin systems, microkernel architecture, modular monoliths

**Multi-agent / Distributed**
- Multiple independent deployment units
- Network-based communication
- Separate processes or services
- Independent scaling capability
- Examples: Microservices, service-oriented architecture, distributed systems

### Dimension 2: Methodology (Development Approach)

**Lean**
- Minimal viable implementation
- Proven patterns and practices
- Waste elimination focus
- Rapid iteration and deployment
- Characteristics: Quick to build, low overhead, pattern-based

**Architected / Engineered**
- Structured processes and workflows
- Systematic design approaches
- Quality gates and validation
- Documented standards and procedures
- Characteristics: Repeatable, reliable, process-driven

**Intelligent / Adaptive**
- Analysis-driven decisions
- Context-aware implementations
- Machine learning or AI integration
- Self-modifying or evolving systems
- Characteristics: Complex, adaptive, data-informed

## Classification Matrix

```
              Monolithic          Modular             Multi-agent
              
Lean          Template            Component           Parallel
              selection           imports             agents
              
Architected   Structured          Library             Orchestrated
              workflows           assembly            pipelines
              
Intelligent   Smart               Dynamic             Distributed
              templates           composition         intelligence
```

## Application Examples

### Monolithic-Lean
**Characteristics**: Single file or simple application, uses proven patterns
**Examples**: 
- Command-line tools with template selection
- Single-page applications with standard libraries
- Configuration-driven applications

**When appropriate**: Individual developers, rapid prototyping, simple requirements

### Monolithic-Architected
**Characteristics**: Structured application with defined layers and processes
**Examples**:
- MVC web applications with established patterns
- Desktop applications following design patterns
- Traditional three-tier applications

**When appropriate**: Small to medium teams, stable requirements, proven domain

### Monolithic-Intelligent
**Characteristics**: Single application with AI/ML capabilities or adaptive behavior
**Examples**:
- Applications with embedded recommendation engines
- Self-tuning database systems
- Context-aware user interfaces

**When appropriate**: Single-system AI applications, personalization requirements

### Modular-Lean
**Characteristics**: Plugin or component system using simple patterns
**Examples**:
- Plugin-based editors or IDEs
- Component libraries with clear interfaces
- Framework with extension points

**When appropriate**: Extensibility needed, community contributions expected

### Modular-Architected
**Characteristics**: Well-defined module system with governance
**Examples**:
- Enterprise application platforms
- CMS systems with plugin ecosystems
- Package-based systems with version management

**When appropriate**: Large teams, enterprise requirements, compliance needs

### Modular-Intelligent
**Characteristics**: Module system with dynamic selection or configuration
**Examples**:
- Auto-configuring module systems
- Context-aware plugin selection
- Adaptive middleware platforms

**When appropriate**: Complex integration scenarios, dynamic environments

### Multi-agent-Lean
**Characteristics**: Multiple services using simple patterns
**Examples**:
- Microservices with standardized communication
- Containerized applications with clear contracts
- Parallel processing workers

**When appropriate**: Scalability needs, team autonomy, proven service patterns

### Multi-agent-Architected
**Characteristics**: Orchestrated services with defined workflows
**Examples**:
- Service meshes with governance
- Enterprise service buses
- Workflow orchestration platforms

**When appropriate**: Complex business processes, multiple teams, compliance requirements

### Multi-agent-Intelligent
**Characteristics**: Distributed AI systems or adaptive service networks
**Examples**:
- Multi-agent AI systems
- Self-organizing service networks
- Distributed machine learning platforms

**When appropriate**: Complex AI workloads, autonomous systems, research applications

## Decision Framework

### Coupling Selection Criteria

**Choose Monolithic when**:
- Single team ownership
- Low complexity requirements
- Startup or MVP phase
- Performance-critical applications
- Simple deployment requirements

**Choose Modular when**:
- Extensibility required
- Multiple teams contributing
- Plugin ecosystem desired
- Phased feature rollout
- Library or framework development

**Choose Multi-agent when**:
- Independent scaling needs
- Polyglot requirements (multiple languages)
- Organizational boundaries align with services
- High availability requirements
- Complex distributed workflows

### Methodology Selection Criteria

**Choose Lean when**:
- Speed to market critical
- Proven domain with known patterns
- Small team or individual developer
- Low complexity requirements
- Iteration speed more important than process

**Choose Architected when**:
- Repeatability required
- Compliance or audit needs
- Multiple teams requiring coordination
- Long-term maintenance expected
- Quality gates necessary

**Choose Intelligent when**:
- Complex decision-making required
- Adaptation to changing conditions needed
- Large-scale data processing
- Personalization or recommendation requirements
- Research or experimental projects

## Anti-Patterns

**Distributed Monolith**: Multi-agent architecture with monolithic coupling (tight dependencies between services)

**Over-Architected Simplicity**: Lean problem solved with architected approach (excessive process for simple task)

**Premature Intelligence**: Intelligent approach when lean patterns would suffice (AI/ML where rules-based logic appropriate)

**Modular Monolith Confusion**: Claiming modular architecture while maintaining monolithic deployment and coupling

## Evolution Paths

### Common Progressions

**Monolithic-Lean → Monolithic-Architected**: As system matures and team grows

**Monolithic-Architected → Modular-Architected**: When extensibility becomes requirement

**Modular-Architected → Multi-agent-Architected**: When independent scaling or deployment needed

**Lean → Architected**: When repeatability and quality gates become necessary

**Architected → Intelligent**: When automation of decision-making provides value

### Warning Signs for Migration

**Monolithic limitations**:
- Deployment coordination blocks teams
- Codebase too large for effective ownership
- Scaling requirements differ by component

**Methodology limitations**:
- Lean: Repeatability issues, quality problems, scaling team size
- Architected: Process overhead slowing delivery, bureaucracy over value
- Intelligent: Unnecessary complexity, debugging difficulty, explainability needs

## Hybrid Approaches

**Reality**: Most large systems combine multiple approaches

**Examples**:
- Monolithic core with modular extensions
- Multi-agent system with architected governance and lean service implementation
- Intelligent components within architected framework

**Guideline**: Choose appropriate approach for each subsystem based on its specific requirements rather than forcing single methodology across entire system.
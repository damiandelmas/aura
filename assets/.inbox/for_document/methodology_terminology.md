# Software Development Methodology Terminology

## Lean Software Development

### Origins
Adapted from Toyota Production System and lean manufacturing principles by Mary and Tom Poppendieck in 2003.

### Seven Principles

**1. Eliminate Waste**
- Unnecessary code or functionality
- Delays in development process
- Unclear or changing requirements
- Bureaucratic overhead
- Slow internal communication
- Quality defects requiring rework

**2. Amplify Learning**
- Short iteration cycles for rapid feedback
- Retrospectives to capture lessons learned
- Code reviews and pair programming
- Documentation of decisions and rationale
- Experimentation and prototyping

**3. Decide as Late as Possible**
- Keep options open until cost of delay exceeds value of information
- Make decisions based on facts rather than speculation
- Defer commitment until last responsible moment
- Enable reversible decisions through loose coupling

**4. Deliver as Fast as Possible**
- Minimize time from idea to deployment
- Reduce work-in-progress
- Continuous integration and deployment
- Eliminate delays and bottlenecks

**5. Empower the Team**
- Respect developers as domain experts
- Enable decision-making at execution level
- Provide context rather than detailed instructions
- Trust team to find best solutions

**6. Build Integrity In**
- Refactor continuously
- Test-driven development
- Automated quality checks
- Architectural standards and reviews

**7. See the Whole**
- Optimize entire value stream, not individual parts
- Understand system-level effects of local decisions
- Consider long-term maintainability
- Balance speed with sustainability

### Relationship to Agile

Lean and Agile are complementary:
- Agile focuses on development process (sprints, user stories, standups)
- Lean focuses on value stream and waste elimination
- Both emphasize iterative development and rapid feedback
- Lean provides analytical framework for optimizing Agile practices

### Common Misconceptions

**Not equivalent to "minimal"**: Lean means optimized, not sparse or feature-poor
**Not anti-documentation**: Lean opposes wasteful documentation, not useful documentation
**Not just for startups**: Applicable to organizations of any size
**Not anti-planning**: Opposes over-planning and premature decisions

## Agile Development

### Agile Manifesto Values (2001)

**Individuals and interactions** over processes and tools
**Working software** over comprehensive documentation
**Customer collaboration** over contract negotiation
**Responding to change** over following a plan

### Twelve Principles

1. Satisfy customer through early and continuous delivery
2. Welcome changing requirements, even late in development
3. Deliver working software frequently (weeks, not months)
4. Business people and developers work together daily
5. Build projects around motivated individuals
6. Face-to-face conversation is most efficient communication
7. Working software is primary measure of progress
8. Sustainable development pace indefinitely
9. Continuous attention to technical excellence and good design
10. Simplicity - maximizing work not done
11. Self-organizing teams produce best architectures and designs
12. Regular reflection and adjustment of behavior

### Common Frameworks

**Scrum**: Sprints, daily standups, sprint planning, retrospectives
**Kanban**: Visual workflow, work-in-progress limits, continuous flow
**Extreme Programming (XP)**: Pair programming, TDD, continuous integration, small releases
**Lean Startup**: Build-measure-learn cycles, validated learning, pivot or persevere

## SOLID Principles (Object-Oriented Design)

Introduced by Robert C. Martin (Uncle Bob)

**S - Single Responsibility Principle**
- A class should have only one reason to change
- Each class addresses a single concern
- Promotes high cohesion, low coupling

**O - Open/Closed Principle**
- Open for extension, closed for modification
- Add new functionality without changing existing code
- Achieved through interfaces, inheritance, composition

**L - Liskov Substitution Principle**
- Subtypes must be substitutable for their base types
- Derived classes must not violate base class contracts
- Ensures proper inheritance hierarchies

**I - Interface Segregation Principle**
- Clients should not depend on interfaces they don't use
- Many specific interfaces better than one general-purpose interface
- Prevents fat interfaces with unused methods

**D - Dependency Inversion Principle**
- High-level modules should not depend on low-level modules
- Both should depend on abstractions
- Abstractions should not depend on details

## DRY, KISS, YAGNI

### DRY (Don't Repeat Yourself)
**Definition**: Every piece of knowledge must have a single, unambiguous representation in a system

**Application**:
- Extract duplicated code into functions
- Use configuration instead of hardcoded values
- Apply inheritance or composition for shared behavior

**Trade-off**: Can lead to premature abstraction if applied too rigidly

### KISS (Keep It Simple, Stupid)
**Definition**: Systems work best when kept simple rather than made complex

**Application**:
- Prefer simple solutions over clever ones
- Avoid unnecessary complexity
- Write code for humans to read
- Choose clarity over brevity

**Trade-off**: Sometimes complexity is essential - KISS means appropriate simplicity, not oversimplification

### YAGNI (You Aren't Gonna Need It)
**Definition**: Don't implement functionality until it is actually needed

**Context**: Extreme Programming principle

**Application**:
- Avoid speculative generality
- Build for current requirements, not potential future needs
- Refactor when new requirements emerge

**Trade-off**: May require more refactoring later, but avoids wasted effort on unused features

## Technical Debt

### Definition
Coined by Ward Cunningham: The implied cost of additional rework caused by choosing easy solution now instead of better approach that would take longer.

### Types

**Deliberate Technical Debt**: Conscious decision to ship quickly, with plan to refactor
**Accidental Technical Debt**: Unintended due to lack of knowledge or poor practices
**Bit Rot**: Code degradation over time as environment evolves

### Technical Debt Quadrant (Martin Fowler)

```
              Reckless    |    Prudent
Deliberate    "We don't   |    "We must ship now
              have time"  |    and deal with
                          |    consequences"
--------------+-----------|------------------
Inadvertent   "What's     |    "Now we know
              layering?"  |    how we should
                          |    have done it"
```

### Management

**Measurement**: Technical Debt Ratio = Remediation Cost / Development Cost
**Tracking**: Maintain technical debt backlog
**Repayment**: Allocate percentage of sprint capacity to debt reduction
**Prevention**: Code reviews, automated testing, architectural standards

## Domain-Driven Design (DDD)

Introduced by Eric Evans in 2003

### Core Concepts

**Ubiquitous Language**: Shared vocabulary between domain experts and developers

**Bounded Context**: Explicit boundary within which a model applies

**Entities**: Objects with unique identity that persists over time

**Value Objects**: Objects defined by their attributes, not identity

**Aggregates**: Cluster of entities and value objects with consistency boundary

**Domain Events**: Something significant that happened in the domain

**Repositories**: Abstraction for accessing aggregate roots

### Strategic Design

**Context Mapping**: Understanding relationships between bounded contexts
**Anti-Corruption Layer**: Translate between different bounded contexts
**Shared Kernel**: Subset of model shared by multiple contexts

### Relationship to Microservices

Bounded contexts often map to microservice boundaries, making DDD valuable for distributed system architecture.

## DevOps

### Definition
Integration of software development (Dev) and IT operations (Ops) to shorten development lifecycle while delivering features, fixes, and updates frequently.

### Core Practices

**Continuous Integration (CI)**: Merge code changes frequently, automated testing
**Continuous Deployment (CD)**: Automated deployment to production
**Infrastructure as Code**: Manage infrastructure through code and version control
**Monitoring and Logging**: Observability of system behavior
**Microservices**: Architectural approach enabling independent deployment

### Cultural Aspects

**Collaboration**: Breaking down silos between development and operations
**Automation**: Reduce manual processes and human error
**Measurement**: Data-driven decision making
**Sharing**: Transparent communication and knowledge sharing

### Tools Ecosystem

**CI/CD**: Jenkins, GitLab CI, GitHub Actions, CircleCI
**Containers**: Docker, Kubernetes
**Infrastructure**: Terraform, Ansible, CloudFormation
**Monitoring**: Prometheus, Grafana, ELK stack

## DORA Metrics

Developed by DevOps Research and Assessment (acquired by Google)

### Four Key Metrics

**Deployment Frequency**: How often code is deployed to production
**Lead Time for Changes**: Time from code commit to production deployment
**Mean Time to Recovery (MTTR)**: Time to restore service after incident
**Change Failure Rate**: Percentage of deployments causing production failures

### Performance Levels

**Elite**: Deploy multiple times per day, lead time < 1 hour, MTTR < 1 hour, change failure rate < 15%
**High**: Deploy weekly to monthly, lead time 1 day to 1 week, MTTR < 1 day, change failure rate 16-30%
**Medium**: Deploy monthly to semi-annually, lead time 1 week to 1 month, MTTR 1 day to 1 week, change failure rate 31-45%
**Low**: Deploy less than semi-annually, lead time > 6 months, MTTR > 1 week, change failure rate > 45%

### Application

Organizations use DORA metrics to:
- Benchmark performance against industry
- Identify improvement opportunities
- Track impact of process changes
- Justify investments in automation
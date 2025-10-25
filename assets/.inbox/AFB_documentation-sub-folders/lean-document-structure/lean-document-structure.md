Lean Documentation Structure
Based on your existing folders, here's what would actually help your team:
architecture/
Real stuff people need to know:

system-overview.md - How the pieces fit together
data-flow.md - How data moves through the system
deployment.md - How to run it, ports, dependencies
decisions.md - Key choices and why (not formal ADRs)

functionality/
What it actually does:

core-features.md - What the system provides
api-reference.md - How to use it
troubleshooting.md - When things break
examples.md - Copy-paste working code

methodology/
How we work:

development.md - How to contribute, setup, test
deployment.md - How to ship changes
standards.md - Code style, naming, patterns we actually follow
#### workflow

formalize the process for VISION control.

formalize the process for R&D. How do we manage knowledge?
	LINK to `document` or `URL` + language-agnostic summary of 'what' and 'why'
	KNOWLEDGE REGISTRY

formalize the process for linking `plan` to `implement`
	we should know exactly what plan was used for an implementation.
	this can be managed post facto by the develop-log agent

**IMPLEMENTATION GRAPH**
session-id (conversation) + develop log + implementation plan (and all associated design documents)
	IN: WHAT is the most agile method to enable this?

DESIGN should be treated as an all-encompassing staging area for development.
Architecture documents, planning documents should be version controlled.
They should be created like a pseudo-codebase.
- [ ] test using git sub-module for the .context folder
	- [ ] design/architecture VS document/architecture: can these be 'diffed' to have a VISION vs REALITY drift tracker?

changes
modules

each module should have changes in it that track progress towards a complete plan for implementation. the OMEGA of design is a flawless implementation plan.

when we have several modules, we want them to accomodate one another. as such we might want each to have their own 'architecture' folder. and then an aggregated 'architecture' folder that attempts to merge all modules into one.

this enables multiple parallel streams of design. we could pull out the 'diff' and ensure alignment before implementation. we really just need to sus out what is being changed, what that means for the architecture, and how that enables the vision. IS the vision being changed? DOES the document/architecture need to change to accomodate this?
	WHAT is the `type` of plan? Refactor? Extension? etc
	We can use this to resolve the degree of accomodation, conflict of current staged implementation plans.

we should have a dashboard for design. it should become its own codebase.
what are we designing? what does this mean for the codebase? how can we structure this knowledge to 'on-board' any new ai agent?
	on-board for implementation
	on-board for design
what is the `PROMPT + document package` for implementation?
what is the `PROMPT + document package` for design?

We should never be starting from scratch for ANY conversation. There is NO POINT to have to on-board any new conversation to the vision. It takes 30 minutes to an hour just to align on vision. This should happen immediately. Each new conversation should have a clear and concise understanding of the vision. UNLESS - we need counter points, counter arguments, critical thought & constructive criticism. This should be an AGENT or a `PROMPT + document package`.

Note: All PROMPT + document packages are eventually `imem compose {{query}}` calls.

DESIGN changes should be extremely concise. This is a timeline of research and development. There are many divergent paths and potentially conflicting approachings emerging here. It should work as an anti-drift document package.

Each module would contain its own diverse set of brainstorming, auditing, research etc. We don't want to have to move files into other folders. We should enable messy organization at this point. /.changes/ simply enables a reliable way of block-chaining ideation and design. It creates the knowledge graph foundation.

VISION
It's better to capture insights and vision in messy, unformatted, rough language than perfect & authoritative markdown. These are the core anti-drift logs.

There would be an overall VISION. then there would be a VISION for each design module. 

##### SANDBOX

.claude
	.conversations


.context/.registry/knowledge
.context/.registry/skills?

.context/.vision/ >>> |ANTI-DRIFT|
	architecture, core-user-messages, business logic

design/.changes
design/.modules

design/refactor-cli/.changes
design/refactor-cli/.stages
design/refactor-cli/.plan
design/refactor-cli/.vision

NEED:
SOP for testing the ACTUAL codebase not TDD tests
SOP for sandbox creations, worktrees etc

document
	runbooks <<< slash commands, agents etc?
	architecture

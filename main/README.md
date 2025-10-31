# HSX Project Documentation Package

This `main/` folder captures the top-level documentation flow for the HSX runtime and tooling initiative.  
Use it to align mandate, study, architecture, and design efforts before diving into feature or refactor packages.

## Document Map
1. `(0)context.md` — Snapshot of project scope, stakeholders, and current phase.
2. `(1)mandate.md` — Leadership mandate defining goals, scope, and success metrics.
3. `(2)study.md` — Feasibility analysis, key questions, options, and decisions.
4. `(3)architecture.md` — High-level system decomposition and guiding principles.
5. `(4)design.md` — Overview linking to detailed system/toolkit designs.
   - `(4.1)system_design.md` — MiniVM, executive, mailbox, runtime services.
   - `(4.2)toolkit_design.md` — Shell, debugger, tooling, packaging.
6. `(5)dod.md` — Definition of done for the project-level design package.

## Usage Guidance
- Update these documents when the project mandate changes, major decisions are made, or milestones are re-sequenced.
- Feature-specific details live under `functionality/` and refactor efforts under `refactor/`; reference this package to ensure alignment.
- Keep `docs/hsx_spec-v2.md` and `MILESTONES.md` in sync with any changes recorded here.

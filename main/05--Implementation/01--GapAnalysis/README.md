# Gap Analysis Workspace

This directory hosts the implementation gap analysis that maps the intent of each numbered design document in `main/04--Design/` to the current product state. The goal is to make it obvious what parts of the design have shipped, what is in flight, and which items still need specification or implementation work.

## Layout

- Create one sub-folder per numbered design document, reusing the same numeric prefix as the source material (for example `01--Scheduler`, `02--Mailbox`, etc.).
- Inside every sub-folder add a `01--Study.md` file that captures the gap analysis for that specific design. You can grow the folder with supporting artefacts when needed (raw notes, checklists, evidence links), but keep `01--Study.md` as the canonical summary.

## `01--Study.md` Contents

Each study file should answer four questions:

1. **Scope recap** — a short synopsis of the design document and links back into `main/04--Design/`.
2. **Current implementation** — what already exists today (code paths, tests, tools, documentation) that satisfy the design intent.
3. **Missing or partial coverage** — the gaps that block full compliance, including open bugs, deferred features, or documentation work.
4. **Next actions** — ordered steps or owners that will close the gaps, ideally cross-referenced with issues, milestones, or TODO items.

Feel free to add tables or status tags when that improves clarity, but keep the structure lightweight enough for quick updates.

## How to Use

1. Pick a design document in `main/04--Design/`.
2. Mirror its number and name here, create the folder if it does not exist, and seed `01--Study.md` using the outline above.
3. Update the study whenever we land work that changes the implementation status or when new requirements surface.

This approach keeps the design-to-implementation contract transparent and gives every contributor a predictable place to look when validating scope or planning new work.

# Study Reference Rework Plan

## Goal
Establish traceability between the study document (`main/(2)study.md`), architecture views (`main/(3)architecture/…`), and design specs (`main/(4)design/…`). The study should use labelled “Design Goals” (DG) and optional “Design Options” (DO) for each section so architecture/design documents can cite them directly.

## Proposed labelling

| New label | Study section | Notes |
|-----------|---------------|-------|
| DG-1.x | Context / Mandate summary | High-level goals already captured in `(0)` and `(1)` docs; cross-reference only where necessary. |
| DG-2.x | Problem Frame & Inspirations | Architecture documents should cite specific DG-2.* items when explaining structural decisions. |
| DG-3.x | Toolchain & Artefact Studies (current `## Toolchain & Artefact Studies`) | `### Assembler & Object Model` → DG-3.1, etc. |
| DG-4.x | MiniVM Study | Assign major/minor numbers per subsection. |
| DG-5.x | Executive / Scheduler Study | Links to `(3.2)` and `(4.2)` docs. |
| DG-6.x | Mailbox Study | Links to `(3.3)` and `(4.3)`. |
| DG-7.x | Value/Command Study | Links to `(3.4)` and `(4.4)`. |
| DG-8.x | Toolkit Study | Links to `(4.6)toolkit.md`. |
| DO-* | Optional explorations | Mark optional paths (e.g., alternative TUI frameworks, future relay) for completeness without implying mandatory design. |

## Playbook
- [ ] Draft DG/DO numbering scheme for each section of `main/(2)study.md`.
- [ ] Update `main/(2)study.md` headings to include DG/DO tags (e.g., `### DG-3.1 Assembler & Object Model`).
- [ ] Insert cross-reference guidelines in `main/(3)architecture` docs (e.g., cite DG-3.1 when discussing toolchain expectations).
- [ ] Update design specs under `main/(4)design/` to reference relevant DG/DO IDs at the start of each section.
- [ ] Add “Preconditions” and “Postconditions” sections to each design doc (`(4.1)`–`(4.7)`) outlining required system state and expected deliverables.
- [ ] Keep `docs/executive_protocol.md` and other shared references aligned with new DG/DO tags where applicable.

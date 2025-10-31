# Study Reference Rework Plan

## Goal
Establish traceability between the study document ([02--Study/02--Study.md](../02--Study/02--Study.md)), architecture views ([03--Architecture](../03--Architecture/)), and design specs ([04--Design](../04--Design/)). The study should use labelled "Design Goals" (DG) and optional "Design Options" (DO) for each section so architecture/design documents can cite them directly.

## Proposed labelling

| New label | Study section | Notes |
|-----------|---------------|-------|
| DG-1.x | Context / Mandate summary | High-level goals already captured in `(0)` and `(1)` docs; cross-reference only where necessary. |
| DG-2.x | Problem Frame & Inspirations | Architecture documents should cite specific DG-2.* items when explaining structural decisions. |
| DG-3.x | Toolchain & Artefact Studies (current `## Toolchain & Artefact Studies`) | `### Assembler & Object Model` → DG-3.1, etc. |
| DG-4.x | MiniVM Study | Assign major/minor numbers per subsection. |
| DG-5.x | Executive / Scheduler Study | Links to `[03.02--Executive](../03--Architecture/03.02--Executive.md)` and `[04.02--Executive](../04--Design/04.02--Executive.md)` docs. |
| DG-6.x | Mailbox Study | Links to `[03.03--Mailbox](../03--Architecture/03.03--Mailbox.md)` and `[04.03--Mailbox](../04--Design/04.03--Mailbox.md)`. |
| DG-7.x | Value/Command Study | Links to `[03.04--ValCmd](../03--Architecture/03.04--ValCmd.md)` and `[04.04--ValCmd](../04--Design/04.04--ValCmd.md)`. |
| DG-8.x | Toolkit Study | Links to [04.06--Toolkit.md](../04--Design/04.06--Toolkit.md). |
| DO-* | Optional explorations | Mark optional paths (e.g., alternative TUI frameworks, future relay) for completeness without implying mandatory design. |

## Playbook
- [ ] Draft DG/DO numbering scheme for each section of [02--Study/02--Study.md](../02--Study/02--Study.md).
- [ ] Update [02--Study/02--Study.md](../02--Study/02--Study.md) headings to include DG/DO tags (e.g., `### DG-3.1 Assembler & Object Model`).
- [ ] Insert cross-reference guidelines in [03--Architecture](../03--Architecture/) docs (e.g., cite DG-3.1 when discussing toolchain expectations).
- [ ] Update design specs under [04--Design](../04--Design/) to reference relevant DG/DO IDs at the start of each section.
- [ ] Add “Preconditions” and “Postconditions” sections to each design doc ([04.01](../04--Design/04.01--VM.md)–[04.07](../04--Design/04.07--Provisioning.md)) outlining required system state and expected deliverables.
- [ ] Keep [docs/executive_protocol.md](../../docs/executive_protocol.md) and other shared references aligned with new DG/DO tags where applicable.

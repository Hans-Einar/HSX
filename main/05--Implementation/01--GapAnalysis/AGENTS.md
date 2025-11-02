# Gap Analysis - Coordination Agent Guide

This directory orchestrates progress across all implementation tracks. Use this guide when working at the "grand plan" level.

## 1. Mandatory Reading (in order)
1. `../04--Design/04.00--Design.md` – design governance and cross-module assumptions.
2. `GrandImplementationPlan.md` – master schedule (python-first) and quality gates.
3. `GrandImplementationNotes.md` – current module status / last updates.
4. `DependencyTree.md` – historical dependency map; reference when sequencing work.
5. Module-specific `AGENTS.md`, `02--ImplementationPlan.md`, `03--ImplementationNotes.md` before delegating or diving into a module.

## 2. Coordination Workflow
### Pre-Planning
- [ ] Confirm design documents exist and cover the upcoming work.
- [ ] Identify upcoming review gates (design, implementation, integration).
- [ ] Ensure module plans reference the correct design section(s).

### During Planning / Execution
- [ ] Validate that each module is following the design-first checklist (see module `AGENTS.md`).
- [ ] Schedule incremental reviews (design → implementation → integration → comprehensive) and record them in the plan.
- [ ] Track Definition of Done compliance across modules.

### Post-Execution
- [ ] Update module notes/logs and `GrandImplementationNotes.md` with outcomes.
- [ ] Flag any design document updates that were required and ensure the design owner closes the loop.
- [ ] Adjust `GrandImplementationPlan.md` if sequencing or dependencies change.

## 3. Process Expectations
- **Design-first**: every module task must cite the authoritative design section and feed back clarifications.
- **Bidirectional traceability**: if implementation changes behaviour, update the design document and note it in the plan.
- **Quality gates**:
  1. Design review (before implementation starts).
  2. Implementation review (phase completion).
  3. Integration review (before cross-module usage).
  4. Comprehensive review (before stress / release).
- **Definition of Done (global)**:
  - Implementation matches the referenced design section.
  - Tests updated/executed; results logged.
  - Implementation notes updated with outcomes and follow-ups.
  - Design documents amended if reality diverges.
  - Git log / progress trackers refreshed.

## 4. General Rules
- Stay python-first; defer C ports until the plan explicitly calls for them.
- Keep documentation in sync (design ↔ plan ↔ notes ↔ code).
- Use pytest or targeted scripts for regression coverage and log commands/results.
- If pausing work, leave clear TODOs in both module notes and the grand notes.

Thanks for coordinating! This layer keeps the whole implementation effort aligned with the design contract.

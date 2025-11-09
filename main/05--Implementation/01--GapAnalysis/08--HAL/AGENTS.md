# HAL Implementation - Agent Guide

## 1. Mandatory Reading (in order)
1. **Design Spec** - `../../../04--Design/04.08--HAL.md` (driver responsibilities, syscall contracts, peripheral state machines). Treat this as authoritative.
2. **Retrospective** - `../Retrospective.md` for current process expectations.
3. **Grand Plan** - `../GrandImplementationPlan.md` (sequencing, review gates).
4. **Module Plan** - `02--ImplementationPlan.md` (phase tasks, dependencies, acceptance criteria).
5. **Implementation Notes** - `03--ImplementationNotes.md` (recent work, open questions).
6. **DependencyTree.md** when coordinating with Executive, Mailbox, or Provisioning milestones.

## 2. Design Alignment & Checklists
### Design Review Checklist
- [ ] Read the relevant sections of 04.08 before coding (peripheral API, IRQ flow, shared buffers).
- [ ] Record ambiguities in `03--ImplementationNotes.md` and resolve them quickly.
- [ ] Update 04.08 whenever syscall behaviour, descriptor layouts, or timing guarantees change.
- [ ] Keep driver tables and register maps in sync with implementation.

### Definition of Done
- [ ] Implementation conforms to the referenced design sections.
- [ ] Tests added/updated and executed; commands/results logged in the notes.
- [ ] `02--ImplementationPlan.md` status updated; blockers surfaced early.
- [ ] Design doc amended (or follow-up filed) for any behaviour/API drift.
- [ ] `04--git.md` entry written when changes land, citing design sections touched.
- [ ] Review gates (design -> implementation -> integration) completed.

## 3. Workflow
### Pre-Implementation
- [ ] Review the design subsection for the targeted peripheral.
- [ ] Confirm dependencies (Executive events, Mailbox surfaces, Toolchain headers) are ready.
- [ ] Log planned tests and coordination needs in the notes.
- [ ] Align with Provisioning/Toolchain owners when shared assets change.

### Implementation
- [ ] Execute tasks as outlined in `02--ImplementationPlan.md`.
- [ ] Keep design and plan docs synchronized as decisions are made.
- [ ] Run targeted suites (`python/tests/test_hal_*`, `python/tests/test_mailbox_manager.py`, integration smoke tests) and capture outcomes.
- [ ] Draft design updates while context is fresh.

### Post-Implementation
- [ ] Complete the Definition of Done checklist.
- [ ] Document session summary, design references, tests, and next steps in `03--ImplementationNotes.md`.
- [ ] Update cross-module trackers (`../GrandImplementationNotes.md`) when status changes.
- [ ] Prepare review artifacts if nearing a gate.

## 4. Testing
- Prioritize HAL regression suites (`python/tests/test_hal_*`, hardware simulation tests) and affected integration suites.
- Record every command and result in the notes for traceability.
- When touching ISR timing or buffering, add stress/soak tests per plan.

## 5. Reviews & Hand-off
- Schedule design reviews before altering syscall contracts.
- Seek implementation review at phase completion; integration review before exposing new APIs to apps.
- Leave explicit TODOs/blockers in the notes when pausing work.
- Update `04--git.md` when commits are prepared, referencing design deltas.

Follow this guide to keep HAL development aligned with the design contract and maintain smooth hand-offs between agents.

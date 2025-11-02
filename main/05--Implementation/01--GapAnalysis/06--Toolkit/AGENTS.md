# Toolkit Implementation - Agent Guide

## 1. Mandatory Reading (in order)
1. **Design Spec** – `../../../04--Design/04.06--Toolkit.md` (CLI/TUI utilities, helper scripts).
2. **Retrospective** – `../Retrospective.md` for process improvements.
3. **Grand Plan** – `../GrandImplementationPlan.md` (sequencing, review gates).
4. **Module Plan** – `02--ImplementationPlan.md` (phase breakdown, checklists).
5. **Implementation Notes** – `03--ImplementationNotes.md` (latest work).
6. **DependencyTree.md** when coordinating with Executive/Toolchain deliverables.

## 2. Design Alignment & Checklists
### Design Document Review Checklist
- [ ] Read relevant sections of 04.06 before coding (CLI behaviour, UX expectations, telemetry tools).
- [ ] Log ambiguities/questions in `03--ImplementationNotes.md` and resolve them.
- [ ] Update 04.06 when workflows/UI change.
- [ ] Ensure user stories/command references remain accurate.

### Definition of Done
- [ ] Implementation matches the referenced design section(s).
- [ ] Tests/CLI scripts executed; results documented in notes.
- [ ] `02--ImplementationPlan.md` and `03--ImplementationNotes.md` updated.
- [ ] Design doc amended (or follow-up filed) if behaviour changed.
- [ ] `04--git.md` log entry added once changes land.
- [ ] Review gates satisfied (design → implementation → integration).

## 3. Workflow
### Pre-Implementation
- [ ] Read the design section covering the tool/workflow being updated.
- [ ] Review outstanding tasks/dependencies in the plan.
- [ ] Capture open design questions in the notes.
- [ ] Confirm the next review gate is scheduled.

### Implementation
- [ ] Follow the task checklist in `02--ImplementationPlan.md`.
- [ ] Keep design documentation and plan aligned with decisions.
- [ ] Run relevant tests/scripts (`python/tests/test_toolkit_*`, smoke tests, CLI demos) and capture results.
- [ ] Draft design doc updates for UI/CLI changes while context is fresh.

### Post-Implementation
- [ ] Complete the Definition of Done checklist.
- [ ] Update design doc or log follow-up tasks for outstanding changes.
- [ ] Record session summary, tests, and follow-ups in `03--ImplementationNotes.md`.
- [ ] Update cross-module trackers (`../GrandImplementationNotes.md`) if status changes.

## 4. Testing
- Use targeted suites (`python/tests/test_toolkit_*`, CLI smoke tests, integration demos).
- Log commands/outcomes in the notes.
- When coordinating with Executive/Toolchain, run end-to-end flows indicated in the plan.

## 5. Reviews & Hand-off
- Observe incremental reviews (design/implementation/integration).
- Leave explicit TODOs/blockers in the notes if pausing work.
- Update `04--git.md` after preparing commits, referencing design sections where updated.

Follow this guide to keep Toolkit development aligned with the design contract and maintain smooth hand-offs. Happy hacking!

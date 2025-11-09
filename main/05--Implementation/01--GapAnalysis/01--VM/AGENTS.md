# VM Implementation - Agent Guide

## 1. Mandatory Reading (in order)
1. **Design Spec** – `../../../04--Design/04.01--VM.md` (ISA, PSW, loader, etc.). This is the authoritative contract.
2. **Retrospective** – `../Retrospective.md` for current process adjustments.
3. **Grand Plan** – `../GrandImplementationPlan.md` (module sequencing, quality gates).
4. **Module Plan** – `02--ImplementationPlan.md` (phase detail & checklists).
5. **Implementation Notes** – `03--ImplementationNotes.md` (what the last session accomplished).
6. **DependencyTree.md** when VM work impacts other modules.

## 2. Design Alignment & Checklists
### Design Document Review Checklist
- [ ] Read the relevant portion of 04.01 before coding.
- [ ] Log ambiguities/questions in `03--ImplementationNotes.md`.
- [ ] Update 04.01 when opcode/behaviour diverges from the spec.
- [ ] Confirm tables (opcode map, PSW flags, memory layout) remain accurate.

### Definition of Done
- [ ] Implementation conforms to the referenced design section(s).
- [ ] Tests added/updated and executed (unit + integration); results recorded.
- [ ] `02--ImplementationPlan.md` and `03--ImplementationNotes.md` updated.
- [ ] Design document amended or follow-up filed for any changes.
- [ ] `04--git.md` entry updated once changes land.
- [ ] Review gates (design/implementation/integration) satisfied.

## 3. Workflow
### Pre-Implementation
- [ ] Read design section(s), note clarifications.
- [ ] Review plan dependencies and outstanding TODOs.
- [ ] Capture open design questions in `03--ImplementationNotes.md`.
- [ ] Confirm upcoming review gate is scheduled.

### Implementation
- [ ] Follow the task checklist in `02--ImplementationPlan.md`.
- [ ] Keep design and plan in sync as decisions are made.
- [ ] Run targeted pytest suites (`python/tests/test_vm_*`, `python/tests/test_ir_*`, etc.) and capture results.
- [ ] Draft design updates (opcode table, PSW notes, etc.) as needed.

### Post-Implementation
- [ ] Complete Definition of Done checklist.
- [ ] Update design doc or log a follow-up issue.
- [ ] Record session summary/tests/follow-ups in `03--ImplementationNotes.md`.
- [ ] Update `../GrandImplementationNotes.md` if schedule/phase status changes.

## 4. Testing
- Prefer focused suites first (`python/tests/test_vm_*`, `python/tests/test_ir_*`, `python/tests/test_linker.py`, etc.).
- Log command lines and outcomes in the session notes.
- Coordinate cross-module tests when plan specifies (e.g., loader + executive interactions).

## 5. Reviews & Hand-off
- Honour incremental reviews (design → implementation → integration).
- Leave explicit TODOs/blockers in the notes for the next agent.
- Update `04--git.md` once commits are prepared, including design doc references if updated.

Adhering to this guide keeps VM development aligned with the design contract and ensures seamless agent hand-offs. Happy hacking!

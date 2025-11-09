# ValCmd Implementation - Agent Guide

## 1. Mandatory Reading (in order)
1. **Design Spec** – `../../../04--Design/04.04--ValCmd.md` (value & command services). This is the authoritative specification.
2. **Retrospective** – `../Retrospective.md` for the latest process expectations.
3. **Grand Plan** – `../GrandImplementationPlan.md` (module sequencing, review gates).
4. **Module Plan** – `02--ImplementationPlan.md` (phase breakdown, checklists).
5. **Implementation Notes** – `03--ImplementationNotes.md` (recent session context).
6. **DependencyTree.md`** when coordinating with Mailbox/Executive interactions.

## 2. Design Alignment & Checklists
### Design Document Review Checklist
- [ ] Read the relevant sections of 04.04 before coding.
- [ ] Log ambiguities/questions in `03--ImplementationNotes.md` and resolve them.
- [ ] Update 04.04 whenever APIs/behaviours diverge or clarifications are made.
- [ ] Ensure opcode/command/value tables remain accurate and complete.

### Definition of Done
- [ ] Implementation conforms to the referenced design sections.
- [ ] Tests added/updated and executed; results logged in notes.
- [ ] `02--ImplementationPlan.md` and `03--ImplementationNotes.md` updated.
- [ ] Design doc amended (or follow-up filed) if behaviour changed.
- [ ] `04--git.md` log entry added once changes land.
- [ ] Required review gates (design → implementation → integration) satisfied.

## 3. Workflow
### Pre-Implementation
- [ ] Read design sections covering the target feature (value ops, command routing, etc.).
- [ ] Review outstanding plan items and dependencies.
- [ ] Capture open design questions in the notes.
- [ ] Confirm upcoming review gate is scheduled.

### Implementation
- [ ] Follow the task checklist in `02--ImplementationPlan.md`.
- [ ] Keep design and plan in sync as decisions are made.
- [ ] Run targeted pytest suites (`python/tests/test_valcmd_*`, `python/tests/test_executive_sessions.py`, etc.) and capture results.
- [ ] Draft design updates as new behaviours are implemented.

### Post-Implementation
- [ ] Complete the Definition of Done checklist above.
- [ ] Update the design doc or log follow-up tasks for any outstanding changes.
- [ ] Record session summary, tests, and next steps in `03--ImplementationNotes.md`.
- [ ] Update cross-module trackers (`../GrandImplementationNotes.md`) if status/priorities change.

## 4. Testing
- Focus on relevant suites (`python/tests/test_valcmd_*`, `python/tests/test_exec_mailbox.py`, integration tests once available).
- Log commands and outcomes in the notes.
- For cross-module flows (Mailbox/Executive), coordinate as specified in the plan.

## 5. Reviews & Hand-off
- Honour incremental reviews:
  - Design review before new capability work.
  - Implementation review at phase completion.
  - Integration review before exposing APIs to downstream consumers.
- Leave explicit TODOs/blockers in the notes when pausing work.
- Update `04--git.md` once commits are prepared, including design references where updated.

Follow this guide to keep ValCmd development aligned with the design contract and maintain clean hand-offs between agents. Happy hacking!

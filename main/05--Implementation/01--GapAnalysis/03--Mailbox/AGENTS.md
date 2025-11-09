# Mailbox Implementation - Agent Guide

Welcome! This guide captures the working agreement for the Mailbox module.

## 1. Mandatory Reading (in order)
1. **Design Spec** – `../../../04--Design/04.03--Mailbox.md` (authoritative contract). Read the section(s) for your task before writing code.
2. **Retrospective** – `../Retrospective.md` (current process improvements).
3. **Grand Plan** – `../GrandImplementationPlan.md` (module sequencing & review gates).
4. **Module Plan** – `02--ImplementationPlan.md` (phase details, checklists).
5. **Implementation Notes** – `03--ImplementationNotes.md` (latest session log and open questions).
6. **Dependency Tree** – `../DependencyTree.md` when cross-module interactions are involved.

## 2. Design Alignment & Checklists
### Design Document Review Checklist
- [ ] Confirm the referenced section(s) in 04.03 cover the work you are about to implement.
- [ ] Capture ambiguities or contradictions in `03--ImplementationNotes.md`.
- [ ] If implementation reveals new behaviour or constraints, update the design document (or open a follow-up task).
- [ ] Ensure opcode/API/status tables remain accurate.

### Definition of Done (module-specific)
- [ ] Implementation matches the referenced design sections.
- [ ] Tests added/updated and executed; results recorded in `03--ImplementationNotes.md`.
- [ ] `02--ImplementationPlan.md` progress boxes updated.
- [ ] `03--ImplementationNotes.md` session entry added with tests & follow-ups.
- [ ] Design document updated or annotated when behaviour diverges.
- [ ] `04--git.md` log updated once changes land.

## 3. Workflow
### Pre-Implementation
- [ ] Read the relevant design section(s) and note clarifications.
- [ ] Review plan dependencies and outstanding TODOs.
- [ ] Document open design questions in `03--ImplementationNotes.md`.
- [ ] Verify required review gate (design/implementation/integration) is scheduled.

### Implementation
- [ ] Work the checklist in `02--ImplementationPlan.md` for the active task.
- [ ] Keep design doc and plan in sync as decisions are made.
- [ ] Run targeted pytest suites and capture output in notes.
- [ ] If design updates are required, draft them while context is fresh.

### Post-Implementation
- [ ] Complete the Definition of Done checklist.
- [ ] Update design documentation (or file follow-up items) before closing the task.
- [ ] Record work summary, tests, next steps in `03--ImplementationNotes.md`.
- [ ] Update `../GrandImplementationNotes.md` when progress affects cross-module scheduling.

## 4. Testing
- Use focused suites first (`python/tests/test_mailbox_*`, `python/tests/test_executive_sessions.py`, etc.).
- Document command lines and outcomes in the session notes.
- For integration/regression tests, reference the plan’s test matrix and log any gaps.

## 5. Reviews & Hand-off
- Incremental reviews are mandatory:
  - Design review before a new phase starts.
  - Implementation review when a phase completes.
  - Integration review before cross-module consumers rely on the feature.
- Leave clear TODOs and blockers in `03--ImplementationNotes.md` if work continues later.
- Update `04--git.md` once commits are prepared; note if design docs were touched.

Following this workflow keeps the implementation aligned with the design contract and ensures future agents can resume work without losing context. Happy hacking!

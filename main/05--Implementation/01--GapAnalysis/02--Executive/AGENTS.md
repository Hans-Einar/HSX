# Executive Implementation - Agent Guide

## 1. Mandatory Reading (in order)
1. **Design Spec** – `../../../04--Design/04.02--Executive.md` (authoritative behaviour, RPCs, scheduler contract).
2. **Retrospective** – `../Retrospective.md` for current process adjustments.
3. **Grand Plan** – `../GrandImplementationPlan.md` for sequencing and quality gates.
4. **Module Plan** – `02--ImplementationPlan.md` (phase detail & checklists).
5. **Implementation Notes** – `03--ImplementationNotes.md` for last-session context.
6. **DependencyTree.md`** when coordinating with VM/Mailbox dependencies.

## 2. Design Alignment & Checklists
### Design Document Review Checklist
- [ ] Read the relevant section of 04.02 before coding.
- [ ] Capture ambiguities in `03--ImplementationNotes.md`; resolve or escalate.
- [ ] Update 04.02 when new behaviour or constraints emerge.
- [ ] Ensure RPC tables, state diagrams, and event schemas remain accurate.

### Definition of Done
- [ ] Implementation matches the referenced design section(s).
- [ ] Tests added/updated and executed; results logged.
- [ ] `02--ImplementationPlan.md` and `03--ImplementationNotes.md` updated.
- [ ] Design document updated (or follow-up filed) when behaviour differs.
- [ ] `04--git.md` entry added after changes land.
- [ ] Incremental reviews (design/implementation/integration) completed or scheduled.

## 3. Workflow
### Pre-Implementation
- [ ] Read design spec section(s) and note clarifications.
- [ ] Review outstanding TODOs and dependencies in the module plan.
- [ ] Log open questions/risks in `03--ImplementationNotes.md`.
- [ ] Confirm which review gate (design/implementation/integration) applies and line it up.

### Implementation
- [ ] Follow the checklist for the active task in `02--ImplementationPlan.md`.
- [ ] Keep design and plan synced with decisions.
- [ ] Run targeted pytest suites (`python/tests/test_executive_*`, etc.) and capture results.
- [ ] Draft design doc updates as behavioural decisions are made.

### Post-Implementation
- [ ] Complete the Definition of Done checklist.
- [ ] Update design docs or create follow-up tasks for any changes.
- [ ] Record session summary, tests, follow-ups in `03--ImplementationNotes.md`.
- [ ] Update cross-module trackers (`../GrandImplementationNotes.md`) if priorities shift.

## 4. Testing
- Focus on relevant suites first (`python/tests/test_executive_*`, `python/tests/test_shell_client.py`, etc.).
- Log commands/outcomes in session notes.
- For integration scenarios, coordinate with VM/Mailbox tests as specified in the plan.

## 5. Reviews & Hand-off
- Respect the incremental review cadence:
  - Design review before new capability work.
  - Implementation review when a phase completes.
  - Integration review before exposing new RPCs/events to downstream consumers.
- Leave clear TODOs/blockers in the notes if work continues later.
- Update `04--git.md` once commits are prepared and include any design updates.

Following this guide keeps executive development aligned with the design contract and provides smooth hand-offs between agents. Happy hacking!

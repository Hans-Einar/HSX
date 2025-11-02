# TUI Debugger Implementation - Agent Guide

## 1. Mandatory Reading (in order)
1. **Design Spec** - `../../../04--Design/04.10--TUI_Debugger.md` (interface layout, navigation flows, event wiring). Authoritative reference.
2. **Retrospective** - `../Retrospective.md` for current process expectations.
3. **Grand Plan** - `../GrandImplementationPlan.md` (cross-module sequencing, review gates).
4. **Module Plan** - `02--ImplementationPlan.md` (phase tasks, dependencies, acceptance criteria).
5. **Implementation Notes** - `03--ImplementationNotes.md` (session history, open issues).
6. **DependencyTree.md** when coordinating with Executive, CLI Debugger, or Toolkit deliverables.

## 2. Design Alignment & Checklists
### Design Review Checklist
- [ ] Read the relevant sections of 04.10 before coding (UI layout, key bindings, event subscriptions).
- [ ] Log ambiguities in `03--ImplementationNotes.md` and resolve quickly.
- [ ] Update 04.10 whenever UI/UX, shortcuts, or data bindings change.
- [ ] Keep mock-ups, screen flows, and feature tables aligned with implementation.

### Definition of Done
- [ ] Implementation conforms to the referenced design sections.
- [ ] Tests/demos executed; commands/results logged in the notes.
- [ ] `02--ImplementationPlan.md` status updated as tasks progress; blockers surfaced.
- [ ] Design doc amended (or follow-up filed) for any UX/behaviour drift.
- [ ] `04--git.md` entry added once changes land, citing design sections touched.
- [ ] Review gates (design -> implementation -> integration) completed.

## 3. Workflow
### Pre-Implementation
- [ ] Review the design section for the UI panel or workflow being implemented.
- [ ] Confirm dependencies (Executive events, CLI debugger APIs, Toolkit helpers) are ready.
- [ ] Log planned demos/tests and coordination needs in the notes.
- [ ] Sync with CLI/VSCode debugger owners when shared components evolve.

### Implementation
- [ ] Execute tasks as outlined in `02--ImplementationPlan.md`.
- [ ] Keep design and plan docs synchronized as decisions occur.
- [ ] Run targeted tests (`python/tests/test_tui_debugger.py`, UI smoke tests) and record outcomes.
- [ ] Capture design updates and screenshots while context is fresh.

### Post-Implementation
- [ ] Complete the Definition of Done checklist.
- [ ] Document session summary, design references, tests, and next steps in `03--ImplementationNotes.md`.
- [ ] Update cross-module trackers (`../GrandImplementationNotes.md`) when status changes.
- [ ] Prepare materials for upcoming review gates (demos, screenshots).

## 4. Testing
- Exercise TUI smoke tests and automated suites where available.
- Run end-to-end debugger workflows with the Executive once events are wired.
- Log every command/demo result in the notes for traceability.

## 5. Reviews & Hand-off
- Schedule design reviews before altering UX flows or visual design.
- Seek implementation review at phase completion; integration review before releasing to users.
- Leave explicit TODOs/blockers in the notes when pausing work.
- Update `04--git.md` after preparing commits, referencing design changes and assets updated.

Follow this guide to keep the TUI debugger aligned with design expectations and maintain smooth hand-offs between agents.

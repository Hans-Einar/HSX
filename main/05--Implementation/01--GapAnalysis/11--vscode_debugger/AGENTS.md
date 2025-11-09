# VS Code Debugger Implementation - Agent Guide

## 1. Mandatory Reading (in order)
1. **Design Spec** - `../../../04--Design/04.11--vscode_debugger.md` (DAP integration, extension packaging, UX flows). Authoritative source.
2. **Retrospective** - `../Retrospective.md` for current process improvements.
3. **Grand Plan** - `../GrandImplementationPlan.md` (cross-module sequencing, review gates).
4. **Module Plan** - `02--ImplementationPlan.md` (phase tasks, dependencies, acceptance criteria).
5. **Implementation Notes** - `03--ImplementationNotes.md` (session history, open issues).
6. **DependencyTree.md** when coordinating with Executive, CLI/TUI debugger, or Toolkit deliverables.

## 2. Design Alignment & Checklists
### Design Review Checklist
- [ ] Read the relevant sections of 04.11 before coding (DAP message flow, configuration, UI contributions).
- [ ] Log ambiguities in `03--ImplementationNotes.md` and resolve them promptly.
- [ ] Update 04.11 whenever commands, launch configs, or contributed views change.
- [ ] Keep protocol tables and extension manifests in sync with implementation.

### Definition of Done
- [ ] Implementation conforms to the referenced design sections.
- [ ] Tests/demos executed; commands/results logged in the notes.
- [ ] `02--ImplementationPlan.md` status updated and blockers surfaced.
- [ ] Design doc amended (or follow-up filed) for behaviour/API drift.
- [ ] `04--git.md` entry recorded after changes land, citing design sections touched.
- [ ] Review gates (design -> implementation -> integration) completed.

## 3. Workflow
### Pre-Implementation
- [ ] Review design sections covering the feature (DAP requests, UI integration, packaging).
- [ ] Confirm dependencies (Executive endpoints, CLI debugger helpers, Toolkit utilities) are ready.
- [ ] Log planned tests (unit, integration, VS Code smoke) and coordination needs in the notes.
- [ ] Align with CLI/TUI debugger owners when shared assets evolve.

### Implementation
- [ ] Execute tasks as outlined in `02--ImplementationPlan.md`.
- [ ] Keep design and plan documentation synchronized with decisions.
- [ ] Run targeted suites (`python/tests/test_vscode_debugger.py`, extension smoke tests) and record outcomes.
- [ ] Draft design updates while context is fresh.

### Post-Implementation
- [ ] Complete the Definition of Done checklist.
- [ ] Document session summary, design references, tests, and next steps in `03--ImplementationNotes.md`.
- [ ] Update cross-module trackers (`../GrandImplementationNotes.md`) as status changes.
- [ ] Prepare artefacts for review gates (demo scripts, screenshots).

## 4. Testing
- Exercise automated tests and extension smoke suites per plan.
- Validate DAP flows against both Executive simulators and live sessions.
- Record every command/demo result in the notes for traceability.

## 5. Reviews & Hand-off
- Schedule design reviews before changing DAP schema or extension UI.
- Seek implementation review at phase completion; integration review before publishing builds.
- Leave explicit TODOs/blockers in the notes when pausing work.
- Update `04--git.md` when commits are prepared, referencing design updates and assets changed.

Follow this guide to keep VS Code debugger development aligned with design expectations and enable smooth hand-offs.

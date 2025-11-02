# CLI Debugger Implementation - Agent Guide

## 1. Mandatory Reading (in order)
1. **Design Spec** - `../../../04--Design/04.09--Debugger.md` (command set, event model, UX flows). Primary reference.
2. **Retrospective** - `../Retrospective.md` for the latest process guidance.
3. **Grand Plan** - `../GrandImplementationPlan.md` (cross-module sequencing, review gates).
4. **Module Plan** - `02--ImplementationPlan.md` (phase tasks, dependencies, acceptance criteria).
5. **Implementation Notes** - `03--ImplementationNotes.md` (recent progress, open issues).
6. **DependencyTree.md** when coordinating with Executive, Mailbox, or Toolkit updates.

## 2. Design Alignment & Checklists
### Design Review Checklist
- [ ] Read the relevant sections of 04.09 before coding (command parsing, session wiring, breakpoint UX).
- [ ] Record ambiguities in `03--ImplementationNotes.md` and resolve them quickly.
- [ ] Update 04.09 when command semantics, event shapes, or UX affordances change.
- [ ] Ensure help text and CLI usage align with the design spec tables.

### Definition of Done
- [ ] Implementation matches the referenced design sections.
- [ ] Tests added/updated and executed; commands/results logged in the notes.
- [ ] `02--ImplementationPlan.md` status kept current; blockers surfaced.
- [ ] Design doc updated (or follow-up filed) for any behaviour delta.
- [ ] `04--git.md` entry added after changes land, citing design sections touched.
- [ ] Review gates (design -> implementation -> integration) completed.

## 3. Workflow
### Pre-Implementation
- [ ] Re-read design subsections for upcoming features (command grammar, output formatting, event subscriptions).
- [ ] Review plan dependencies (Executive event APIs, Provisioning data, Toolchain metadata).
- [ ] Log planned tests and open questions in the notes.
- [ ] Coordinate with Executive/Toolkit owners when shared clients change.

### Implementation
- [ ] Follow the task checklist in `02--ImplementationPlan.md`.
- [ ] Keep design and plan documentation synchronized as decisions occur.
- [ ] Run targeted suites (`python/tests/test_shell_client.py`, `python/tests/test_executive_sessions.py`, debugger-specific smoke tests) and record results.
- [ ] Draft design updates while details are fresh.

### Post-Implementation
- [ ] Complete the Definition of Done checklist.
- [ ] Document session summary, design references, tests, and follow-ups in `03--ImplementationNotes.md`.
- [ ] Update cross-module trackers (`../GrandImplementationNotes.md`) when status changes.
- [ ] Prepare artefacts for upcoming review gates.

## 4. Testing
- Focus on debugger-oriented suites (`python/tests/test_shell_client.py`, `python/tests/test_executive_sessions.py`, CLI integration demos).
- Exercise event-stream and breakpoint flows end-to-end once available.
- Log every command and outcome in the notes for traceability.

## 5. Reviews & Hand-off
- Schedule design reviews before expanding command sets or protocols.
- Seek implementation review at phase completion; integration review before exposing new UX to users.
- Leave explicit TODOs/blockers in the notes when pausing work.
- Update `04--git.md` after preparing commits, referencing design deltas and impacted components.

Follow this guide to keep debugger development aligned with the design contract and enable smooth hand-offs.

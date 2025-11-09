# Provisioning & Persistence Implementation - Agent Guide

## 1. Mandatory Reading (in order)
1. **Design Spec** - `../../../04--Design/04.07--Provisioning.md` (HXE metadata, streaming RPCs, transports). This is the source of truth.
2. **Retrospective** - `../Retrospective.md` for cross-module process expectations.
3. **Grand Plan** - `../GrandImplementationPlan.md` (module sequencing, review gates).
4. **Module Plan** - `02--ImplementationPlan.md` (phase breakdown, dependencies, acceptance criteria).
5. **Implementation Notes** - `03--ImplementationNotes.md` (latest sessions, open issues).
6. **DependencyTree.md** when coordinating with Executive, Mailbox, or Toolchain milestones.

## 2. Design Alignment & Checklists
### Design Review Checklist
- [ ] Read the relevant sections of 04.07 before coding (metadata schema, RPC flows, transport contracts).
- [ ] Capture ambiguities/questions in `03--ImplementationNotes.md` and resolve them quickly.
- [ ] Update 04.07 when behaviour, state machines, or RPC payloads change.
- [ ] Keep provisioning state diagrams and sequence charts in sync with implementation.

### Definition of Done
- [ ] Implementation matches the referenced design sections.
- [ ] Tests added/updated and executed; commands/results logged in the notes.
- [ ] `02--ImplementationPlan.md` checkboxes kept current; blockers recorded.
- [ ] Design doc updated (or follow-up filed) for any behaviour/API delta.
- [ ] `04--git.md` entry written after changes land, citing design sections touched.
- [ ] Required review gates (design -> implementation -> integration) completed.

## 3. Workflow
### Pre-Implementation
- [ ] Re-read the design subsection that covers the upcoming feature.
- [ ] Review plan dependencies and confirm prerequisites are satisfied.
- [ ] Log open design questions and expected tests in the notes.
- [ ] Coordinate with Executive/Mailbox owners when shared interfaces change.

### Implementation
- [ ] Follow the task checklist in `02--ImplementationPlan.md`.
- [ ] Keep design/plan docs aligned as decisions are taken.
- [ ] Run targeted suites (`python/tests/test_provisioning_*`, `python/tests/test_vm_stream_loader.py`, executive integration tests) and capture outcomes.
- [ ] Draft design updates while context is fresh.

### Post-Implementation
- [ ] Complete the Definition of Done checklist.
- [ ] Document the session (summary, design references, tests, next steps) in `03--ImplementationNotes.md`.
- [ ] Update cross-module trackers (`../GrandImplementationNotes.md`) when scope/status changes.
- [ ] Prep review materials if the phase reaches a gate.

## 4. Testing
- Target provisioning-specific suites first (`python/tests/test_provisioning_*`, `python/tests/test_hxe_v2_metadata.py`, executive loader tests).
- When transports or persistence touch disk/network, include smoke tests per plan.
- Record every command, result, and failure in the notes for traceability.

## 5. Reviews & Hand-off
- Schedule design reviews before introducing new metadata/RPCs.
- Seek implementation review at phase completion; integration review before exposing new APIs.
- Leave explicit TODOs/blockers in the notes when pausing work.
- Update `04--git.md` once commits are ready, referencing the design deltas.

Follow this guide to keep provisioning work aligned with the design contract and ensure clean hand-offs between agents.

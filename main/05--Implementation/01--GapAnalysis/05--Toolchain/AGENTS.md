# Toolchain Implementation - Agent Guide

## 1. Mandatory Reading (in order)
1. **Design Spec** – `../../../04--Design/04.05--Toolchain.md` (assembler, linker, build scripts).
2. **Retrospective** – `../Retrospective.md` for latest process improvements.
3. **Grand Plan** – `../GrandImplementationPlan.md` (sequencing, review gates).
4. **Module Plan** – `02--ImplementationPlan.md` (phase breakdown, checklists).
5. **Implementation Notes** – `03--ImplementationNotes.md` (recent activity).
6. **DependencyTree.md** when coordinating with VM/Executive/Mailbox deliverables.

## 2. Design Alignment & Checklists
### Design Document Review Checklist
- [ ] Read relevant parts of 04.05 before coding (MVASM syntax, HXO/HXE format, pragma handling).
- [ ] Log ambiguities/questions in `03--ImplementationNotes.md` and resolve them.
- [ ] Update 04.05 when new directives/flags/formats are introduced.
- [ ] Ensure tables (opcode metadata, section formats) remain accurate.

### Definition of Done
- [ ] Implementation matches design specification.
- [ ] Tests updated/executed (`python/tests/test_hsx_cc_build.py`, `python/tests/test_linker*.py`, etc.); results logged.
- [ ] `02--ImplementationPlan.md` and `03--ImplementationNotes.md` updated.
- [ ] Design documentation amended (or follow-up filed) if behaviour changed.
- [ ] `04--git.md` log entry recorded when changes land.
- [ ] Review gates satisfied (design → implementation → integration).

## 3. Workflow
### Pre-Implementation
- [ ] Read the design section covering the target feature (pragma handling, metadata, packaging, etc.).
- [ ] Review outstanding tasks/dependencies in the plan.
- [ ] Capture open design questions in the notes.
- [ ] Confirm upcoming review gate is arranged.

### Implementation
- [ ] Follow the checklist in `02--ImplementationPlan.md`.
- [ ] Keep design doc and plan aligned with decisions.
- [ ] Run targeted pytest suites (`python/tests/test_hsx_cc_build.py`, `python/tests/test_linker*.py`, `python/tests/test_vm_stream_loader.py`, etc.).
- [ ] Draft design doc updates for new directives/formats while context is fresh.

### Post-Implementation
- [ ] Complete the Definition of Done checklist.
- [ ] Update design doc or log follow-up tasks as needed.
- [ ] Record session summary, tests, and follow-ups in `03--ImplementationNotes.md`.
- [ ] Update cross-module trackers (`../GrandImplementationNotes.md`) if schedule/status changes.

## 4. Testing
- Focus on relevant suites first (`python/tests/test_hsx_cc_build.py`, `python/tests/test_linker*.py`, `python/tests/test_hxe_v2_metadata.py`, etc.).
- Log command lines and results in the notes.
- Execute end-to-end flows (hsx-cc-build, assembler+linker) when phases require integration validation.

## 5. Reviews & Hand-off
- Honour incremental reviews:
  - Design review before changing formats/directives.
  - Implementation review at phase completion.
  - Integration review before consumers rely on new toolchain features.
- Leave explicit TODOs/blockers in the notes when pausing work.
- Update `04--git.md` after preparing commits, including design references where applicable.

Use this guide to keep toolchain development aligned with the design contract and maintain smooth hand-offs between agents. Happy hacking!

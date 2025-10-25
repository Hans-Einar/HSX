# AGENTS — Phase & Documentation Guide

## Phase Checklist
- [x] Architecture phase complete — `main/(3)architecture/` captures the stable high-level structure. Only revisit these files when the architecture itself changes.
- [x] Design phase active — track open design tasks via `main/(4)design/playbook.md`. Detailed interface semantics belong under `main/(4)design/`.
- [ ] Implementation phase — will begin once design playbook items reach sign-off.
- [ ] Validation / Release — populate when implementation stabilises and test plans are locked.

## Working Notes for Contributors
- Architecture docs (`main/(3)architecture/*.md`) stay high-level: describe components, relationships, and guiding principles. Avoid embedding detailed ABI tables, magic numbers, or module identifiers here.
- Design docs (`main/(4)design/*.md`) house normative specifications: exact SVC module/function IDs, data structures, timeout rules, state diagrams, etc. Update these as design decisions solidify.
- When transitioning between phases, update the checklist above and note the primary coordination artifact (currently `main/(4)design/playbook.md`).
- Cross-reference implementation artefacts (e.g., Python prototype, native headers) from design docs rather than from architecture files to keep the phase boundaries clear.

# AGENTS – Phase & Documentation Guide

## Phase Checklist
- [x] Architecture phase complete – [03--Architecture](03--Architecture/) captures the stable high-level structure. Only revisit these files when the architecture itself changes.
- [x] Design phase active – track open design tasks via [04--Design/playbook.md](04--Design/playbook.md). Detailed interface semantics belong under [04--Design](04--Design/).
- [ ] Implementation phase – will begin once design playbook items reach sign-off.
- [ ] Validation / Release – populate when implementation stabilises and test plans are locked.

## Working Notes for Contributors
- Architecture docs ([03--Architecture](03--Architecture/)) stay high-level: describe components, relationships, and guiding principles. Avoid embedding detailed ABI tables, magic numbers, or module identifiers here.
- Design docs ([04--Design](04--Design/)) house normative specifications: exact SVC module/function IDs, data structures, timeout rules, state diagrams, etc. Update these as design decisions solidify.
- When transitioning between phases, update the checklist above and note the primary coordination artifact (currently [04--Design/playbook.md](04--Design/playbook.md)).
- Cross-reference implementation artefacts (e.g., Python prototype, native headers) from design docs rather than from architecture files to keep the phase boundaries clear.

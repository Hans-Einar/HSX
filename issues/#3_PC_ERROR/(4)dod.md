# Definition of Done — #3 JMP immediate sign-extension corrupts PC

## TL;DR
- Issue summary: `./(1)issue.md`
- Review summary: `./(2)review.md`
- Remediation summary: `./(3)remediation.md`

## Quick Links
- Issue description: `./(1)issue.md`
- Review: `./(2)review.md`
- Remediation plan: `./(3)remediation.md`
- Implementation playbook: `./(5)implementation.md`
- Git log: `./(6)git.md`

## Completion Checklist
- [ ] Review approved (`(2)review.md`)
- [ ] Remediation plan approved (`(3)remediation.md`)
- [x] Implementation tasks complete (see below)
- [ ] Tests updated/passing
- [ ] Documentation updated
- [x] Implementation playbook current (`(5)implementation.md`)
- [ ] Git log updated (`(6)git.md`)
- [ ] Stakeholders signed off

## Implementation Tasks
- [x] T1: Runtime fix for unsigned jump immediates
  - [x] Update `MiniVM.step` control-flow handling
  - [x] Validate mailbox producer demo end-to-end
- [x] T2: Toolchain/test updates for jump formatting
  - [x] Extend assembler/disassembler output and add regression tests
- [ ] T3: Documentation refresh
  - [ ] Update ISA spec and trace/disasm help text

## Verification
- [x] Unit tests added/updated: `python/tests` (new VM jump regression)
- [ ] Integration tests updated: `examples/demos/mailbox`
- [x] Manual validation complete: `producer.hxe trace (max 64 steps)`

## Notes / Follow-ups
- Await ISA clarification confirming unsigned encoding before landing runtime change.
- Consider extending instruction width if future jumps require >12 bits.

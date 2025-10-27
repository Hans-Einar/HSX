# Definition of Done — #3 JMP immediate sign-extension corrupts PC

## TL;DR
- Issue summary: `./(1)issue.md`
- Study summary: `./(2)study.md`
- Remediation summary: `./(3)remediation.md`

## Quick Links
- Issue description: `./(1)issue.md`
- Study: `./(2)study.md`
- Remediation plan: `./(3)remediation.md`
- Implementation playbook: `./(5)implementation.md`
- Git log: `./(6)git.md`

## Completion Checklist
- [x] Study approved (`(2)study.md`)
- [x] Remediation plan approved (`(3)remediation.md`)
- [x] Implementation tasks complete (see below)
- [x] Tests updated/passing
- [x] Documentation updated
- [x] Implementation playbook current (`(5)implementation.md`)
- [x] Git log updated (`(6)git.md`)
- [ ] Stakeholders signed off

## Implementation Tasks
- [x] T1: Runtime fix for unsigned jump immediates
  - [x] Update `MiniVM.step` control-flow handling
  - [x] Validate mailbox producer demo end-to-end
- [x] T2: Toolchain/test updates for jump formatting
  - [x] Extend assembler/disassembler output and add regression tests
- [x] T3: Documentation refresh
  - [x] Update ISA spec and trace/disasm help text

## Verification
- [x] Unit tests added/updated: `python/tests` (new VM jump regression)
- [x] Integration tests updated: `examples/demos/mailbox` (`host_vm.py producer.hxe` trace run)
- [x] Manual validation complete: `producer.hxe trace (max 64 steps)`

## Notes / Follow-ups
- Documentation now captures unsigned branch immediates and clock telemetry; monitor for future ISA width extensions if >12-bit jumps become necessary.

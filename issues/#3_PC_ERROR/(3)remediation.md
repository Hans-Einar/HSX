# Remediation Plan — JMP immediate sign-extension corrupts PC

## Overview
- Owner(s): VM runtime + toolchain maintainers
- Target milestone / deadline: M4 mailbox validation (ASAP)
- Dependencies: clarification from ISA owners on absolute jump encoding width

## Objectives
- Ensure absolute jump/branch opcodes land in the intended 12-bit code address window.
- Keep signed immediates for load/store/ALU semantics while supporting unsigned control-flow targets.
- Provide regression coverage that fails if the PC underflows past the code segment.

## Work Breakdown
| Task ID | Description | Owner | Status | Notes |
| --- | --- | --- | --- | --- |
| T1 | Split immediate handling for control-flow opcodes and adjust VM execution | Runtime team | Not started | Requires ISA confirmation |
| T2 | Update assembler/disassembler formatting and add regression tests for high-address jumps | Toolchain team | Not started | Tests should include VM execution harness |
| T3 | Refresh docs/help text to explain unsigned branch immediates | Docs | Not started | Coordinate with spec maintainers |

### Detailed Steps

#### T1 Control-flow immediate fix
1. Update `MiniVM.step` to treat `JMP`/`JZ`/`JNZ` immediates as unsigned 12-bit values.
2. Adjust `decode_instruction` (and any assembler helpers) so only relevant opcodes apply sign extension.
3. Verify mailbox producer sample executes past the problematic jump without PC faults.

#### T2 Toolchain & regression updates
1. Extend assembler/disassembler to display both raw and effective addresses for jumps, matching runtime changes.
2. Add automated tests that execute `JMP 0x0A10` (and similar) verifying the PC becomes `0x00000A10`.
3. Integrate the regression into CI (`python/tests` or integration demos).

#### T3 Documentation refresh
1. Update `docs/hsx_spec.md` to explicitly state unsigned handling for absolute jumps.
2. Review CLI/help output for trace/disasm tools to mention the new formatting.
3. Announce the fix to stakeholders once merged.

## Verification Strategy
- Unit: add a VM step test that loads a single `JMP 0x0A10` instruction and asserts `vm.pc == 0x00000A10` after execution.
- Integration: rerun mailbox producer/consumer demos end-to-end.
- Manual: inspect trace/disassembly output to ensure both raw and effective addresses are shown correctly.

## Rollout Plan
- Create feature branch off latest `main`, land runtime fix first, then toolchain/tests, then docs.
- Monitor CI for regressions; coordinate with ISA owners before merging.
- Back-out plan: revert the runtime change and disable new tests if unexpected regressions surface.

## Communication
- Provide status updates in weekly runtime/toolchain syncs.
- Notify mailbox demo owners once regression passes.
- Update issue tracker (`(4)dod.md`) as milestones complete.

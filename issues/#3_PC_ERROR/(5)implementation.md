# Implementation Playbook — #3 JMP immediate sign-extension corrupts PC

## Task Tracker

### T1 Runtime fix (`not started`)
- [ ] Step 1 — Audit `MiniVM.step` and related helpers for signed immediate usage
  - Notes: Focus on `JMP`, `JZ`, `JNZ`, `CALL`
  - Artifacts: `platforms/python/host_vm.py`
- [ ] Step 2 — Implement unsigned decode path and add targeted unit test
- [ ] Step 3 — Validate mailbox producer demo executes without PC fault

### T2 Toolchain/tests (`not started`)
- [ ] Step 1 — Update assembler/disassembler operand rendering to include raw + effective addresses
- [ ] Step 2 — Add regression in `python/tests` covering `JMP 0x0A10`

### T3 Documentation (`not started`)
- [ ] Step 1 — Refresh ISA spec and tooling docs to state unsigned jump immediates

## Implementation Issues Log

### I1 `Unsigned jump semantics pending ISA confirmation` (`open`)
- **Summary:** Need authoritative answer on whether absolute jumps should be unsigned or expanded beyond 12 bits.
- **Review:** Current behaviour contradicts expected absolute addressing; runtime cannot proceed without clarification.
- **Remediation:** Schedule sync with ISA owner, capture outcome in remediation doc.
- **Implementation:**
  - Commits: TBD
  - Tests: TBD

## Context & Artifacts
- Source files / directories touched: `platforms/python/host_vm.py`, `python/disassemble.py`, `python/disasm_util.py`
- Test suites to run: `python/tests`, mailbox demos under `examples/demos`
- Commands / scripts used: `python platforms/python/host_vm.py <image> --trace`, targeted unit tests once added

## Handover Notes
- Current status: Issue logged; remediation tasks queued but not started.
- Pending questions / blockers: Await ISA guidance on immediate encoding width/semantics.
- Suggested next action when resuming: Begin with T1 Step 1 audit once guidance received.

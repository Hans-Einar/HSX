# Issue: JMP immediate sign-extension corrupts PC

- Working title: `JMP immediate sign-extension corrupts PC`
- Tracking ID: `#3`
- Reported by: `QA / mailbox demos`
- Date opened: `2025-10-16`

## Summary
- Absolute `JMP` instructions with targets above 0x07FF are decoded with a sign-extended 12-bit immediate, forcing the VM to jump to 0xFFFFxxxx instead of the intended code address.
- Affected samples (e.g. the mailbox producer demo) immediately fault with `PC 0xFFFFFA10 is outside code length ...`, making them impossible to run.

## Context
- Expected behaviour: absolute control-flow opcodes (e.g. `JMP`, `JZ`, `JNZ`) should treat the encoded address as an unsigned 12-bit field that lands in the 0x0000–0x0FFF code window, matching the HSX ISA documentation.
- Current behaviour: `decode_instruction` sign-extends the 12-bit field, so `0x0A10` becomes `-1520`; the VM then writes `PC=0xFFFFFA10` and the next fetch immediately trips the out-of-range guard.
- Environment: commit `afc408a9c7fbf1fbef98b60b88e22dc1067284da`, Python VM (`platforms/python/host_vm.py`) with default configuration.
- Reproduction steps:
  1. Assemble any program containing `JMP 0x0A10` (or run the mailbox producer demo).
  2. Execute it on the Python MiniVM (`python platforms/python/host_vm.py <program> --trace`).
  3. Observe the jump reporting `JMP 0xFFFFFA10 imm=-1520 (0xA10)` followed by `[VM] PC 0xFFFFFA10 is outside code length ...`.

## Evidence
- Minimal repro (single instruction image) highlights the faulty decode:
  ```text
  [TRACE] 0x0000: 0x21000A10 JMP 0xFFFFFA10 imm=-1520 (0xA10)
  [VM] PC 0xFFFFFA10 is outside code length 4
  ```
- The mailbox producer build exhibits the same failure once it reaches its mailbox-handling trampoline.

## Impact
- Severity: **High** — absolute jumps above 0x07FF are unusable, blocking large programs and demos that place code beyond the first 2 KiB.
- Affected components: Python MiniVM decoder/executor, assembler/disassembler output, all consumers relying on absolute branch targets.
- Dependencies: Blocks mailbox milestone validation and any demos that rely on generated linker layouts beyond the first code page.

## Stakeholders
- Owner: VM runtime team
- Reviewer(s): Toolchain maintainers
- Notified teams: Mailbox demo owners, scheduler/executive team

## Initial Notes / Hypotheses
- `decode_instruction` always sign-extends the 12-bit field; `JMP`/`JZ`/`JNZ` should treat it as unsigned while ALU immediates remain signed.
- Long-term fix likely needs ISA clarification and possible encoding change if more than 12 bits are required.
- Disassembler/trace outputs should surface both the raw field and the effective address to aid validation.

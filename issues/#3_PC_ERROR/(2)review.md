# Review — JMP immediate sign-extension corrupts PC

## Reviewer
- Name / role: gpt-5-codex (runtime analysis)
- Date: 2025-10-16
- Artifacts reviewed (code paths, commits, specs):
  - `platforms/python/host_vm.py::MiniVM.step`
  - `python/disassemble.py::decode_instruction`
  - HSX ISA notes in `docs/hsx_spec.md` (branch encoding overview)
  - Reproduction trace from minimal `JMP 0x0A10` image

## Spec & Contract References
- HSX ISA documentation expects absolute `JMP` immediates to address the 0x0000–0x0FFF code window without sign extension (see `docs/hsx_spec.md`, instruction encoding table).

## Observed Divergence
| Area | Expected behaviour | Actual behaviour | Evidence (logs/files) |
| --- | --- | --- | --- |
| MiniVM decode of absolute jumps | Load target from the 12-bit field as an unsigned address before writing PC. | The 12-bit field is sign-extended to `-1520`, yielding `PC=0xFFFFFA10` and immediate PC fault. | Minimal repro trace showing `JMP 0xFFFFFA10 imm=-1520 (0xA10)` followed by `[VM] PC 0xFFFFFA10 is outside code length 4`. |

## Root Cause Analysis
- `decode_instruction` globally sign-extends the 12-bit immediate and returns the signed value for all opcodes.
- `MiniVM.step` uses the signed value directly when executing `JMP`/`JZ`/`JNZ`, so any target >= 0x0800 underflows the PC.
- The assembler/disassembler mirror the same decode, so textual output also reports negative offsets, obscuring the intended absolute address.

## Suggested Direction
- Split immediate handling: keep sign extension for data/ALU immediates, but treat absolute control-flow fields as unsigned when computing the next PC.
- Update trace/disassembly helpers to surface both the raw field and the effective address for easier validation.
- Add regression tests that execute a `JMP` to an address above 0x0800 to ensure the PC lands inside the code region.

## Risks / Side Effects
- Changing immediate semantics may affect conditional branches or instructions that rely on signed offsets; we need to audit all consumers before flipping behaviour.
- Toolchain components (assembler, linker, optimizer) might encode relative jumps differently; ensure updated decode still matches encoded binaries.

## Sign-off / Next Steps
- Proceed to draft remediation plan capturing decoder split and regression coverage.
- Track implementation status in `(3)remediation.md` and `(5)implementation.md`.

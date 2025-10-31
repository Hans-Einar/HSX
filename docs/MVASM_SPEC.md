# MVASM Specification

> SDP Reference: 2025-10 Main Run (Design Playbook #11)

## Purpose
Define the human-readable assembly language consumed by `python/asm.py` so compiler, linker, and tooling teams share one authoritative contract. MVASM feeds the toolchain that emits `.hxo` objects and `.hxe` executables; this spec aligns with `docs/asm.md` and `docs/hxe_format.md`.

## Source File Structure
- MVASM files default to the `.text` section until `.data` switches context.
- Lines may contain labels, directives, instructions, or comments (`;` starts a comment).
- Identifiers must match `[A-Za-z_.][A-Za-z0-9_.$]*`.
- `.include "path.mvasm"` performs textual inclusion with loop detection; paths resolve relative to the including file.

```
.text
.entry
.extern _svc_stdio_write
main:
    LDI R1, 42
    MOV R0, R1
    RET
```

## Directives

| Directive | Arguments | Description |
|-----------|-----------|-------------|
| `.text` | — | Switch to the code section. Default when the file starts. |
| `.data` | — | Switch to the read-only data section (mapped at `RODATA_BASE`, currently 0x4000). |
| `.entry [symbol]` | optional symbol | Marks the entry point. Without an argument, uses the next label. |
| `.extern name` | symbol | Declares that the current unit exports `name`. |
| `.import name` | symbol | Declares that the current unit expects `name` to be resolved by the linker. |
| `.align <power-of-two>` | integer | Pads the current section to the requested alignment (bytes). |
| `.byte v1, …` | literals | Emits 8-bit values. Supports decimal/hex and character literals (`'A'`). |
| `.half v1, …` / `.hword` | literals | Emits 16-bit values. |
| `.word v1, …` | literals or symbol refs | Emits 32-bit values. Symbol operands may use `symbol`, `lo16(symbol)`, `hi16(symbol)`, or `off16(symbol)` to request relocations. |
| `.asciz "text"` / `.string "text"` | string literal | Emits UTF-8 bytes followed by `0x00`. Supports standard `\n`, `\r`, `\t`, `\\`, `\0`, `\xNN` escapes. |

## Registers and Operands
- HSX exposes 16 general-purpose registers `R0`–`R15`.
- `R0` conventionally carries return values; other caller/callee save rules are handled by the ABI.
- Immediate operands are signed 12-bit unless noted. Encodings that treat the field as unsigned (e.g., branch offsets, `SVC` module/function selectors) are handled automatically by the assembler.
- Memory operands use `LD Rd, [Rs + imm]` and `ST [Rs + imm], Rd` where `imm` is a 12-bit signed byte offset.

## Instruction Set Summary

| Category | Mnemonics | Notes |
|----------|-----------|-------|
| Data movement | `LDI`, `LD`, `ST`, `MOV`, `LDB`, `LDH`, `STB`, `STH`, `LDI32`, `PUSH`, `POP` | `LDI32` consumes two words: the opcode followed by a 32-bit literal. Byte/halfword loads sign-extend. |
| Integer ALU | `ADD`, `SUB`, `MUL`, `DIV`, `AND`, `OR`, `XOR`, `NOT`, `CMP` | All register-to-register; `CMP` writes condition codes in the PSW. |
| Control flow | `JMP`, `JZ`, `JNZ`, `CALL`, `RET`, `BRK` | `JZ/JNZ` test the provided register. `BRK` triggers a debugger stop. |
| Floating/FP helpers | `FADD`, `FSUB`, `FMUL`, `FDIV`, `I2F`, `F2I` | Operate on f16 values stored in 32-bit registers. |
| System services | `SVC mod, fn` | Encodes module/function IDs in the immediate field. Arguments travel in `R0`–`R3` per `docs/abi_syscalls.md`. |

Opcode values follow `OPC` in `python/asm.py`; tooling should treat mnemonics as the public contract while opcode IDs remain stable for the VM decoder.

## Labels and Relocations
- Labels end with `:` and bind to the current section offset.
- `CALL symbol`, `JMP label`, and similar forms create relocations resolved at link time.
- `lo16(symbol)`, `hi16(symbol)`, and `off16(symbol)` expressions can appear in immediate operands or data directives; the assembler emits explicit relocation records in the `.hxo` output (see `docs/asm.md`).

## System Call Usage
```
LDI R1, 'H'
LDI R2, 1          ; stdout handle per runtime convention
SVC 0x01, 0x01     ; module 1 (task control/UART), function 1 (UART_WRITE)
```
Refer to `docs/abi_syscalls.md` for definitive module/function tables and argument mapping.

## Example
```
.include "stdlib.mvasm"
.text
.entry main
main:
    LDI32 R1, 0x00010002   ; target mailbox descriptor
    LDI R2, msg
    SVC 0x05, 0x02         ; MAILBOX_SEND
    RET

.data
msg:
    .asciz "hello\n"
```

## Maintainer
- Hans Einar (HSX Project)
- Updated under the 2025-10 SDP run; future edits must retain this header note.

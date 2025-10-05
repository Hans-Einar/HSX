# 🧩 MVASM Specification (Machine–Virtual Assembly)

---

## 🧭 Overview

**MVASM** (“Machine–Virtual Assembly”) is the human‑readable assembly language for the **HSX Virtual Machine**.  
It maps directly to the HSX instruction set and is assembled by `asm.py` into executable `.hxe` binaries.

MVASM is not based on any external architecture (like AVR or ARM); it is **unique to HSX** and designed for:
- clarity when debugging LLVM lowering output
- deterministic translation to bytecode
- easy extension with pseudo‑ops (`.import`, `.data`, etc.)

---

## 📘 File extensions

| Type | Extension | Description |
|------|------------|-------------|
| Source | `.mvasm` | Human‑readable HSX assembly |
| Object | `.hxo` | Assembled relocatable object (future) |
| Executable | `.hxe` | Linked image for the VM |

---

## 🧱 File structure

An `.mvasm` file consists of **directives**, **labels**, and **instructions**:

```asm
.entry
; -- function main --
main:
main__entry:
LDI R1, 42
MOV R0, R1
RET
```

### Grammar overview

```
<file> ::= { <directive> | <label> | <instruction> | <comment> }

<directive> ::= '.' <keyword> [arguments]
<label>     ::= <identifier> ':'
<instruction> ::= <mnemonic> [operands]
<comment> ::= ';' <text>
```

---

## ⚙️ Directives

| Directive | Meaning |
|------------|----------|
| `.entry` | Marks the program entry point (first executed symbol) |
| `.import name` | Declares an imported function symbol (resolved by linker) |
| `.extern name` | Declares an external symbol provided by another module |
| `.data` | Begin a data segment (raw words or bytes) |
| `.text` | Begin a code segment (default if omitted) |

Example:
```asm
.text
.entry
.extern sinf
.import uart_send
```

---

## 🔤 Registers

HSX has **16 general registers** (`R0–R15`), each 32‑bit wide.  
- `R0` is used for function return values.  
- `R14` and `R15` are often reserved for stack / system usage (by convention).  

---

## 🔣 Instruction Syntax

All instructions have the general form:
```
MNEMONIC Rd, Rs1, Rs2 [imm]
```
where `imm` (immediate) is optional.

### Examples
| Instruction | Description |
|--------------|--------------|
| `LDI R1, 42` | Load immediate constant |
| `ADD R0, R1, R2` | Integer addition |
| `FADD R3, R4, R5` | Half‑precision addition |
| `F2I R0, R1` | Convert f16 → int32 |
| `CALL func` | Call function |
| `RET` | Return from function |
| `ST [R2+0], R1` | Store to memory |
| `LD R3, [R2+0]` | Load from memory |
| `SVC mod, fn` | System call (used for I/O, CAN, etc.) |

---

## 🧮 Arithmetic instructions

| Mnemonic | Meaning | Operands |
|-----------|----------|-----------|
| `ADD` | Integer add | Rd, Rs1, Rs2 |
| `SUB` | Integer subtract | Rd, Rs1, Rs2 |
| `MUL` | Integer multiply | Rd, Rs1, Rs2 |
| `DIV` | Integer divide | Rd, Rs1, Rs2 |
| `MOD` | Modulo | Rd, Rs1, Rs2 |

---

## 🔢 Floating‑point (f16) instructions

| Mnemonic | Description |
|-----------|--------------|
| `FADD` | Add f16 |
| `FSUB` | Subtract f16 |
| `FMUL` | Multiply f16 |
| `FDIV` | Divide f16 |
| `F2I` | Convert f16 → i32 |
| `I2F` | Convert i32 → f16 |
| `H2F` | Promote f16 → f32 |
| `F2H` | Demote f32 → f16 |

---

## 🧠 Control flow

| Mnemonic | Description |
|-----------|-------------|
| `JMP label` | Unconditional jump |
| `JNZ Rd, label` | Jump if Rd ≠ 0 |
| `CALL symbol` | Function call |
| `RET` | Return |

---

## 🧰 Memory access

| Mnemonic | Description |
|-----------|-------------|
| `LD Rd, [Rs + imm]` | Load from memory |
| `ST [Rs + imm], Rd` | Store to memory |

Addresses are word‑aligned (each word = 32 bits).

---

## 🧩 System Calls

System calls use the `SVC` instruction:

```
SVC mod, fn
```
- `mod` = subsystem (e.g., UART, CAN, FS, VAL, etc.)
- `fn` = function index within that module

Example:
```asm
LDI R1, 'H'
SVC 1, 0   ; UART.write
```

---

## 💾 Example Program

```asm
.entry
; Simple test that adds two values and halts
LDI R1, 5
LDI R2, 7
ADD R0, R1, R2
SVC 1, 0   ; print result
RET
```

---

## 📜 Assembler behavior

`asm.py` performs:
- label resolution and branch fixups
- recording of `.import` and `.extern` entries
- generation of 32‑bit instruction words
- writing HSX header (`HSXE` magic, CRC, entry point, word count)

Future `hld.py` linker will:
- resolve imports/externs
- merge `.data` and `.text` segments
- produce relocatable `.hxo` or final `.hxe` image.

---

**Maintainer:** Hans Einar (HSX Project)  
**Updated:** 2025‑10‑06  

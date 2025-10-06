# ⚙️ HSX Floating-Point Architecture

---

## 🧭 Overview

The **HSX Virtual Machine (VM)** adopts a *hybrid floating‑point model* that prioritizes deterministic behavior and compact code for embedded targets (especially AVR microcontrollers).  
This document describes the rationale, architecture, and relationship between **f16 (binary16)** and **f32 (binary32)** usage within HSX.

---

## 📘 Related Document
See also: [HSX_F16_GUIDE.md](HSX_F16_GUIDE.md)

---

## 🧮 Floating‑Point Layers

| Layer | Precision | Description |
|--------|-------------|-------------|
| **ISA / Register level** | f16 | Compact hardware‑neutral 16‑bit float |
| **C / Runtime compute layer** | f32 | Full 32‑bit precision for math libraries |
| **Storage / Communication** | f16 | Default format for HSX Value, FRAM, CAN |

---

## 🔠 ISA Design (VM-Level)

Current instruction set supports **only f16 natively**:

| Mnemonic | Description |
|-----------|--------------|
| `FADD Rd, Rs1, Rs2` | Add two f16 registers |
| `FSUB Rd, Rs1, Rs2` | Subtract two f16 registers |
| `FMUL Rd, Rs1, Rs2` | Multiply two f16 registers |
| `FDIV Rd, Rs1, Rs2` | Divide two f16 registers |
| `H2F Rd, Rs1` | Convert f16 → f32 |
| `F2H Rd, Rs1` | Convert f32 → f16 |

Each operation works on 16‑bit registers and assumes IEEE‑754 binary16 semantics.

---

## 🧩 C Runtime Integration

When compiling from C/LLVM:

- All C `float` and `double` expressions are computed in **f32** precision.  
- HSX backend automatically inserts `H2F` and `F2H` conversions when moving between the VM’s register file and runtime math functions.
- Functions such as `sin()`, `cos()`, `pow()`, etc., are resolved through a **soft‑float mathlib** or linked runtime (`libhsx_mathf32.a`).

Example:
```c
// C code
float y = sinf(x) + 0.5f;

// Lowered to pseudo‑HSX
H2F R1, R2     ; promote f16 → f32
CALL sinf
F2H R2, R1     ; demote result back to f16
```

---

## 🧩 Optional Future Extension: HSX‑F32 Set

Planned as an optional architecture extension for STM32 / host VMs with native FPUs.

| Mnemonic | Description |
|-----------|--------------|
| `F32ADD`, `F32SUB`, `F32MUL`, `F32DIV` | Native 32‑bit ops |
| `FMAC32` | Fused multiply‑add |
| `F32CMP`, `F32ABS`, `F32NEG` | Comparison and unary ops |

ISA identification: `HSX-F32` extension bit in header.

---

## 🧠 Rationale Summary

| Factor | f16 (Current) | f32 (Extension) |
|---------|----------------|----------------|
| Memory footprint | ✅ half | ⚙️ 2× |
| AVR compatibility | ✅ simple | ❌ heavy |
| Accuracy | ⚠️ moderate (3–4 digits) | ✅ full (7 digits) |
| VM complexity | ✅ minimal | ⚙️ medium |
| LLVM backend effort | ✅ easy | ❌ higher |

---

## ✅ Decision Summary

| Decision | Status |
|-----------|---------|
| Keep f16-only ISA for core HSX | ✅ |
| Use f32 internally in mathlib | ✅ |
| Define F2H/H2F conversion ops | ✅ |
| Reserve future HSX‑F32 extension | ⚙️ planned |

---

**Maintainer:** Hans Einar (HSX Project)  
**Updated:** 2025‑10‑04  

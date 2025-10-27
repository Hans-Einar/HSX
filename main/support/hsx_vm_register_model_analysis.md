# HSX VM Register Model Analysis
**Comparison: Workspace Pointer (WP) vs Copy-on-Attach (Shadow Registers)**  
*Pro-mode analysis, October 2025*

---

## 1. The two baselines

### A. Workspace-Pointer (WP) model
- Architectural registers live in memory at `WP + reg_offset`.
- Interpreter pins `WP` in a real host register for the whole timeslice.
- Each VM register access = one load/store using base+imm addressing.
- Context switch = write a new `WP` (and PC/flags), done.

### B. Copy-on-attach (Shadow file)
- On attach: copy K architectural regs from `[WP]` into host state (real registers or compiler locals).
- Execute using the shadow (ideally real host regs → near-zero per-access latency).
- On detach: flush back dirty regs (subset ρ of K).
- Context switch cost = copy in/out; per-instruction cost ≈ 0 if the shadow truly stays in registers.

⚠️ If the “shadow” spills to RAM, you pay the copy **and** still do memory traffic — worst of both worlds.

---

## 2. Detailed cost model

Let:

| Symbol | Meaning |
|:--|:--|
| K | Number of VM architectural registers |
| rR / rW | Average register reads / writes per VM instruction |
| N | VM instructions executed in one timeslice |
| Lr / Lw | Measured latency (cycles) of a load/store to the register bank |
| A | Addressing overhead (cycles) beyond the memory op (≈ 0 if base+imm) |
| ρ | Fraction of regs that end up dirty during the slice |
| Sspill | Per-access penalty if shadow spills |

### Formulas

**WP per timeslice**
```
T_wp ≈ N * (rR*(Lr + A) + rW*(Lw + A))
```

**Copy per timeslice**
```
T_cpy ≈ (K*Lr) + (ρ*K*Lw) + N*(rR + rW)*Sspill
```

Break-even:
```
T_cpy < T_wp
⇒ N > [ K*Lr + ρ*K*Lw ] / [ rR*(Lr+A−Sspill) + rW*(Lw+A−Sspill) ]
```

---

## 3. Micro-architectural realities

1. **Keep WP pinned** in a host register (callee-saved).
2. **Addressing add is usually free** with `[base + imm]`.
3. **Pack register slab** into ≤ 2 cache lines; align WP to cache-line boundary.
4. **Write costs** can exceed reads on simple MCUs; consider lazy write-back.
5. **Register pressure:** on Cortex-M / RV32 you can’t pin many shadows; compiler will spill.
6. **Immediate range limits:** avoid large offsets or use register windows.

---

## 4. Hybrids that punch above their weight

### 1) Hot-set mirror + dirty mask
Mirror the most frequently accessed 4–8 regs in host registers.  
Track a dirty bitmask; flush only dirty mirrors on switch.

### 2) Register windows
Partition the file into banks selected by WP (TMS9900-style).  
Calls move WP by a fixed stride; context switch = WP change.

### 3) Adaptive promotion
Start in WP mode; if a task runs > N\* instructions, promote to copy mode for the rest of the slice.

---

## 5. Example numbers

| Example | Parameters | Result |
|:--|:--|:--|
| Cortex-M, TCM, K=16, rR=2, rW=1, Lr=Lw=1, ρ=0.5 | N\* ≈ 8 instructions (only if all 16 in real regs) |
| RV32, 8 hot regs mirrored | Hybrid gives ~80 % of copy benefit with WP simplicity |
| Desktop/JIT | Copy wins quickly (N tens), not our embedded case |

---

## 6. Decision rule

1. **Measure** on target hardware: Lr/Lw, Sspill, (rR,rW) histogram, and ρ.
2. **Choose**:
   - If Sspill > 0 → stay with **WP** or **hot-set mirror**.
   - If you can pin ≥ 8 regs with no spill → consider **adaptive promotion**.
3. **Layout**:
   - Fastest memory for reg bank.
   - Align WP to cache line.
   - Keep offsets in ISA immediate range.

---

## 7. Micro-benchmark harness (C-style pseudocode)

```c
volatile uint32_t *wp = bank_aligned_in_TCM();
volatile uint32_t sink;

uint32_t measure_Lr(void) {
    reset_cycle_counter();
    uint32_t start = rdcycle();
    for (int i=0; i<1000; ++i) {
        sink += wp[2]; sink += wp[3]; sink += wp[0];
    }
    return (rdcycle() - start)/(3*1000);
}

uint32_t measure_Lw(void) {
    reset_cycle_counter();
    uint32_t start = rdcycle();
    for (int i=0; i<1000; ++i) {
        wp[1]=i; wp[4]=i+1; wp[7]=i+2;
    }
    return (rdcycle() - start)/(3*1000);
}

// ρ: count dirty regs during workload.
// (rR,rW): collect opcode histogram.
```

Use DWT->CYCCNT (Cortex-M) or `rdcycle` CSR (RISC-V).  
Warm caches, disable interrupts.

---

## 8. Engineering patterns to make WP fast

- WP in a fixed callee-saved register.
- Pre-compute large offsets per block.
- Hoist repeated loads to a temp.
- Delay stores and batch flush.
- Bank hot vs cold regs.
- Mark helpers’ clobber lists carefully.

---

## 9. Answer to the intuition

| Case | Outcome |
|:--|:--|
| Context switch every cycle (N≈1) | WP ≈ Copy — total cost identical. |
| Moderate/long run & no spills | Copy can win once N > N\*. |
| Embedded MCU with few host regs | WP or Hybrid wins almost always. |

---

## 10. Recommendation for HSX

1. **Use WP-based context switching** by default (simple, deterministic).  
2. **Add hot-set mirror (4–8 regs)** with dirty bitmask for speed-critical paths.  
3. **Instrument** the interpreter to collect Lr/Lw, ρ, and histogram data.  
4. **Optionally enable adaptive promotion** on hosts that can hold a full shadow without spills.

**Result:**  
You keep the TMS9900-style simplicity (context switch = swap WP) while harvesting nearly all available performance.

---

Skjønner—jeg får for tiden en I/O‑feil i filskriveren her, så jeg kan ikke legge ved direkte nedlastbare vedlegg akkurat nå. For å ikke stoppe deg, legger jeg ved repo‑stilte versjoner av begge filene i to “heredoc”‑blokker du kan lime rett inn fra repo‑roten:

Kjør fra repo‑roten (samme branch): kopier/lim hver blokk i terminalen.
Dette oppretter/overskriver main/04--Design/04.01--VM.md og main/04--Design/04.02--Executive.md.

1) Oppdatert VM‑design (v3) — breakpoints flyttet til Executive, register‑API lagt inn, autorun via clock/quantum
cat > main/04--Design/04.01--VM.md <<'MD'
# 04.01--VM — Design (v3, repo style)
**Status:** DRAFT • **Date:** 2025-10-28 • **Owner:** HSX Core

> **Design stance:** VM is a **dumb machine**. It does **no scheduling**, performs **no automatic context switching**, and services **no syscalls/HAL**. It always runs **under an Executive** which drives stepping, context selection, and debug (incl. breakpoints).

**Authoritative context (repo‑local):**
- Architecture: [03.01--VM](../03--Architecture/03.01--VM.md), [03.00--Architecture](../03--Architecture/03.00--Architecture.md)
- Study & Requirements: [02--Study](../02--Study/02--Study.md), [02.01--Requirements](../02--Study/02.01--Requirements.md)
- Implementation‑phase specs (normative inputs referenced by design):  
  [docs/abi_syscalls.md](../../docs/abi_syscalls.md) • [docs/MVASM_SPEC.md](../../docs/MVASM_SPEC.md) •
  [docs/hxe_format.md](../../docs/hxe_format.md) • [docs/executive_protocol.md](../../docs/executive_protocol.md) •
  [docs/resource_budgets.md](../../docs/resource_budgets.md)

**Traceability (fill from 02.01--Requirements):** Refs DR[..], DG[..], DO[..].

---

## 1. Scope & Non‑Goals
### 1.1 Scope
- Decode & execute HSX ISA for tasks loaded from `.hxe`.
- Maintain per‑task **TaskContext** and arenas (code/data/stack).
- Raise **SVC/BRK** traps; emit execution causes to Executive.
- Expose a **minimal control‑plane API** to the Executive.

### 1.2 Non‑Goals
- **No scheduling** and **no automatic context switch** (context changes only on explicit call).
- **No SVC servicing/HAL** (VM only traps; Executive handles).
- **No transports/provisioning** (Executive routines).

---

## 2. External Interfaces (VM ↔ Executive)
> The Executive owns the control plane. VM exposes a **narrow** API and traps (SVC/BRK).

### 2.1 Control‑plane API (host‑side calls into VM)
| API | Args | Returns | Notes |
|---|---|---|---|
| `vm_init(mem_cfg)` | page sizes, cache configs, alloc hooks, *autorun_quanta?* | rc | Configure paging/arenas. |
| `vm_load_hxe(hxe_ptr, len)` | pointer/descriptor to verified `.hxe` | pid (int), rc | Load one task; allocate arenas. |
| `vm_unload(pid)` | pid | rc | Free arenas and context. |
| `vm_pids()` | – | list[int] | Enumerate tasks. |
| `vm_set_context(pid)` | pid | rc | Make **pid** active; **no** implicit swap. |
| `vm_step()` | – | StepResult | **One instruction** for the active task *(or up to `autorun_quanta` if configured)*. |
| `vm_clock(n)` | n (int) | StepResult | Execute **n** instructions (or stop on svc/break/fault). |
| `vm_reg_get(reg_id)` | const | u32 | Read register in **active** context (PC/SP/… included). |
| `vm_reg_set(reg_id, value)` | const, u32 | rc | Write register in **active** context (policy‑gated). |
| `vm_reg_get_for(pid, reg_id)` | pid, const | u32 | (Optional sugar) Read register for **pid** without state change. |
| `vm_reg_set_for(pid, reg_id, value)` | pid, const, u32 | rc | (Optional sugar) Write register for **pid**. |

**StepResult**: `pc`, `reason ∈ {ok, break, fault, svc}`, optional `svc_id`, `events_emitted`, `cycles_est`.

**Notes**
- **Breakpoints are not a VM concern.** Executive checks PC vs breakpoint table **before** calling `vm_step/clock`.  
- The **autorun** behavior can be achieved either by `vm_clock(n)` or via an optional `autorun_quanta` init parameter; default is **1** for deterministic stepping.

### 2.2 Trap interface (VM → Executive)
- **SVC**: VM raises; Executive dispatches to module handlers (mailbox/val/cmd/provisioning/HAL).  
- **BRK**: VM halts with `reason=break` if the bytecode explicitly executes BRK.  
- **Faults**: illegal instruction, bounds, misaligned access → mapped to Executive events.

**Time base:** In attached mode, cadence is defined by the Executive scheduler. SVC timeouts carry units (µs/ticks) per [abi_syscalls.md](../../docs/abi_syscalls.md).

---

## 3. Registers & Enumeration
### 3.1 Register constants (design guideline)
| Constant | Meaning |
|---|---|
| `REG_PC` = 0 | Program Counter |
| `REG_SP` = 1 | Stack Pointer |
| `REG_PSW` = 2 | Status/flags |
| `REG_WP` = 3 | Workspace pointer |
| `REG_R0`..`REG_R15` = 16..31 | General purpose registers windowed by `WP` |

> Exact values can be frozen in a shared header during implementation; VM must expose them consistently to Executive/tooling.

### 3.2 TaskContext (normative, VM‑internal)
| Field | Type | Description |
|---|---|---|
| `pc` | u32 | Program counter (byte address) |
| `sp` | u32 | Stack pointer (VM stack) |
| `psw` | u32 | Processor status/flags |
| `wp` | u32 | Workspace pointer |
| `reg_base` | u32 | Base of register arena (for R0..R15 windows) |
| `stack_base` | u32 | Start of stack arena |
| `stack_limit` | u32 | Guard/limit |
| `fault_code` | u16 | Latched fault (0 = none) |
| `pid` | u16 | Task id |

**Invariant:** `stack_base ≤ sp < stack_limit`. Context swap = swap a few words (`pc/sp/psw/wp`).

---

## 4. Execution Model
- **Attached‑only**: VM advances **only** when Executive calls `vm_step/clock`.  
- **No internal scheduler**: VM does not pick the next PID; Executive decides via `vm_set_context`.  
- **Debug friendliness**: deterministic stepping, remote control, no hidden preemption.

---

## 5. Memory Model
### 5.1 Layout
- **Code**: read‑only, pageable (e.g., external FRAM/flash + RAM cache).  
- **Data/heap**: read/write; optional **software paging** (fixed‑size pages).  
- **Stack**: pinned.

### 5.2 Code paging (design‑level)
- **Double‑buffer** 256–512 B lines; prefetch near line end; far jump aborts & aligns new burst.  
- Heuristic: decode‑assisted look‑ahead for branch/call targets.

### 5.3 Data paging (optional)
- TLB 2–4 entries; classes: pinned(stack, IPC), RO(globals), RW(heap); write‑back + `VMEM.FLUSH()` hint.  
- Cross‑page R/W split; atomic word stores via critical section when required.

---

## 6. Instruction Set & ABI (anchors)
- ISA/assembler: [MVASM_SPEC](../../docs/MVASM_SPEC.md), [asm.md](../../docs/asm.md).  
- SVC calling convention/IDs: [abi_syscalls.md](../../docs/abi_syscalls.md).  
- BRK honoured only when present in bytecode (tool breakpoints are Executive‑side).

---

## 7. Events & Observability
- Emit (via Executive): `debug_break` (on BRK), `fault`, `mailbox_wait/wake`, `svc_error`; optional `trace_step`.  
- Event schema & flow: [executive_protocol.md](../../docs/executive_protocol.md).  
- Back‑pressure handled by Executive; VM never blocks output.

---

## 8. Performance & Resource Targets
| Target | Metric | Initial target |
|---|---|---|
| Context switch | overhead | O(1) swap `pc/sp/psw/wp` |
| Step throughput | instr/s (M4 @ 48 MHz) | 2–4 M instr/s (design goal) |
| Code cache line | bytes | 256–512 B |
| Data TLB | entries | 2–4 |
| RAM budget | bytes | see [resource_budgets.md](../../docs/resource_budgets.md) |
| Event rate | events/s | bounded by Exec rate‑limit |

---

## 9. Error Model
| Class | Description | Action |
|---|---|---|
| Illegal instruction | Unknown opcode/format | Fault; emit event; stop with `reason=fault` |
| Bounds fault | Stack/addr out of range | Fault; emit; stop |
| Illegal SVC | SVC id not mapped/forbidden | Fault; emit; stop |
| BRK opcode | In bytecode | Stop with `reason=break` |

---

## 10. Verification (links to tests)
- See **[MiniVM_tests.md](../06--Test/system/MiniVM_tests.md)**.  
- Contract: context swap O(1), SVC/BRK semantics, illegal ops, bounds.  
- Behaviour: paging (sequential/far jump/abort), data miss/evict/flush.  
- Limits: RAM budgets; step throughput (smoke).

---

## 11. DoD
- [ ] Control‑plane API & register constants frozen.  
- [ ] TaskContext & invariants frozen.  
- [ ] Memory model & paging FSM sketched.  
- [ ] ABI/SVC + MVASM anchors validated.  
- [ ] Events & error model listed; tied to Executive protocol.  
- [ ] Test anchors linked; resource targets per platform added.

---

## Appendix — Pseudocode (attached‑only stepping)
```text
function vm_step():
  ctx = active_context()
  if ctx is None: return { reason: fault }
  instr = fetch_decode(ctx.pc)
  nextpc, action = execute(instr, ctx)
  if action == BRK: return { pc: nextpc, reason: break }
  if action == SVC: raise_svc(instr.svc_id); return { pc: nextpc, reason: svc, svc_id: instr.svc_id }
  if action == FAULT: emit_fault(...); return { pc: ctx.pc, reason: fault }
  ctx.pc = nextpc
  return { pc: ctx.pc, reason: ok }


MD


---

### 2) Oppdatert Executive‑design (v3) — *Breakpoint Manager i Executive, register‑/VM‑kontrollflate for verktøy*

```bash
cat > main/04--Design/04.02--Executive.md <<'MD'
# 04.02--Executive — Design (v3, repo style)
**Status:** DRAFT • **Date:** 2025-10-28 • **Owner:** HSX Core

> Executive orchestrates **sessions**, **scheduler semantics** (attached single‑instruction contract), **SVC dispatch/servicing**, **IPC (mailbox)**, **values/commands**, **provisioning**, and the **event stream**.  
> **Breakpoints** and debug run‑control are **Executive responsibilities** (not VM).

**Authoritative context (repo‑local):**
- Architecture: [03.02--Executive](../03--Architecture/03.02--Executive.md), [03.00--Architecture](../03--Architecture/03.00--Architecture.md)
- Study & Requirements: [02--Study](../02--Study/02--Study.md), [02.01--Requirements](../02--Study/02.01--Requirements.md)
- Shared specs: [docs/abi_syscalls.md](../../docs/abi_syscalls.md), [docs/executive_protocol.md](../../docs/executive_protocol.md), [docs/resource_budgets.md](../../docs/resource_budgets.md)

**Traceability:** Refs DR[..], DG[..], DO[..].

---

## 1. Scope
- Drive VM via **attached** stepping (`vm_set_context`, `vm_step/clock`), **no automatic VM scheduling**.  
- Implement **SVC bridge**: dispatch SVCs to module handlers (mailbox/val/cmd/provisioning/HAL).  
- Manage **sessions** (exclusive debugger), **breakpoints**, **event stream** (ACK/rate‑limit).  
- Provide **host control‑plane** for tooling (attach, step/clock, bp.set/clear, reg.get/set, ps).

---

## 2. Public Interfaces
### 2.1 SVC/ABI (module 0x06 EXEC) — summarized
> The authoritative table lives in **[abi_syscalls.md](../../docs/abi_syscalls.md)**. Executive implements these:
| Func | R0 | R1 | R2 | R3 | Ret | Errors | Time base |
|---|---|---|---|---|---|---|---|
| `GET_VERSION` | buf | len | – | – | n | – | µs/ticks |
| `STEP` | – | – | – | – | rc | – | µs/ticks |
| `CLOCK` | n | – | – | – | rc | – | µs/ticks |
| `ATTACH`/`DETACH` | pid | – | – | – | rc | EPERM | – |
| `PS` | buf | len | flags | – | n | – | – |
| `SCHED` | op | arg | – | – | rc | EINVAL | – |

*(Exact set per abi_syscalls; table here is a design anchor.)*

### 2.2 Host Control‑Plane (non‑SVC, for tooling)
| API | Args | Returns | Notes |
|---|---|---|---|
| `session.open(pid?)` | pid or null | rc | Claims exclusive debug session (locks). |
| `session.close()` | – | rc | Releases lock. |
| `ps()` | – | list[pid, state, pc] | Snapshot of tasks. |
| `vm.set_context(pid)` | pid | rc | Select active PID (passes through to VM). |
| `vm.step()` / `vm.clock(n)` | – / n | StepResult | Drives VM under scheduler rules. |
| `reg.get(pid, reg_id)` | pid, const | u32 | Reads register via VM (may use `vm_set_context` + `vm_reg_get`). |
| `reg.set(pid, reg_id, value)` | pid, const, u32 | rc | Writes register (policy‑gated). |
| `bp.set(pid, addr)` | pid, code addr | rc | Adds to **per‑PID** breakpoint set. |
| `bp.clear(pid, addr)` | pid, code addr | rc | Removes breakpoint. |
| `bp.list(pid)` | pid | list[addr] | Lists breakpoints. |

> Tool breakpoints are **pure Executive logic** (no code patching required); they work by **pre‑step PC compare**.

---

## 3. Scheduler & Run‑Control (attached)
### 3.1 Semantics
- **Single‑instruction quantum**: a scheduler slice retires 1 instruction *(or up to a configured quantum via `vm_clock(n)`) **unless** halted by SVC/BRK/fault/breakpoint*.  
- **Blocking/wake**: mailbox waits or sleep park the PID; timeouts wake; fairness maintained among READY PIDs.  
- **Session lock**: only one debugger can attach to a PID set; enforced at Executive level.

### 3.2 Breakpoint manager (Executive‑side)
- Maintains **per‑PID** sets of PC addresses.  
- **Pre‑step gate**: before calling `vm_step/clock`, Executive reads the **PC** (`reg.get(pid, REG_PC)`). If it matches a breakpoint, **do not step**; emit `debug_break`.  
- **Post‑step check**: also honours BRK opcode (VM returns `reason=break`).  
- **Actions**: on break ⇒ publish event, keep PID in READY/STOPPED state until user resumes or clears bp.

### 3.3 Pseudocode
```text
for pid in sched.ready():
  if debug_session and pid in bp_table and reg.get(pid, REG_PC) in bp_table[pid]:
    emit(debug_break(pid, pc)); continue
  res = vm.clock(quantum)  # or vm.step()
  if res.reason == svc: handle_svc(res.svc_id, pid)
  elif res.reason == break: emit(debug_break(pid, res.pc))
  elif res.reason == fault: emit(fault(pid, res.pc)); park(pid)
  sched.account(pid, res)

4. Event Protocol

Categories/fields live in executive_protocol.md
.

ACK/rate‑limit & back‑pressure rules apply to debug_break, fault, svc_error, sched_slice, etc.

Reconnect semantics: session lock, keepalive, replay window (tooling design ties in).

5. Mailbox, Values/Commands, Provisioning

Implemented as SVC modules (mailbox=0x05, val=0x07, cmd=0x08, provisioning=TBD). See abi_syscalls.md
.

Semantics described in their respective designs; Executive dispatches & enforces policy.

6. Resource Budgets & Limits

Per target (AVR128DA28, Cortex‑M) limits for queues, descriptor pools, PID contexts, event buffers. See resource_budgets.md
.

Time base (µs/ticks) is consistent across SVC tables and scheduler accounting.

7. Verification (links to tests)

See Executive_tests.md
.

Validate: session exclusivity, breakpoint gate (pre‑step), fairness under waits, back‑pressure behaviour, reconnect robustness.

8. DoD

 SVC/ABI table (EXEC 0x06) consistent with abi_syscalls.md.

 Host control‑plane documented (session/step/clock/bp/reg/ps).

 Scheduler semantics & breakpoint gate implemented.

 Events wired to protocol with ACK/rate‑limit.

 Test anchors linked; resource budgets applied per target.

Appendix — States (minimal)
NEW → READY → (RUN) → { BLOCKED(wait/sleep) | READY | STOPPED(break) | FAULTED }


MD


---

Vil du at jeg også skal oppdatere **04.06--Toolkit.md** med en liten JSON‑kontrollflate for `vm.*`, `reg.*`, `bp.*` (kommandonavn, felt og eksempler) slik at verktøyene kan skriptes direkte mot Executive?
::contentReference[oaicite:0]{index=0}













Takk—jeg har oppdatert begge dokumentene med endringene du ba om (breakpoints flyttet til Executive, register‑API i VM, og valgfri autorun via vm_clock(n)/autorun_quanta).

⚠️ Jeg får for øyeblikket en feil i filskriveren her, så jeg kan ikke legge ved klikk‑for‑nedlasting. For at du skal få filene nå, legger jeg ved to en‑linjes “heredoc”-kommandoer (kopiér inn i terminal i repo‑roten), og selve Markdown‑innholdet rett under for copy/paste.

Metode A — Opprett filene med én paste i terminal

04.01--VM.md

cat > main/04--Design/04.01--VM.md <<'MD'
# 04.01--VM — Design (v3, repo style)
**Status:** DRAFT • **Date:** 2025-10-28 • **Owner:** HSX Core

> **Design stance:** VM is a **dumb machine**. It does **no scheduling**, performs **no automatic context switching**, and services **no syscalls/HAL**. It always runs **under an Executive** which drives stepping, context selection, and debug (incl. breakpoints).

**Authoritative context (repo‑local):**
- Architecture: [03.01--VM](../03--Architecture/03.01--VM.md), [03.00--Architecture](../03--Architecture/03.00--Architecture.md)
- Study & Requirements: [02--Study](../02--Study/02--Study.md), [02.01--Requirements](../02--Study/02.01--Requirements.md)
- Implementation‑phase specs (normative inputs referenced by design):  
  [docs/abi_syscalls.md](../../docs/abi_syscalls.md) • [docs/MVASM_SPEC.md](../../docs/MVASM_SPEC.md) •
  [docs/hxe_format.md](../../docs/hxe_format.md) • [docs/executive_protocol.md](../../docs/executive_protocol.md) •
  [docs/resource_budgets.md](../../docs/resource_budgets.md)

**Traceability (fill from 02.01--Requirements):** Refs DR[..], DG[..], DO[..].

---

## 1. Scope & Non‑Goals
### 1.1 Scope
- Decode & execute HSX ISA for tasks loaded from `.hxe`.
- Maintain per‑task **TaskContext** and arenas (code/data/stack).
- Raise **SVC/BRK** traps; emit execution causes to Executive.
- Expose a **minimal control‑plane API** to the Executive.

### 1.2 Non‑Goals
- **No scheduling** and **no automatic context switch** (context changes only on explicit call).
- **No SVC servicing/HAL** (VM only traps; Executive handles).
- **No transports/provisioning** (Executive routines).

---

## 2. External Interfaces (VM ↔ Executive)
> The Executive owns the control plane. VM exposes a **narrow** API and traps (SVC/BRK).

### 2.1 Control‑plane API (host‑side calls into VM)
| API | Args | Returns | Notes |
|---|---|---|---|
| `vm_init(mem_cfg)` | page sizes, cache configs, alloc hooks, *autorun_quanta?* | rc | Configure paging/arenas. |
| `vm_load_hxe(hxe_ptr, len)` | pointer/descriptor to verified `.hxe` | pid (int), rc | Load one task; allocate arenas. |
| `vm_unload(pid)` | pid | rc | Free arenas and context. |
| `vm_pids()` | – | list[int] | Enumerate tasks. |
| `vm_set_context(pid)` | pid | rc | Make **pid** active; **no** implicit swap. |
| `vm_step()` | – | StepResult | **One instruction** for the active task *(or up to `autorun_quanta` if configured)*. |
| `vm_clock(n)` | n (int) | StepResult | Execute **n** instructions (or stop on svc/break/fault). |
| `vm_reg_get(reg_id)` | const | u32 | Read register in **active** context (PC/SP/… included). |
| `vm_reg_set(reg_id, value)` | const, u32 | rc | Write register in **active** context (policy‑gated). |
| `vm_reg_get_for(pid, reg_id)` | pid, const | u32 | (Optional sugar) Read register for **pid** without state change. |
| `vm_reg_set_for(pid, reg_id, value)` | pid, const, u32 | rc | (Optional sugar) Write register for **pid**. |

**StepResult**: `pc`, `reason ∈ {ok, break, fault, svc}`, optional `svc_id`, `events_emitted`, `cycles_est`.

**Notes**
- **Breakpoints are not a VM concern.** Executive checks PC vs breakpoint table **before** calling `vm_step/clock`.  
- The **autorun** behavior can be achieved either by `vm_clock(n)` or via an optional `autorun_quanta` init parameter; default is **1** for deterministic stepping.

### 2.2 Trap interface (VM → Executive)
- **SVC**: VM raises; Executive dispatches to module handlers (mailbox/val/cmd/provisioning/HAL).  
- **BRK**: VM halts with `reason=break` if the bytecode explicitly executes BRK.  
- **Faults**: illegal instruction, bounds, misaligned access → mapped to Executive events.

**Time base:** In attached mode, cadence is defined by the Executive scheduler. SVC timeouts carry units (µs/ticks) per [abi_syscalls.md](../../docs/abi_syscalls.md).

---

## 3. Registers & Enumeration
### 3.1 Register constants (design guideline)
| Constant | Meaning |
|---|---|
| `REG_PC` = 0 | Program Counter |
| `REG_SP` = 1 | Stack Pointer |
| `REG_PSW` = 2 | Status/flags |
| `REG_WP` = 3 | Workspace pointer |
| `REG_R0`..`REG_R15` = 16..31 | General purpose registers windowed by `WP` |

> Exact values can be frozen in a shared header during implementation; VM must expose them consistently to Executive/tooling.

### 3.2 TaskContext (normative, VM‑internal)
| Field | Type | Description |
|---|---|---|
| `pc` | u32 | Program counter (byte address) |
| `sp` | u32 | Stack pointer (VM stack) |
| `psw` | u32 | Processor status/flags |
| `wp` | u32 | Workspace pointer |
| `reg_base` | u32 | Base of register arena (for R0..R15 windows) |
| `stack_base` | u32 | Start of stack arena |
| `stack_limit` | u32 | Guard/limit |
| `fault_code` | u16 | Latched fault (0 = none) |
| `pid` | u16 | Task id |

**Invariant:** `stack_base ≤ sp < stack_limit`. Context swap = swap a few words (`pc/sp/psw/wp`).

---

## 4. Execution Model
- **Attached‑only**: VM advances **only** when Executive calls `vm_step/clock`.  
- **No internal scheduler**: VM does not pick the next PID; Executive decides via `vm_set_context`.  
- **Debug friendliness**: deterministic stepping, remote control, no hidden preemption.

---

## 5. Memory Model
### 5.1 Layout
- **Code**: read‑only, pageable (e.g., external FRAM/flash + RAM cache).  
- **Data/heap**: read/write; optional **software paging** (fixed‑size pages).  
- **Stack**: pinned.

### 5.2 Code paging (design‑level)
- **Double‑buffer** 256–512 B lines; prefetch near line end; far jump aborts & aligns new burst.  
- Heuristic: decode‑assisted look‑ahead for branch/call targets.

### 5.3 Data paging (optional)
- TLB 2–4 entries; classes: pinned(stack, IPC), RO(globals), RW(heap); write‑back + `VMEM.FLUSH()` hint.  
- Cross‑page R/W split; atomic word stores via critical section when required.

---

## 6. Instruction Set & ABI (anchors)
- ISA/assembler: [MVASM_SPEC](../../docs/MVASM_SPEC.md), [asm.md](../../docs/asm.md).  
- SVC calling convention/IDs: [abi_syscalls.md](../../docs/abi_syscalls.md).  
- BRK honoured only when present in bytecode (tool breakpoints are Executive‑side).

---

## 7. Events & Observability
- Emit (via Executive): `debug_break` (on BRK), `fault`, `mailbox_wait/wake`, `svc_error`; optional `trace_step`.  
- Event schema & flow: [executive_protocol.md](../../docs/executive_protocol.md).  
- Back‑pressure handled by Executive; VM never blocks output.

---

## 8. Performance & Resource Targets
| Target | Metric | Initial target |
|---|---|---|
| Context switch | overhead | O(1) swap `pc/sp/psw/wp` |
| Step throughput | instr/s (M4 @ 48 MHz) | 2–4 M instr/s (design goal) |
| Code cache line | bytes | 256–512 B |
| Data TLB | entries | 2–4 |
| RAM budget | bytes | see [resource_budgets.md](../../docs/resource_budgets.md) |
| Event rate | events/s | bounded by Exec rate‑limit |

---

## 9. Error Model
| Class | Description | Action |
|---|---|---|
| Illegal instruction | Unknown opcode/format | Fault; emit event; stop with `reason=fault` |
| Bounds fault | Stack/addr out of range | Fault; emit; stop |
| Illegal SVC | SVC id not mapped/forbidden | Fault; emit; stop |
| BRK opcode | In bytecode | Stop with `reason=break` |

---

## 10. Verification (links to tests)
- See **[MiniVM_tests.md](../06--Test/system/MiniVM_tests.md)**.  
- Contract: context swap O(1), SVC/BRK semantics, illegal ops, bounds.  
- Behaviour: paging (sequential/far jump/abort), data miss/evict/flush.  
- Limits: RAM budgets; step throughput (smoke).

---

## 11. DoD
- [ ] Control‑plane API & register constants frozen.  
- [ ] TaskContext & invariants frozen.  
- [ ] Memory model & paging FSM sketched.  
- [ ] ABI/SVC + MVASM anchors validated.  
- [ ] Events & error model listed; tied to Executive protocol.  
- [ ] Test anchors linked; resource targets per platform added.

---

## Appendix — Pseudocode (attached‑only stepping)
```text
function vm_step():
  ctx = active_context()
  if ctx is None: return { reason: fault }
  instr = fetch_decode(ctx.pc)
  nextpc, action = execute(instr, ctx)
  if action == BRK: return { pc: nextpc, reason: break }
  if action == SVC: raise_svc(instr.svc_id); return { pc: nextpc, reason: svc, svc_id: instr.svc_id }
  if action == FAULT: emit_fault(...); return { pc: ctx.pc, reason: fault }
  ctx.pc = nextpc
  return { pc: ctx.pc, reason: ok }


MD


**04.02--Executive.md**
```bash
cat > main/04--Design/04.02--Executive.md <<'MD'
# 04.02--Executive — Design (v3, repo style)
**Status:** DRAFT • **Date:** 2025-10-28 • **Owner:** HSX Core

> Executive orchestrates **sessions**, **scheduler semantics** (attached single‑instruction contract), **SVC dispatch/servicing**, **IPC (mailbox)**, **values/commands**, **provisioning**, and the **event stream**.  
> **Breakpoints** and debug run‑control are **Executive responsibilities** (not VM).

**Authoritative context (repo‑local):**
- Architecture: [03.02--Executive](../03--Architecture/03.02--Executive.md), [03.00--Architecture](../03--Architecture/03.00--Architecture.md)
- Study & Requirements: [02--Study](../02--Study/02--Study.md), [02.01--Requirements](../02--Study/02.01--Requirements.md)
- Shared specs: [docs/abi_syscalls.md](../../docs/abi_syscalls.md), [docs/executive_protocol.md](../../docs/executive_protocol.md), [docs/resource_budgets.md](../../docs/resource_budgets.md)

**Traceability:** Refs DR[..], DG[..], DO[..].

---

## 1. Scope
- Drive VM via **attached** stepping (`vm_set_context`, `vm_step/clock`), **no automatic VM scheduling**.  
- Implement **SVC bridge**: dispatch SVCs to module handlers (mailbox/val/cmd/provisioning/HAL).  
- Manage **sessions** (exclusive debugger), **breakpoints**, **event stream** (ACK/rate‑limit).  
- Provide **host control‑plane** for tooling (attach, step/clock, bp.set/clear, reg.get/set, ps).

---

## 2. Public Interfaces
### 2.1 SVC/ABI (module 0x06 EXEC) — summarized
> The authoritative table lives in **[abi_syscalls.md](../../docs/abi_syscalls.md)**. Executive implements these:
| Func | R0 | R1 | R2 | R3 | Ret | Errors | Time base |
|---|---|---|---|---|---|---|---|
| `GET_VERSION` | buf | len | – | – | n | – | µs/ticks |
| `STEP` | – | – | – | – | rc | – | µs/ticks |
| `CLOCK` | n | – | – | – | rc | – | µs/ticks |
| `ATTACH`/`DETACH` | pid | – | – | – | rc | EPERM | – |
| `PS` | buf | len | flags | – | n | – | – |
| `SCHED` | op | arg | – | – | rc | EINVAL | – |

*(Exact set per abi_syscalls; table here is a design anchor.)*

### 2.2 Host Control‑Plane (non‑SVC, for tooling)
| API | Args | Returns | Notes |
|---|---|---|---|
| `session.open(pid?)` | pid or null | rc | Claims exclusive debug session (locks). |
| `session.close()` | – | rc | Releases lock. |
| `ps()` | – | list[pid, state, pc] | Snapshot of tasks. |
| `vm.set_context(pid)` | pid | rc | Select active PID (passes through to VM). |
| `vm.step()` / `vm.clock(n)` | – / n | StepResult | Drives VM under scheduler rules. |
| `reg.get(pid, reg_id)` | pid, const | u32 | Reads register via VM (may use `vm_set_context` + `vm_reg_get`). |
| `reg.set(pid, reg_id, value)` | pid, const, u32 | rc | Writes register (policy‑gated). |
| `bp.set(pid, addr)` | pid, code addr | rc | Adds to **per‑PID** breakpoint set. |
| `bp.clear(pid, addr)` | pid, code addr | rc | Removes breakpoint. |
| `bp.list(pid)` | pid | list[addr] | Lists breakpoints. |

> Tool breakpoints are **pure Executive logic** (no code patching required); they work by **pre‑step PC compare**.

---

## 3. Scheduler & Run‑Control (attached)
### 3.1 Semantics
- **Single‑instruction quantum**: a scheduler slice retires 1 instruction *(or up to a configured quantum via `vm_clock(n)`) **unless** halted by SVC/BRK/fault/breakpoint*.  
- **Blocking/wake**: mailbox waits or sleep park the PID; timeouts wake; fairness maintained among READY PIDs.  
- **Session lock**: only one debugger can attach to a PID set; enforced at Executive level.

### 3.2 Breakpoint manager (Executive‑side)
- Maintains **per‑PID** sets of PC addresses.  
- **Pre‑step gate**: before calling `vm_step/clock`, Executive reads the **PC** (`reg.get(pid, REG_PC)`). If it matches a breakpoint, **do not step**; emit `debug_break`.  
- **Post‑step check**: also honours BRK opcode (VM returns `reason=break`).  
- **Actions**: on break ⇒ publish event, keep PID in READY/STOPPED state until user resumes or clears bp.

### 3.3 Pseudocode
```text
for pid in sched.ready():
  if debug_session and pid in bp_table and reg.get(pid, REG_PC) in bp_table[pid]:
    emit(debug_break(pid, pc)); continue
  res = vm.clock(quantum)  # or vm.step()
  if res.reason == svc: handle_svc(res.svc_id, pid)
  elif res.reason == break: emit(debug_break(pid, res.pc))
  elif res.reason == fault: emit(fault(pid, res.pc)); park(pid)
  sched.account(pid, res)

4. Event Protocol

Categories/fields live in executive_protocol.md
.

ACK/rate‑limit & back‑pressure rules apply to debug_break, fault, svc_error, sched_slice, etc.

Reconnect semantics: session lock, keepalive, replay window (tooling design ties in).

5. Mailbox, Values/Commands, Provisioning

Implemented as SVC modules (mailbox=0x05, val=0x07, cmd=0x08, provisioning=TBD). See abi_syscalls.md
.

Semantics described in their respective designs; Executive dispatches & enforces policy.

6. Resource Budgets & Limits

Per target (AVR128DA28, Cortex‑M) limits for queues, descriptor pools, PID contexts, event buffers. See resource_budgets.md
.

Time base (µs/ticks) is consistent across SVC tables and scheduler accounting.

7. Verification (links to tests)

See Executive_tests.md
.

Validate: session exclusivity, breakpoint gate (pre‑step), fairness under waits, back‑pressure behaviour, reconnect robustness.

8. DoD

 SVC/ABI table (EXEC 0x06) consistent with abi_syscalls.md.

 Host control‑plane documented (session/step/clock/bp/reg/ps).

 Scheduler semantics & breakpoint gate implemented.

 Events wired to protocol with ACK/rate‑limit.

 Test anchors linked; resource budgets applied per target.

Appendix — States (minimal)
NEW → READY → (RUN) → { BLOCKED(wait/sleep) | READY | STOPPED(break) | FAULTED }


MD


---

## Metode B — Ren Markdown (kopiér innholdet)

**04.01--VM.md**
```md
# 04.01--VM — Design (v3, repo style)
**Status:** DRAFT • **Date:** 2025-10-28 • **Owner:** HSX Core
[...samme innhold som over i heredoc for VM...]


04.02--Executive.md

# 04.02--Executive — Design (v3, repo style)
**Status:** DRAFT • **Date:** 2025-10-28 • **Owner:** HSX Core
[...samme innhold som over i heredoc for Executive...]


Hvis du ønsker at jeg også legger til tooling‑kommandogrensesnitt (JSON‑meldinger for vm.*, reg.*, bp.*) i 04.06--Toolkit.md så speiler vi kontrollflaten 1:1 mot Executive.
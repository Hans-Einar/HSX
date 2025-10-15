# HSX Scheduler Implementation Review — GPT‑Pro Summary

This document condenses the scheduler feedback into an actionable plan. It targets the **Python host VM + executive** and aligns with the mailbox fixes you just completed.

---

## Goals
- Deterministic scheduling: **one step = one guest instruction**.
- No register copying on context switch; use **base-pointer indirection** for registers and stack.
- Correct, debuggable **trap/wait/wake** semantics with strong invariants and tests.

---

## Where the implementation diverged
- **Registers/stack copied** at switch instead of using `{reg_base, stack_base, stack_limit}` indirection.
- **“Cycles” vs “steps”** ambiguity: a “step” advanced multiple instructions before rotation.
- **Trap resume/PC drift** risks due to multi-instruction execution within one rotation.
- **Weak invariants** (bases allowed to be zero; stack guard not enforced consistently).

---

## Step Contract (Scheduler ↔ VM)
- **One VM step executes exactly one guest instruction.**
- Results of `vm.step()`:
  - `OK`: requeue PID at tail of READY.
  - `TRAP(SVC, mod, fn)`: handle SVC; **do not execute another instruction** for this PID this round. Resume at `pc_after_trap` next time.
  - `BLOCKED(wait_reason)`: move PID to the relevant **wait queue** immediately.
  - `HALT/EXIT`: reap PID and free resources.
  - `FAULT`: kill or panic per policy.
- **Rotation:** round‑robin over READY PIDs, exactly one step each.

---

## Invariants (Assert in code)
- For any PID in `READY` or `RUNNING`:
  - `reg_base != 0`, `stack_base != 0`, `stack_limit > stack_base`.
- Architectural SP is **16‑bit** (`sp16`); effective SP = `stack_base + (sp16 & 0xFFFF)`.
- VM reads/writes GPRs **only** via `reg_base` (no shared Python arrays).
- Context switch mutates only `{pc, psw, reg_base, stack_base, stack_limit, sp16}`.

---

## Minimal TCB & Memory Model
```python
@dataclass
class TCB:
    pid: int
    pc: int
    psw: int
    reg_base: int
    stack_base: int
    stack_limit: int
    sp16: int
    state: Literal["READY","RUNNING","WAIT_MBX","WAIT_TIME","EXIT"]
    wait_key: tuple|None  # e.g., ("mbx", handle) or ("timer", deadline)
```
**Per‑task arenas:**
```
[ regs (16×4B) ]  <- reg_base
[ stack (S B) ]   <- stack_base .. stack_limit
```
Alignment: word‑aligned bases; enforce mask on SP at every VM SP read/write.

---

## Context Switch & Round‑Robin Step (Pseudo)
```python
def activate(t: TCB):
    vm.pc, vm.psw = t.pc, t.psw
    vm.reg_base, vm.stack_base, vm.stack_limit = t.reg_base, t.stack_base, t.stack_limit
    vm.sp = t.sp16 & 0xFFFF

def store_active(t: TCB):
    t.pc, t.psw = vm.pc, vm.psw
    t.sp16 = vm.sp & 0xFFFF  # no register copying

def step_once():
    t = readyq.pop_left()
    activate(t)
    r = vm.step()  # one instruction only
    store_active(t)
    if   r.kind == "OK":        readyq.push_right(t)
    elif r.kind == "TRAP":      handle_trap(t, r);  (readyq.push_right(t) if t.state=="READY" else None)
    elif r.kind == "BLOCKED":   move_to_waitq(t, r.reason)
    elif r.kind == "HALT":      t.state="EXIT"; reap(t)
    elif r.kind == "FAULT":     panic_or_kill(t, r)
```

---

## Wait/Wake Semantics
- **Wait queues** keyed by reason: `("mbx", handle)`, `("timer", tick)`, etc.
- **Wake**:
  - Mailbox send: enqueue **one** or **all** waiters per policy.
  - Timer tick: move expired waiters back to READY.
- On wake, task reenters READY and will run **one instruction on its next turn**.

---

## Instrumentation & CLI
- **Sched trace ring:** `(ts, pid, event, pc)` for `STEP|TRAP|BLOCK|WAKE|HALT`.
- **Counters per PID:** `steps_executed`, `switches`, `blocks`, `wakes`.
- **CLI:** 
  - `clock step N` → run N **rounds** (one step per READY PID per round).
  - `clock step N -p PID` → run N steps only on PID.
  - `sched stats` → dump counters.
- Deterministic stepping aids mailbox/debug scenarios.

---

## Test Matrix (Unit + Integration)
1. **Base-pointer isolation:** PID1 writes `R3`; PID2 `R3` unchanged after rotation.
2. **Stack guards:** tiny stack + deep call → `HSX_ERR_STACK_OVERFLOW`.
3. **Fair RR:** PIDs 1,2,3; `clock step 9` → each advanced **3 instructions** in PID order.
4. **Trap resume:** SVC from PID1 resumes at `pc_after_trap`; exactly one instruction per rotation.
5. **Mailbox wait/wake:** consumer blocks on `RECV(INFINITE)`; producer `SEND` wakes consumer; verify PC/SP integrity.
6. **Timeout wake:** finite timeout wakes at tick N; task runs one instruction and rotates.

---

## Documentation Updates
- Replace “**cycles**” with “**steps**” everywhere; define *one step = one instruction* and strict RR rotation.
- Add a **scheduler contract** section with the rules above.
- Clarify **register/stack base model** and SP masking in the VM description.
- Document CLI: `clock step`, `-p PID`, and `sched stats`.

---

## Risks & Mitigations
- **Partial refactor:** ensure every VM GPR access goes through `reg_base`. *Mitigation:* single access layer + asserts.
- **SP widening bugs:** always mask to 16‑bit on read/write. *Mitigation:* SP accessor enforces masking.
- **Hidden multi‑instruction exec:** never loop in `vm.step()` or scheduler. *Mitigation:* unit test forbids >1 instruction per activation.

---

## Definition of Done (Scheduler)
- [ ] No register copies on context switch; **bases non‑zero** and asserted.
- [ ] One‑instruction **step**; strict round‑robin rotation.
- [ ] Stack guard exceptions surface as `HSX_ERR_STACK_OVERFLOW`.
- [ ] SVC resumes at `pc_after_trap` with correct PC/SP.
- [ ] Mailbox **wait/wake** verified in SVC E2E tests.
- [ ] CLI: `clock step` (+ `-p PID`) and `sched stats` implemented.
- [ ] All new tests green.

---

## Rollout Plan
1) Implement bases + TCB + asserts (no behavior change yet).  
2) Switch scheduler to **one‑instruction steps**; add `clock step` and `sched stats`.  
3) Wire wait queues & timer wakeups; integrate with mailbox path.  
4) Land tests (base-pointer, stack guard, trap resume, RR fairness, wait/wake).  
5) Update docs; remove “cycles”.  
6) Clean up traces and finalize demo scripts.

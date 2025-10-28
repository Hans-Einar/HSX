# HSX — Design Review for `main/04--Design/`
**Date:** 2025-10-27  
**Branch:** `chores/document_merge_2`

**Grounding:** Cross-checked against `01--Mandate`, `02--Study` (+ `02.01--Requirements`), and `03--Architecture` files shared in this branch. Design docs are treated as WIP; this review flags **gaps to freeze (P0)** before implementation and gives a **playbook** you can apply file-by-file.

> **Link hygiene:** New naming (`04.xx--Name.md`) is good. Keep internal links relative and avoid parentheses.

---

## Executive summary
**Overall direction:** Consistent with architecture: Executive drives VM (attached mode), mailbox = canonical IPC, Val/Cmd for telemetry/commands, provisioning via CAN/SD/host.  
**P0 to freeze now** (normative, referenced from design):
1) **ABI/SVC** — single authoritative table (module/function IDs, R0–R3, Ret, Errors, **time base**) + `EXEC_GET_VERSION` capability handshake. Source of truth: `docs/abi_syscalls.md` → referenced in design.  
2) **Scheduler semantics** — single-instruction quantum (attached), fairness, blocking (`sleep/wait`), attached vs. standalone time base. (Design: Executive.)  
3) **Mailbox semantics** — first-reader / all-readers / tap, back-pressure, overflow policy, fairness. (Design: Mailbox.)  
4) **Event protocol** — categories/fields, session lock, rate-limit/ACK/retry, reconnect. Source: `docs/executive_protocol.md` → referenced in design.  
5) **Resource budgets** — per target (AVR128DA28, Cortex‑M): flash/RAM for Executive, VM, mailbox/FD pools, stack/arena per PID. Source: `docs/resource_budgets.md`.  
6) **Packaging & persistence** — `.hxe` header/version/CRC (`docs/hxe_format.md`) and FRAM layout (`05--Implementation/shared/persistence_layout.md`) → referenced from Provisioning design.

---

## Review rubric (apply to each design file)
- **Front-matter:** *Preconditions/Postconditions* + **Refs:** DR[..], DG[..], DO[..].
- **Public interface:** SVC/API tables (ID, R0–R3, Ret, Errors, **time base**), pasted from `docs/abi_syscalls.md` and scoped to the module.
- **State & sequences:** one compact state machine + 1–2 key sequence diagrams.
- **Limits & budgets:** RAM/flash targets, descriptor pools, latency/throughput.
- **Observability & errors:** event fields/types, error model, logs/metrics.
- **Verification hooks:** explicit test anchors → link to `06--Test/<area>/*.md`.
- **DoD excerpt:** what must be true to call the design “done”.

---

## 04.00--Design.md (design set overview)
**Status:** Good umbrella; ensure it *links to* and *pulls in* the P0 tables (ABI, scheduler, mailbox, event, budgets, packaging/persistence).  
**Gaps:** Add a **“Design readiness checklist”** that must be ✅ before implementation gates open (mirrors the P0 list).  
**Action:** Include a small **traceability map** (table) from `(02.01) Requirements` → `(04.xx)` → `(06--Test)`.

---

## 04.01--VM.md — MiniVM
**Should lock:**
- **Workspace-pointer** model (O(1) context swap), `TaskContext` table (`pc, sp, psw, reg_base, stack_base, stack_limit, …`); BRK/SVC traps & error mapping.
- **Execution modes:** attached (Executive drives `STEP/CLOCK(n)`) vs standalone loop (time base stated).
- **Memory model:** code paging (double-buffer I-cache) + optional software paging for data/heap (page size, small TLB, pinned classes for stack/IPC); cross-page R/W rules.

**Gaps to add (P0):**
- Normative `TaskContext` fields + invariants.
- Attached **time base** and tolerance for `STEP/CLOCK(n)` slices.
- Paging FSM (prefetch/evict) + miss handling.

**Tests (06--Test/system/MiniVM_tests.md):**
- Context swap O(1); SVC arg/ret; BRK causes; page miss/evict/flush; cross-page R/W.

---

## 04.02--Executive.md — Scheduler, Sessions & SVC Bridge
**Should lock:**
- **EXEC (0x06)** table: `GET_VERSION`, `STEP`, `CLOCK(n)`, `ATTACH/DETACH`, `PS`, `SCHED` (+ errors/time base).
- **Scheduler semantics:** single-instruction contract, fairness, wait/wake via mailbox/sleep.
- **Event protocol:** categories/fields, **ACK/rate-limit**, **session lock** (exclusive debugger), reconnect (reference `docs/executive_protocol.md`).

**Gaps to add (P0):**
- Explicit buffer sizes/back-pressure policy for the event stream.
- Sequence diagrams: attach→step→break; subscribe→ACK/back-pressure; reconnect after link loss.

**Tests (06--Test/system/Executive_tests.md):**
- Session exclusivity, back-pressure behaviour, fairness under waits, reconnect robustness.

---

## 04.03--Mailbox.md — IPC
**Should lock:**
- **Delivery modes** (first-reader / all-readers / tap) and **policy** (overflow: block vs `EAGAIN`; fairness; retention).
- **Handle lifecycle:** `OPEN/BIND/PEEK/RECV/TAP/CLOSE`; namespaces (`svc:`, `app:`, `shared:`); stdio via reserved `svc:` channels.

**Gaps to add (P0):**
- Latency targets/time base for `SEND/RECV` and wake timing.

**Tests (06--Test/system/Mailbox_tests.md):**
- Fan-out correctness across modes; overflow; tap neutrality; wait/wake timing.

---

## 04.04--ValCmd.md — Values & Commands
**Should lock:**
- **Numeric OID** addressing (`group:value`), f16 values (bool=0/1), zero-arg commands.
- **Auth/policy** for external transports; throttling/publish-rate; FRAM persistence hooks.

**Gaps to add (P0):**
- Descriptor tables (flags, units, ranges, publish-rate, FRAM key); error model (`ENOENT`, `EPERM`, `EAGAIN`).

**Tests (06--Test/system/ValCmd_tests.md):**
- Numeric vs named addressing; auth failures; persist/load round-trip; rate caps.

---

## 04.05--Toolchain.md — Asm/LLC/Linker & artefacts
**Should lock (reference docs/**toolchain**):**
- **Assembler (MVASM)** — see `docs/MVASM_SPEC.md`, `docs/asm.md`.
- **hsx-llc** — see `docs/hsx_llc.md`, `docs/toolchain.md`.
- **Linker & packaging** — `docs/packaging.md`, `docs/hxe_format.md` (header fields: magic, version, entry, sizes, CRC), and **listing/sidecar** format.
- **Artefacts for DoD:** `.hxo`, `.hxe`, `listing.*`, symbol/line tables (debug sidecar).

**Gaps to add (P0):**
- Required fields/sections for each artefact + stability guarantees for downstream tools.

**Tests (06--Test/toolchain/*):**
- Deterministic listing/sidecar; well-formed `.hxe` with CRC/compat policy.

---

## 04.06--Toolkit.md — Shell & Debugger
**Should lock:**
- CLI/RPC surface; event subscription; session lifecycle; break/watch workflows.
- **Event JSON schema** (minimum + stability for scripting).

**Gaps to add (P0):**
- Reconnect behaviour; snapshot outputs for CI; rate-limit awareness.

**Tests (06--Test/toolkit/debugger_tests.md / Shell_tests.md):**
- Attach/reconnect; breakpoint accuracy; back-pressure; JSON snapshot stability.

---

## 04.07--Provisioning.md — Loading & Persistence
**Should lock:**
- **Load flows** via CAN/SD/host; status via mailbox/value; restart sequencing.
- **FRAM layout** (`05--Implementation/shared/persistence_layout.md`): keys, CRC, rollback; lifecycle policy.
- **`.hxe` header** & compatibility (from `docs/hxe_format.md`).

**Gaps to add (P0):**
- Failure modes (CRC mismatch, partial update), atomicity/rollback steps.

**Tests (06--Test/system/Provisioning_tests.md):**
- CRC corruption case; interrupted update; version downgrade rules; wear budgeting.

---

## (Suggested) 04.08--HAL.md — Drivers/Timebase (if not present)
**Purpose:** Stabilise driver contracts (UART, CAN, FRAM/EEPROM, FS, GPIO/Timers, **Timebase**) so SVC modules can be built as separate libraries later.  
**Action:** Map each to a **reserved SVC module ID** in `docs/abi_syscalls.md` (authoritative list).

---

## Cross-cutting: Traceability & DoD
- **Traceability:** Each design file starts with *Refs:* DR[..], DG[..], DO[..] (from `02.01--Requirements.md`). Keep DG/DO labels in headings.
- **Resource budgets:** Include per-target tables inside designs; also summarise in `docs/resource_budgets.md` and reference from each.
- **DoD matrix:** Maintain `07--DoD/07--DoD.md` (or `05--Implementation/dod.md`) as Module ↔ DR/DG/DO ↔ Min test plan.

---

## Playbook (patch steps)
1) Paste the **ABI/SVC** table skeleton into Executive/Mailbox/ValCmd/Provisioning designs and bind to `docs/abi_syscalls.md` as source of truth.  
2) Add **scheduler FSM** (attached mode) + fairness rules into Executive; include `STEP/CLOCK` time base.  
3) Add **Mailbox semantics** table (first/all/tap, overflow, fairness) + latency/time base targets.  
4) Move **event protocol detail** to `docs/executive_protocol.md`, reference it in Executive + Toolkit designs.  
5) Insert **resource budgets** per target into each design and point to `docs/resource_budgets.md`.  
6) In Provisioning, embed summarized `.hxe` header/compat and FRAM rollback policy (link to `docs/hxe_format.md` / persistence layout).  
7) For each design, add **Verification hooks** → link to the right `06--Test` file and list Given/When/Then anchors.  
8) Ensure internal links use the new `04.xx--Name.md` naming (no parentheses).

---

## ABI/SVC skeleton (paste into designs)
| Module | ID | Func | R0 | R1 | R2 | R3 | Ret | Errors | Time base |
|---|---|---|---|---|---|---|---|---|---|
| EXEC | 0x06 | GET_VERSION | buf | len | – | – | n | – | µs/ticks |
| EXEC | 0x06 | STEP/CLOCK | n | – | – | – | rc | – | µs/ticks |
| MBOX | 0x05 | SEND/RECV/PEEK/TAP | h | ptr | len | flags | rc/n | EAGAIN/ETIMEDOUT | µs |
| VAL  | 0x07 | GET/SET | oid | buf/f16 | len/flags | – | rc/n | ENOENT/EPERM | µs |
| CMD  | 0x08 | CALL | oid | flags | token | – | rc | EPERM/ETIME | ms |
| PROV | 0x16 | LOAD/STATUS | ptr | len | flags | – | rc | EIO/EBADMSG | ms |
| HAL* | 0x10–0x15 | UART/CAN/FRAM/FS/GPIO/TIME | … | … | … | … | … | … | … |


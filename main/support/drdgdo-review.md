# DR / DG / DO — Review & Proposed Updates
Dato: 2025-10-24

## Scope (docs reviewed)
(1) **mandate**, (2) **study**, (2.1) **requirements (traceability)**, *hsx_vm_register_model_analysis.md*, *refactorNotes.md*, *studyReferenceRework.md*, and the (3.x) architecture set (vm, executive, mailbox, values/commands, tooling, provisioning).

---

## A) DR — Proposed changes/additions (P0)
**Goal:** make design contracts *testable & normative* before full design/impl.

| ID | Requirement (succinct) | Rationale |
|---|---|---|
| **DR‑2.1a (acceptance)** | Add *measurable* acceptance criteria for WP context switching (O(1)) incl. microbench method (Lr/Lw, ρ, histogram). | Study + register analysis favour WP; make it verifiable. fileciteturn0file1 fileciteturn0file3 |
| **DR‑2.5 (new)** | **ABI enumerations & versioning handshake**: single authoritative header; `EXEC_GET_VERSION` capability query is mandatory. | Prevent Python↔C drift; aligns with refactor plan. fileciteturn0file4 |
| **DR‑3.1 (new)** | **HXE format**: freeze header fields (magic, ver, EP, sizes, CRC), compat rules; listing/debug sidecar is an artefact. | Consistent packaging across hosts/nodes. fileciteturn0file1 |
| **DR‑5.1 (new)** | **Scheduler contract & timebase**: define single‑instruction quantum in attached mode; specify time unit (µs/ticks), fairness, and blocking (`sleep/wait`). | Executive behaves as OS‑light; tooling depends on invariants. fileciteturn0file54 |
| **DR‑5.2 (new)** | **Resource budgets per target**: RAM/flash for Executive, MiniVM, FD tables, mailbox pools, stack/arena per PID. | MCU constraints must be explicit. fileciteturn0file46 fileciteturn0file52 |
| **DR‑5.3 (new)** | **Persistence layout**: FRAM/E2 keyspace, CRC/rollback, lifecycle. | Needed for provisioning & calibration persistence. fileciteturn0file58 |
| **DR‑6.1 (new)** | **Mailbox semantics (normative)**: delivery modes (first‑reader/all‑readers/tap), back‑pressure, overflow policy. | Mailbox is canonical IPC; semantics must be a contract. fileciteturn0file55 |
| **DR‑7.1 (new)** | **Value/command security & policy**: min auth levels for `val.set`, `cmd.call` flags/tokens over external transports. | Protect sensitive ops; described in V/C layer. fileciteturn0file56 |
| **DR‑8.1 (new)** | **Debug event stream & session locking**: event categories, rate limit/ACK/retry, exclusive PID locks. | Tooling & exec notes require a durable event bus. fileciteturn0file54 fileciteturn0file57 |

> **Note:** Keep original DR numbering; treat new items as `.x` extensions (e.g., DR‑5.1) to preserve traceability defined in (2.1). fileciteturn0file48

---

## B) DG — Clarifications/additions
Map to the study’s DG taxonomy; keep cross‑refs in headings per rework plan. fileciteturn0file51

| ID | Update | Why |
|---|---|---|
| **DG‑3.4** | **Code‑gen SVC header** → one source of truth for module/func IDs; Python scrapes same header. | Eliminates literal drift. fileciteturn0file4 |
| **DG‑5.4** | **Single‑instruction contract** when attached; VM yields clock to Executive; standalone mode documented separately. | Matches executive architecture. fileciteturn0file54 fileciteturn0file53 |
| **DG‑3.5** | **Listing + debug sidecar required** from linker. | Feeds debugger & CI. fileciteturn0file1 |
| **DG‑6.4** | **Reserved stdio mailboxes** (`svc:stdin/out/err`) and handle policy. | Makes tooling portable. fileciteturn0file55 |
| **DG‑7.4** | **Numeric addressing is canonical**; names optional. | Saves RAM, aligns with V/C doc. fileciteturn0file47 |
| **DG‑1.4** | **Python↔C parity tests**: common test matrix must pass before C port. | Locks behaviour across implementations. fileciteturn0file46 |

---

## C) DO — Backlog (not gating MVP)
| DO | Suggestion | Source |
|---|---|---|
| **DO‑VM‑hotset** | Mirror 4–8 hot regs + dirty mask. | Register analysis. fileciteturn0file49 |
| **DO‑VM‑adaptive** | Adaptive promotion to shadow when long slices. | Register analysis. fileciteturn0file49 |
| **DO‑mailbox‑ns** | Extended namespaces / QoS variants. | Study & mailbox view. fileciteturn0file47 fileciteturn0file55 |
| **DO‑val‑bulk** | `val.bulk_get/set` RPCs. | Study backlog. fileciteturn0file47 |
| **DO‑tool‑altIR** | Alternative IR / Rust backend. | Study toolchain. fileciteturn0file47 |
| **DO‑hxe‑sym** | Optional embedded symtab in `.hxe`. | Study formats. fileciteturn0file47 |
| **DO‑relay** | On‑target debug relay/TUI footprint. | (2.1) requirements DO‑8.a. fileciteturn0file48 |

---

## D) Traceability updates (how to land this cleanly)
1) Tag headings in `(2)study.md` with **DG‑x.y** per rework plan. fileciteturn0file51  
2) Insert new DR items into `(2.1)requirements.md` and map them to DGs (matrix). fileciteturn0file48  
3) Cite the DG IDs inside `(3.x)` architecture views where relevant (mailboxes, exec, vm, values/commands). fileciteturn0file52 fileciteturn0file55 fileciteturn0file54 fileciteturn0file53 fileciteturn0file56  
4) In design specs `(4.x)`, start with **Preconditions/Postconditions** listing DR/DG references. fileciteturn0file51  
5) Implement SVC header code‑gen; migrate modules to `0x06` executive & add `EXEC_GET_VERSION`. fileciteturn0file4

---

## E) Ready‑to‑paste normative tables

### E.1 Syscall/ABI (skeleton)
| Module | ID | Func | R0 | R1 | R2 | R3 | Ret | Errors | Time base |
|---|---|---|---|---|---|---|---|---|---|
| EXEC | 0x06 | GET_VERSION | buf | len | – | – | n | – | µs/ticks |
| MBOX | 0x05 | SEND | h | ptr | len | flags | rc | EAGAIN/ETIMEDOUT | µs |
| VAL  | 0x07 | GET | oid | buf | len | – | n | ENOENT | µs |
| CMD  | 0x08 | CALL | oid | flags | token | – | rc | EPERM | ms |

### E.2 Mailbox semantics (normative)
- **first‑reader‑clears**: eksakt én mottaker; andre ser ikke meldingen.  
- **all‑readers‑clear**: alle bundne mottakere må `RECV` før clear.  
- **tap**: ikke‑destruktiv kopi; back‑pressure nøytral.  
- **overflow**: blokk vs. `−EAGAIN` etter policy; logg `overrun`‑event. fileciteturn0file55

### E.3 Resource budgets (per target)
| Target | Exec (flash/RAM) | VM core | Mailboxes/FD | Stack/arena per PID | Notes |
|---|---|---|---|---|---|
| AVR128DA28 | … | … | … | … | tighten |
| Cortex‑M4  | … | … | … | … | TCM when avail |

> Fill concrete numbers during sizing pass; keep headroom ≥ 20 %. fileciteturn0file46

### E.4 Debug/event stream (minimum)
- **Categories:** `trace_step`, `debug_break`, `mailbox_*`, `sched`, `val_change`.  
- **Flow:** `session.open` → events (ACK/rate limit) → `session.close`.  
- **Locking:** one active debugger per PID (enforced). fileciteturn0file54 fileciteturn0file57

---

## F) What can start now (safe parallel work)
- Tooling polish (shell/debugger UI & event handling). fileciteturn0file57  
- Executive groundwork (PCB/FD/stdio, session mgmt). fileciteturn0file54  
- Provisioning CLI & FRAM hooks. fileciteturn0file58  

## G) Out‑of‑scope here but noted
- HAL/security dedicated architecture views when footprint & policy are concretised. fileciteturn0file52


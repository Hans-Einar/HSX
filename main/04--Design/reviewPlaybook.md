# Design Review Playbook – `main/04--Design/`

Snapshot of the GPT design review distilled into actionable checklists. Tick items here as the design set is updated; keep the authoritative design content in the corresponding `04.xx--*.md` files.

---

## Freeze-First (P0) Items
- [ ] Publish a single authoritative **ABI/SVC table** (module IDs, R0–R3 usage, return semantics, errors, time base) and reference it from every design; include `EXEC_GET_VERSION`.
  - **Survey:** `04.00--Design.md` only lists design documents; none of the `04.xx` files include a consolidated ABI/SVC table, and `docs/abi_syscalls.md` remains the only detailed source.
  - **Solution:** Add an `ABI/SVC Overview` subsection to `04.00--Design.md` containing a master table derived from `docs/abi_syscalls.md`, then embed module-specific excerpts (EXEC, MBOX, VAL, CMD, PROV) in the relevant `04.xx` files with a note that the spec file is authoritative and includes `EXEC_GET_VERSION` guidelines.
- [ ] Lock **scheduler semantics**: single-instruction quantum, fairness rules, blocking/wake behaviour, attached vs. standalone time base.
  - **Survey:** `04.02--Executive.md` describes round-robin behaviour and wait/wake flows, but it lacks a dedicated scheduler section summarising the quantum, explicit fairness rules, and a clear contract for host-driven versus standalone time bases.
  - **Solution:** Create a focused `Scheduler Semantics` section in `04.02--Executive.md` that presents a ready/run/wait/sleep state table (or diagram), formally states the one-instruction quantum, fairness/starvation guarantees, and clearly distinguishes attached (host tick) versus standalone timing plus wake latency bounds.
- [ ] Lock **mailbox semantics**: delivery modes, back-pressure, overflow policy, fairness guarantees.
  - **Survey:** `04.03--Mailbox.md` explains operations in prose but lacks a consolidated delivery-mode matrix and explicit statements about overflow/back-pressure policies, fairness ordering, or latency targets.
  - **Solution:** Expand `04.03--Mailbox.md` with a `Delivery Semantics` matrix covering first-reader/all-readers/tap behaviour, detail overflow/back-pressure handling (blocking vs. EAGAIN thresholds), specify fairness ordering/latency expectations, and cross-reference scheduler/event timing.
- [ ] Finalise **event protocol**: categories, payload schema, session locking, rate-limit/ACK, reconnect procedure (source: `docs/executive_protocol.md`).
  - **Survey:** Event streaming is discussed in `04.02--Executive.md` and `04.06--Toolkit.md`, but neither provides a structured JSON schema, ACK/rate-limit table, or explicit reconnect workflow—the authoritative detail is only in `docs/executive_protocol.md`.
  - **Solution:** Align `04.02--Executive.md` and `04.06--Toolkit.md` by adding a shared schema/behaviour summary that references `docs/executive_protocol.md`, outlining categories, payload fields, session lock semantics, ACK/rate-limit expectations, buffer sizing, and reconnect steps while confirming the protocol doc remains canonical.
- [ ] Document **resource budgets** per target (AVR128DA28, Cortex-M) aligned with `docs/resource_budgets.md`.
  - **Survey:** `docs/resource_budgets.md` contains draft numbers, but `04.00--Design.md` and the subsystem designs only reference it; they do not include local budget tables or per-target summaries.
  - **Solution:** Add a `Resource Budgets` appendix to `04.00--Design.md` that summarises the per-target flash/RAM/stack/mailbox allocations, and include concise budget tables within each subsystem design highlighting their consumption and linking back to the master document.
- [ ] Embed **packaging & persistence** contract: `.hxe` header/version/CRC rules (`docs/hxe_format.md`) and FRAM layout (`05--Implementation/shared/persistence_layout.md`).
  - **Survey:** `04.07--Provisioning.md` references the external documents but does not restate the `.hxe` header fields, CRC/compat policy, or FRAM key/rollback rules, nor does it outline failure handling explicitly.
  - **Solution:** Extend `04.07--Provisioning.md` with `HSX Packaging` and `Persistence Layout` subsections summarising `.hxe` header requirements, version/CRC handling, FRAM key allocation/rollback policy, and typical failure scenarios (CRC mismatch, partial update, downgrade) drawn from the referenced specs.

---

## 04.00--Design.md (Overview)
- [ ] Add a “Design readiness” checklist mirroring the freeze-first items.
- [ ] Insert a traceability table linking `(02.01) Requirements` ↔ `04.xx` design docs ↔ relevant `06--Test` entries.
- [ ] Ensure links to the authoritative ABI/scheduler/mailbox/event/resource docs are present.

## 04.01--VM.md (MiniVM)
- [ ] Add normative `TaskContext` field table with invariants.
- [ ] Specify attached vs. standalone time base and slice tolerance for `STEP/CLOCK`.
- [ ] Document paging FSM (prefetch/evict/miss handling) and cross-page access guarantees.
- [ ] Reference required verification in `06--Test/system/MiniVM_tests.md` (context swap O(1), SVC/BRK, paging).

## 04.02--Executive.md (Scheduler & Sessions)
- [ ] Embed EXEC module (0x06) ABI table including errors/time base.
- [ ] Describe scheduler FSM: ready/run/wait/sleep/paused with fairness rules.
- [ ] Detail event stream buffer sizing and back-pressure policy.
- [ ] Add sequence diagrams for attach→step→break, subscribe→ACK, and reconnect flows.
- [ ] Link verification hooks in `06--Test/system/Executive_tests.md`.

## 04.03--Mailbox.md (IPC)
- [ ] Document delivery modes (first-reader, all-readers, tap) with overflow/back-pressure/fairness policy.
- [ ] Capture handle lifecycle and namespace behaviour (svc:/app:/shared:/stdio).
- [ ] Add latency/time-base targets for SEND/RECV and wake timing.
- [ ] Cross-reference `06--Test/system/Mailbox_tests.md`.

## 04.04--ValCmd.md (Values & Commands)
- [ ] Provide descriptor tables (flags, units, ranges, publish rate, FRAM key) and error model (ENOENT, EPERM, EAGAIN).
- [ ] Spell out auth/policy expectations per transport.
- [ ] Cover persistence round-trip behaviour with FRAM integration.
- [ ] Link verification hooks in `06--Test/system/ValCmd_tests.md`.

## 04.05--Toolchain.md (Assembler/LLC/Linker)
- [ ] Summarise required fields/sections for `.hxo`, `.hxe`, listing/sidecar artefacts with stability promises.
- [ ] Reference supporting specs (`docs/MVASM_SPEC.md`, `docs/asm.md`, `docs/hsx_llc.md`, `docs/hxe_format.md`, `docs/packaging.md`, `docs/toolchain.md`).
- [ ] Ensure deterministic-output tests are cited (`06--Test/toolchain/*`).

## 04.06--Toolkit.md (Shell & Debugger)
- [ ] Capture CLI/RPC surface plus event JSON schema (minimum/stable fields).
- [ ] Document reconnect behaviour and snapshot logging for CI.
- [ ] Include rate-limit/back-pressure expectations matching the executive design.
- [ ] Point to `06--Test/toolkit/debugger_tests.md` and `06--Test/toolkit/Shell_tests.md`.

## 04.07--Provisioning.md (Loading & Persistence)
- [ ] Lay out CAN/SD/host load sequences, including status channels and restart sequencing.
- [ ] Summarise `.hxe` header compatibility rules and FRAM rollback policy.
- [ ] Describe failure handling (CRC mismatch, partial update, downgrade, wear limits).
- [ ] Reference tests in `06--Test/system/Provisioning_tests.md`.

## Suggested 04.08--HAL.md (Drivers/Timebase)
- [ ] Decide whether to spin up a HAL design doc; if so, map each driver to reserved SVC module IDs per `docs/abi_syscalls.md`.
- [ ] Outline base contracts for UART, CAN, FRAM/EEPROM, FS, GPIO/Timers, and time base.

---

## Cross-Cutting Tasks
- [ ] Ensure every design file starts with **Preconditions/Postconditions** plus **Refs: DR[..], DG[..], DO[..]** sourced from `02.01--Requirements.md`.
- [ ] Propagate DG/DO labels into section headings for traceability.
- [ ] Embed per-target resource tables in each design and align them with `docs/resource_budgets.md`.
- [ ] Maintain the DoD matrix in `07--DoD/07--DoD.md` (or `05--Implementation/dod.md`) mapping Module ↔ DR/DG/DO ↔ minimum tests.
- [ ] Verify all internal links use the `04.xx--Name.md` scheme (no parentheses / stale paths).

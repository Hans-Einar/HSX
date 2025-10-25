# Design Playbook — Open Items

> Track outstanding design contracts and documentation tasks called out in the architecture review. Each section summarises the gap and breaks it into actionable steps.

## 1. Syscall / ABI Specification
- *Reminder:* confirm corresponding design docs capture explicit Preconditions/Postconditions when updated.
- **Status:** Draft complete — `docs/abi_syscalls.md` captures current module/function tables and lays out follow-up work (module version query, future changes expected).
- **Missing:** Dedicated document referenced by VM/executive specs; consistent error codes; timeout semantics.
- **Tasks:**
  - [x] Draft syscall table (new file `docs/abi_syscalls.md`) covering modules 0x05–0x08 (+ core).
  - [x] Cross-check against Python VM implementation (`platforms/python/host_vm.py`) for current behaviour.
  - [ ] Review with runtime/tooling leads; update architecture/design docs with link.

## 2. Mailbox Semantics
- *Reminder:* ensure `(3.3)` and `(4.3)` retain up-to-date Preconditions/Postconditions during future revisions.
- **Status:** In progress — architectural overview in `(3.3)` stays high-level; detailed behaviour captured in `(4.3)mailbox.md`. State diagrams and timeout contracts still pending implementation alignment.
- **Missing:** Visual state diagrams, final timeout/error code contract, scheduler alignment once blocking waits land.
- **Tasks:**
  - [x] Capture delivery modes, back-pressure, and timeout semantics in `(4.3)mailbox.md`.
  - [x] Add state diagrams and example flows illustrating wait/wake transitions.
  - [x] Align with scheduler design so wait/wake transitions are consistent and timeout codes are finalised.

## 3. Scheduler & Wait State Machine
- *Reminder:* keep scheduler design docs' Preconditions/Postconditions aligned with implementation changes.
- **Status:** Architecture references behaviour but lacks formal state diagram/priorities.
- **Missing:** READY/RUNNING/WAIT/SLEEP transitions, clock modes, fairness guarantees.
- **Tasks:**
  - [x] Produce state machine diagram and embed in `(3.2)executive.md`.
  - [x] Define invariant checks (one instruction per step, wait queues) for `(4.2)executive.md`.
  - [x] Update implementation issue `issues/#2_scheduler` to reference final contract.

## 4. Resource Budgets
- *Reminder:* propagate any budget updates into design doc Preconditions/Postconditions.
- **Status:** Not documented.
- **Missing:** RAM/flash budgets per target, register bank/stack sizes, descriptor pool limits, FRAM capacity.
- **Tasks:**
  - [x] Gather target specs (AVR128DA28, Cortex-M) and draft `docs/resource_budgets.md`.
  - [x] Reference budgets in architecture views (VM, mailbox, provisioning).
  - [x] Incorporate limits into design/test plans.

## 5. Event Stream / Debug Protocol
- *Reminder:* toolkit/executive design docs must maintain Preconditions/Postconditions when event work evolves.
- **Status:** Mentioned but not normative.
- **Missing:** Event types, payload fields, sequencing, rate limits, reconnect behaviour.
- **Tasks:**
  - [x] Extend `docs/executive_protocol.md` with event schema and examples.
  - [x] Update tooling design `(4.6)toolkit.md` with expectations (drop handling, filtering).
  - [ ] Add tests for event stream delivery once protocol finalised.

## 6. HXE Format & Provisioning Manifest
- *Reminder:* add/refresh Preconditions/Postconditions in toolkit/provisioning design specs alongside this work.
- **Status:** High-level description; no full spec.
- **Missing:** Header field definitions, versioning, capability flags, CRC procedure, manifest schema for provisioning.
- **Tasks:**
  - [ ] Create `docs/hxe_format.md` with header layout, alignment, compatibility rules.
  - [ ] Define provisioning manifest structure (embedded in `.hxe` or sidecar) and note in `(4.5)`/`(4.7)`.
  - [ ] Reflect spec references in toolchain/provisioning design docs.

## 7. FRAM / Persistence Layout
- *Reminder:* ensure provisioning/value design docs include Preconditions/Postconditions once defined.
- **Status:** Conceptual.
- **Missing:** Key ranges, storage format, wear-leveling/rollback strategies, error handling.
- **Tasks:**
  - [ ] Draft FRAM key layout aligned with resource budgets.
  - [ ] Document load/save sequence in `(3.6)provisioning.md`/`(4.7)provisioning.md` with failure handling.
  - [ ] Coordinate with value subsystem to ensure persist modes map to FRAM plan.

## 8. Security / Access Control
- *Reminder:* capture Preconditions/Postconditions in security-related design once authored.
- **Status:** Not addressed yet.
- **Missing:** Policy for commands/values (auth levels, tokens), CAN message authentication, provisioning integrity (signatures/checks).
- **Tasks:**
  - [ ] Identify security requirements (with stakeholders) and draft `docs/security.md` outline.
  - [ ] Update design docs (values/commands, provisioning, tooling) once policy agreed.
  - [ ] Ensure tooling/executive enforce policy (auth tokens, ACLs).

## 9. Implementation Alignment — Workspace Pointer Remediation
- *Reminder:* update VM/executive design Preconditions/Postconditions when remediation lands.
- **Status:** Architecture/design expect pointer swapping; Python VM still clones state.
- **Missing:** Implementation changes and test coverage for register-window model (`issues/#2_scheduler`).
- **Tasks:**
  - [ ] Drive issue `issues/#2_scheduler` remediation to completion (T1–T4).
  - [ ] Update design docs to remove "current copy" caveats once merged.
  - [ ] Add regression tests ensuring context switches no longer copy state.

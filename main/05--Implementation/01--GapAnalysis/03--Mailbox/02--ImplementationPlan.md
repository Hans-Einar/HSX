# Mailbox Implementation Plan

## Planned Implementation Order (Grand Plan)

1. Phase 1 - Python mailbox manager parity (sessions, send/recv foundation).
2. Phase 2 - Wait/timeout handling, fan-out, and tracing hooks.
3. Phase 3 - Provisioning hooks aligned with streaming coordination.
4. Phase 4 - Stability and stress testing once features land.
5. Phase 5 - C port (deferred until the Python layers stabilize).
6. Phase 6 - Documentation and sample refresh.

## Sprint Scope

Drive Phases 1 through 4 (plus documentation updates in Phase 6) on the Python side. Keep Phase 5, the C port, parked for a post-Python sprint and record any C-specific findings as future follow-ups.

## Overview

This implementation plan addresses the gaps identified in the Mailbox Study document ([01--Study.md](./01--Study.md)) and aligns with the implementation notes in the System document ([../../system/Mailbox.md](../../system/Mailbox.md)). The plan is organized chronologically with clear dependencies tracked in [DependencyTree.md](../DependencyTree.md).

**Design Reference:** [04.03--Mailbox.md](../../../04--Design/04.03--Mailbox.md)

---

## Process Expectations

### Design-First Workflow
- Always read the relevant sections of `04.03--Mailbox.md` **before** starting implementation work.
- Document ambiguities or clarifications in `03--ImplementationNotes.md` and resolve or escalate prior to coding.
- Update the design document whenever implementation reveals new behaviour, constraints, or API adjustments.

### Definition of Done (applies to every task/phase)
- [ ] Implementation matches the referenced design section(s).
- [ ] Tests updated/executed; commands and results captured in `03--ImplementationNotes.md`.
- [ ] `02--ImplementationPlan.md` checkboxes refreshed.
- [ ] `03--ImplementationNotes.md` entry recorded (focus, status, tests, follow-ups).
- [ ] Design document updated (or follow-up filed) if behaviour diverges.
- [ ] `04--git.md` log updated once changes land.
- [ ] Required review gate(s) completed (design + implementation + integration).

### Review Gates
1. **Design Review** - Confirm referenced design sections and clarifications before coding a phase.
2. **Implementation Review** - Run after completing each phase to validate against the design.
3. **Integration Review** - Required before exposing new mailboxes/events to Executive/Provisioning/Tooling consumers.
4. **Comprehensive Review** - Before stress testing or packaging milestones.

### Design Document Review Checklist
- [ ] Status/opcode tables in 04.03 remain accurate.
- [ ] Wait/wake diagrams align with implementation.
- [ ] Resource limits, namespace rules, and timeout semantics are current.
- [ ] Observability/event semantics match the design.
- [ ] Newly discovered constraints captured in the design.

---

## Phase 1: Complete Python Implementation

### 1.1 Add Timeout Status Code

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 1 day

**Rationale:**  
Design specifies `HSX_MBX_STATUS_TIMEOUT` (0x07) for timeout expiry (section 5.1.1). Current implementation returns `WOULDBLOCK` on timeout - ABI needs update for compliance.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [x] Add `HSX_MBX_STATUS_TIMEOUT` (0x07) to `include/hsx_mailbox.h`
- [x] Add `HSX_MBX_STATUS_TIMEOUT` to `python/hsx_mailbox_constants.py`
- [x] Update mailbox manager to return TIMEOUT status on expiry
- [x] Update SVC handler to map TIMEOUT status correctly
- [x] Add timeout status tests (finite timeout expiry scenarios)
- [x] Update `docs/abi_syscalls.md` with TIMEOUT status code
- [x] Verify constant synchronization tests pass

---

### 1.2 Add Descriptor Exhaustion Status

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 1 day

**Rationale:**  
Design defines `HSX_MBX_STATUS_NO_DESCRIPTOR` (0x05) for descriptor pool exhaustion (section 5.1.1). Not currently in C header or Python constants.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [x] Add `HSX_MBX_STATUS_NO_DESCRIPTOR` (0x05) to `include/hsx_mailbox.h`
- [x] Add `HSX_MBX_STATUS_NO_DESCRIPTOR` to `python/hsx_mailbox_constants.py`
- [x] Update mailbox manager to return NO_DESCRIPTOR on pool exhaustion
- [x] Update BIND operation to detect and report exhaustion
- [x] Add descriptor exhaustion tests (create descriptors until pool exhausted)
- [x] Update `docs/abi_syscalls.md` with NO_DESCRIPTOR status code
- [x] Verify constant synchronization tests pass

---

### 1.3 Event Emission Integration

**Priority:** HIGH  
**Dependencies:** Executive Phase 1.2 (Event streaming foundation)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies structured events for debugger/tooling (sections 5.2, 8). System/Mailbox.md notes: "Emit mailbox-related events for debugger/tooling." Essential for visibility and debugging.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [x] Define mailbox event types: mailbox_send, mailbox_recv, mailbox_wait, mailbox_wake, mailbox_timeout, mailbox_overrun
- [x] Define event schema for each type (seq, ts, pid, descriptor, handle, size, etc.)
- [x] Integrate with executive event streaming (emit_event calls)
- [x] Emit mailbox_send event on successful send
- [x] Emit mailbox_recv event on successful receive
- [x] Emit mailbox_wait event when task blocks on mailbox
- [x] Emit mailbox_wake event when task unblocks from mailbox
- [x] Emit mailbox_timeout event when mailbox operation times out
- [x] Emit mailbox_overrun event when messages dropped (fan-out, tap)
- [x] Add event emission tests (verify events generated correctly)
- [x] Document mailbox event schema in `docs/executive_protocol.md`

---

### 1.4 Resource Monitoring APIs

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies tracking descriptor usage, queue depth, memory footprint (section 4.6). System/Mailbox.md notes: "Document memory footprint knobs tied to resource budgets."

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [x] Add descriptor usage tracking (active descriptors, max pool size)
- [x] Add per-descriptor queue depth tracking (current/max messages)
- [x] Add memory footprint calculation (descriptor overhead + message data)
- [x] Implement `mailbox_stats()` API to query resource usage
- [x] Add RPC command `mailbox_snapshot` enhancement for resource stats
- [x] Add per-task handle count tracking
- [x] Add resource monitoring tests
- [x] Document resource monitoring APIs

---

### 1.5 Validate Fan-Out Reclamation

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies messages acknowledged by all readers are removed (section 4.4.2). Implementation tracks `last_seq` per handle but reclamation logic should be verified.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [x] Review fan-out reclamation algorithm implementation
- [x] Verify message cleanup when all readers acknowledge
- [x] Add test for fan-out with multiple readers (verify reclamation)
- [x] Add test for reader with lagging `last_seq` (verify messages retained)
- [x] Add test for all readers catching up (verify cleanup)
- [x] Document fan-out reclamation algorithm
- [x] Add memory leak tests for fan-out scenarios

---

### 1.6 Validate Tap Isolation

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design states taps should not block descriptor owner (sections 4.4.3, 6). System/Mailbox.md notes: tap mode exists but priority/isolation needs validation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [x] Review tap implementation for blocking behavior
- [x] Verify taps use drop-on-overflow policy
- [x] Verify taps don't block owner sends
- [x] Add test for tap with slow consumer (verify drops, no blocking)
- [x] Add test for tap with fast consumer (verify receives all)
- [x] Add tap isolation tests (owner unaffected by tap state)
- [x] Document tap isolation guarantees

---

## Phase 2: HXE v2 Declarative Support

### 2.1 Define .mailbox Section Format

**Priority:** MEDIUM  
**Dependencies:** Executive Phase 3.1 (HXE v2 format support)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies `.mailbox` metadata section for declarative mailbox creation (section 4.5.1). Schema needs to be defined for toolchain integration.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [x] Design .mailbox section JSON/binary format
- [x] Define fields: target, capacity, mode_mask, bindings
- [x] Define validation rules (capacity limits, valid targets)
- [x] Document .mailbox section format
- [x] Create example .mailbox sections
- [x] Add format version field for future extensions
- [x] Coordinate with HXE format specification updates

---

### 2.2 Section Parser

**Priority:** MEDIUM  
**Dependencies:** Executive Phase 3.1 (HXE v2 support)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Parser needed to extract .mailbox metadata from HXE header (section 4.5.1). Enables declarative mailbox configuration.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [x] Implement .mailbox section parser in executive
- [x] Parse JSON/binary .mailbox data from HXE header
- [x] Validate .mailbox section contents
- [x] Handle parsing errors gracefully
- [x] Add .mailbox parsing tests (valid/invalid sections)
- [x] Document parser API
- [x] Integrate with HXE loader

---

### 2.3 Preprocessed Creation

**Priority:** MEDIUM  
**Dependencies:** 2.2 (Section parser)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies creating mailboxes before VM execution (section 3.9). Ensures mailboxes are ready when task starts.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [x] Implement mailbox creation from .mailbox metadata
- [x] Create descriptors during task load (before VM execution)
- [x] Register mailbox bindings with executive
- [x] Handle creation failures (descriptor exhaustion)
- [x] Add preprocessed mailbox tests (verify created before VM runs)
- [x] Document preprocessed mailbox lifecycle
- [x] Update task load sequence documentation

---

### 2.4 Update Toolchain

**Priority:** LOW  
**Dependencies:** 2.1 (.mailbox section format)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Toolchain needs to generate .mailbox sections from application code. Enables declarative mailbox specification in source.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [x] Design source annotation syntax for mailbox declarations
- [x] Update assembler to recognize mailbox directives
- [x] Update compiler to generate .mailbox metadata
- [x] Implement .mailbox section generation in HXE builder
- [x] Add toolchain tests for .mailbox generation
- [x] Document mailbox declaration syntax
- [x] Provide examples of declarative mailbox usage

---

## Phase 3: Scheduler Integration

### 3.1 Formal WAIT_MBX State

**Priority:** HIGH  
**Dependencies:** Executive Phase 4.1 (Formal state machine)  
**Estimated Effort:** 2-3 days  
**Design Reference:** [04.03--Mailbox.md](../../../04--Design/04.03--Mailbox.md) Sections 4.3, 4.4.4, 4.7, 5.2  
**Design Questions Resolved:** _(record clarifications in 03--ImplementationNotes.md prior to coding)_  
**Design Updates Needed:** _(capture required spec edits here and action them post-implementation)_

**Pre-Implementation Checklist**
- [x] Read design Sections 4.3 (Execution Model) and 4.7 (State Transitions).
- [x] Confirm scheduler expectations in 04.02--Executive.md align with Mailbox WAIT_MBX semantics.
- [x] Document open design questions / assumptions in `03--ImplementationNotes.md`.

**Implementation Tasks**
- [x] Ensure mailbox blocking transitions tasks to `WAIT_MBX` (executive + VM controller state).
- [x] Verify the executive state machine recognises and preserves `WAIT_MBX`.
- [x] Update task tracking to store wait metadata (descriptor, handle, timeout, deadline).
- [x] Implement mailbox wait callbacks / pending state bookkeeping for scheduler integration.
- [x] Add targeted tests (unit + integration) covering wait + wake + timeout flows.
- [x] Update documentation (`docs/executive_protocol.md`, design notes) to describe semantics.

**Post-Implementation Checklist**
- [x] Validate behaviour against design sections (state diagrams, wait/wake flow).
- [x] Update 04.03 and 04.02 design docs if behaviour changed or clarifications were required (validated: no edits needed).
- [x] Record outcomes, tests, and follow-ups in `03--ImplementationNotes.md`.
- [ ] Confirm review gate (implementation review) has been completed/logged.

---

### 3.2 Timeout Heap Management

**Priority:** HIGH  
**Dependencies:** Executive Phase 4.2 (Wait/wake improvements with timer heap)  
**Estimated Effort:** 2-3 days  
**Design Reference:** [04.03--Mailbox.md](../../../04--Design/04.03--Mailbox.md) Section 4.4.4 & 5.1.2  
**Design Questions Resolved:** _TBD_  
**Design Updates Needed:** _TBD_

**Pre-Implementation Checklist**
- [x] Review timeout semantics in Sections 4.4.4 and 5.1.2.
- [x] Cross-check Executive scheduler expectations in 04.02 (timer heap integration).
- [x] Capture edge cases (poll, finite, infinite) in `03--ImplementationNotes.md`.

**Implementation Tasks**
- [x] Integrate mailbox waits with the executive timer heap (finite timeout path).
- [x] Ensure infinite timeouts skip heap registration.
- [x] Implement timeout expiry callbacks (wake task, return TIMEOUT status, emit events).
- [x] Add instrumentation/counters for timeouts as per design.
- [x] Extend tests to cover finite/infinite/poll timeout scenarios.
- [x] Update documentation to describe timeout scheduling behaviour.

**Post-Implementation Checklist**
- [x] Reconcile implementation with design (deadline calculations, event payloads).
- [x] Update design doc if new constraints (e.g., heap capacity) are identified (validated: none).
- [x] Record tests/results/follow-ups in `03--ImplementationNotes.md`.
- [ ] Close out the corresponding review gate.

---

### 3.3 Wake Priority Handling

**Priority:** MEDIUM  
**Dependencies:** 3.1 (Formal WAIT_MBX state)  
**Estimated Effort:** 1-2 days  
**Design Reference:** [04.03--Mailbox.md](../../../04--Design/04.03--Mailbox.md) Sections 4.4.2, 4.6, 6  
**Design Questions Resolved:** _TBD_  
**Design Updates Needed:** _TBD_

**Pre-Implementation Checklist**
- [x] Review wake ordering requirements (owner vs taps vs fan-out) in Sections 4.4.2 and 4.6.
- [x] Document any design ambiguities about starvation avoidance or fairness.
- [x] Confirm executive scheduler expectations for wake order.

**Implementation Tasks**
- [x] Ensure waiter queues preserve FIFO order per descriptor.
- [x] Enforce wake priority (owner + fan-out subscribers + taps).
- [x] Add regression tests for multiple waiters, tap observers, and fairness.
- [x] Document wake priority and starvation guarantees.
- [x] Surface diagnostics (e.g., queue snapshots) to aid debugging.

**Post-Implementation Checklist**
- [x] Validate behaviour against design (no starvation, deterministic wake order).
- [x] Update design doc if additional clarifications were necessary (none needed).
- [x] Log outcomes/tests/follow-ups in `03--ImplementationNotes.md`.
- [ ] Confirm relevant review gate complete.

---

### 3.4 Scheduler Counters

**Priority:** LOW  
**Dependencies:** 3.1 (Formal WAIT_MBX state)  
**Estimated Effort:** 1 day  
**Design Reference:** [04.03--Mailbox.md](../../../04--Design/04.03--Mailbox.md) Section 4.6  
**Design Questions Resolved:** _TBD_  
**Design Updates Needed:** _TBD_

**Pre-Implementation Checklist**
- [x] Confirm which counters are mandated by the design (MAILBOX_STEP, MAILBOX_WAKE, MAILBOX_TIMEOUT).
- [x] Validate how counters should surface via executive diagnostics (compare with 04.02).

**Implementation Tasks**
- [x] Implement counters in the executive scheduler and expose via stats API.
- [x] Ensure counters increment for all relevant paths (send, recv, timeout).
- [x] Add regression tests validating counter increments.
- [x] Document counter semantics and usage.

**Post-Implementation Checklist**
- [x] Verify design alignment (values, granularity, reset behaviour).
- [x] Update design doc with any additional observability notes.
- [ ] Log results/tests/follow-ups in `03--ImplementationNotes.md`.
- [ ] Record completion at the applicable review gate.

---

## Phase 4: Resource Management

### 4.1 Quota Enforcement

**Priority:** MEDIUM  
**Dependencies:** 1.4 (Resource monitoring APIs)  
**Estimated Effort:** 2-3 days  
**Design Reference:** [04.03--Mailbox.md](../../../04--Design/04.03--Mailbox.md) Sections 4.6, 6; `docs/resource_budgets.md`  
**Design Questions Resolved:** _TBD_  
**Design Updates Needed:** _TBD_

**Pre-Implementation Checklist**
- [x] Review resource management guidance in Section 4.6 and existing `resource_budgets.md`.
- [x] Document required quota profiles (host vs embedded) in `03--ImplementationNotes.md`.
- [x] Confirm interaction with Executive resource reporting (04.02).

**Implementation Tasks**
- [x] Implement descriptor pool limit enforcement (configurable per profile).
- [x] Enforce per-task handle quotas at BIND/OPEN.
- [x] Return correct status codes (`NO_DESCRIPTOR`, `ENOSPC`, etc.) when limits exceeded.
- [x] Add regression tests covering quota breaches and recovery.
- [x] Update documentation (`resource_budgets.md`, design notes) with configuration guidance.

**Post-Implementation Checklist**
- [x] Validate behaviour against design (limits, status codes, diagnostics).
- [x] Update design doc if additional constraints or configuration options introduced.
- [x] Record results/tests/follow-ups in `03--ImplementationNotes.md`.
- [ ] Ensure review gate(s) captured the change.

---

### 4.2 Resource Budgets

**Priority:** MEDIUM  
**Dependencies:** 4.1 (Quota enforcement)  
**Estimated Effort:** 1-2 days  
**Design Reference:** [04.03--Mailbox.md](../../../04--Design/04.03--Mailbox.md) Section 4.6; `docs/resource_budgets.md`  
**Design Questions Resolved:** Host (`desktop`) vs embedded mailbox quotas captured in docs; configurable knobs surfaced through controller profiles.  
**Design Updates Needed:** Addressed in 04.03 Section 4.6 (profiles paragraph).

**Pre-Implementation Checklist**
- [x] Gather current platform constraints (host + embedded) and log in notes.
- [x] Review existing budget guidance to ensure mailbox additions integrate cleanly.

**Implementation Tasks**
- [x] Define descriptor pool sizes and default capacities per platform profile.
- [x] Update `docs/resource_budgets.md` with mailbox entries and rationale.
- [x] Provide guidance for tuning quotas (dev vs production vs constrained targets).
- [x] Cross-link configuration knobs in design + plan.

**Post-Implementation Checklist**
- [x] Ensure resource budget documentation aligns with implementation defaults.
- [x] Update design doc if new configuration considerations exist.
- [x] Record outcomes/tests/follow-ups in `03--ImplementationNotes.md`.
- [ ] Confirm review gate completion.

---

### 4.3 Exhaustion Handling

**Priority:** MEDIUM  
**Dependencies:** 4.1 (Quota enforcement)  
**Estimated Effort:** 1-2 days  
**Design Reference:** [04.03--Mailbox.md](../../../04--Design/04.03--Mailbox.md) Sections 4.6, 6; 5.1.1  
**Design Questions Resolved:** Descriptor exhaustion should emit a `mailbox_exhausted` event and surface via CLI; handle quota saturation treated equivalently.  
**Design Updates Needed:** Section 6 updated with operator guidance.

**Pre-Implementation Checklist**
- [x] Review design guidance on exhaustion scenarios (descriptor pool, queue overrun).
- [x] Identify required observability (events, CLI output, counters).

**Implementation Tasks**
- [x] Implement detection and logging for descriptor exhaustion / queue overruns.
- [x] Ensure existing descriptors continue functioning when pool is exhausted.
- [x] Return correct status codes (`NO_DESCRIPTOR`, etc.) on BIND/OPEN failure.
- [x] Add recovery tests (close descriptors, allocate new ones).
- [x] Update operator documentation with mitigation guidance.

**Post-Implementation Checklist**
- [x] Validate behaviour against design (events, status codes, diagnostics).
- [x] Update design doc if additional diagnostics or behaviours were added.
- [x] Record results/tests/follow-ups in `03--ImplementationNotes.md`.
- [ ] Confirm review gate completion.
- [ ] Validate behaviour against design (events, recovery, status codes).
- [ ] Update design doc if additional diagnostics or behaviours were added.
- [x] Record tests/results/follow-ups in `03--ImplementationNotes.md`.
- [ ] Confirm review gate completion.

---

### 4.4 Stdio Rate Limiting

**Priority:** LOW  
**Dependencies:** 1.6 (Validate tap isolation)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design mentions rate limits for tap consumers to prevent starvation (section 6). Protects stdio performance.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [x] Design rate limiting policy for tap consumers
- [x] Implement rate limit tracking per tap
- [x] Drop tap messages when rate limit exceeded
- [x] Add rate limit configuration (messages per second)
- [x] Add rate limiting tests
- [x] Document stdio rate limiting behavior
- [x] Provide tuning guidelines

---

## Phase 5: Documentation and Testing

### 5.1 Event Schema Documentation

**Priority:** MEDIUM  
**Dependencies:** 1.3 (Event emission integration)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Mailbox event types need formal documentation in protocol specification. Enables tool integration.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [ ] Document mailbox_send event schema in `docs/executive_protocol.md`
- [ ] Document mailbox_recv event schema
- [ ] Document mailbox_wait event schema
- [ ] Document mailbox_wake event schema
- [ ] Document mailbox_timeout event schema
- [ ] Document mailbox_overrun event schema
- [ ] Provide event usage examples
- [ ] Add event schema validation tests

---

### 5.2 HXE Section Examples

**Priority:** LOW  
**Dependencies:** 2.1 (.mailbox section format)  
**Estimated Effort:** 1 day

**Rationale:**  
Examples help developers understand declarative mailbox usage. Documentation gap identified in Study.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [ ] Create example .mailbox section for simple IPC
- [ ] Create example for fan-out scenario
- [ ] Create example for tap monitoring
- [ ] Create example for stdio redirection
- [ ] Add examples to documentation
- [ ] Include explanatory comments

---

### 5.3 Usage Pattern Documentation

**Priority:** LOW  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Documentation gap: missing examples of fan-out and tap usage patterns (Study section 3).

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [ ] Document single-reader usage pattern
- [ ] Document fan-out usage pattern with examples
- [ ] Document tap usage pattern with examples
- [ ] Document namespace usage (svc:, pid:, app:, shared:)
- [ ] Document blocking vs. polling patterns
- [ ] Document error handling patterns
- [ ] Add code examples for each pattern
- [ ] Create tutorial-style documentation

---

### 5.4 Expand Test Coverage

**Priority:** MEDIUM  
**Dependencies:** Phases 1-4 complete  
**Estimated Effort:** 1 week

**Rationale:**  
Test coverage expansion needed for new features and gap closures. Ensures quality and prevents regressions.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [ ] Add tests for timeout status code behavior
- [ ] Add tests for descriptor exhaustion scenarios
- [ ] Add tests for event emission (all event types)
- [ ] Add tests for resource monitoring APIs
- [ ] Add tests for .mailbox section processing
- [ ] Add tests for scheduler integration (WAIT_MBX state)
- [ ] Add tests for quota enforcement
- [ ] Add stress tests (many descriptors, many messages)
- [ ] Add concurrency tests (multiple tasks, contention)
- [ ] Measure and document test coverage metrics
- [ ] Add tests to CI pipeline

---

## Phase 6: C Port

### 6.1 C Mailbox Manager

**Priority:** LOW (Deferred until VM C port complete)  
**Dependencies:** VM Phase 2 (C port)  
**Estimated Effort:** 2-3 weeks

**Rationale:**  
Like VM and Executive, mailbox needs C implementation for MCU deployment. Python is reference only.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [ ] Create C mailbox manager structure (`platforms/c/mailbox/`)
- [ ] Port MailboxDescriptor structure to C
- [ ] Port MailboxMessage structure to C
- [ ] Port HandleState structure to C
- [ ] Implement BIND operation in C
- [ ] Implement OPEN operation in C
- [ ] Implement SEND operation in C
- [ ] Implement RECV operation in C
- [ ] Implement PEEK operation in C
- [ ] Implement TAP operation in C
- [ ] Implement CLOSE operation in C
- [ ] Add C build system integration
- [ ] Document C mailbox API

---

### 6.2 Zero-Copy Message Handling

**Priority:** LOW  
**Dependencies:** 6.1 (C mailbox manager)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Optimize for embedded without Python overhead. Design specifies C-compatible message headers for zero-copy (Study section 1).

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [ ] Design zero-copy message buffer strategy
- [ ] Implement message buffer pool for C port
- [ ] Implement zero-copy SEND (pass buffer ownership)
- [ ] Implement zero-copy RECV (return buffer ownership)
- [ ] Add buffer pool management (alloc/free)
- [ ] Handle buffer exhaustion gracefully
- [ ] Add zero-copy tests
- [ ] Benchmark performance vs. copy-based approach
- [ ] Document zero-copy semantics and limitations

---

### 6.3 Resource Profile Tuning

**Priority:** LOW  
**Dependencies:** 6.1 (C mailbox manager), 4.2 (Resource budgets)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Implement AVR/embedded descriptor pool sizing (section 4.6). Optimize for constrained environments.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [ ] Define AVR resource profile (minimal descriptors, small capacities)
- [ ] Define ARM Cortex-M profile (moderate descriptors)
- [ ] Define host platform profile (large pools)
- [ ] Implement compile-time profile selection
- [ ] Add profile-specific tests on target hardware
- [ ] Measure memory footprint per profile
- [ ] Document profile selection and configuration
- [ ] Provide tuning guidelines for custom profiles

---

### 6.4 Cross-Platform Test Suite

**Priority:** LOW  
**Dependencies:** 6.1 (C mailbox manager)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Shared test vectors for Python and C implementations. Ensures behavioral equivalence across platforms.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.03--Mailbox](../../../04--Design/04.03--Mailbox.md)
- [ ] Create shared test vector format (JSON test cases)
- [ ] Define test vector schema (inputs, expected outputs)
- [ ] Port existing Python tests to test vector format
- [ ] Implement test harness for C port
- [ ] Implement test result comparison
- [ ] Add cross-platform tests to CI pipeline
- [ ] Document test vector format
- [ ] Add regression tests for all mailbox operations

---

## Definition of Done (DoD)

This implementation is considered complete when all of the following criteria are met:

### Phase 1 Completion
- [ ] Timeout status code added to headers and constants
- [ ] Descriptor exhaustion status added to headers and constants
- [ ] Event emission integrated with executive event stream (all 6 event types)
- [ ] Resource monitoring APIs functional (descriptor usage, queue depth, memory)
- [ ] Fan-out reclamation verified and tested
- [ ] Tap isolation verified and tested
- [ ] All Phase 1 tests pass with 100% success rate
- [ ] Code review completed
- [ ] No regression in existing functionality

### Phase 2 Completion
- [ ] .mailbox section format defined and documented
- [ ] Section parser implemented and tested
- [ ] Preprocessed mailbox creation functional
- [ ] Toolchain updated to generate .mailbox sections
- [ ] All Phase 2 tests pass
- [ ] HXE format documentation updated

### Phase 3 Completion
- [ ] Formal WAIT_MBX state integration complete
- [ ] Timeout heap management integrated
- [ ] Wake priority handling verified
- [ ] Scheduler counters implemented and exposed
- [ ] All Phase 3 tests pass
- [ ] Integration with executive scheduler verified
- [ ] Issue #2_scheduler cross-referenced

### Phase 4 Completion
- [ ] Quota enforcement implemented (descriptor pool, per-task handles)
- [ ] Resource budgets finalized in documentation
- [ ] Exhaustion handling verified (graceful degradation)
- [ ] Stdio rate limiting implemented (if applicable)
- [ ] All Phase 4 tests pass
- [ ] Resource management documented

### Phase 5 Completion
- [ ] Event schema documented in executive protocol
- [ ] HXE section examples provided
- [ ] Usage pattern documentation complete
- [ ] Test coverage expanded (>80% for mailbox subsystem)
- [ ] All Phase 5 tests pass
- [ ] All documentation reviewed and approved

### Phase 6 Completion
- [ ] C mailbox manager implements all operations
- [ ] Zero-copy message handling optimized
- [ ] Resource profiles tuned for target platforms
- [ ] Cross-platform test suite passes on both Python and C
- [ ] All Phase 6 tests pass
- [ ] C port documentation complete

### Overall Quality Criteria
- [ ] Zero known security vulnerabilities in mailbox implementation
- [ ] Zero known data corruption or message loss bugs
- [ ] All design requirements (DR-*) satisfied
- [ ] All design goals (DG-*) achieved or explicitly deferred with rationale
- [ ] CI pipeline green on all supported platforms
- [ ] Code follows project style guidelines and passes linting
- [ ] All changes committed with clear, descriptive commit messages
- [ ] Implementation notes updated in System/Mailbox.md
- [ ] Integration with VM SVC dispatcher verified
- [ ] Integration with Executive scheduler and event stream verified

### Traceability
- [ ] All design requirements tracked to implementation
- [ ] All test cases traced to requirements
- [ ] All gaps from Study document addressed or explicitly deferred
- [ ] DependencyTree.md updated with completion status
- [ ] Cross-references to issue #1_mailbox and #2_scheduler resolved

---

## Cross-References

**Design Documents:**
- [04.03--Mailbox.md](../../../04--Design/04.03--Mailbox.md) - Mailbox Design Specification
- [System/Mailbox.md](../../system/Mailbox.md) - Implementation Notes

**Gap Analysis:**
- [01--Study.md](./01--Study.md) - Gap Analysis Study

**Dependencies:**
- [DependencyTree.md](../DependencyTree.md) - Cross-module dependency tracking

**Related Components:**
- VM (SVC module 0x05 dispatcher)
- Executive (scheduler integration, event stream, timer heap)
- HXE v2 format (.mailbox metadata sections)
- Value/Command services (subscription integration)

**Related Issues:**
- `issues/#1_mailbox/` - Implementation history and updates
- `issues/#2_scheduler` - State machine integration

**Test Specifications:**
- Test plans to be documented in `main/06--Test/system/Mailbox_tests.md`

**Protocol Documentation:**
- `docs/executive_protocol.md` - Event schema documentation
- `docs/abi_syscalls.md` - Module 0x05 SVC specifications

**Resource Documentation:**
- `docs/resource_budgets.md` - Descriptor pool sizes and quotas

---

**Last Updated:** 2025-10-31  
**Status:** Initial Plan  
**Owner:** Mailbox Implementation Team

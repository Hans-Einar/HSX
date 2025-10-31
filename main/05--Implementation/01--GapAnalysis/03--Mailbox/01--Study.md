# Gap Analysis: Mailbox

## 1. Scope Recap

_Brief synopsis of the design document and links back to the design specification._

**Design Reference:** [04.03--Mailbox.md](../../../04--Design/04.03--Mailbox.md)

**Summary:**  
The Mailbox subsystem design specifies an executive-owned IPC service providing deterministic task-to-task and host-to-task messaging. It serves as the core IPC mechanism for HSX. Key design principles include:

- **Executive-driven model** - no autonomous scheduling, all operations orchestrated by executive
- **Deterministic delivery** - FIFO ordering within descriptors, consistent fan-out delivery
- **Multiple delivery modes** - single-reader (default), fan-out, tap (non-destructive observers)
- **Namespace isolation** - `svc:`, `pid:`, `app:`, `shared:` for service/task/application/broadcast scoping
- **Blocking and timeouts** - poll/finite/infinite timeout support with scheduler integration
- **Resource bounded** - statically configured descriptor pools, capacity limits per `resource_budgets.md`
- **Portable structures** - C-compatible message headers for zero-copy firmware integration
- **Wait/wake coordination** - tasks transition to `WAIT_MBX` state, scheduler wakes on message arrival or timeout

---

## 2. Current Implementation

_What already exists today that satisfies the design intent._

**Code Paths:**
- **Python mailbox manager:** `python/mailbox.py` (572 lines, fully functional)
  - `MailboxManager` class with complete IPC subsystem
  - `MailboxDescriptor` dataclass with all design fields
  - `MailboxMessage` and `HandleState` dataclasses
  - Full SVC implementation: `bind`, `open`, `send`, `recv`, `peek`, `tap`, `close`
  - Namespace support: `svc:`, `pid:`, `app:`, `shared:` with target parsing
  - Delivery modes: single-reader, fan-out (with drop/block policies), tap mode
  - Stdio integration: per-task `stdin`/`stdout`/`stderr` mailbox handling
  - Waiter list management and descriptor lifecycle
- **Constants and definitions:** `python/hsx_mailbox_constants.py` (67 lines)
  - Python constants mirroring C header definitions
- **C header:** `include/hsx_mailbox.h` (128 lines)
  - Shared constants between C and Python
  - Status codes, mode flags, namespace IDs, timeout constants
  - ABI calling convention documentation
- **Assembly helpers:** `examples/lib/hsx_mailbox.mvasm`, `examples/lib/hsx_mailbox.h`
  - Assembly wrappers for SVC calls
- **VM SVC dispatcher:** Mailbox module 0x05 implemented in `platforms/python/host_vm.py`
  - Handler routes to executive mailbox manager

**Tests:**
- `python/tests/test_mailbox_manager.py` - Core mailbox manager unit tests
- `python/tests/test_mailbox_integration.py` - Integration scenarios
- `python/tests/test_mailbox_svc_runtime.py` - SVC runtime tests
- `python/tests/test_mailbox_wait.py` - Blocking and waiter tests
- `python/tests/test_mailbox_namespace.py` - Namespace parsing and isolation
- `python/tests/test_mailbox_lifecycle.py` - Descriptor lifecycle and cleanup
- `python/tests/test_mailbox_constants.py` - Constant synchronization tests
- `python/tests/test_exec_mailbox.py` - Executive integration tests
- **Total test coverage:** 837 lines across 8 test files

**Tools:**
- `python/shell_client.py` - Includes `listen` command for tapping mailbox streams
- `python/execd.py` - Executive RPC commands: `mailbox_snapshot`, `send`, `listen`
- `python/blinkenlights.py` - Visual monitoring of mailbox activity

**Documentation:**
- `docs/abi_syscalls.md` - Module 0x05 mailbox SVC specifications marked "Implemented (Python)"
- Design documents: `main/04--Design/04.03--Mailbox.md` (347 lines), `main/03--Architecture/03.03--Mailbox.md`
- Issue tracking: `issues/#1_mailbox/` - multiple documents on implementation, verification, updates

---

## 3. Missing or Partial Coverage

_Gaps that block full compliance with the design._

**Open Items:**
- **HXE v2 declarative mailbox creation (4.5.1, 3.9):** Design specifies `.mailbox` metadata section preprocessing to create mailboxes before VM execution. Not implemented - mailboxes are created dynamically at runtime via BIND SVC only.
- **Timeout status code (5.1.1):** Design specifies `HSX_MBX_STATUS_TIMEOUT` (0x07) for timeout expiry. Current implementation returns `WOULDBLOCK` on timeout - ABI update pending.
- **Executive event emission (5.2, 8):** Design specifies structured events (`mailbox_send`, `mailbox_recv`, `mailbox_wait`, `mailbox_wake`, `mailbox_timeout`, `mailbox_overrun`) for debugger/tooling. Current implementation has basic internal tracking but no formal event emission to executive event stream.
- **Resource monitoring/accounting (4.6, 5.2):** Design specifies tracking descriptor usage, queue depth, memory footprint against `resource_budgets.md`. Current implementation tracks descriptors but lacks formal quota enforcement and monitoring APIs.
- **Descriptor exhaustion status (5.1.1):** Design defines `HSX_MBX_STATUS_NO_DESCRIPTOR` (0x05) but not in current C header or Python constants.
- **Scheduler integration validation (4.3, 4.4.4, 8):** Design specifies formal `WAIT_MBX` state transitions with timeout heap management. Current implementation has waiter lists but integration with scheduler state machine may be incomplete (related to `issues/#2_scheduler`).
- **Tap priority enforcement (4.4.3, 6):** Design states taps should not block descriptor owner. Implementation has tap mode but priority/isolation may need validation.
- **Fan-out reclamation algorithm (4.4.2):** Design specifies messages acknowledged by all readers are removed. Implementation tracks `last_seq` per handle but reclamation logic should be verified for correctness.
- **Stdio rate limiting (6):** Design mentions rate limits for tap consumers to prevent starvation. Not explicitly implemented or configurable.
- **C port:** Like VM and Executive, mailbox needs C implementation for MCU deployment. Python is reference only.

**Deferred Features:**
- **Advanced descriptor policies:** Design mentions compile-time disabled features for embedded profiles. No build system for variant selection.
- **Value/command subscription storms mitigation (6):** Design mentions coalescing notification bursts. Not implemented - relies on application-level throttling.
- **FRAM-backed descriptor persistence:** Design mentions flushing descriptors on provisioning reload. Not implemented - descriptors are runtime-only.

**Documentation Gaps:**
- HXE v2 `.mailbox` section format not documented - schema for declarative mailbox creation undefined
- Resource budget specifics incomplete - actual descriptor pool sizes per platform not finalized in `resource_budgets.md`
- Event schema for mailbox events not formally documented in `executive_protocol.md`
- Missing examples of fan-out and tap usage patterns

---

## 4. Next Actions

_Ordered steps to close the gaps._

**Priority Actions:**

**Phase 1: Complete Python Implementation**
1. **Add timeout status code** - Define `HSX_MBX_STATUS_TIMEOUT` in C header and Python constants per section 5.1.1
2. **Add descriptor exhaustion status** - Define `HSX_MBX_STATUS_NO_DESCRIPTOR` per section 5.1.1
3. **Event emission integration** - Emit structured mailbox events (`mailbox_send`, `mailbox_recv`, `mailbox_wait`, `mailbox_wake`, `mailbox_timeout`, `mailbox_overrun`) to executive event stream per sections 5.2 and 8
4. **Resource monitoring APIs** - Expose descriptor usage, queue depth, memory footprint tracking per section 4.6
5. **Validate fan-out reclamation** - Verify message cleanup algorithm when all readers acknowledge per section 4.4.2
6. **Validate tap isolation** - Ensure taps don't block owner with drop-on-overflow policy per sections 4.4.3 and 6

**Phase 2: HXE v2 Declarative Support**
7. **Define `.mailbox` section format** - Specify HXE metadata section schema for declarative mailbox creation
8. **Section parser** - Parse `.mailbox` sections from HXE header per section 4.5.1
9. **Preprocessed creation** - Create mailboxes before VM execution per architecture section 3.9
10. **Update toolchain** - Generate `.mailbox` sections from application code annotations

**Phase 3: Scheduler Integration**
11. **Formal WAIT_MBX state** - Ensure mailbox blocking transitions to explicit `WAIT_MBX` state per section 4.3
12. **Timeout heap management** - Implement or validate timer heap for blocked mailbox operations per section 4.4.4
13. **Wake priority handling** - Verify FIFO wake order and tap priority per sections 4.6 and 6
14. **Scheduler counters** - Track `MAILBOX_STEP`, `MAILBOX_WAKE`, `MAILBOX_TIMEOUT` for diagnostics per section 4.6

**Phase 4: Resource Management**
15. **Quota enforcement** - Implement descriptor pool limits and per-task handle limits per section 4.6
16. **Resource budgets** - Finalize descriptor pool sizes and capacity defaults in `resource_budgets.md`
17. **Exhaustion handling** - Graceful degradation when descriptor pool exhausted per section 6
18. **Stdio rate limiting** - Implement tap rate limits to prevent starvation per section 6

**Phase 5: Documentation and Testing**
19. **Event schema documentation** - Document mailbox event types and fields in `executive_protocol.md`
20. **HXE section examples** - Provide examples of `.mailbox` metadata sections
21. **Usage pattern documentation** - Document fan-out and tap usage patterns with examples
22. **Expand test coverage** - Add tests for timeout status, exhaustion scenarios, event emission

**Phase 6: C Port**
23. **C mailbox manager** - Implement MailboxManager equivalent in C for MCU targets
24. **Zero-copy message handling** - Optimize for embedded without Python overhead
25. **Resource profile tuning** - Implement AVR/embedded descriptor pool sizing per section 4.6
26. **Cross-platform test suite** - Shared test vectors for Python and C implementations

**Cross-References:**
- Design Requirements: DR-1.1, DR-1.3, DR-5.1, DR-5.2, DR-6.1, DR-8.1
- Design Goals: DG-1.2, DG-1.3, DG-1.4, DG-5.1, DG-5.2, DG-5.3, DG-6.1, DG-6.2, DG-6.3, DG-6.4, DG-8.2
- Related issues: `issues/#1_mailbox/` (implementation history), `issues/#2_scheduler` (state machine integration)
- Related: HXE v2 format (needs `.mailbox` section), Executive event streaming, Value/command subscriptions

---

**Last Updated:** 2025-10-31  
**Status:** In Progress (Python implementation substantial, HXE v2 and C port not started)

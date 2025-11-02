# Executive Implementation Plan

## Planned Implementation Order (Grand Plan)

1. Phase 1 - Core debugger infrastructure (sessions, PID locks, keepalive).
2. Phase 2 - Event streaming and scheduler integration.
3. Phase 3 - RPC/controller extensions for the streaming loader.
4. Phase 4 - Clock and task orchestration polish.
5. Phase 5 - Python TUI integration hooks.
6. Phase 6 - C port (deferred until Python milestones land).
7. Phase 7 - Documentation and validation pass.

## Sprint Scope

This sprint delivers the Python phases (1 through 5) and the associated validation work, while explicitly deferring the Phase 6 C port. Capture any C-specific discoveries as TODOs for the deferred phase and keep the plan focused on Python execution.

## Overview

This implementation plan addresses the gaps identified in the Executive Study document ([01--Study.md](./01--Study.md)) and aligns with the implementation notes in the System document ([../../system/Executive.md](../../system/Executive.md)). The plan is organized chronologically with clear dependencies tracked in [DependencyTree.md](../DependencyTree.md).

**Design Reference:** [04.02--Executive.md](../../../04--Design/04.02--Executive.md)

---

## Phase 1: Core Debugger Infrastructure

### 1.1 Session Management

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies session.open/close/keepalive with PID locks and capability negotiation (section 5.2). System/Executive.md notes: "Implement PID lock table + capability negotiation" as a core requirement. Foundation for all client interactions.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Design session state structure (session_id, client_info, capabilities, owned_pids, timestamp)
- [x] Implement `session.open` RPC command with capability negotiation
- [x] Implement `session.close` RPC command with PID lock cleanup
- [x] Implement `session.keepalive` RPC command with timeout detection
- [x] Add session lock table tracking which PIDs are owned by which sessions
- [x] Add EBUSY error handling when attempting operations on locked PIDs
- [x] Add session timeout handling (auto-close inactive sessions)
- [x] Add session tests (open/close lifecycle, timeout, PID locking)
- [x] Update `docs/executive_protocol.md` with session management API

---

### 1.2 Event Streaming Foundation

**Priority:** HIGH  
**Dependencies:** 1.1 (Session management)  
**Estimated Effort:** 4-5 days

**Rationale:**  
Design specifies comprehensive event streaming with subscribe/unsubscribe/ack (Section 7). System/Executive.md notes: "Build EventStreamer with bounded queue + ACK handling per docs/executive_protocol.md; include warning events on drop." Critical for debugger and tooling integration.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Design event schema structure (seq, ts, pid, type, data) per Section 7.1
- [x] Implement bounded ring buffer per session (configurable size: 100-1000 events)
- [x] Implement `events.subscribe` RPC command with event type filtering
- [x] Implement `events.unsubscribe` RPC command
- [x] Implement `events.ack` RPC command for flow control
- [x] Add drop-oldest policy when buffer is full
- [x] Emit warning events when events are dropped (back-pressure indication)
- [x] Add event routing from VM to subscribed sessions
- [x] Define core event types: trace_step, debug_break, task_state, scheduler
- [x] Add event streaming tests (subscribe, buffer overflow, ack protocol)
- [x] Update `docs/executive_protocol.md` with event streaming API and schema

---

### 1.3 Breakpoint Management

**Priority:** HIGH  
**Dependencies:** 1.2 (Event streaming for debug_break events)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies bp.set/clear/list with per-PID breakpoint sets and pre/post-step checking (sections 5.2, 8.6). Essential debugger feature.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Design breakpoint structure (address, pid, enabled, hit_count)
- [x] Implement per-PID breakpoint sets (dict mapping PID to set of breakpoints)
- [x] Implement `bp.set(pid, address)` RPC command
- [x] Implement `bp.clear(pid, address)` RPC command
- [x] Implement `bp.list(pid)` RPC command
- [x] Add pre-step breakpoint checking (before VM step)
- [x] Add post-step breakpoint checking (after VM step)
- [x] Emit debug_break event when breakpoint hits
- [x] Pause task on breakpoint hit
- [x] Add breakpoint tests (set/clear, hit detection, multiple breakpoints)
- [x] Update `docs/executive_protocol.md` with breakpoint API

---

### 1.4 Symbol Loading

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies .sym JSON file loading and caching at task load time (section 5.4). Required for stack reconstruction, disassembly annotations, and symbol enumeration.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Define .sym JSON file format (functions, variables, types)
- [x] Implement symbol file loader (parse JSON, validate structure)
- [x] Add symbol caching per PID (load at task load time)
- [x] Add symbol lookup by address (for stack frames)
- [x] Add symbol lookup by name (for watch expressions)
- [x] Add symbol file path configuration (default: same dir as HXE + .sym extension)
- [x] Handle missing symbol files gracefully (no crash, just no symbols)
- [x] Add symbol loading tests (valid/invalid format, lookup tests)
- [x] Document .sym file format in `docs/` directory

---

### 1.5 Stack Reconstruction

**Priority:** MEDIUM  
**Dependencies:** 1.4 (Symbol loading), VM Phase 1.5 (trace APIs)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies stack.info API with frame pointer walking and symbol lookup (section 5.3). Critical for debugger stack traces.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Implement `stack.info(pid, max_frames)` RPC command
- [x] Design stack frame structure (pc, sp, fp, func_name, func_addr, line_num)
- [x] Implement frame pointer walking algorithm
- [x] Use VM register access APIs to read SP, FP, PC
- [x] Read memory to walk frame chain
- [x] Map addresses to function names using symbol table
- [x] Handle stack walk termination (null FP, max frames, invalid address)
- [x] Add error handling for corrupted stacks
- [x] Add stack reconstruction tests (normal calls, deep stacks, no symbols)
- [x] Update `docs/executive_protocol.md` with stack.info API
- [x] Enhance UI stack views with interactive frame drill-down / symbol annotations
- [x] Thread `stack.info` helper through remaining debugger front-ends once they migrate from scaffolding

---

### 1.6 Disassembly API

**Priority:** MEDIUM  
**Dependencies:** 1.4 (Symbol loading), VM (disassembler available)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies disasm.read with symbol annotations and caching strategies (section 5.4). Enables source-level debugging views.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Implement `disasm.read(pid, addr, count, mode)` RPC command
- [x] Integrate with existing Python disassembler (`python/disassemble.py`)
- [x] Add symbol annotation (label function names, variable references)
- [x] Support modes: on-demand (no cache), cached (cache results)
- [x] Read task memory via VM memory access APIs
- [x] Add address-to-symbol mapping in output
- [x] Handle disassembly errors (invalid opcodes, out-of-bounds)
- [x] Add disassembly tests (various opcodes, with/without symbols)
- [x] Update `docs/executive_protocol.md` with disasm.read API

---

## Phase 2: Enhanced Debugging Features

### 2.1 Symbol Enumeration

**Priority:** MEDIUM  
**Dependencies:** 1.4 (Symbol loading)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design specifies symbols.list API for function/variable enumeration (section 5.5). Useful for debugger UI autocomplete and exploration.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Implement `symbols.list(pid, type)` RPC command
- [x] Support type filters: 'functions', 'variables', 'all'
- [x] Return symbol list with names, addresses, sizes, types
- [x] Add pagination support for large symbol tables
- [x] Add symbol tests (enumerate functions, variables, filtering)
- [x] Update `docs/executive_protocol.md` with symbols.list API

---

### 2.2 Memory Regions

**Priority:** LOW  
**Dependencies:** 1.4 (Symbol loading)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design specifies memory.regions API reporting layout from .sym or HXE header (section 5.6). Helps debuggers understand memory map.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Implement `memory.regions(pid)` RPC command
- [x] Extract regions from HXE header (code, data, stack, heap)
- [x] Extract regions from .sym file (if available)
- [x] Return region list with start, end, type, permissions, name
- [x] Add memory region tests
- [x] Update `docs/executive_protocol.md` with memory.regions API

---

### 2.3 Watch Expressions

**Priority:** MEDIUM  
**Dependencies:** 1.2 (Event streaming), 1.4 (Symbol loading)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies watch.add/remove/list with change detection (section 5.7). Enables monitoring of memory locations and variables.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Implement `watch.add(pid, expr, type)` RPC command
- [x] Implement `watch.remove(pid, watch_id)` RPC command
- [x] Implement `watch.list(pid)` RPC command
- [x] Support expression types: address, symbol name
- [x] Parse symbol names and resolve to addresses
- [x] Track previous value for change detection
- [x] Check watches after each step (post-step hook)
- [x] Emit watch_update events when values change
- [x] Add watch expression tests (add/remove, change detection, symbol resolution)
- [x] Update `docs/executive_protocol.md` with watch API

---

### 2.4 Event Back-Pressure

**Priority:** MEDIUM  
**Dependencies:** 1.2 (Event streaming foundation)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies events.ack protocol and drop-oldest policy (section 7.3). System/Executive.md notes: "Build EventStreamer with bounded queue + ACK handling."

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Implement ACK sequence number tracking per session
- [x] Add flow control based on unacknowledged event count
- [x] Implement slow client detection (lag threshold)
- [x] Add configurable buffer size per session
- [x] Log warnings when events are dropped
- [x] Add back-pressure metrics (drops per session, lag time)
- [x] Add back-pressure tests (slow client, buffer overflow)
- [x] Document back-pressure behavior in protocol docs

---

### 2.5 Task State Events

**Priority:** HIGH  
**Dependencies:** 1.2 (Event streaming), 3.1 (Formal state machine)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies structured task_state events with reason codes (section 7.2). Essential for debugger UI state tracking.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Define task_state event structure (pid, old_state, new_state, reason)
- [x] Define reason codes: debug_break, sleep, mailbox_wait, timeout, returned, killed, loaded
- [x] Emit task_state events on all state transitions
- [x] Add reason field to state transition logic
- [x] Add task state event tests
- [x] Update event schema documentation with task_state event

---

### 2.6 Register Change Tracking

**Priority:** LOW  
**Dependencies:** 1.2 (Event streaming), VM Phase 1.5 (trace APIs)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies optional changed_regs field in trace_step events to optimize TUI (section 7.2). Performance optimization for debugger displays.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Track previous register values per PID
- [x] Compare registers after each step
- [x] Add changed_regs field to trace_step events (array of register IDs)
- [x] Make register change tracking optional (config flag)
- [x] Add register change tests
- [x] Document changed_regs field in event schema

---

## Phase 3: HXE v2 and Metadata

### 3.1 HXE v2 Format Support

**Priority:** MEDIUM  
**Dependencies:** VM Phase 1.6 (streaming loader for large HXE files)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies extending loader to handle version 0x0002 with metadata sections (sections 1.2, 3.8). Enables value/command/mailbox metadata.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Extend Python MiniVM loader to recognise version 0x0002 (app_name, allow_multiple_instances, meta table) while remaining compatible with v1 images.
- [x] Expose metadata/detail blocks from `load_hxe_bytes()` so `ExecutiveState.load()` can consume them (including app_name + flags).
- [x] Implement metadata table parsing helpers for `.value`, `.cmd`, `.mailbox` sections and build canonical descriptor structures.
- [x] Teach `ExecutiveState.load()` to register declarative values/commands/mailboxes with existing managers (or stage stubs if runtime support is pending), and enforce allow_multiple_instances policy + app_name uniqueness.
- [x] Surface metadata in task records (`ps`, `info`, etc.) for downstream consumers.
- [x] Add pytest coverage for v2 loader paths (header parsing, metadata table, duplicate-instance handling) plus integration smoke via execd load.
- [ ] Update `docs/hxe_format.md`/protocol docs with any behavioural clarifications discovered during implementation.

---

### 3.2 Metadata Preprocessing

**Priority:** MEDIUM  
**Dependencies:** 3.1 (HXE v2 format support)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies parsing .value/.cmd/.mailbox sections and registering resources before VM execution (sections 1.2, 6.2). Enables declarative resource configuration.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Implement metadata preprocessing at task load time
- [x] Register value resources from .value section
- [x] Register command resources from .cmd section
- [x] Register mailbox bindings from .mailbox section
- [x] Validate metadata before VM execution (check for conflicts)
- [x] Add metadata preprocessing tests
- [x] Document metadata section formats

---

### 3.3 App Name Handling

**Priority:** LOW  
**Dependencies:** 3.1 (HXE v2 format)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design specifies extracting app_name from HXE header with multiple instance tracking (section 4.2). Enables named applications and instance management.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Extract app_name from HXE header (v2 format)
- [x] Track app instances with _#0, _#1 suffixes
- [x] Return EEXIST error if multiple instances not allowed
- [x] Add app name to task state and ps output
- [x] Add app name tests (single instance, multiple instances, conflicts)
- [ ] Document app naming conventions

---

## Phase 4: Scheduler and State Machine

### 4.1 Formal State Machine

**Priority:** HIGH  
**Dependencies:** None (refactors existing scheduler)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies explicit READY/RUNNING/WAIT_MBX/SLEEPING/PAUSED/RETURNED states with documented transitions (sections 8.1-8.2). System/Executive.md notes importance of scheduler state machine.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Define TaskState enum: READY, RUNNING, WAIT_MBX, SLEEPING, PAUSED, RETURNED, KILLED
- [x] Document state transition diagram
- [x] Refactor existing task state tracking to use TaskState enum
- [x] Implement state transition validation (only allow valid transitions)
- [x] Add state entry/exit hooks for debugging
- [x] Add state machine tests (all transitions, invalid transitions)
- [x] Document state machine in design docs

---

### 4.2 Wait/Wake Improvements

**Priority:** HIGH  
**Dependencies:** 4.1 (Formal state machine), Mailbox (wait/wake integration)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies timer heap for sleep deadlines and complete mailbox wait list integration (section 8.4). Completes scheduler functionality.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [x] Implement timer heap for SLEEPING task deadlines
- [x] Add timer expiration checking on each scheduler tick
- [x] Integrate mailbox wait lists with WAIT_MBX state
- [x] Add mailbox wake callback to transition WAIT_MBX -> READY
- [x] Add timeout support for mailbox operations
- [x] Add wait/wake tests (sleep timeouts, mailbox wakes)
- [x] Document wait/wake semantics

---

### 4.3 Scheduler Events

**Priority:** MEDIUM  
**Dependencies:** 1.2 (Event streaming), 4.1 (Formal state machine)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design specifies emitting scheduler events on context switches (section 7.2). Enables scheduler visualization and debugging.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Define scheduler event structure (old_pid, new_pid, reason, quantum_remaining)
- [ ] Emit scheduler events on every context switch
- [ ] Add reason codes: quantum_expired, sleep, wait_mbx, paused, killed
- [ ] Add scheduler event tests
- [ ] Update event schema documentation with scheduler event

---

### 4.4 Context Isolation Validation

**Priority:** HIGH  
**Dependencies:** VM Phase 1.7 (register access APIs)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies executive never directly manipulates PC/SP/registers (sections 4.1, 4.2, 8.2). System/Executive.md notes: related to issue #2_scheduler for context switching remediation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Audit existing executive code for direct context manipulation
- [ ] Replace direct context access with VM API calls
- [ ] Ensure executive only uses VM APIs: vm_reg_get, vm_reg_set, vm_reg_get_for, vm_reg_set_for
- [ ] Add assertions to detect context isolation violations
- [ ] Add context isolation tests (verify executive doesn't touch VM internals)
- [ ] Document context isolation principle
- [ ] Cross-reference with issue #2_scheduler

---

## Phase 5: Trace Infrastructure

### 5.1 Executive-Side Trace Storage

**Priority:** MEDIUM  
**Dependencies:** 1.2 (Event streaming), VM Phase 1.5 (trace APIs)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies configurable trace buffers with variant-specific sizes (section 6.4). System/Executive.md notes need for trace buffer management.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement trace record ring buffer (configurable size: 0, 100, 1000+ records)
- [ ] Define trace record structure (seq, ts, pid, pc, opcode, regs, flags)
- [ ] Add trace capture on each step (poll VM trace APIs)
- [ ] Implement trace query API (get recent N records for PID)
- [ ] Add trace buffer configuration (minimal: 0, development: 100, full: 1000+)
- [ ] Add trace buffer tests (capture, query, overflow)
- [ ] Document trace buffer configuration

---

### 5.2 Trace Record Format

**Priority:** MEDIUM  
**Dependencies:** 5.1 (Executive-side trace storage)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design specifies standardizing trace record structure (section 6.4). Ensures consistent trace data across tools.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Formalize trace record structure (seq, pid, pc, opcode, regs)
- [ ] Add optional fields (flags, changed_regs, mem_access)
- [ ] Implement trace record serialization (for export)
- [ ] Add trace record deserialization (for import)
- [ ] Document trace record format
- [ ] Add trace format tests

---

### 5.3 VM Trace Polling

**Priority:** MEDIUM  
**Dependencies:** 5.1 (Executive-side trace storage), VM Phase 1.5 (trace APIs)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design specifies polling VM minimal trace state after each step (section 6.4). Integrates VM and executive trace systems.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Call vm_get_last_pc() after each VM step
- [ ] Call vm_get_last_opcode() after each VM step
- [ ] Call vm_get_last_regs() after each VM step
- [ ] Store trace data in executive trace buffer
- [ ] Add trace polling configuration (enable/disable)
- [ ] Add trace polling tests
- [ ] Document trace polling behavior

---

## Phase 6: Modular Architecture and C Port

### 6.1 Modular Backend Design

**Priority:** MEDIUM  
**Dependencies:** Phase 4 complete (stable Python implementation)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Design specifies refactoring to support pluggable backends (section 1.1). Enables multiple deployment scenarios and C port preparation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Define backend interface contracts (filesystem, protocol, HAL)
- [ ] Refactor Python executive into core + backends
- [ ] Implement filesystem backends: host (Python I/O), SPI SD, CAN
- [ ] Implement protocol backends: JSON-RPC (TCP), UART, direct API
- [ ] Implement HAL backends: Python stub, future C HAL integration
- [ ] Add backend selection configuration
- [ ] Add modular backend tests
- [ ] Document backend interface

---

### 6.2 Executive Variant Profiles

**Priority:** MEDIUM  
**Dependencies:** 6.1 (Modular backend design)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies minimal/development/full debugger build configurations (section 1.1). Optimizes executive for different deployment scenarios.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Define minimal variant: no trace buffer, basic scheduler, minimal protocol
- [ ] Define development variant: 100-record trace buffer, debugger APIs, JSON-RPC
- [ ] Define full debugger variant: 1000+ record trace, all debugger features, event streaming
- [ ] Create build configuration system for variant selection
- [ ] Add variant-specific feature flags
- [ ] Document variant profiles and use cases
- [ ] Add variant build tests

---

### 6.3 C Port Structure

**Priority:** LOW (Deferred until VM C port complete)  
**Dependencies:** VM Phase 2 (C port), 6.1 (Modular backend design)  
**Estimated Effort:** 2-3 weeks

**Rationale:**  
Design specifies C executive for MCU targets with pluggable modules. Critical for embedded deployment but depends on VM C port.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Create C executive structure (`platforms/c/executive/`)
- [ ] Port core scheduler to C
- [ ] Port task state management to C
- [ ] Port protocol handler to C
- [ ] Implement C backend modules (filesystem, HAL)
- [ ] Add C build system (Makefile, CMake)
- [ ] Add cross-compilation support
- [ ] Document C port architecture

---

### 6.4 Backend Modules

**Priority:** LOW (Deferred)  
**Dependencies:** 6.3 (C port structure)  
**Estimated Effort:** 2-3 weeks

**Rationale:**  
Design specifies multiple backend implementations for different deployment scenarios (section 1.1).

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement SPI SD filesystem backend for C port
- [ ] Implement CAN filesystem backend for C port
- [ ] Implement UART protocol backend for C port
- [ ] Implement STM32 HAL backend
- [ ] Implement other MCU HAL backends as needed
- [ ] Add backend switching at compile time
- [ ] Add backend tests on target hardware
- [ ] Document backend selection and configuration

---

## Phase 7: Advanced Features

### 7.1 Observer Sessions

**Priority:** LOW  
**Dependencies:** 1.1 (Session management), 1.2 (Event streaming)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design allows read-only observer sessions alongside owner session (sections 3.46, 7.2). Enables multiple monitoring clients.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Add observer capability flag to session.open
- [ ] Restrict write operations for observer sessions (read-only)
- [ ] Allow multiple observer sessions simultaneously
- [ ] Implement priority event handling (owner before observers)
- [ ] Add observer session tests
- [ ] Document observer session semantics

---

### 7.2 FRAM Persistence

**Priority:** LOW  
**Dependencies:** 3.2 (Metadata preprocessing), HAL (FRAM interface)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Design specifies value persistence to FRAM with debounce (section 6.6). Enables persistent configuration across reboots.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Design FRAM layout for value persistence
- [ ] Implement value write debouncing (avoid excessive writes)
- [ ] Add value load from FRAM at boot
- [ ] Add value save to FRAM on change
- [ ] Add FRAM wear leveling (if needed)
- [ ] Add FRAM persistence tests
- [ ] Document FRAM layout and persistence semantics

---

### 7.3 Resource Budget Enforcement

**Priority:** LOW  
**Dependencies:** None (enhancement)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies runtime checks against resource budgets (sections 6.8, 8.5). System/Executive.md notes: "Integrate resource budget telemetry."

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Parse resource budgets from `docs/resource_budgets.md`
- [ ] Track RAM usage per task (code, data, stack, heap)
- [ ] Track flash usage per task
- [ ] Enforce limits at task load time
- [ ] Add resource exhaustion error handling
- [ ] Add resource budget telemetry (current usage vs limits)
- [ ] Add resource budget tests
- [ ] Document resource budget enforcement

---

### 7.4 Priority Scheduling

**Priority:** LOW  
**Dependencies:** 4.1 (Formal state machine)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design mentions future priority overlays on round-robin (sections 8.2, 8.5). Enhancement for real-time task support.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Add priority field to task state
- [ ] Implement priority-based ready queue (multiple priority levels)
- [ ] Modify scheduler to select highest priority ready task
- [ ] Add priority inheritance for mutex/mailbox contention (if needed)
- [ ] Add priority configuration API
- [ ] Add priority scheduling tests (preemption, starvation prevention)
- [ ] Document priority scheduling semantics

---

### 7.5 EXEC_GET_VERSION SVC

**Priority:** HIGH  
**Dependencies:** Shared ABI Header (external dependency)  
**Estimated Effort:** 1 day

**Rationale:**  
System/Executive.md notes: "Expose EXEC_GET_VERSION SVC + RPC command returning shared header info" per DR-2.5. Required for ABI version handshake.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Wait for shared ABI header to be generated (track in DependencyTree.md)
- [ ] Implement EXEC_GET_VERSION syscall (module 0x00)
- [ ] Return version information from shared header
- [ ] Add RPC command for EXEC_GET_VERSION
- [ ] Add version handshake tests
- [ ] Document EXEC_GET_VERSION in protocol docs
- [ ] Coordinate with VM SVC implementation

---

## Definition of Done (DoD)

This implementation is considered complete when all of the following criteria are met:

### Phase 1 Completion
- [ ] Session management fully implemented (open/close/keepalive, PID locks)
- [ ] Event streaming foundation functional (subscribe/unsubscribe, bounded buffer)
- [ ] Breakpoint management working (set/clear/list, hit detection)
- [ ] Symbol loading operational (.sym file parsing, lookup)
- [ ] Stack reconstruction functional (frame walking, symbol mapping)
- [x] Disassembly API working (with symbol annotations)
- [ ] All Phase 1 tests pass with 100% success rate
- [ ] Code review completed
- [ ] No regression in existing functionality

### Phase 2 Completion
- [ ] Symbol enumeration implemented
- [ ] Memory regions API functional
- [ ] Watch expressions working (add/remove/list, change detection)
- [ ] Event back-pressure handling complete (ACK protocol, drop policy)
- [ ] Task state events emitted on all transitions
- [ ] Register change tracking operational (optional optimization)
- [ ] All Phase 2 tests pass
- [ ] Protocol documentation updated

### Phase 3 Completion
- [ ] HXE v2 format support complete (version detection, metadata parsing)
- [ ] Metadata preprocessing functional (.value/.cmd/.mailbox sections)
- [ ] App name handling implemented (instance tracking, EEXIST handling)
- [ ] All Phase 3 tests pass
- [ ] HXE format documentation updated

### Phase 4 Completion
- [ ] Formal state machine implemented (all states, validated transitions)
- [ ] Wait/wake integration complete (timer heap, mailbox integration)
- [ ] Scheduler events emitted on context switches
- [ ] Context isolation validated (executive uses only VM APIs)
- [ ] All Phase 4 tests pass
- [ ] State machine documented

### Phase 5 Completion
- [ ] Executive-side trace storage implemented (configurable buffer sizes)
- [ ] Trace record format standardized
- [ ] VM trace polling operational (last_pc/opcode/regs)
- [ ] All Phase 5 tests pass
- [ ] Trace infrastructure documented

### Phase 6 Completion
- [ ] Modular backend design complete (pluggable backends)
- [ ] Executive variant profiles defined (minimal/development/full)
- [ ] C port structure established (deferred until VM C port complete)
- [ ] Backend modules implemented (filesystem, protocol, HAL)
- [ ] All Phase 6 tests pass
- [ ] Backend interface documented

### Phase 7 Completion
- [ ] Observer sessions implemented
- [ ] FRAM persistence complete
- [ ] Resource budget enforcement operational
- [ ] Priority scheduling implemented
- [ ] EXEC_GET_VERSION SVC functional
- [ ] All Phase 7 tests pass
- [ ] All advanced features documented

### Overall Quality Criteria
- [ ] Zero known security vulnerabilities in executive implementation
- [ ] Zero known data corruption bugs
- [ ] All design requirements (DR-*) satisfied
- [ ] All design goals (DG-*) achieved or explicitly deferred with rationale
- [ ] CI pipeline green on all supported platforms
- [ ] Code follows project style guidelines and passes linting
- [ ] All changes committed with clear, descriptive commit messages
- [ ] Implementation notes updated in System/Executive.md
- [ ] Integration with VM Phase 1.5 (trace APIs) and Phase 1.7 (register access) verified
- [ ] Integration with Mailbox (wait/wake) verified

### Traceability
- [ ] All design requirements tracked to implementation
- [ ] All test cases traced to requirements
- [ ] All gaps from Study document addressed or explicitly deferred
- [ ] DependencyTree.md updated with completion status
- [ ] Cross-references to issue #2_scheduler resolved

---

## Cross-References

**Design Documents:**
- [04.02--Executive.md](../../../04--Design/04.02--Executive.md) - Executive Design Specification
- [System/Executive.md](../../system/Executive.md) - Implementation Notes

**Gap Analysis:**
- [01--Study.md](./01--Study.md) - Gap Analysis Study

**Dependencies:**
- [DependencyTree.md](../DependencyTree.md) - Cross-module dependency tracking

**Related Components:**
- VM (execution engine, trace APIs, register access)
- Mailbox (wait/wake integration, IPC)
- HAL (hardware abstraction for C port)
- Debugger tools (TUI, VSCode integration)

**Related Issues:**
- `issues/#2_scheduler` - Context switching remediation

**Test Specifications:**
- Test plans to be documented in `main/06--Test/system/Executive_tests.md`

**Protocol Documentation:**
- `docs/executive_protocol.md` - JSON-RPC protocol specification

**ABI Documentation:**
- `docs/abi_syscalls.md` - Syscall definitions (module 0x00 for EXEC_GET_VERSION)

---

**Last Updated:** 2025-10-31  
**Status:** Initial Plan  
**Owner:** Executive Implementation Team

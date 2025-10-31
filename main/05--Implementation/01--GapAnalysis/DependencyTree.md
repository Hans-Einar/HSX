# Implementation Dependency Tree

## Overview

This document tracks implementation dependencies between the various Gap Analysis folders and their implementation plans. It serves as a coordination point to ensure that work proceeds in the correct order and that blocking dependencies are resolved before dependent work begins.

**Purpose:**
- Coordinate implementation order across components
- Track blocking dependencies between modules
- Identify critical path for overall implementation
- Prevent wasted effort on work that depends on incomplete components
- Provide visibility into overall implementation progress

---

## Legend

**Status Values:**
- 🔴 **Not Started** - No implementation work begun
- 🟡 **In Progress** - Active implementation work
- 🟢 **Complete** - Implementation finished and tested
- 🔵 **Blocked** - Waiting on dependency
- ⚪ **Deferred** - Explicitly postponed to future phase

**Priority:**
- P0: Critical path, blocks multiple other components
- P1: High priority, blocks some components
- P2: Medium priority, independent or few dependencies
- P3: Low priority, nice-to-have or deferred features

---

## Critical Dependencies

### Shared ABI Header

**Status:** 🔴 Not Started  
**Priority:** P0  
**Owner:** TBD  
**Blocks:**
- VM Phase 1.8 (Integrate Shared Syscall Header)
- Executive (SVC dispatcher)
- Mailbox (SVC module 0x05)
- All syscall-related implementations

**Description:**  
Shared header file defining module/function IDs for all syscalls. Must be generated and agreed upon before components can reference standardized constants.

**Todo:**
- [ ] Define module ID namespace (0x00-0xFF)
- [ ] Define function ID format within modules
- [ ] Generate C header file
- [ ] Generate Python constants file
- [ ] Document header versioning strategy
- [ ] Publish header to shared location

---

### Executive Scheduler/Event System

**Status:** 🟡 In Progress  
**Priority:** P0  
**Owner:** Executive Team  
**Blocks:**
- Mailbox (wait/wake integration)
- VM (trace event integration)
- Debugger (event stream consumption)

**Description:**  
Executive must provide scheduler primitives for blocking/unblocking PIDs and event emission before mailbox can implement wait/timeout semantics.

**Todo:**
- [ ] Finalize event stream schema
- [ ] Implement block/unblock PID APIs
- [ ] Implement event emission (emit_event)
- [ ] Document scheduler API
- [ ] Test scheduler with multiple tasks

---

## Module Implementation Status

### 01--VM

**Status:** 🟡 In Progress  
**Priority:** P0 (Critical - foundation for all task execution)  
**Implementation Plan:** [01--VM/02--ImplementationPlan.md](./01--VM/02--ImplementationPlan.md)

**Dependencies:**
- **External:** None (VM is foundational)
- **Internal:** Shared ABI Header (for Phase 1.8)

**Provides To:**
- Executive: VM execution engine
- Mailbox: SVC dispatch for module 0x05
- Debugger: Trace APIs and register access
- All components: Task execution substrate

**Current Phase:** Phase 1 (Python Reference Implementation)

**Completion Criteria:**
- [ ] Phase 1: Python reference implementation complete (shifts, PSW, DIV, ADC/SBC, trace APIs, streaming loader)
- [ ] Phase 2: C embedded port functional
- [ ] Phase 3: Advanced features (heap, paging, value/command services)
- [ ] Phase 4: Documentation and validation complete

---

### 02--Executive

**Status:** 🟡 In Progress  
**Priority:** P0 (Critical - orchestrates all VM and task operations)  
**Implementation Plan:** [02--Executive/02--ImplementationPlan.md](./02--Executive/02--ImplementationPlan.md)

**Dependencies:**
- **Requires:** VM Phase 1 (basic execution, trace APIs)
- **Requires:** Shared ABI Header

**Provides To:**
- All components: Scheduler, event stream, clock control
- Mailbox: Block/unblock APIs for wait/timeout
- Debugger: Event stream for trace consumption
- Tools: JSON-RPC protocol interface

**Current Phase:** Phase 1 (Core Debugger Infrastructure)

**Completion Criteria:**
- [ ] Session management (open/close/keepalive, PID locks)
- [ ] Event streaming foundation (subscribe/unsubscribe, bounded buffer, ACK protocol)
- [ ] Breakpoint management (set/clear/list, hit detection)
- [ ] Symbol loading and stack reconstruction
- [ ] Disassembly API with symbol annotations
- [ ] Formal state machine with wait/wake integration
- [ ] HXE v2 metadata support
- [ ] Trace infrastructure with configurable buffers

---

### 03--Mailbox

**Status:** 🟡 In Progress  
**Priority:** P1 (High - core IPC mechanism)  
**Implementation Plan:** [03--Mailbox/02--ImplementationPlan.md](./03--Mailbox/02--ImplementationPlan.md) *(To be created)*

**Dependencies:**
- **Requires:** Executive scheduler/event system (block/unblock APIs)
- **Requires:** Shared ABI Header (module 0x05 definitions)
- **Requires:** VM Phase 1 (for SVC dispatch)

**Provides To:**
- All task-based components: IPC mechanism
- Debugger: Mailbox event stream
- Tools: Stdio integration

**Current Phase:** TBD

**Completion Criteria:**
- [ ] Delivery modes implemented (single-reader, fan-out, tap)
- [ ] Wait/wake integration with executive
- [ ] Namespace support (svc:, pid:, app:, shared:)
- [ ] Back-pressure policies (block/drop)
- [ ] Stdio mailbox integration
- [ ] Event emission for mailbox operations

---

### 04--ValCmd

**Status:** 🔴 Not Started  
**Priority:** P2 (Medium - value command interface)  
**Implementation Plan:** [04--ValCmd/02--ImplementationPlan.md](./04--ValCmd/02--ImplementationPlan.md) *(To be created)*

**Dependencies:**
- **Requires:** VM Phase 3.3 (Value/Command services)
- **Requires:** Executive (event stream)
- **Requires:** Shared ABI Header

**Provides To:**
- Tools: Value inspection and command interface
- Debugger: Value queries

**Current Phase:** Not Started

**Completion Criteria:**
- [ ] Value service API implemented
- [ ] Command service API implemented
- [ ] Integration with executive protocol
- [ ] Documentation complete

---

### 05--Toolchain

**Status:** 🟡 In Progress  
**Priority:** P1 (High - required for development)  
**Implementation Plan:** [05--Toolchain/02--ImplementationPlan.md](./05--Toolchain/02--ImplementationPlan.md) *(To be created)*

**Dependencies:**
- **Requires:** VM Phase 1.1 (shift operations - for ISA completeness)
- **Requires:** VM Phase 1.2 (ADC/SBC - for ISA completeness)
- **Requires:** VM Phase 1.4 (DIV - for ISA completeness)

**Provides To:**
- All components: Assembly, compilation, build tools
- Developers: HXE binary generation

**Current Phase:** TBD

**Completion Criteria:**
- [ ] MVASM supports full ISA (including new opcodes)
- [ ] Disassembler supports full ISA
- [ ] HXE builder functional
- [ ] LLVM backend complete
- [ ] Build pipeline automated

---

### 06--Toolkit

**Status:** 🔴 Not Started  
**Priority:** P2 (Medium - development support tools)  
**Implementation Plan:** [06--Toolkit/02--ImplementationPlan.md](./06--Toolkit/02--ImplementationPlan.md) *(To be created)*

**Dependencies:**
- **Requires:** Executive (JSON-RPC protocol)
- **Requires:** VM (trace APIs)

**Provides To:**
- Developers: CLI tools, shell client, monitoring

**Current Phase:** Not Started

**Completion Criteria:**
- [ ] Shell client complete
- [ ] Monitoring tools complete
- [ ] CLI utilities complete

---

### 07--Provisioning

**Status:** 🔴 Not Started  
**Priority:** P2 (Medium - deployment support)  
**Implementation Plan:** [07--Provisioning/02--ImplementationPlan.md](./07--Provisioning/02--ImplementationPlan.md) *(To be created)*

**Dependencies:**
- **Requires:** VM Phase 1.6 (streaming HXE loader)
- **Requires:** VM Phase 2 (C port for embedded targets)

**Provides To:**
- Deployment: CAN/UART provisioning
- Embedded targets: Over-the-air updates

**Current Phase:** Not Started

**Completion Criteria:**
- [ ] Streaming provisioning protocol implemented
- [ ] CAN transport implemented
- [ ] UART transport implemented
- [ ] Provisioning tools complete

---

### 08--HAL

**Status:** 🔴 Not Started  
**Priority:** P1 (High - hardware abstraction)  
**Implementation Plan:** [08--HAL/02--ImplementationPlan.md](./08--HAL/02--ImplementationPlan.md) *(To be created)*

**Dependencies:**
- **Requires:** VM Phase 2 (C port)
- **Requires:** Executive (event system)

**Provides To:**
- Embedded targets: Hardware abstraction layer
- VM: Platform-specific primitives

**Current Phase:** Not Started

**Completion Criteria:**
- [ ] HAL interface defined
- [ ] Platform implementations (STM32, etc.)
- [ ] Integration with C port
- [ ] HAL tests on target hardware

---

### 09--Debugger

**Status:** 🔴 Not Started  
**Priority:** P1 (High - critical for development)  
**Implementation Plan:** [09--Debugger/02--ImplementationPlan.md](./09--Debugger/02--ImplementationPlan.md) *(To be created)*

**Dependencies:**
- **Requires:** VM Phase 1.5 (trace APIs)
- **Requires:** VM Phase 1.7 (register access APIs)
- **Requires:** Executive (event stream)

**Provides To:**
- Developers: Debugging capabilities
- TUI Debugger: Core debugging functionality
- VSCode Debugger: Core debugging functionality

**Current Phase:** Not Started

**Completion Criteria:**
- [ ] Breakpoint support
- [ ] Single-step execution
- [ ] Register inspection
- [ ] Memory inspection
- [ ] Stack trace generation
- [ ] Integration with debugger UIs

---

### 10--TUI_Debugger

**Status:** 🔴 Not Started  
**Priority:** P2 (Medium - TUI interface)  
**Implementation Plan:** [10--TUI_Debugger/02--ImplementationPlan.md](./10--TUI_Debugger/02--ImplementationPlan.md) *(To be created)*

**Dependencies:**
- **Requires:** Debugger (core debugging functionality)
- **Requires:** Executive (event stream)

**Provides To:**
- Developers: Terminal-based debugging UI

**Current Phase:** Not Started

**Completion Criteria:**
- [ ] TUI interface implemented
- [ ] Integration with core debugger
- [ ] Trace display
- [ ] Register/memory views
- [ ] Interactive commands

---

### 11--vscode_debugger

**Status:** 🔴 Not Started  
**Priority:** P2 (Medium - IDE integration)  
**Implementation Plan:** [11--vscode_debugger/02--ImplementationPlan.md](./11--vscode_debugger/02--ImplementationPlan.md) *(To be created)*

**Dependencies:**
- **Requires:** Debugger (core debugging functionality)
- **Requires:** Executive (event stream)

**Provides To:**
- Developers: VSCode debugging integration

**Current Phase:** Not Started

**Completion Criteria:**
- [ ] VSCode extension implemented
- [ ] Debug adapter protocol support
- [ ] Integration with core debugger
- [ ] Source-level debugging

---

## Critical Path Analysis

### Immediate Priorities (Current Sprint)

1. **VM Phase 1 Completion** (P0)
   - Blocks: Toolchain ISA updates, Executive trace integration, Debugger
   - Target: Complete shift ops, PSW flags, DIV, ADC/SBC

2. **Shared ABI Header** (P0)
   - Blocks: VM Phase 1.8, Executive SVC integration, Mailbox SVC
   - Target: Define and publish header

3. **Executive Scheduler/Event System** (P0)
   - Blocks: Mailbox wait/wake, VM trace integration, Debugger
   - Target: Finalize scheduler APIs and event schema

### Near-Term Priorities (Next 2-4 Weeks)

4. **VM Phase 1.5-1.6** (P0)
   - Trace APIs for debugger integration
   - Streaming loader for provisioning

5. **Mailbox Wait/Wake Integration** (P1)
   - Depends on: Executive scheduler
   - Enables: Full IPC functionality

6. **Toolchain ISA Updates** (P1)
   - Depends on: VM Phase 1 complete
   - Enables: Full development workflow

### Medium-Term Priorities (1-2 Months)

7. **VM Phase 2: C Port** (P0)
   - Depends on: VM Phase 1 complete
   - Enables: Embedded deployment, HAL, Provisioning

8. **Debugger Core** (P1)
   - Depends on: VM trace APIs, Executive event stream
   - Enables: TUI/VSCode debuggers

9. **HAL** (P1)
   - Depends on: VM C port
   - Enables: Hardware deployment

### Long-Term Priorities (2+ Months)

10. **VM Phase 3: Advanced Features** (P2)
    - Heap, paging, value/command services

11. **Provisioning** (P2)
    - Depends on: VM streaming loader, C port
    - Enables: Deployment workflows

12. **TUI/VSCode Debuggers** (P2)
    - Depends on: Debugger core
    - Enhances: Developer experience

---

## Blocking Issues

### Active Blocks

1. **Shared ABI Header** (blocking 3+ modules)
   - **Impact:** Cannot finalize SVC integration
   - **Action Required:** Assign owner, define header format
   - **Target Date:** TBD

2. **Executive Scheduler APIs** (blocking Mailbox, Debugger)
   - **Impact:** Cannot implement wait/timeout, event streaming
   - **Action Required:** Complete scheduler API specification
   - **Target Date:** TBD

### Resolved Blocks

*(None yet)*

---

## Update History

| Date | Module | Status Change | Notes |
|------|--------|---------------|-------|
| 2025-10-31 | VM | 🟡 In Progress | Phase 1 implementation begun, Study and Implementation Plan complete |
| 2025-10-31 | Executive | 🟡 In Progress | Implementation Plan created with 7 phases and detailed task breakdown |
| 2025-10-31 | DependencyTree | 🟢 Complete | Initial dependency tree created |

---

## Notes and Conventions

**Updating This Document:**
- Update status when a module begins work (🔴 → 🟡)
- Update status when a module completes a phase (🟡 → 🟢)
- Update status when blocked on dependency (🟡 → 🔵)
- Add entries to "Update History" table with each change
- Review dependencies quarterly to ensure accuracy

**Communication:**
- This document should be reviewed in weekly sync meetings
- Blocking issues should be escalated immediately
- Critical path changes should be communicated to all teams

**Tool Integration:**
- Consider integrating with project management tools
- Consider auto-generating dependency graphs
- Consider CI integration to detect broken dependencies

---

**Last Updated:** 2025-10-31  
**Maintained By:** Implementation Coordination Team  
**Review Cadence:** Weekly

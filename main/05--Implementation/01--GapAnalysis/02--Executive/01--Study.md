# Gap Analysis: Executive

## 1. Scope Recap

_Brief synopsis of the design document and links back to the design specification._

**Design Reference:** [04.02--Executive.md](../../../04--Design/04.02--Executive.md)

**Summary:**  
The Executive design specifies a host controller that manages MiniVM lifecycle, scheduling, and IPC services. It serves as a lightweight operating system coordinating tasks and abstracting hardware. Key responsibilities include:

- **Modular architecture** with pluggable backends (filesystem, protocol/shell, HAL, debug/trace)
- **Task scheduling** with single-instruction quanta and cooperative round-robin
- **Protocol server** (JSON-over-TCP) for shell/debugger clients with session management
- **HXE v2 metadata preprocessing** - parse `.value`/`.cmd`/`.mailbox` sections before VM execution
- **SVC bridge** handling syscalls from VM (mailbox, value/command, provisioning, HAL)
- **Debug/trace support** with configurable buffer sizes for minimal/development/full debugger variants
- **Event streaming** with session locks, back-pressure, and ACK protocol
- **Provisioning workflows** for loading/reloading tasks with FRAM persistence
- **Advanced debugger APIs** including stack reconstruction, disassembly with symbols, watch expressions, breakpoint management

---

## 2. Current Implementation

_What already exists today that satisfies the design intent._

**Code Paths:**
- **Executive daemon:** `python/execd.py` (1,055 lines)
  - `ExecutiveState` class managing tasks, scheduling, and VM control
  - JSON-RPC command handling over TCP socket
  - Basic commands: `ping`, `info`, `attach`, `detach`, `load`, `ps`, `clock`, `step`, `trace`, `pause`, `resume`, `kill`
  - Scheduler control: `sched` command for priority/quantum updates
  - Memory inspection: `peek`, `poke`, `dumpregs`
  - Mailbox integration: `mailbox_snapshot`, `send`, `listen`
  - Stdio routing: `stdio_fanout`, `dmesg` for log buffer
  - Auto-clock thread with rate control
  - Task state tracking via `task_states` dictionary
  - Log buffer with sequence numbers (512 entry ring buffer)
- **Executive client library:** `python/executive.py` (154 lines)
  - Simple client interface for executive protocol
  - Basic load and control operations
- **VM client:** `python/vmclient.py` - Protocol client for VM RPC communication
- **Mailbox manager:** `python/mailbox.py` - IPC subsystem implementation

**Tests:**
- `python/tests/test_exec_mailbox.py` - Executive mailbox integration tests
- `python/tests/test_scheduler_stats.py` - Scheduler statistics validation
- `python/exec_smoke.py` - Basic smoke test script

**Tools:**
- `python/shell_client.py` - Interactive shell client for executive protocol
- `python/blinkenlights.py` - Visual monitor/debugger TUI

**Documentation:**
- `docs/executive_protocol.md` - JSON-RPC protocol specification with core commands
- Design documents: `main/04--Design/04.02--Executive.md`
- Architecture: `main/03--Architecture/03.02--Executive.md`

---

## 3. Missing or Partial Coverage

_Gaps that block full compliance with the design._

**Open Items:**
- **Session management API (5.2):** Design specifies `session.open`, `session.close`, `session.keepalive` with PID locks and capability negotiation. Not implemented in current `execd.py` - no session tracking or lock management.
- **Event streaming (Section 7):** Design specifies comprehensive event streaming with `events.subscribe`, `events.unsubscribe`, `events.ack` and structured event schema (trace_step, debug_break, task_state, scheduler, mailbox_send/recv, watch_update, stdout/stderr). Current implementation only processes VM events internally - no subscription API or event streaming to clients.
- **Stack reconstruction API (5.3):** Design specifies `stack.info(pid, max_frames)` to walk call stack using frame pointers and symbol lookup. Not implemented.
- **Disassembly API (5.4):** Design specifies `disasm.read(pid, addr, count, mode)` with symbol annotations and caching strategies. Not implemented.
- **Symbol enumeration API (5.5):** Design specifies `symbols.list(pid, type)` to enumerate functions/variables from `.sym` files. No symbol loading or enumeration capability.
- **Memory region info API (5.6):** Design specifies `memory.regions(pid)` to report memory layout. Not implemented.
- **Watch expression API (5.7):** Design specifies `watch.add`, `watch.remove`, `watch.list` for tracking memory locations and emitting change events. Not implemented.
- **Breakpoint management API (5.2, 8.6):** Design specifies `bp.set`, `bp.clear`, `bp.list` with per-PID breakpoint sets and pre/post-step checking. Not implemented.
- **HXE v2 metadata preprocessing (1.1, 3.8, 6.2):** Design specifies parsing `.value`/`.cmd`/`.mailbox` sections from HXE header at load time and registering resources before VM execution. No HXE v2 format support or metadata processing.
- **Modular executive variants (1.1):** Design specifies three variants (minimal, development, full debugger) with different trace buffer sizes and feature sets. Current implementation is monolithic Python - no build system for variant selection.
- **Executive-side trace storage (6.4):** Design specifies configurable trace buffers (minimal: none, development: ~100 records, full: 1000+ records) in executive. Current implementation has no trace buffer management.
- **Context state isolation (4.1, 4.2, 8.2):** Design specifies executive NEVER stores or manipulates task context (PC, SP, registers) - context lives in VM. Current implementation may still snapshot context during switches (see scheduler issue #2).
- **Formal scheduler state machine (8.1, 8.2):** Design specifies explicit states (READY, RUNNING, WAIT_MBX, SLEEPING, PAUSED, RETURNED) with documented transitions. Current implementation tracks basic state but lacks formal state machine.
- **Wait/wake integration (8.4):** Design specifies timer heap for sleep deadlines and mailbox wait lists with wake events. Current implementation has basic support but incomplete timer management.
- **Back-pressure and ACK protocol (7.3):** Design specifies bounded ring buffer per session with `events.ack` for flow control. Not implemented.
- **App name and multiple instance handling (4.2):** Design specifies extracting `app_name` from HXE header with `_#0`, `_#1` suffixes for multiple instances, or EEXIST error if disallowed. Not implemented.
- **C embedded port:** Like VM, executive needs C port for MCU deployment with pluggable backend modules.

**Deferred Features:**
- **Observer sessions (3.46, 7.2):** Design allows read-only observer sessions alongside owner session with priority handling. Basic framework not in place yet.
- **Register change tracking (7.2):** Optional `changed_regs` field in `trace_step` events to optimize TUI. Requires trace infrastructure first.
- **Security and access control (Section 10):** Design acknowledges lack of authentication, ACLs, or session capabilities. Explicitly deferred as design option.
- **FRAM persistence hooks (6.6):** Value persistence to FRAM with debounce on writes. Basic scaffolding may exist but not complete.
- **Resource budget enforcement (6.8, 8.5):** Runtime checks against resource budgets from `docs/resource_budgets.md`. Not actively enforced.
- **Priority scheduling (8.2, 8.5):** Design mentions future priority overlays on round-robin. Current implementation uses basic round-robin only.

**Documentation Gaps:**
- Event schema definitions incomplete - design specifies many event types not documented in `docs/executive_protocol.md`
- Session lifecycle documentation missing (handshake, keepalive, reconnect semantics)
- No examples of `.sym` file format for symbol loading
- Missing API reference for debugger commands (stack, disasm, symbols, watch, breakpoints)

---

## 4. Next Actions

_Ordered steps to close the gaps._

**Priority Actions:**

**Phase 1: Core Debugger Infrastructure**
1. **Session management** - Implement `session.open`, `session.close`, `session.keepalive` with PID lock tracking and capability negotiation per section 5.2
2. **Event streaming foundation** - Implement bounded ring buffer, `events.subscribe`/`events.unsubscribe`, and event schema per sections 7.1-7.2
3. **Breakpoint management** - Implement `bp.set`, `bp.clear`, `bp.list` with per-PID sets and pre/post-step checking per sections 5.2 and 8.6
4. **Symbol loading** - Implement `.sym` JSON file loading and caching at task load time per section 5.4
5. **Stack reconstruction** - Implement `stack.info` API with frame pointer walking and symbol lookup per section 5.3
6. **Disassembly API** - Implement `disasm.read` with symbol annotations and on-demand/cached strategies per section 5.4

**Phase 2: Enhanced Debugging Features**
7. **Symbol enumeration** - Implement `symbols.list` API for function/variable enumeration per section 5.5
8. **Memory regions** - Implement `memory.regions` API reporting layout from .sym or HXE header per section 5.6
9. **Watch expressions** - Implement `watch.add`/`remove`/`list` with change detection per section 5.7
10. **Event back-pressure** - Implement `events.ack` protocol and drop-oldest policy per section 7.3
11. **Task state events** - Emit structured `task_state` events with reason codes (debug_break, sleep, mailbox_wait, etc.) per section 7.2
12. **Register change tracking** - Add optional `changed_regs` field to `trace_step` events per section 7.2

**Phase 3: HXE v2 and Metadata**
13. **HXE v2 format support** - Extend loader to handle version 0x0002 with metadata sections per sections 1.2 and 3.8
14. **Metadata preprocessing** - Parse `.value`/`.cmd`/`.mailbox` sections and register resources before VM execution per sections 1.2 and 6.2
15. **App name handling** - Extract `app_name` from HXE header with multiple instance tracking per section 4.2

**Phase 4: Scheduler and State Machine**
16. **Formal state machine** - Implement explicit READY/RUNNING/WAIT_MBX/SLEEPING/PAUSED/RETURNED states with documented transitions per sections 8.1-8.2
17. **Wait/wake improvements** - Implement timer heap for sleep deadlines and complete mailbox wait list integration per section 8.4
18. **Scheduler events** - Emit `scheduler` events on context switches per section 7.2
19. **Context isolation validation** - Ensure executive never directly manipulates PC/SP/registers, only uses VM APIs per sections 4.1, 4.2, 8.2

**Phase 5: Trace Infrastructure**
20. **Executive-side trace storage** - Implement configurable trace buffers with variant-specific sizes per section 6.4
21. **Trace record format** - Standardize trace record structure with seq/pid/pc/opcode/regs fields per section 6.4
22. **VM trace polling** - Poll VM minimal trace state (`last_pc`, `last_opcode`, `last_regs`) after each step per section 6.4

**Phase 6: Modular Architecture and C Port**
23. **Modular backend design** - Refactor Python implementation to support pluggable backends (filesystem, protocol, HAL) per section 1.1
24. **Executive variant profiles** - Define minimal/development/full debugger build configurations per section 1.1
25. **C port structure** - Design and implement C executive with pluggable modules for MCU targets
26. **Backend modules** - Implement filesystem backends (host, SPI SD, CAN), protocol backends (JSON-RPC, UART, direct API), and HAL implementations per section 1.1

**Phase 7: Advanced Features**
27. **Observer sessions** - Implement read-only observer mode with priority event handling per sections 3.46 and 7.2
28. **FRAM persistence** - Complete value persistence hooks with debounce per section 6.6
29. **Resource budget enforcement** - Add runtime checks against resource budgets per sections 6.8 and 8.5
30. **Priority scheduling** - Add optional priority overlays on round-robin scheduler per sections 8.2 and 8.5

**Cross-References:**
- Design Requirements: DR-1.1, DR-1.2, DR-1.3, DR-2.5, DR-3.1, DR-5.1, DR-5.2, DR-5.3, DR-6.1, DR-7.1, DR-8.1
- Design Goals: DG-1.2, DG-1.3, DG-1.4, DG-2.3, DG-3.1-3.5, DG-4.2, DG-5.1-5.4, DG-6.1-6.4, DG-7.1-7.3, DG-8.1-8.3
- Related issues: `issues/#2_scheduler` for context switching remediation
- Debugger functionality: `functionality/#1_TUI_DEBUGGER` for debugger requirements

---

**Last Updated:** 2025-10-31  
**Status:** In Progress (Basic executive functional, advanced debugger features and modular architecture not started)

# Toolkit Implementation Plan

## Planned Implementation Order (Grand Plan)

1. Phase 1 - Python CLI and monitor enhancements (manager logging/configuration).
2. Phase 2 - Shared debugger toolkit services aligned with executive/mailbox event APIs.
3. Phase 3 - Health monitoring and diagnostics polish for the manager stack.
4. Phase 4 - Packaging and TUI deliverables (deferred until Python workflows settle).

## Sprint Scope

Concentrate on the Python-oriented work in Phases 1 through 3. Leave the Phase 4 packaging/TUI backlog for a later sprint and simply record requirements that surface while executing the Python milestones.

## Overview

This implementation plan addresses the gaps identified in the Toolkit Study document ([01--Study.md](./01--Study.md)). The plan is organized chronologically with clear dependencies tracked in [DependencyTree.md](../DependencyTree.md).

**Design Reference:** [04.06--Toolkit.md](../../../04--Design/04.06--Toolkit.md)

**Note:** Process manager (`hsx_manager.py`) is functional. This plan focuses on creating the `hsxdbg` core package (used by all three debugger frontends) and enhancing the manager with logging, configuration, and health monitoring.

---

## Phase 1: Debugger Core Infrastructure

### 1.1 Create hsxdbg Package Structure

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design specifies comprehensive Python `hsxdbg` package with 5 major components (section 4.2.1). Foundation for all debugger frontends (CLI, TUI, VS Code).

**Todo:**
- [ ] Create `python/hsxdbg/` package directory
- [ ] Create `__init__.py` with package exports
- [ ] Create module structure (transport, session, events, cache, commands)
- [ ] Add package metadata (version, author, dependencies)
- [ ] Create basic package tests
- [ ] Document package architecture

---

### 1.2 Implement Transport Layer

**Priority:** HIGH  
**Dependencies:** 1.1 (Package structure), Executive Phase 1 (Session management)  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies JSON-over-TCP RPC client with connection management (section 5). Core communication layer for debugger.

**Todo:**
- [ ] Create `hsxdbg/transport.py` module
- [ ] Implement TCP socket connection with timeout
- [ ] Implement JSON message framing (length-prefixed or newline-delimited)
- [ ] Implement request/response correlation (message IDs)
- [ ] Add connection retry logic with exponential backoff
- [ ] Implement connection state tracking (disconnected, connecting, connected)
- [ ] Add connection lifecycle callbacks (on_connect, on_disconnect)
- [ ] Handle socket errors gracefully
- [ ] Add transport tests (mock server)
- [ ] Document transport API

---

### 1.3 Implement Session Manager

**Priority:** HIGH  
**Dependencies:** 1.2 (Transport layer), Executive Phase 1.1 (Session management)  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies connection lifecycle and capability negotiation (section 5.1). Manages debugger sessions with executive.

**Todo:**
- [ ] Create `hsxdbg/session.py` module
- [ ] Implement session open (connect to executive)
- [ ] Implement capability negotiation protocol
- [ ] Implement PID attachment (exclusive or observer mode)
- [ ] Track session state (PID, capabilities, lock status)
- [ ] Implement keepalive/heartbeat mechanism
- [ ] Implement session close (clean disconnect)
- [ ] Handle session conflicts (PID already locked)
- [ ] Add session manager tests
- [ ] Document session API

---

### 1.4 Implement Command Layer

**Priority:** HIGH  
**Dependencies:** 1.2 (Transport layer), 1.3 (Session manager)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Design specifies typed helpers for debugger operations (section 4.2.1). High-level API for debugger frontends.

**Todo:**
- [ ] Create `hsxdbg/commands.py` module
- [ ] Implement execution control commands (step, resume, pause)
- [ ] Implement breakpoint commands (set_breakpoint, clear_breakpoint, list_breakpoints)
- [ ] Implement memory commands (read_memory, write_memory)
- [ ] Implement register commands (read_registers, write_register)
- [ ] Implement stack commands (get_stack_trace, select_frame)
- [ ] Implement watch commands (add_watch, remove_watch, list_watches)
- [ ] Implement disassembly commands (disassemble)
- [ ] Return typed response objects (not raw JSON)
- [ ] Add error handling and validation
- [ ] Add command layer tests
- [ ] Document command API

---

### 1.5 Protocol Specification

**Priority:** HIGH  
**Dependencies:** 1.2, 1.3, 1.4 (Transport, session, commands)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design requires formalized JSON schemas for debugger RPC messages (section 5). Ensures consistency and documentation.

**Todo:**
- [ ] Document JSON schema for session messages
- [ ] Document JSON schema for execution control messages
- [ ] Document JSON schema for breakpoint messages
- [ ] Document JSON schema for memory/register messages
- [ ] Document JSON schema for stack/watch messages
- [ ] Document error response format
- [ ] Add schema examples
- [ ] Update `docs/executive_protocol.md` with debugger RPC section
- [ ] Create protocol reference document

---

## Phase 2: Event Streaming

### 2.1 Implement Event Bus

**Priority:** HIGH  
**Dependencies:** 1.2 (Transport layer), Executive Phase 1.2 (Event streaming)  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies async event dispatcher with bounded queues (section 5.2). Real-time updates for debugger frontends.

**Todo:**
- [ ] Create `hsxdbg/events.py` module
- [ ] Implement async event dispatcher (asyncio or threading)
- [ ] Implement bounded event queues (configurable size)
- [ ] Implement subscriber registration by event type
- [ ] Implement event delivery to subscribers
- [ ] Handle slow subscribers (queue overflow)
- [ ] Implement event filtering by PID
- [ ] Add event bus tests
- [ ] Document event bus API

---

### 2.2 Event Protocol

**Priority:** HIGH  
**Dependencies:** 2.1 (Event bus)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design requires event schemas for various event types (section 5.2). Structured event data for frontends.

**Todo:**
- [ ] Define `trace_step` event schema (seq, ts, pid, pc, opcode, psw)
- [ ] Define `debug_break` event schema (seq, ts, pid, reason, pc)
- [ ] Define `mailbox_*` event schemas (message, send, receive)
- [ ] Define `scheduler` event schema (task state changes)
- [ ] Define `watch_update` event schema (watch_id, old_value, new_value)
- [ ] Define `stdout`/`stderr` event schemas (pid, text)
- [ ] Document event schemas
- [ ] Add event parsing/serialization helpers
- [ ] Add event protocol tests

---

### 2.3 Back-Pressure Handling

**Priority:** MEDIUM  
**Dependencies:** 2.1 (Event bus)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies queue overflow detection and slow-down requests (section 5.2.3). Prevents event loss.

**Todo:**
- [ ] Implement queue size monitoring
- [ ] Detect queue overflow conditions
- [ ] Send slow-down request to executive
- [ ] Throttle event generation if needed
- [ ] Resume normal rate when queue drains
- [ ] Add back-pressure tests
- [ ] Document back-pressure mechanism

---

### 2.4 Event Filtering

**Priority:** MEDIUM  
**Dependencies:** 2.1 (Event bus)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Selective subscription by event type and PID reduces unnecessary processing.

**Todo:**
- [ ] Implement event type filtering
- [ ] Implement PID filtering
- [ ] Allow subscribers to specify filters
- [ ] Apply filters before queuing events
- [ ] Add filtering tests
- [ ] Document filtering API

---

## Phase 3: State Cache

### 3.1 Implement Cache Module

**Priority:** MEDIUM  
**Dependencies:** 1.4 (Command layer), 2.1 (Event bus)  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies mirroring registers, memory, stacks, watches, mailboxes (section 4.2.1). Minimizes RPC round-trips.

**Todo:**
- [ ] Create `hsxdbg/cache.py` module
- [ ] Implement register cache (R0-R15, PC, SP, PSW)
- [ ] Implement memory cache (address ranges)
- [ ] Implement call stack cache
- [ ] Implement watch value cache
- [ ] Implement mailbox descriptor cache
- [ ] Populate cache on initial query
- [ ] Add cache tests
- [ ] Document cache API

---

### 3.2 Cache Invalidation

**Priority:** MEDIUM  
**Dependencies:** 3.1 (Cache module), 2.1 (Event bus)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Update cache on events, invalidate on control operations. Ensures cache consistency.

**Todo:**
- [ ] Update register cache on trace_step events
- [ ] Update memory cache on memory_changed events
- [ ] Update stack cache on debug_break events
- [ ] Update watch cache on watch_update events
- [ ] Invalidate cache on resume/step commands
- [ ] Invalidate cache on memory/register writes
- [ ] Add invalidation tests
- [ ] Document invalidation behavior

---

### 3.3 Cache Query API

**Priority:** MEDIUM  
**Dependencies:** 3.1 (Cache module), 3.2 (Invalidation)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Efficient local queries without RPC round-trips. Improves frontend responsiveness.

**Todo:**
- [ ] Implement register query from cache
- [ ] Implement memory query from cache
- [ ] Implement stack query from cache
- [ ] Implement watch query from cache
- [ ] Fall back to RPC if cache miss
- [ ] Add query API tests
- [ ] Document query API

---

## Phase 4: Manager Enhancements

### 4.1 Logging System

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies capturing component stdout/stderr to log files (section 6.3). Essential for debugging and monitoring.

**Todo:**
- [ ] Implement log file capture for VM component
- [ ] Implement log file capture for Executive component
- [ ] Implement log file capture for Shell component
- [ ] Add log file rotation (size-based or time-based)
- [ ] Store logs in configurable directory
- [ ] Add timestamps to log entries
- [ ] Add log viewing command in manager
- [ ] Add logging tests
- [ ] Document logging system

---

### 4.2 Configuration File

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies config file support for ports, paths, options (section 6.3). Enables customization without code changes.

**Todo:**
- [ ] Choose config format (YAML or TOML)
- [ ] Define configuration schema (ports, paths, logging, etc.)
- [ ] Implement config file loading
- [ ] Provide default configuration
- [ ] Allow command-line overrides
- [ ] Validate configuration on load
- [ ] Add config tests
- [ ] Document configuration options
- [ ] Provide example config files

---

### 4.3 Health Checks

**Priority:** LOW  
**Dependencies:** 4.1 (Logging)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design mentions periodic verification of component health (section 6.3). Detects component failures.

**Todo:**
- [ ] Implement periodic health check thread/task
- [ ] Check if component processes are running
- [ ] Check if component ports are responsive
- [ ] Detect zombie processes
- [ ] Log health check results
- [ ] Alert on health check failures
- [ ] Add health check tests
- [ ] Document health check behavior

---

### 4.4 Automated Restart

**Priority:** LOW  
**Dependencies:** 4.3 (Health checks)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design mentions detecting crashes and restarting components (section 6.3). Improves system reliability.

**Todo:**
- [ ] Detect component crashes via health checks
- [ ] Implement automatic restart logic
- [ ] Add restart delay and retry limit
- [ ] Log restart attempts
- [ ] Notify user of restarts
- [ ] Prevent restart loops (max retries)
- [ ] Add restart tests
- [ ] Document restart behavior

---

## Phase 5: Testing and Documentation

### 5.1 Expand Test Coverage

**Priority:** HIGH  
**Dependencies:** Phases 1-4 complete  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Unit tests for all debugger core modules ensure quality. Currently minimal test coverage (221 lines).

**Todo:**
- [ ] Add transport layer unit tests (connection, framing, retry)
- [ ] Add session manager unit tests (open, negotiate, close)
- [ ] Add event bus unit tests (subscribe, dispatch, filter)
- [ ] Add cache unit tests (populate, invalidate, query)
- [ ] Add command layer unit tests (all commands)
- [ ] Add manager tests (lifecycle, logging, config)
- [ ] Measure test coverage (target >80%)
- [ ] Add tests to CI pipeline
- [ ] Document test architecture

---

### 5.2 Integration Tests

**Priority:** MEDIUM  
**Dependencies:** 5.1 (Unit tests)  
**Estimated Effort:** 1 week

**Rationale:**  
End-to-end tests for manager lifecycle and debugger core integration.

**Todo:**
- [ ] Create integration test suite
- [ ] Test manager component lifecycle (start, stop, restart)
- [ ] Test debugger core with mock executive
- [ ] Test session establishment and teardown
- [ ] Test event streaming pipeline
- [ ] Test cache consistency
- [ ] Add integration tests to CI
- [ ] Document integration test suite

---

### 5.3 User Guide

**Priority:** MEDIUM  
**Dependencies:** Phase 4 (Manager enhancements)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Manager commands and configuration documentation. User-facing documentation.

**Todo:**
- [ ] Write user guide in `docs/toolkit_manager.md`
- [ ] Document all manager commands
- [ ] Document configuration file format
- [ ] Provide usage examples
- [ ] Add troubleshooting section
- [ ] Document logging locations
- [ ] Review and refine documentation

---

### 5.4 Packaging

**Priority:** LOW  
**Dependencies:** Phases 1-4 complete  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Design specifies cross-platform installers for Windows, macOS, Linux. Distribution packaging.

**Todo:**
- [ ] Create Python package setup (setup.py or pyproject.toml)
- [ ] Create entry points for hsx-manager, hsx-shell
- [ ] Create Windows installer (MSI or NSIS)
- [ ] Create macOS installer (DMG or PKG)
- [ ] Create Linux packages (DEB, RPM)
- [ ] Test installers on all platforms
- [ ] Add version management
- [ ] Document packaging process
- [ ] Create distribution documentation

---

## Definition of Done (DoD)

This implementation is considered complete when all of the following criteria are met:

### Phase 1 Completion
- [ ] hsxdbg package structure created
- [ ] Transport layer functional with connection management
- [ ] Session manager handling connection lifecycle and capabilities
- [ ] Command layer providing typed debugger operations
- [ ] Protocol specification documented
- [ ] All Phase 1 tests pass
- [ ] Integration with Executive debugger APIs verified

### Phase 2 Completion
- [ ] Event bus dispatching events asynchronously
- [ ] Event protocol schemas defined and documented
- [ ] Back-pressure handling preventing event loss
- [ ] Event filtering by type and PID working
- [ ] All Phase 2 tests pass
- [ ] Event streaming integration verified

### Phase 3 Completion
- [ ] Cache module mirroring state locally
- [ ] Cache invalidation working correctly
- [ ] Cache query API reducing RPC calls
- [ ] All Phase 3 tests pass
- [ ] Cache consistency verified

### Phase 4 Completion
- [ ] Logging system capturing component output
- [ ] Configuration file support working
- [ ] Health checks detecting component failures
- [ ] Automated restart recovering from crashes
- [ ] All Phase 4 tests pass
- [ ] Manager enhancements functional

### Phase 5 Completion
- [ ] Test coverage >80% for toolkit components
- [ ] Integration tests passing
- [ ] User guide complete
- [ ] Cross-platform packages available
- [ ] All Phase 5 tests pass

### Overall Quality Criteria
- [ ] hsxdbg core package functional and well-tested
- [ ] All three debugger frontends can use hsxdbg core (CLI, TUI, VS Code)
- [ ] Manager enhanced with logging, config, health checks, restart
- [ ] Integration with Executive debugger APIs verified
- [ ] CI pipeline green on all platforms
- [ ] Code follows project style guidelines
- [ ] All documentation reviewed and approved

### Traceability
- [ ] All design requirements tracked to implementation
- [ ] All gaps from Study document addressed
- [ ] DependencyTree.md updated with completion status
- [ ] Debugger frontends (09, 10, 11) verified to work with hsxdbg core

---

## Cross-References

**Design Documents:**
- [04.06--Toolkit.md](../../../04--Design/04.06--Toolkit.md) - Toolkit Design Specification
- [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md) - CLI Debugger Design
- [04.10--TUI_Debugger.md](../../../04--Design/04.10--TUI_Debugger.md) - TUI Debugger Design
- [04.11--vscode_debugger.md](../../../04--Design/04.11--vscode_debugger.md) - VS Code Debugger Design

**Gap Analysis:**
- [01--Study.md](./01--Study.md) - Gap Analysis Study

**Dependencies:**
- [DependencyTree.md](../DependencyTree.md) - Cross-module dependency tracking
- [02--Executive](../02--Executive/01--Study.md) - Debugger APIs (Phase 1-2)
- [05--Toolchain](../05--Toolchain/01--Study.md) - Symbol files (Phase 3)

**Provides To:**
- [09--Debugger](../09--Debugger/01--Study.md) - CLI debugger uses hsxdbg core
- [10--TUI_Debugger](../10--TUI_Debugger/01--Study.md) - TUI debugger uses hsxdbg core
- [11--vscode_debugger](../11--vscode_debugger/01--Study.md) - VS Code debugger uses hsxdbg core

**Documentation:**
- `docs/executive_protocol.md` - Executive RPC protocol (to be updated with debugger section)
- `docs/toolkit_manager.md` - Manager user guide (to be created)

**Tools:**
- `python/hsx_manager.py` - Process manager (existing, to be enhanced)
- `python/shell_client.py` - Shell client (existing)
- `python/hsxdbg/` - Debugger core package (to be created)

---

**Last Updated:** 2025-10-31  
**Status:** Initial Plan  
**Owner:** Toolkit Implementation Team

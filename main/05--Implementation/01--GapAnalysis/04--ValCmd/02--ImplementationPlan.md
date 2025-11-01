# ValCmd Implementation Plan

## Planned Implementation Order (Grand Plan)

1. Phase 1 - Value service scaffolding (Python).
2. Phase 2 - Command service core flows (Python).
3. Phase 3 - Telemetry and mailbox bindings (Python).
4. Phase 4 - Shell adapters and interactive workflows (Python).
5. Phase 5 - Extended scenarios and regression coverage (Python).
6. Phase 6 - Documentation and examples refresh.
7. Phase 7 - C port (deferred until Python validation completes).

## Sprint Scope

Advance Phases 1 through 6 on the Python side and hold the Phase 7 C port for a later sprint. Note any C considerations as future tasks while keeping the current execution Python-only.

## Overview

This implementation plan addresses the gaps identified in the ValCmd Study document ([01--Study.md](./01--Study.md)) and aligns with the implementation notes in the System document ([../../system/ValCmd.md](../../system/ValCmd.md)). The plan is organized chronologically with clear dependencies tracked in [DependencyTree.md](../DependencyTree.md).

**Design Reference:** [04.04--ValCmd.md](../../../04--Design/04.04--ValCmd.md)

**Note:** The entire value/command subsystem is currently missing. This plan starts from scratch to build the complete telemetry and control interface for HSX applications.

---

## Phase 1: Core Data Structures and Registry

### 1.1 Create C Header Files

**Priority:** HIGH  
**Dependencies:** Shared ABI Header (external dependency)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design references `include/hsx_value.h` and `include/hsx_command.h` but these don't exist. Foundation for all value/command operations.

**Todo:**
- [ ] Create `include/hsx_value.h` with status codes, flags, data structures
- [ ] Create `include/hsx_command.h` with status codes, flags, data structures
- [ ] Define `HSX_VAL_*` status codes (SUCCESS, ENOENT, EPERM, ENOSPC, etc.)
- [ ] Define `HSX_CMD_*` status codes
- [ ] Define value flags (RO, PERSIST, STICKY, PIN, BOOL)
- [ ] Define command flags (PIN, ASYNC_ALLOWED)
- [ ] Define auth levels (PUBLIC, USER, ADMIN, FACTORY)
- [ ] Add header guards and documentation comments
- [ ] Create Python constants file mirroring C headers

---

### 1.2 Implement Compact Value Entry

**Priority:** HIGH  
**Dependencies:** 1.1 (C header files)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies 8-byte `hsx_val_entry` structure (section 4.2). Core data structure for value registry.

**Todo:**
- [ ] Define `hsx_val_entry` struct (group_id, value_id, flags, auth_level, owner_pid, last_f16, desc_head)
- [ ] Implement struct packing to achieve 8-byte size
- [ ] Add OID calculation from (group_id, value_id)
- [ ] Implement value entry initialization
- [ ] Implement value entry validation
- [ ] Add unit tests for value entry structure
- [ ] Document value entry format

---

### 1.3 Implement Compact Command Entry

**Priority:** HIGH  
**Dependencies:** 1.1 (C header files)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Similar to value entry, commands need compact storage structure (section 4.2). Enables command registry.

**Todo:**
- [ ] Define `hsx_cmd_entry` struct (group_id, cmd_id, flags, auth_level, owner_pid, handler_ref, desc_head)
- [ ] Implement struct packing for compact storage
- [ ] Add OID calculation for commands
- [ ] Implement command entry initialization
- [ ] Implement command entry validation
- [ ] Add unit tests for command entry structure
- [ ] Document command entry format

---

### 1.4 Implement Descriptor Types

**Priority:** HIGH  
**Dependencies:** 1.1 (C header files)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies mix-in descriptor pattern for metadata (sections 4.2.2-4.2.4). Enables rich metadata for values/commands.

**Todo:**
- [ ] Define descriptor base type with type tag and next pointer
- [ ] Implement Group descriptor (group_id, name_offset)
- [ ] Implement Name descriptor (name_offset)
- [ ] Implement Unit descriptor (unit_offset)
- [ ] Implement Range descriptor (min_f16, max_f16, default_f16)
- [ ] Implement Persist descriptor (debounce_ms, persist_addr)
- [ ] Implement descriptor chain building
- [ ] Implement descriptor chain traversal
- [ ] Add descriptor tests (build chains, query metadata)
- [ ] Document descriptor format and usage

---

### 1.5 String Table Management

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies deduplicated null-terminated string storage (section 4.2.6). Optimizes memory for names, units, help text.

**Todo:**
- [ ] Implement string table with fixed size pool
- [ ] Implement string deduplication (hash-based lookup)
- [ ] Implement string insertion (returns offset)
- [ ] Implement string retrieval by offset
- [ ] Add string table overflow handling
- [ ] Track string table usage metrics
- [ ] Add string table tests
- [ ] Document string table format

---

### 1.6 Registry Initialization

**Priority:** HIGH  
**Dependencies:** 1.2 (Value entry), 1.3 (Command entry), 1.5 (String table)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies fixed-size value/command tables with OID-based lookup (section 4.3). Core registry implementation.

**Todo:**
- [ ] Implement value registry with configurable table size
- [ ] Implement command registry with configurable table size
- [ ] Implement OID-based lookup (hash table or linear scan)
- [ ] Implement registration slot allocation
- [ ] Implement registry cleanup on task termination
- [ ] Add registry capacity tracking
- [ ] Add registry initialization tests
- [ ] Document registry structure and limits

---

## Phase 2: Python VALUE SVC Module (0x07)

### 2.1 VALUE_REGISTER

**Priority:** HIGH  
**Dependencies:** 1.6 (Registry initialization)  
**Estimated Effort:** 3-4 days

**Rationale:**  
First VALUE SVC to implement. Design specifies registration with PID capture and descriptor chain building (section 4.4.1). System/ValCmd.md notes this is SVC 0x0700.

**Todo:**
- [ ] Implement VALUE_REGISTER SVC handler (0x0700)
- [ ] Capture caller PID automatically
- [ ] Allocate value entry in registry
- [ ] Parse descriptor pointer from R4
- [ ] Build descriptor chain from metadata
- [ ] Validate group_id and value_id uniqueness
- [ ] Return OID on success or error code
- [ ] Handle registry exhaustion (ENOSPC)
- [ ] Add VALUE_REGISTER tests
- [ ] Update `docs/abi_syscalls.md` with implementation status

---

### 2.2 VALUE_LOOKUP

**Priority:** MEDIUM  
**Dependencies:** 2.1 (VALUE_REGISTER)  
**Estimated Effort:** 1-2 days

**Rationale:**  
No-create lookup for existing values. Enables checking if value exists before registration.

**Todo:**
- [ ] Implement VALUE_LOOKUP SVC handler (0x0701)
- [ ] Search registry by (group_id, value_id)
- [ ] Return OID if found, ENOENT if not
- [ ] Add VALUE_LOOKUP tests
- [ ] Document VALUE_LOOKUP usage

---

### 2.3 VALUE_GET

**Priority:** HIGH  
**Dependencies:** 2.1 (VALUE_REGISTER)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Core read operation. Design specifies PID verification and auth_level checks (section 4.4.2). System/ValCmd.md notes this is SVC 0x0702.

**Todo:**
- [ ] Implement VALUE_GET SVC handler (0x0702)
- [ ] Lookup value by OID
- [ ] Verify caller owns value (PID check) or auth_level allows access
- [ ] Return f16 value in R0 low 16 bits
- [ ] Return ENOENT if OID not found
- [ ] Return EPERM if PID/auth check fails
- [ ] Add VALUE_GET tests (owned, external, auth levels)
- [ ] Document VALUE_GET behavior

---

### 2.4 VALUE_SET

**Priority:** HIGH  
**Dependencies:** 2.3 (VALUE_GET), 3.1 (Mailbox notifications)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Core write operation. Design specifies epsilon threshold, rate limiting, notification dispatch (section 4.4.2). System/ValCmd.md notes this is SVC 0x0703.

**Todo:**
- [ ] Implement VALUE_SET SVC handler (0x0703)
- [ ] Lookup value by OID
- [ ] Verify caller owns value or auth_level allows write
- [ ] Check read-only flag (return EPERM if set)
- [ ] Apply epsilon threshold (skip if change below threshold)
- [ ] Apply rate limiting (skip if too frequent)
- [ ] Update value entry with new f16
- [ ] Trigger mailbox notifications to subscribers
- [ ] Mark persistence dirty if PERSIST flag set
- [ ] Add VALUE_SET tests (epsilon, rate limit, notifications)
- [ ] Document VALUE_SET behavior

---

### 2.5 VALUE_LIST

**Priority:** MEDIUM  
**Dependencies:** 2.1 (VALUE_REGISTER)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Enumeration support for tooling. System/ValCmd.md notes this is SVC 0x0704.

**Todo:**
- [ ] Implement VALUE_LIST SVC handler (0x0704)
- [ ] Filter by group_id (0xFF for all groups)
- [ ] Filter by caller PID (only show owned values)
- [ ] Write OID list to output buffer
- [ ] Respect max_items limit
- [ ] Return actual count
- [ ] Handle buffer too small gracefully
- [ ] Add VALUE_LIST tests
- [ ] Document VALUE_LIST behavior

---

### 2.6 VALUE_SUB

**Priority:** MEDIUM  
**Dependencies:** 2.1 (VALUE_REGISTER), Mailbox (subscription support)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Subscribe to value changes via mailbox (section 4.4.3). System/ValCmd.md notes this is SVC 0x0705.

**Todo:**
- [ ] Implement VALUE_SUB SVC handler (0x0705)
- [ ] Lookup value by OID
- [ ] Verify mailbox target is valid
- [ ] Register subscriber in value entry's subscription list
- [ ] Handle duplicate subscriptions
- [ ] Add VALUE_SUB tests
- [ ] Document subscription semantics

---

### 2.7 VALUE_PERSIST

**Priority:** LOW  
**Dependencies:** 2.1 (VALUE_REGISTER), Phase 6 (FRAM integration)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Toggle persistence mode for values (section 4.4.4). System/ValCmd.md notes this is SVC 0x0706.

**Todo:**
- [ ] Implement VALUE_PERSIST SVC handler (0x0706)
- [ ] Lookup value by OID
- [ ] Verify caller owns value
- [ ] Update persist mode (0=volatile, 1=load, 2=load+save)
- [ ] Add/update Persist descriptor
- [ ] Add VALUE_PERSIST tests
- [ ] Document persistence modes

---

## Phase 3: Python COMMAND SVC Module (0x08)

### 3.1 CMD_REGISTER

**Priority:** HIGH  
**Dependencies:** 1.6 (Registry initialization)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Command registration similar to VALUE_REGISTER (section 4.4.1). System/ValCmd.md notes this is SVC 0x0800.

**Todo:**
- [ ] Implement CMD_REGISTER SVC handler (0x0800)
- [ ] Capture caller PID automatically
- [ ] Allocate command entry in registry
- [ ] Parse descriptor pointer from R4
- [ ] Build descriptor chain from metadata
- [ ] Store handler reference (callback address)
- [ ] Return OID on success or error code
- [ ] Handle registry exhaustion (ENOSPC)
- [ ] Add CMD_REGISTER tests
- [ ] Update `docs/abi_syscalls.md` with implementation status

---

### 3.2 CMD_LOOKUP

**Priority:** MEDIUM  
**Dependencies:** 3.1 (CMD_REGISTER)  
**Estimated Effort:** 1 day

**Rationale:**  
No-create lookup for existing commands. System/ValCmd.md notes this is SVC 0x0801.

**Todo:**
- [ ] Implement CMD_LOOKUP SVC handler (0x0801)
- [ ] Search registry by (group_id, cmd_id)
- [ ] Return OID if found, ENOENT if not
- [ ] Add CMD_LOOKUP tests
- [ ] Document CMD_LOOKUP usage

---

### 3.3 CMD_CALL

**Priority:** HIGH  
**Dependencies:** 3.1 (CMD_REGISTER)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Synchronous command invocation with auth checks (section 4.4.5). System/ValCmd.md notes this is SVC 0x0802.

**Todo:**
- [ ] Implement CMD_CALL SVC handler (0x0802)
- [ ] Lookup command by OID
- [ ] Verify auth_level allows access
- [ ] Verify PIN token if PIN flag set
- [ ] Invoke command handler (VM callback)
- [ ] Return command result status
- [ ] Emit cmd_invoked event
- [ ] Emit cmd_completed event
- [ ] Add CMD_CALL tests (auth, PIN, handler invocation)
- [ ] Document CMD_CALL behavior

---

### 3.4 CMD_CALL_ASYNC

**Priority:** MEDIUM  
**Dependencies:** 3.3 (CMD_CALL), Mailbox (async result posting)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Asynchronous command invocation with mailbox result posting. System/ValCmd.md notes this is SVC 0x0803.

**Todo:**
- [ ] Implement CMD_CALL_ASYNC SVC handler (0x0803)
- [ ] Lookup command by OID
- [ ] Verify ASYNC_ALLOWED flag set
- [ ] Verify auth_level and PIN token
- [ ] Schedule command execution (async)
- [ ] Post (oid, rc) result to mailbox when complete
- [ ] Add CMD_CALL_ASYNC tests
- [ ] Document async semantics

---

### 3.5 CMD_HELP

**Priority:** LOW  
**Dependencies:** 3.1 (CMD_REGISTER), 1.4 (Descriptor types)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Retrieve help text from descriptors. System/ValCmd.md notes this is SVC 0x0804.

**Todo:**
- [ ] Implement CMD_HELP SVC handler (0x0804)
- [ ] Lookup command by OID
- [ ] Traverse descriptor chain for help text
- [ ] Write help string to output buffer
- [ ] Respect max_len limit
- [ ] Return ENOENT if no help text
- [ ] Add CMD_HELP tests
- [ ] Document help text format

---

## Phase 4: Executive Integration

### 4.1 Event Emission

**Priority:** HIGH  
**Dependencies:** Executive Phase 1.2 (Event streaming), Phase 2 & 3 complete  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies event emission for debugger/tooling (section 5.2). System/ValCmd.md notes: "Event + transport bindings feeding toolkit watch panels."

**Todo:**
- [ ] Define value_changed event schema (seq, ts, pid, oid, old_f16, new_f16)
- [ ] Define value_registered event schema (seq, ts, pid, oid, group_id, value_id)
- [ ] Define cmd_invoked event schema (seq, ts, pid, oid, group_id, cmd_id)
- [ ] Define cmd_completed event schema (seq, ts, pid, oid, rc)
- [ ] Integrate with executive event streaming (emit_event)
- [ ] Emit value_changed on VALUE_SET
- [ ] Emit value_registered on VALUE_REGISTER
- [ ] Emit cmd_invoked on CMD_CALL start
- [ ] Emit cmd_completed on CMD_CALL finish
- [ ] Add event emission tests
- [ ] Document event schema in `docs/executive_protocol.md`

---

### 4.2 Executive RPC Commands

**Priority:** MEDIUM  
**Dependencies:** Phase 2 & 3 complete  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies RPC commands for shell/tooling (section 5.3). System/ValCmd.md notes: val.list, val.get, val.set, cmd.list, cmd.call commands.

**Todo:**
- [ ] Implement `val.list` RPC command (enumerate values)
- [ ] Implement `val.get(oid)` RPC command (read value)
- [ ] Implement `val.set(oid, f16)` RPC command (write value)
- [ ] Implement `cmd.list` RPC command (enumerate commands)
- [ ] Implement `cmd.call(oid)` RPC command (invoke command)
- [ ] Add JSON-RPC protocol handlers
- [ ] Support both numeric OID and named access
- [ ] Add RPC command tests
- [ ] Update `docs/executive_protocol.md` with ValCmd RPC commands

---

### 4.3 Resource Tracking

**Priority:** LOW  
**Dependencies:** 1.6 (Registry initialization)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Monitor table occupancy and string table usage against budgets. System/ValCmd.md notes: "Document transport bindings... in formats docs."

**Todo:**
- [ ] Track value registry occupancy (used/total)
- [ ] Track command registry occupancy (used/total)
- [ ] Track string table usage (bytes used/total)
- [ ] Expose metrics via RPC command (val.stats, cmd.stats)
- [ ] Log warnings when approaching limits
- [ ] Add resource tracking tests
- [ ] Document resource limits in `docs/resource_budgets.md`

---

## Phase 5: HXE v2 Declarative Registration

### 5.1 Section Parser

**Priority:** MEDIUM  
**Dependencies:** Executive Phase 3.1 (HXE v2 format support)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies parsing `.value` and `.cmd` sections from HXE header (section 4.4.1). Enables declarative configuration.

**Todo:**
- [ ] Design .value section format (JSON or binary)
- [ ] Design .cmd section format (JSON or binary)
- [ ] Implement .value section parser
- [ ] Implement .cmd section parser
- [ ] Validate section contents
- [ ] Handle parsing errors gracefully
- [ ] Add section parsing tests
- [ ] Document section formats in `docs/hxe_format.md`

---

### 5.2 Metadata Preprocessing

**Priority:** MEDIUM  
**Dependencies:** 5.1 (Section parser), Phase 2 & 3 (SVC implementation)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies registering all values/commands before VM execution (section 1.1). Ensures resources are ready at task start.

**Todo:**
- [ ] Implement metadata preprocessing during task load
- [ ] Call VALUE_REGISTER for each .value entry
- [ ] Call CMD_REGISTER for each .cmd entry
- [ ] Build descriptor chains from metadata
- [ ] Handle registration failures
- [ ] Add preprocessed registration tests
- [ ] Document preprocessing behavior

---

### 5.3 Descriptor Building

**Priority:** MEDIUM  
**Dependencies:** 5.2 (Metadata preprocessing), 1.4 (Descriptor types)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Construct descriptor chains from section metadata. Enables rich metadata without manual SVC calls.

**Todo:**
- [ ] Parse descriptor metadata from .value/.cmd sections
- [ ] Build Group descriptors
- [ ] Build Name descriptors
- [ ] Build Unit descriptors
- [ ] Build Range descriptors
- [ ] Build Persist descriptors
- [ ] Link descriptors into chains
- [ ] Add descriptor building tests
- [ ] Document descriptor metadata format

---

## Phase 6: Persistence and Notifications

### 6.1 FRAM Integration

**Priority:** LOW  
**Dependencies:** 2.7 (VALUE_PERSIST), HAL (FRAM interface)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Design specifies load-on-boot and debounced writes (section 4.4.4). System/ValCmd.md notes: "Hook persistence writes into provisioning/FRAM layout."

**Todo:**
- [ ] Design FRAM layout for persisted values
- [ ] Implement value load from FRAM at boot
- [ ] Implement debounced value write to FRAM
- [ ] Track which values need persistence
- [ ] Implement FRAM write queue with debounce timer
- [ ] Handle FRAM write failures gracefully
- [ ] Add FRAM persistence tests
- [ ] Document FRAM layout in `docs/persistence_layout.md`

---

### 6.2 Mailbox Notifications

**Priority:** MEDIUM  
**Dependencies:** 2.6 (VALUE_SUB), Mailbox (notification delivery)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies delivering value change notifications to subscribers (section 4.4.3). Enables reactive applications.

**Todo:**
- [ ] Implement notification dispatch on VALUE_SET
- [ ] Format notification message (oid, old_f16, new_f16)
- [ ] Send notification to each subscriber's mailbox
- [ ] Handle mailbox send failures (subscriber gone)
- [ ] Remove dead subscribers from lists
- [ ] Add notification tests (single/multiple subscribers)
- [ ] Document notification message format

---

### 6.3 Change Detection

**Priority:** MEDIUM  
**Dependencies:** 2.4 (VALUE_SET)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies epsilon threshold and rate_limit enforcement (section 4.4.2). Reduces unnecessary notifications and persistence writes.

**Todo:**
- [ ] Implement epsilon threshold check (abs(new - old) < epsilon)
- [ ] Store epsilon value in descriptor or flags
- [ ] Implement rate limiting (min time between changes)
- [ ] Track last_change_time per value
- [ ] Skip notifications if epsilon/rate limit not met
- [ ] Add change detection tests
- [ ] Document epsilon and rate limit semantics

---

## Phase 7: Transport Bindings

### 7.1 CAN Framing

**Priority:** LOW  
**Dependencies:** Phase 2 & 3 complete, HAL (CAN interface)  
**Estimated Effort:** 2-3 weeks

**Rationale:**  
Design specifies OID-to-CAN mapping for external access (section 4.4.6). Enables CAN-based telemetry and control.

**Todo:**
- [ ] Design CAN frame format for GET/SET/PUB/CALL/RET operations
- [ ] Implement OID-to-CAN ID mapping
- [ ] Implement CAN GET handler (read value, send response)
- [ ] Implement CAN SET handler (write value, send ack)
- [ ] Implement CAN PUB handler (publish value changes)
- [ ] Implement CAN CALL handler (invoke command, send result)
- [ ] Add CAN transport tests
- [ ] Document CAN protocol in `docs/can_transport.md`

---

### 7.2 Shell/CLI Integration

**Priority:** MEDIUM  
**Dependencies:** 4.2 (Executive RPC commands)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies numeric and named value access (section 4.4.7). Enables interactive debugging and control.

**Todo:**
- [ ] Implement named value lookup (by string name)
- [ ] Support val.get("my_value") syntax
- [ ] Support val.set("my_value", 3.14) syntax
- [ ] Support cmd.call("my_command") syntax
- [ ] Implement tab completion for value/command names
- [ ] Add shell integration tests
- [ ] Document shell command usage

---

### 7.3 UART Commands

**Priority:** LOW  
**Dependencies:** Phase 2 & 3 complete, HAL (UART interface)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Design mentions external value/command access without PID checks. Enables UART-based monitoring and control.

**Todo:**
- [ ] Design UART command protocol
- [ ] Implement UART GET command
- [ ] Implement UART SET command
- [ ] Implement UART LIST command
- [ ] Implement UART CALL command
- [ ] Bypass PID checks for external access
- [ ] Add UART transport tests
- [ ] Document UART protocol

---

## Phase 8: C Application Interface

### 8.1 Value Wrapper Struct

**Priority:** MEDIUM  
**Dependencies:** Phase 2 complete (VALUE SVCs functional)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Design specifies C `Value` type with operator overloads (section 5.4). Provides transparent SVC access for applications.

**Todo:**
- [ ] Define C `Value` struct with OID field
- [ ] Implement cast operator (Value -> f16) using VALUE_GET SVC
- [ ] Implement assignment operator (Value = f16) using VALUE_SET SVC
- [ ] Implement comparison operators
- [ ] Implement arithmetic operators (+=, -=, etc.)
- [ ] Add Value wrapper tests
- [ ] Document Value wrapper API

---

### 8.2 Transparent SVC Access

**Priority:** MEDIUM  
**Dependencies:** 8.1 (Value wrapper struct)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Operator overloads should invoke SVCs transparently. Simplifies application code.

**Todo:**
- [ ] Verify cast operator generates VALUE_GET SVC
- [ ] Verify assignment operator generates VALUE_SET SVC
- [ ] Optimize for minimal code generation
- [ ] Add assembly inspection tests
- [ ] Document transparent SVC behavior

---

### 8.3 Example HXE Apps

**Priority:** LOW  
**Dependencies:** 8.1 (Value wrapper struct), Phase 5 (Declarative registration)  
**Estimated Effort:** 1 week

**Rationale:**  
Sample applications demonstrate value/command usage patterns. Helps developers understand the API.

**Todo:**
- [ ] Create example: simple value registration and access
- [ ] Create example: value subscription and notifications
- [ ] Create example: command registration and invocation
- [ ] Create example: persistence usage
- [ ] Create example: declarative .value/.cmd sections
- [ ] Document examples in repository
- [ ] Add examples to CI test suite

---

## Phase 9: Advanced Features

### 9.1 Debugger Integration

**Priority:** LOW  
**Dependencies:** Phase 2 complete, Debugger (watch panel support)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Value watch panels enhance debugging experience. Symbol lookup enables named access.

**Todo:**
- [ ] Implement value watch panel in TUI debugger
- [ ] Display value OID, name, current f16, unit
- [ ] Update watch panel on value_changed events
- [ ] Integrate with .sym files for symbol lookup
- [ ] Add value editing from watch panel
- [ ] Add watch panel tests
- [ ] Document watch panel usage

---

### 9.2 Auth Token Validation

**Priority:** MEDIUM  
**Dependencies:** Phase 2 & 3 complete (SVC implementation)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Design specifies Pin flag enforcement and auth_level checks (section 6). Security requirement for production systems.

**Todo:**
- [ ] Implement auth_level hierarchy (PUBLIC < USER < ADMIN < FACTORY)
- [ ] Implement PIN token storage and validation
- [ ] Enforce auth_level on VALUE_GET/SET
- [ ] Enforce auth_level on CMD_CALL
- [ ] Implement PIN validation when PIN flag set
- [ ] Log unauthorized access attempts
- [ ] Add auth tests (various levels, PIN validation)
- [ ] Document authentication and authorization model

---

### 9.3 PID Cleanup

**Priority:** MEDIUM  
**Dependencies:** 1.6 (Registry initialization)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design specifies automatically clearing values/commands when task terminates (section 6). Prevents resource leaks.

**Todo:**
- [ ] Hook into task termination event
- [ ] Enumerate values owned by terminated PID
- [ ] Enumerate commands owned by terminated PID
- [ ] Free value entries and descriptors
- [ ] Free command entries and descriptors
- [ ] Clean up subscribers from terminated PIDs
- [ ] Add PID cleanup tests
- [ ] Document cleanup behavior

---

### 9.4 C Port

**Priority:** LOW (Deferred until VM C port complete)  
**Dependencies:** VM Phase 2 (C port), Phase 1-8 complete  
**Estimated Effort:** 3-4 weeks

**Rationale:**  
Like VM and Executive, value/command subsystem needs C implementation for MCU deployment.

**Todo:**
- [ ] Port registry to C (`platforms/c/valcmd/`)
- [ ] Port value/command entries to C
- [ ] Port descriptor types to C
- [ ] Port string table to C
- [ ] Implement VALUE SVC handlers in C
- [ ] Implement COMMAND SVC handlers in C
- [ ] Implement C-side notifications
- [ ] Implement C-side persistence
- [ ] Add C build system integration
- [ ] Create cross-platform test suite
- [ ] Document C port architecture

---

## Definition of Done (DoD)

This implementation is considered complete when all of the following criteria are met:

### Phase 1 Completion
- [ ] C header files created and documented (hsx_value.h, hsx_command.h)
- [ ] Value entry structure implemented and tested (8-byte compact format)
- [ ] Command entry structure implemented and tested
- [ ] Descriptor types implemented (Group, Name, Unit, Range, Persist)
- [ ] String table management functional (deduplication, storage)
- [ ] Registry initialization operational (value/command tables, OID lookup)
- [ ] All Phase 1 tests pass with 100% success rate
- [ ] Code review completed
- [ ] Python constants mirror C headers

### Phase 2 Completion
- [ ] VALUE_REGISTER functional (PID capture, descriptor chains)
- [ ] VALUE_LOOKUP functional (no-create lookup)
- [ ] VALUE_GET functional (PID verification, auth checks)
- [ ] VALUE_SET functional (epsilon, rate limit, notifications)
- [ ] VALUE_LIST functional (enumeration with filters)
- [ ] VALUE_SUB functional (mailbox subscriptions)
- [ ] VALUE_PERSIST functional (persistence mode toggle)
- [ ] All Phase 2 tests pass
- [ ] VM no longer returns ENOSYS for module 0x07
- [ ] `docs/abi_syscalls.md` updated to "Implemented (Python)"

### Phase 3 Completion
- [ ] CMD_REGISTER functional (PID capture, handler reference)
- [ ] CMD_LOOKUP functional (no-create lookup)
- [ ] CMD_CALL functional (auth checks, handler invocation)
- [ ] CMD_CALL_ASYNC functional (async with mailbox result)
- [ ] CMD_HELP functional (help text retrieval)
- [ ] All Phase 3 tests pass
- [ ] VM no longer returns ENOSYS for module 0x08
- [ ] `docs/abi_syscalls.md` updated to "Implemented (Python)"

### Phase 4 Completion
- [ ] Event emission integrated (4 event types)
- [ ] Executive RPC commands functional (val.list/get/set, cmd.list/call)
- [ ] Resource tracking operational (registry and string table metrics)
- [ ] All Phase 4 tests pass
- [ ] Event schema documented in `docs/executive_protocol.md`

### Phase 5 Completion
- [ ] .value section parser implemented
- [ ] .cmd section parser implemented
- [ ] Metadata preprocessing functional (before VM execution)
- [ ] Descriptor building from metadata operational
- [ ] All Phase 5 tests pass
- [ ] Section formats documented in `docs/hxe_format.md`

### Phase 6 Completion
- [ ] FRAM integration complete (load-on-boot, debounced writes)
- [ ] Mailbox notifications functional (subscriber delivery)
- [ ] Change detection operational (epsilon, rate limit)
- [ ] All Phase 6 tests pass
- [ ] FRAM layout documented in `docs/persistence_layout.md`

### Phase 7 Completion
- [ ] CAN framing implemented (GET/SET/PUB/CALL/RET)
- [ ] Shell/CLI integration functional (named access)
- [ ] UART commands operational (external access)
- [ ] All Phase 7 tests pass
- [ ] Transport protocols documented

### Phase 8 Completion
- [ ] Value wrapper struct implemented
- [ ] Transparent SVC access functional (operator overloads)
- [ ] Example HXE apps created and tested
- [ ] All Phase 8 tests pass
- [ ] C API documented with examples

### Phase 9 Completion
- [ ] Debugger integration complete (watch panels)
- [ ] Auth token validation functional (PIN, auth_level)
- [ ] PID cleanup operational (automatic on task termination)
- [ ] C port complete (deferred until VM C port)
- [ ] All Phase 9 tests pass
- [ ] All advanced features documented

### Overall Quality Criteria
- [ ] Zero known security vulnerabilities in valcmd implementation
- [ ] Zero known data corruption bugs
- [ ] All design requirements (DR-*) satisfied
- [ ] All design goals (DG-*) achieved or explicitly deferred with rationale
- [ ] CI pipeline green on all supported platforms
- [ ] Code follows project style guidelines and passes linting
- [ ] All changes committed with clear, descriptive commit messages
- [ ] Implementation notes updated in System/ValCmd.md
- [ ] Integration with VM SVC dispatcher verified
- [ ] Integration with Executive event stream verified
- [ ] Integration with Mailbox subsystem verified

### Traceability
- [ ] All design requirements tracked to implementation
- [ ] All test cases traced to requirements
- [ ] All gaps from Study document addressed or explicitly deferred
- [ ] DependencyTree.md updated with completion status
- [ ] Test specification created in `main/06--Test/system/ValCmd_tests.md`

---

## Cross-References

**Design Documents:**
- [04.04--ValCmd.md](../../../04--Design/04.04--ValCmd.md) - ValCmd Design Specification
- [System/ValCmd.md](../../system/ValCmd.md) - Implementation Notes

**Gap Analysis:**
- [01--Study.md](./01--Study.md) - Gap Analysis Study

**Dependencies:**
- [DependencyTree.md](../DependencyTree.md) - Cross-module dependency tracking

**Related Components:**
- VM (SVC modules 0x07 and 0x08 dispatcher)
- Executive (event stream, RPC commands, HXE v2 preprocessing)
- Mailbox (subscriptions, notifications)
- HAL (FRAM persistence, CAN/UART transports)
- Debugger (watch panels, value inspection)

**Test Specifications:**
- Test plans to be documented in `main/06--Test/system/ValCmd_tests.md`

**Protocol Documentation:**
- `docs/executive_protocol.md` - Event schema and RPC commands
- `docs/abi_syscalls.md` - SVC specifications for modules 0x07 and 0x08
- `docs/hxe_format.md` - .value and .cmd section formats
- `docs/can_transport.md` - CAN protocol for value/command access (to be created)

**Resource Documentation:**
- `docs/resource_budgets.md` - Registry sizes and string table limits
- `docs/persistence_layout.md` - FRAM layout for persisted values (to be created)

**Specification:**
- `docs/hsx_value_interface.md` - Original specification document (Norwegian)

---

**Last Updated:** 2025-10-31  
**Status:** Initial Plan  
**Owner:** ValCmd Implementation Team

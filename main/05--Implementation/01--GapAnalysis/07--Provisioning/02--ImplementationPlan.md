# Provisioning & Persistence Implementation Plan

## Planned Implementation Order (Grand Plan)

1. Phase 1 - Monolithic HXE loader integration.
2. Phase 2 - Streaming loader RPC workflows tied into the executive.
3. Phase 3 - Progress reporting and event streaming.
4. Phase 4 - Transport adapters and persistence plumbing (Python).
5. Phase 5 - Extended transports, security, and recovery workflows (Python).
6. Phase 6 - Documentation and validation coverage.
7. Phase 7 - C port and embedded provisioning (deferred).

## Sprint Scope

Deliver Phases 1 through 6 on the Python stack so provisioning aligns with the executive and mailbox milestones. The Phase 7 C port remains out of scope for this sprint; log discoveries that impact it as future TODOs.

## Overview

This implementation plan addresses the gaps identified in the Provisioning Study document ([01--Study.md](./01--Study.md)). The plan is organized chronologically with clear dependencies tracked in [DependencyTree.md](../DependencyTree.md).

**Design Reference:** [04.07--Provisioning.md](../../../04--Design/04.07--Provisioning.md)

**Note:** Basic monolithic file loading exists in executive. This plan builds comprehensive provisioning infrastructure with streaming, persistence, transports, and security.

---

## Phase 1: Provisioning Service Foundation

### 1.1 Create Provisioning Module

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies executive-owned provisioning orchestration (section 3). Foundation for all provisioning functionality.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Create `python/provisioning.py` module
- [ ] Create `ProvisioningService` class
- [ ] Add provisioning service to executive initialization
- [ ] Define provisioning configuration (timeouts, buffers, policies)
- [ ] Add basic module tests
- [ ] Document provisioning service API

---

### 1.2 Define Provisioning State Machine

**Priority:** HIGH  
**Dependencies:** 1.1 (Provisioning module)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design requires state tracking for provisioning operations (section 3). Ensures proper workflow management.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define states: IDLE, LOADING, VERIFY, READY, FAILED, ABORTING
- [ ] Implement state transitions with validation
- [ ] Add state change callbacks
- [ ] Track per-session state (sequence, CRC, timeout)
- [ ] Implement timeout handling
- [ ] Add state machine tests
- [ ] Document state machine behavior

---

### 1.3 HXE v2 Header Parser

**Priority:** HIGH  
**Dependencies:** Toolchain Phase 1 (HXE v2 format)  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies parsing HXE v2 metadata sections (section 2.2). Required for declarative registration.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Parse HXE v2 header (`meta_offset`, `meta_count`)
- [ ] Parse section table (name, offset, size for each metadata section)
- [ ] Extract `.value` section data
- [ ] Extract `.cmd` section data
- [ ] Extract `.mailbox` section data
- [ ] Validate header format and checksums
- [ ] Add header parser tests
- [ ] Document HXE v2 format in `docs/hxe_format.md`

---

### 1.4 App Name Conflict Detection

**Priority:** HIGH  
**Dependencies:** 1.3 (Header parser)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies app name conflict detection with `allow_multiple_instances` flag (section 2.3). Prevents conflicts.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Parse `app_name` from HXE metadata
- [ ] Parse `allow_multiple_instances` flag
- [ ] Check existing tasks for `app_name` collision
- [ ] Generate unique instance names if allowed
- [ ] Reject load if conflicts and not allowed
- [ ] Add conflict detection tests
- [ ] Document app name policy

---

### 1.5 Metadata Section Processing

**Priority:** HIGH  
**Dependencies:** 1.3 (Header parser), ValCmd Phases 1-5  
**Estimated Effort:** 1 week

**Rationale:**  
Design requires registering metadata with value/command/mailbox subsystems before VM load (section 2.2).

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Parse value declarations from `.value` section
- [ ] Register values with value subsystem
- [ ] Parse command declarations from `.cmd` section
- [ ] Register commands with command subsystem
- [ ] Parse mailbox declarations from `.mailbox` section
- [ ] Register mailboxes with mailbox subsystem
- [ ] Strip metadata sections before VM load
- [ ] Add metadata processing tests
- [ ] Document metadata registration protocol

---

## Phase 2: Streaming Loader

### 2.1 Implement vm_load_begin

**Priority:** HIGH  
**Dependencies:** VM Phase 1.6 (Streaming loader)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies streaming API for byte-by-byte loading (section 2.1). Starts streaming session.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define `vm_load_begin` RPC interface
- [ ] Allocate VM arenas for new task
- [ ] Create PID in LOADING state
- [ ] Initialize transfer session state
- [ ] Return session handle
- [ ] Add `vm_load_begin` tests
- [ ] Document `vm_load_begin` API

---

### 2.2 Implement vm_load_write

**Priority:** HIGH  
**Dependencies:** 2.1 (vm_load_begin)  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies chunked data transfer with sequence numbers (section 2.1). Core streaming functionality.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define `vm_load_write` RPC interface
- [ ] Accept payload chunks with sequence numbers
- [ ] Validate sequence numbers (detect gaps, duplicates)
- [ ] Perform incremental CRC validation
- [ ] Write to VM arenas
- [ ] Handle header validation incrementally
- [ ] Update transfer progress
- [ ] Add `vm_load_write` tests
- [ ] Document `vm_load_write` API

---

### 2.3 Implement vm_load_end

**Priority:** HIGH  
**Dependencies:** 2.2 (vm_load_write)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies final validation and PID state transition (section 2.1). Completes streaming session.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define `vm_load_end` RPC interface
- [ ] Perform final CRC validation
- [ ] Verify complete HXE structure
- [ ] Process metadata sections (Phase 1.5)
- [ ] Transition PID to READY state
- [ ] Emit provisioning.complete event
- [ ] Add `vm_load_end` tests
- [ ] Document `vm_load_end` API

---

### 2.4 Implement vm_load_abort

**Priority:** MEDIUM  
**Dependencies:** 2.1 (vm_load_begin)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design requires cleanup on error or timeout (section 2.1). Resource management.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define `vm_load_abort` RPC interface
- [ ] Free allocated VM arenas
- [ ] Clean up transfer session state
- [ ] Transition to ABORTING state
- [ ] Emit provisioning.aborted event
- [ ] Add `vm_load_abort` tests
- [ ] Document `vm_load_abort` API

---

### 2.5 Transfer Session Tracking

**Priority:** MEDIUM  
**Dependencies:** 2.1, 2.2, 2.3, 2.4 (Streaming APIs)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Track sequence numbers, CRC, timeouts for reliable transfer. Session management.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Track sequence numbers for each chunk
- [ ] Maintain CRC accumulator
- [ ] Implement timeout timers
- [ ] Detect stalled transfers
- [ ] Auto-abort on timeout
- [ ] Add session tracking tests
- [ ] Document session state management

---

## Phase 3: Progress & Event Streaming

### 3.1 Define Provisioning Event Schema

**Priority:** HIGH  
**Dependencies:** Executive Phase 2 (Event streaming)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies structured events with back-pressure (section 4). Event definitions.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define `provisioning.started` event schema
- [ ] Define `provisioning.progress` event schema (bytes_written, total_bytes, percent)
- [ ] Define `provisioning.complete` event schema
- [ ] Define `provisioning.error` event schema (error code, message)
- [ ] Define `provisioning.aborted` event schema
- [ ] Define `provisioning.persisted` event schema
- [ ] Define `provisioning.rollback` event schema
- [ ] Document event schemas in `docs/executive_protocol.md`

---

### 3.2 Implement Event Emission

**Priority:** HIGH  
**Dependencies:** 3.1 (Event schema)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design requires event emission at provisioning milestones (section 4). Real-time progress updates.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Emit `started` event on provisioning start
- [ ] Emit `progress` events during transfer
- [ ] Emit `complete` event on successful load
- [ ] Emit `error` events on failures
- [ ] Include PID, phase, timestamp in all events
- [ ] Add event emission tests
- [ ] Document event emission behavior

---

### 3.3 Rate-Limiting

**Priority:** MEDIUM  
**Dependencies:** 3.2 (Event emission)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies event coalescing and back-pressure (section 4.2). Prevents event flooding.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Implement event coalescing for progress updates
- [ ] Add configurable rate limit (events per second)
- [ ] Detect slow consumers
- [ ] Apply back-pressure to event generation
- [ ] Add rate-limiting tests
- [ ] Document rate-limiting policy

---

### 3.4 ACK Handling

**Priority:** LOW  
**Dependencies:** 3.2 (Event emission)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design mentions client ACK for flow control (section 4.2). Optional flow control.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define ACK protocol
- [ ] Implement ACK reception
- [ ] Pause event emission on missing ACKs
- [ ] Resume on ACK receipt
- [ ] Add ACK tests
- [ ] Document ACK protocol

---

## Phase 4: Monolithic Loader Enhancement

### 4.1 Pre-Verification

**Priority:** HIGH  
**Dependencies:** Phase 1 (Header parser, metadata processing)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design requires verification before VM load (section 2.4). Catch errors early.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Validate HXE header structure
- [ ] Verify CRC checksums
- [ ] Check section table integrity
- [ ] Validate metadata sections
- [ ] Optional: signature verification
- [ ] Reject invalid HXE files early
- [ ] Add pre-verification tests
- [ ] Document verification checks

---

### 4.2 Source Tracking

**Priority:** MEDIUM  
**Dependencies:** 4.1 (Pre-verification)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design requires tracking load source for `ps` command (section 2.5). Provenance tracking.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Record load source (filepath, CAN master, SD manifest)
- [ ] Store in task metadata
- [ ] Display in `ps` command output
- [ ] Add source tracking tests
- [ ] Document source metadata format

---

### 4.3 Error Mapping

**Priority:** MEDIUM  
**Dependencies:** 4.1 (Pre-verification)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design requires mapping VM errors to provisioning events (section 2.6). Error reporting.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Map `EBADMSG` (bad format) to provisioning.error
- [ ] Map `ENOSPC` (insufficient memory) to provisioning.error
- [ ] Map `ESRCH` (PID not found) to provisioning.error
- [ ] Map `EBUSY` (resource conflict) to provisioning.error
- [ ] Include error details in events
- [ ] Add error mapping tests
- [ ] Document error codes

---

### 4.4 Integration with Metadata Processing

**Priority:** HIGH  
**Dependencies:** Phase 1.5 (Metadata processing)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design requires stripping metadata before VM load (section 2.2). VM receives clean HXE.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Extract metadata sections from HXE
- [ ] Process metadata (register values/commands/mailboxes)
- [ ] Strip metadata sections
- [ ] Pass clean HXE to `vm_load_hxe`
- [ ] Verify VM receives stripped image
- [ ] Add integration tests
- [ ] Document metadata stripping

---

## Phase 5: HAL Transport Bindings

### 5.1 Filesystem Binding

**Priority:** MEDIUM  
**Dependencies:** HAL (08--HAL) filesystem implementation  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies HAL filesystem binding for host file loading (section 3.3). File transport.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Create `hal.fs.open(path)` binding
- [ ] Create `hal.fs.read(fd, size)` binding
- [ ] Create `hal.fs.close(fd)` binding
- [ ] Implement file-based provisioning workflow
- [ ] Add filesystem binding tests
- [ ] Document filesystem transport

---

### 5.2 CAN Binding

**Priority:** LOW  
**Dependencies:** HAL (08--HAL) CAN implementation  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Design specifies CAN broadcast provisioning (section 3.1). CAN transport.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Create `hal.can.recv()` binding
- [ ] Create `hal.can.send()` binding
- [ ] Implement CAN broadcast protocol
- [ ] Handle chunked transfers
- [ ] Implement acknowledgments
- [ ] Add CAN master role
- [ ] Add CAN listener role
- [ ] Add CAN binding tests
- [ ] Document CAN provisioning protocol

---

### 5.3 SD Binding

**Priority:** LOW  
**Dependencies:** HAL (08--HAL) SD card implementation  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies SD manifest parsing (section 3.2). SD card transport.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Parse TOML/JSON manifest files
- [ ] Resolve image paths from manifest
- [ ] Implement boot priority ordering
- [ ] Load HXE files from SD card
- [ ] Add SD binding tests
- [ ] Provide example manifests
- [ ] Document SD manifest format

---

### 5.4 UART Binding

**Priority:** LOW  
**Dependencies:** HAL (08--HAL) UART implementation  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design mentions UART streaming provisioning (section 3.4). Serial transport.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Create UART byte stream ingestion
- [ ] Implement UART framing protocol
- [ ] Handle flow control
- [ ] Add UART binding tests
- [ ] Document UART provisioning

---

### 5.5 Transport Abstraction

**Priority:** MEDIUM  
**Dependencies:** 5.1, 5.2, 5.3, 5.4 (Transport bindings)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Common interface for all transport modes. Simplifies provisioning service.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define transport abstraction interface
- [ ] Implement common transport operations (open, read, close)
- [ ] Abstract transport-specific details
- [ ] Support pluggable transport modules
- [ ] Add abstraction tests
- [ ] Document transport interface

---

## Phase 6: Persistence Layer

### 6.1 FRAM/Flash Schema

**Priority:** LOW  
**Dependencies:** HAL (08--HAL) FRAM/flash drivers  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies persistent storage for HXE blobs and calibration data (section 5). Storage format.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define storage layout (partition table)
- [ ] Define HXE blob format in storage
- [ ] Define manifest format (boot config, task metadata)
- [ ] Define per-task metadata schema
- [ ] Reserve space for value persistence
- [ ] Add schema tests
- [ ] Document FRAM/flash layout

---

### 6.2 Commit Protocol

**Priority:** LOW  
**Dependencies:** 6.1 (FRAM/flash schema)  
**Estimated Effort:** 1 week

**Rationale:**  
Design requires staging, CRC, atomic swap (section 5.2). Safe persistence.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Implement staging area for new HXE
- [ ] Perform CRC verification in staging
- [ ] Implement atomic pointer swap
- [ ] Update manifest on successful commit
- [ ] Add commit protocol tests
- [ ] Document commit procedure

---

### 6.3 Rollback Support

**Priority:** LOW  
**Dependencies:** 6.2 (Commit protocol)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design requires revert to known-good configuration (section 5.3). Safety mechanism.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Track previous configuration (prior manifest)
- [ ] Implement rollback command
- [ ] Restore prior HXE blob
- [ ] Restore prior value data
- [ ] Emit rollback events
- [ ] Add rollback tests
- [ ] Document rollback behavior

---

### 6.4 Wear Management

**Priority:** LOW  
**Dependencies:** 6.1 (FRAM/flash schema)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design mentions write count tracking and partition rotation (section 5.4). Flash longevity.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Track write counts per partition
- [ ] Implement partition rotation
- [ ] Detect excessive wear
- [ ] Alert on wear threshold
- [ ] Add wear management tests
- [ ] Document wear policy

---

### 6.5 Value Subsystem Integration

**Priority:** MEDIUM  
**Dependencies:** 6.1 (FRAM/flash schema), ValCmd Phase 6  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design requires persisting calibration data via value subsystem (section 5.5). Value persistence.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Persist values marked with `val.persist` flag
- [ ] Store value data in FRAM/flash
- [ ] Restore persisted values after load
- [ ] Handle value schema changes
- [ ] Add value persistence tests
- [ ] Document value persistence behavior

---

## Phase 7: Policy & Security

### 7.1 Access Control

**Priority:** LOW  
**Dependencies:** Phase 1 (Provisioning service)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design mentions authorization checks for provisioning operations (section 6.1). Security.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define provisioning permissions
- [ ] Implement authorization checks
- [ ] Restrict privileged operations
- [ ] Add access control tests
- [ ] Document access policy

---

### 7.2 Signature Verification

**Priority:** LOW  
**Dependencies:** Phase 4.1 (Pre-verification)  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies cryptographic validation of HXE images (section 6.2). Optional security.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define signature format (RSA, Ed25519)
- [ ] Implement signature verification
- [ ] Store trusted public keys
- [ ] Reject unsigned images (if policy requires)
- [ ] Add signature tests
- [ ] Document signature scheme

---

### 7.3 Capability Checks

**Priority:** MEDIUM  
**Dependencies:** Phase 1.3 (Header parser)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design requires verifying HXE capability flags match target (section 6.3). Compatibility.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Parse HXE capability flags (`requires_f16`, `needs_mailbox`)
- [ ] Check target capabilities
- [ ] Reject incompatible HXE files
- [ ] Add capability check tests
- [ ] Document capability flags

---

### 7.4 Resource Budget Enforcement

**Priority:** MEDIUM  
**Dependencies:** Phase 1.3 (Header parser)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design requires pre-allocation checks for memory budgets (section 6.4). Resource management.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Parse code/data/stack size requirements
- [ ] Check available memory
- [ ] Reject if insufficient resources
- [ ] Reserve resources before loading
- [ ] Add budget enforcement tests
- [ ] Document resource budgets

---

## Phase 8: Boot Sequence

### 8.1 Boot Configuration

**Priority:** LOW  
**Dependencies:** Phase 6 (Persistence layer)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies startup script with priority ordering (section 7.1). Boot automation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Define boot configuration format
- [ ] Parse boot configuration on startup
- [ ] Implement priority ordering
- [ ] Auto-load HXE files per config
- [ ] Add boot config tests
- [ ] Provide example boot configs
- [ ] Document boot configuration

---

### 8.2 Source Priority Scanning

**Priority:** LOW  
**Dependencies:** Phase 5 (Transport bindings), 8.1 (Boot config)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies scanning host → SD → CAN for boot sources (section 7.2). Auto-provisioning.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Scan host filesystem for preload files
- [ ] Scan SD card manifest
- [ ] Listen for CAN master broadcasts
- [ ] Implement priority ordering
- [ ] Auto-provision from highest priority source
- [ ] Add source scanning tests
- [ ] Document source priority

---

### 8.3 Persisted Value Restoration

**Priority:** MEDIUM  
**Dependencies:** Phase 6.5 (Value persistence)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design requires restoring persisted values after load (section 7.3). State restoration.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Restore persisted value data on boot
- [ ] Restore after new HXE load
- [ ] Handle missing/corrupted value data
- [ ] Emit restoration events
- [ ] Add restoration tests
- [ ] Document restoration behavior

---

### 8.4 Fallback Handling

**Priority:** LOW  
**Dependencies:** Phase 6.3 (Rollback support), 8.1 (Boot config)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design mentions detecting boot failures and rolling back (section 7.4). Boot safety.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Detect boot failures (exceptions, timeouts)
- [ ] Attempt rollback to known-good image
- [ ] Track boot failure count
- [ ] Alert on repeated failures
- [ ] Add fallback tests
- [ ] Document fallback behavior

---

## Phase 9: Testing and Documentation

### 9.1 Unit Tests

**Priority:** HIGH  
**Dependencies:** Phases 1-8 complete  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Comprehensive unit tests for all provisioning components. Quality assurance.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Test provisioning state machine
- [ ] Test HXE v2 parser
- [ ] Test metadata processing
- [ ] Test streaming APIs
- [ ] Test event emission
- [ ] Test transport bindings
- [ ] Test persistence layer
- [ ] Measure test coverage (target >80%)
- [ ] Add tests to CI pipeline

---

### 9.2 Integration Tests

**Priority:** HIGH  
**Dependencies:** 9.1 (Unit tests)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
End-to-end provisioning workflows with mock transports. Integration validation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Test monolithic load workflow
- [ ] Test streaming load workflow
- [ ] Test metadata registration flow
- [ ] Test event emission flow
- [ ] Test mock CAN provisioning
- [ ] Test mock SD provisioning
- [ ] Add integration tests to CI

---

### 9.3 Persistence Tests

**Priority:** MEDIUM  
**Dependencies:** Phase 6 (Persistence layer)  
**Estimated Effort:** 1 week

**Rationale:**  
Power-fail simulation, rollback, wear management tests. Persistence validation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Simulate power failures during commit
- [ ] Test rollback on corruption
- [ ] Test wear management
- [ ] Test value persistence/restoration
- [ ] Verify data integrity
- [ ] Add persistence tests to CI

---

### 9.4 CAN/SD Provisioning Tests

**Priority:** LOW  
**Dependencies:** Phase 5 (Transport bindings)  
**Estimated Effort:** 1 week

**Rationale:**  
Full provisioning scenarios with protocol validation. Transport testing.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Test CAN broadcast protocol
- [ ] Test SD manifest parsing
- [ ] Test chunked transfers
- [ ] Test ACK protocol
- [ ] Test error handling
- [ ] Add CAN/SD tests to CI

---

### 9.5 Documentation

**Priority:** HIGH  
**Dependencies:** Phases 1-8 complete  
**Estimated Effort:** 1 week

**Rationale:**  
Complete HXE v2 format spec and provisioning API documentation. Documentation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.07--Provisioning](../../../04--Design/04.07--Provisioning.md)
- [ ] Complete `docs/hxe_format.md` with metadata section table
- [ ] Document provisioning API in `docs/executive_protocol.md`
- [ ] Document all event schemas
- [ ] Provide CAN provisioning workflow examples
- [ ] Provide SD manifest examples
- [ ] Document persistence handshake
- [ ] Review and refine all documentation

---

## Definition of Done (DoD)

This implementation is considered complete when all of the following criteria are met:

### Phase 1 Completion
- [ ] Provisioning service module created
- [ ] State machine managing provisioning workflow
- [ ] HXE v2 header parser functional
- [ ] App name conflict detection working
- [ ] Metadata sections processed and registered
- [ ] All Phase 1 tests pass

### Phase 2 Completion
- [ ] Streaming APIs implemented (begin/write/end/abort)
- [ ] Transfer session tracking functional
- [ ] Chunked transfers working
- [ ] All Phase 2 tests pass

### Phase 3 Completion
- [ ] Provisioning event schema defined
- [ ] Events emitted at all milestones
- [ ] Rate-limiting preventing event floods
- [ ] All Phase 3 tests pass

### Phase 4 Completion
- [ ] Pre-verification catching invalid HXE files
- [ ] Source tracking recording provenance
- [ ] Error mapping providing clear diagnostics
- [ ] Metadata integration working
- [ ] All Phase 4 tests pass

### Phase 5 Completion
- [ ] Transport bindings implemented (filesystem, CAN, SD, UART)
- [ ] Transport abstraction simplifying provisioning
- [ ] All Phase 5 tests pass

### Phase 6 Completion
- [ ] FRAM/flash persistence working
- [ ] Commit protocol providing atomic updates
- [ ] Rollback support for safety
- [ ] Wear management extending flash life
- [ ] Value persistence working
- [ ] All Phase 6 tests pass

### Phase 7 Completion
- [ ] Access control enforcing permissions
- [ ] Signature verification optional security
- [ ] Capability checks ensuring compatibility
- [ ] Resource budgets preventing overcommit
- [ ] All Phase 7 tests pass

### Phase 8 Completion
- [ ] Boot configuration automating startup
- [ ] Source priority scanning auto-provisioning
- [ ] Value restoration working
- [ ] Fallback handling providing safety
- [ ] All Phase 8 tests pass

### Phase 9 Completion
- [ ] Test coverage >80% for provisioning
- [ ] Integration tests passing
- [ ] Persistence tests passing
- [ ] CAN/SD tests passing
- [ ] All documentation complete

### Overall Quality Criteria
- [ ] Provisioning service orchestrating all workflows
- [ ] Monolithic and streaming load modes working
- [ ] HXE v2 metadata processing functional
- [ ] Event streaming with back-pressure working
- [ ] At least one transport binding functional (filesystem)
- [ ] Integration with VM, Executive, ValCmd verified
- [ ] CI pipeline green on all platforms
- [ ] Code follows project style guidelines
- [ ] All documentation reviewed and approved

### Traceability
- [ ] All design requirements tracked to implementation
- [ ] All gaps from Study document addressed
- [ ] DependencyTree.md updated with completion status
- [ ] Cross-module dependencies verified

---

## Cross-References

**Design Documents:**
- [04.07--Provisioning.md](../../../04--Design/04.07--Provisioning.md) - Provisioning Design Specification

**Gap Analysis:**
- [01--Study.md](./01--Study.md) - Gap Analysis Study

**Dependencies:**
- [DependencyTree.md](../DependencyTree.md) - Cross-module dependency tracking
- [01--VM](../01--VM/01--Study.md) - Streaming loader APIs (Phase 1.6)
- [02--Executive](../02--Executive/01--Study.md) - Event streaming (Phase 2)
- [04--ValCmd](../04--ValCmd/01--Study.md) - Value/command subsystem (Phases 1-5)
- [05--Toolchain](../05--Toolchain/01--Study.md) - HXE v2 format (Phase 1)
- [08--HAL](../08--HAL/01--Study.md) - Hardware abstraction (all transports)

**Documentation:**
- `docs/hxe_format.md` - HXE format specification (to be completed)
- `docs/executive_protocol.md` - Executive RPC protocol (provisioning section to be added)

**Tools:**
- `python/execd.py` - Executive (basic load exists, to be enhanced)
- `python/provisioning.py` - Provisioning service (to be created)

---

**Last Updated:** 2025-10-31  
**Status:** Initial Plan  
**Owner:** Provisioning Implementation Team

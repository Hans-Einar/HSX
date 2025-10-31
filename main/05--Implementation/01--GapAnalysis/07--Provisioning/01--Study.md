# Gap Analysis: Provisioning & Persistence

## 1. Scope Recap

_Brief synopsis of the design document and links back to the design specification._

**Design Reference:** [04.07--Provisioning.md](../../../04--Design/04.07--Provisioning.md)

**Summary:**  
The Provisioning design specifies executive-owned orchestration for HXE image loading and persistence. It comprises:

- **HXE Loading** - Monolithic and streaming modes via `vm_load_hxe` and `vm_load_begin/write/end/abort`
- **HXE v2 Metadata Processing** - Parse and register `.value`, `.cmd`, `.mailbox` sections before VM load
- **App Name Conflict Detection** - Enforce single-instance constraints or generate unique instance names
- **Transport Support** - Host file, CAN broadcast, SD manifest, UART provisioning workflows
- **Persistence Layer** - FRAM/flash storage for calibration data and state retention tied to value subsystem
- **Progress & Events** - Structured event emission with back-pressure and rate-limiting
- **Policy & Security** - Access control, signature verification, capability checks, resource budgets

**Dependencies:**
- Requires VM loader APIs (see [01--VM](../01--VM/01--Study.md))
- Requires executive event streaming (see [02--Executive](../02--Executive/01--Study.md))
- Requires value/command subsystem for metadata processing (see [04--ValCmd](../04--ValCmd/01--Study.md))
- Requires HAL drivers for CAN, SD, FRAM, filesystem (see [08--HAL](../08--HAL/01--Study.md))
- Requires toolchain HXE v2 format support (see [05--Toolchain](../05--Toolchain/01--Study.md))

---

## 2. Current Implementation

_What already exists today that satisfies the design intent._

**Code Paths:**
- **Executive `load` command:** `python/execd.py:122` - Basic monolithic file loading via `vm.load(path)`
  - Calls VM's `load()` method
  - Refreshes task list after loading
  - No HXE v2 metadata preprocessing
  - No streaming support
  - No persistence support
  - No progress events
- **No dedicated provisioning module** - Provisioning functionality not separated from VM load

**Tests:**
- **No provisioning tests** - No tests for provisioning workflows, streaming, persistence, or rollback

**Tools:**
- Shell client `load` command calls executive's basic load functionality

**Documentation:**
- Design documents: `main/04--Design/04.07--Provisioning.md`
- HXE format (incomplete): `docs/hxe_format.md`

---

## 3. Missing or Partial Coverage

_Gaps that block full compliance with the design._

**Open Items:**

**Core Provisioning Infrastructure:**
- **Provisioning service module missing:** No dedicated provisioning orchestration layer in executive
- **HXE v2 metadata preprocessing:** No parsing of `.value`, `.cmd`, `.mailbox` sections from HXE header
- **App name conflict detection:** No checking of `app_name` field or `allow_multiple_instances` flag
- **Metadata stripping:** No removal of metadata sections before passing to VM

**Loading Modes:**
- **Streaming API missing:** No `vm_load_begin/write/end/abort` support for byte-by-byte loading
- **Monolithic loader incomplete:** Current `vm.load()` doesn't perform verification or preprocessing
- **Source tracking:** No recording of load source (filepath, CAN master, SD manifest) for `ps` command
- **Transfer session state:** No tracking of sequence numbers, payload chunks, CRC progress, timeout timers

**Transport Support:**
- **CAN provisioning missing:** No CAN broadcast protocol with chunked transfers and acknowledgements
- **SD manifest missing:** No TOML/JSON manifest parsing for boot configuration
- **UART provisioning missing:** No UART streaming support
- **HAL integration missing:** No HAL bindings for CAN/SD/FRAM/filesystem (HAL itself not implemented - see 08--HAL)

**Persistence Layer:**
- **FRAM/flash persistence missing:** No persistence infrastructure for calibration data or HXE images
- **Commit protocol missing:** No staging, CRC verification, atomic swap functionality
- **Rollback support missing:** No revert to prior known-good configuration
- **Wear management missing:** No write count tracking or partition rotation

**Progress & Events:**
- **Provisioning events missing:** No `provisioning.started`, `provisioning.progress`, `provisioning.complete`, `provisioning.error` events
- **Rate-limiting missing:** No event coalescing or back-pressure handling for progress updates
- **Event schema missing:** No structured event definitions in `executive_protocol.md`

**Policy & Security:**
- **Access control missing:** No authorization checks for provisioning operations
- **Signature verification missing:** No cryptographic validation of HXE images
- **Capability checks missing:** No verification of HXE capability flags (`requires_f16`, `needs_mailbox`)
- **Resource budget enforcement missing:** No pre-allocation checks for code/data/stack sizes

**Boot Sequence:**
- **Boot configuration missing:** No startup script or priority ordering for auto-loading HXE files
- **Source priority scanning missing:** No host preload → SD manifest → CAN master scanning
- **Persisted value restoration missing:** No restoration of `val.persist` data after load

**Deferred Features:**
- **Remote attestation:** Cryptographic proof of loaded application identity
- **Differential updates:** Patch-based provisioning to reduce transfer sizes
- **Multi-target provisioning:** Coordinated fleet updates via CAN broadcast

**Documentation Gaps:**
- HXE format specification incomplete in `docs/hxe_format.md` (no metadata section table schema)
- No provisioning API specification in `docs/executive_protocol.md`
- No examples of CAN/SD provisioning workflows
- No persistence handshake documentation

---

## 4. Next Actions

_Ordered steps to close the gaps._

**Priority Actions:**

**Phase 1: Provisioning Service Foundation (coordinates with Toolchain Phase 1 for HXE v2)**
1. **Create provisioning module** - New `provisioning.py` module in executive with service class
2. **Define provisioning state machine** - IDLE → LOADING → VERIFY → READY → FAILED/ABORTING states
3. **HXE v2 header parser** - Parse `meta_offset`, `meta_count`, section table from HXE header
4. **App name conflict detection** - Check existing tasks for `app_name`, enforce `allow_multiple_instances`
5. **Metadata section processing** - Parse `.value`, `.cmd`, `.mailbox` sections and register with subsystems

**Phase 2: Streaming Loader (coordinates with VM Phase 1)**
6. **Implement `vm_load_begin`** - Allocate arenas, create PID in LOADING state
7. **Implement `vm_load_write`** - Accept chunks, perform incremental header/CRC validation
8. **Implement `vm_load_end`** - Final validation, transition PID to READY
9. **Implement `vm_load_abort`** - Free arenas, reclaim resources on error/timeout
10. **Transfer session tracking** - Sequence numbers, CRC accumulator, timeout timers

**Phase 3: Progress & Event Streaming (coordinates with Executive Phase 2)**
11. **Define provisioning event schema** - `started`, `progress`, `complete`, `error`, `aborted`, `persisted`, `rollback`
12. **Implement event emission** - Structured events with `pid`, `phase`, `ts`, `bytes_written`, `total_bytes`
13. **Rate-limiting** - Event coalescing and back-pressure per `executive_protocol`
14. **ACK handling** - Client acknowledgment for flow control

**Phase 4: Monolithic Loader Enhancement**
15. **Pre-verification** - Header/section checks, signature validation (optional), CRC before VM load
16. **Source tracking** - Record load source (filepath, CAN master, SD manifest) in task metadata
17. **Error mapping** - Map VM errors (`EBADMSG`, `ENOSPC`, `ESRCH`, `EBUSY`) to provisioning events
18. **Integration with metadata processing** - Strip metadata sections before `vm_load_hxe`

**Phase 5: HAL Transport Bindings (requires HAL implementation from 08--HAL)**
19. **Filesystem binding** - `hal.fs.open/read/close` for host file loading
20. **CAN binding** - `hal.can.recv/send` for CAN broadcast provisioning
21. **SD binding** - Manifest parsing (TOML/JSON), image path resolution
22. **UART binding** - Byte stream ingestion for serial provisioning
23. **Transport abstraction** - Common interface for all transport modes

**Phase 6: Persistence Layer**
24. **FRAM/flash schema** - Define storage format for HXE blobs, manifests, per-task metadata
25. **Commit protocol** - Staging area, CRC verification, atomic pointer swap
26. **Rollback support** - Revert to prior known-good configuration on failure
27. **Wear management** - Track write counts, partition rotation per `resource_budgets`
28. **Value subsystem integration** - Persist/restore calibration data via value subsystem

**Phase 7: Policy & Security**
29. **Access control** - Authorization checks for provisioning operations
30. **Signature verification** - Cryptographic validation of HXE images (optional)
31. **Capability checks** - Verify HXE capability flags match target capabilities
32. **Resource budget enforcement** - Pre-allocation checks for code/data/stack sizes

**Phase 8: Boot Sequence**
33. **Boot configuration** - Startup script with priority ordering for auto-loading HXE files
34. **Source priority scanning** - Host preload → SD manifest → CAN master scanning
35. **Persisted value restoration** - Restore `val.persist` data after load
36. **Fallback handling** - Detect boot failures, attempt rollback to known-good image

**Phase 9: Testing and Documentation**
37. **Unit tests** - Provisioning state machine, event emission, metadata parsing
38. **Integration tests** - Monolithic and streaming workflows with mock transports
39. **Persistence tests** - Power-fail simulation, rollback, wear management
40. **CAN/SD provisioning tests** - Full provisioning scenarios with protocol validation
41. **Documentation** - Complete HXE v2 format spec, provisioning API in `executive_protocol.md`
42. **Examples** - Sample CAN/SD workflows, boot configurations

**Cross-References:**
- Design Requirements: DR-1.1, DR-1.2, DR-3.1, DR-5.1, DR-5.2, DR-5.3, DR-6.1, DR-7.1
- Design Goals: DG-1.2, DG-3.1, DG-3.5, DG-5.1, DG-5.2, DG-5.3, DG-7.3
- Dependencies:
  - VM streaming loader [01--VM](../01--VM/01--Study.md) Phase 1
  - Executive event streaming [02--Executive](../02--Executive/01--Study.md) Phase 2
  - Value/Command subsystem [04--ValCmd](../04--ValCmd/01--Study.md) Phases 1-5
  - Toolchain HXE v2 [05--Toolchain](../05--Toolchain/01--Study.md) Phase 1
  - HAL drivers [08--HAL](../08--HAL/01--Study.md) (full implementation)

---

**Last Updated:** 2025-10-31  
**Status:** Not Started (Basic monolithic file load exists, full provisioning infrastructure missing)

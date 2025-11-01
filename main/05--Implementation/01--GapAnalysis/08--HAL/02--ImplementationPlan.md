# Implementation Plan: HAL (Hardware Abstraction Layer)

**Module:** 08--HAL  
**Based on:** [01--Study.md](./01--Study.md), [04.08--HAL Design](../../../04--Design/04.08--HAL.md)  
**Status:** COMPLETE SUBSYSTEM MISSING - Only API headers exist  
**Date:** 2025-11-01

---

## Planned Implementation Order (Grand Plan)

1. Phase 1 - Python HAL mocks to support provisioning/executive workflows.
2. Phase 2 - Python device shims for mailbox/value/command integrations.
3. Phase 3 - Hardware simulation and host-side testing scaffolds.
4. Phase 4 - C driver implementations (deferred).
5. Phase 5 - Embedded integration tests and validation (deferred).
6. Phase 6 - Documentation updates once features stabilize.

## Sprint Scope

Complete the Python mock and simulation work in Phases 1 through 3 (plus any documentation updates) during this sprint. Leave the Phase 4 and 5 C deliverables for the post-Python phase and record related findings as future tasks.

## Overview

The HAL module provides a two-layer hardware abstraction architecture:
1. **Executive-Space HAL**: Syscall handlers and interrupt-driven event emission for 6 peripheral modules
2. **User-Space HAL**: Application library (`libhsx_hal.a`) wrapping syscalls with convenient APIs

**Current State:** Only 796 lines of header files exist. All implementation missing - executive drivers, user-space library, tests, and integration.

**Key Challenge:** This is the largest module spanning both executive-space drivers (Python mock + C embedded) and user-space application libraries across 6 peripherals: UART (0x10), CAN (0x11), Timer (0x12), FRAM (0x13), FS (0x14), GPIO (0x15).

---

## Phase 1: Executive-Space Foundation - UART Module

**Goal:** Implement Python mock UART driver with syscall dispatching and mailbox event emission.

**Dependencies:** 
- Executive Phase 2 (event streaming, mailbox emission)
- VM Phase 1.2 (syscall dispatching infrastructure)

**Estimated Timeline:** 3-4 weeks

### 1.1 Python Mock UART Driver

**Priority:** CRITICAL  
**Dependencies:** None  
**Estimated Effort:** 5-7 days

**Todo:**
- [ ] Create `python/hal/uart_hal.py` module structure
- [ ] Implement `UartDriver` class with loopback mode for testing
- [ ] Implement `uart_init(port, baud, parity, stop_bits)` configuration
- [ ] Implement `uart_write(port, data, length)` with blocking/non-blocking modes
- [ ] Implement `uart_read_poll(port, buffer, max_length)` for polling reads
- [ ] Implement `uart_get_status(port)` returning TX/RX queue depths
- [ ] Add `uart_config_t` structure with baud rate, parity, flow control settings
- [ ] Implement RX buffer with configurable size (default 256 bytes)
- [ ] Add thread-safe access with locks for concurrent operations
- [ ] Implement loopback mode routing TX → RX buffer for testing
- [ ] Add desktop simulation using socket pairs or PTY for external tools
- [ ] Implement line buffering mode for console I/O
- [ ] Add optional RTS/CTS flow control simulation
- [ ] Implement TX timeout handling for blocking writes
- [ ] Create UART capability structure (`hal_uart_caps_t`)

### 1.2 UART Syscall Dispatching

**Priority:** CRITICAL  
**Dependencies:** 1.1  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Add UART module (0x10) to VM syscall dispatcher in `platforms/python/host_vm.py`
- [ ] Implement `SVC_UART_WRITE` (0x10, 0x01) syscall handler
- [ ] Implement `SVC_UART_READ_POLL` (0x10, 0x02) syscall handler
- [ ] Implement `SVC_UART_CONFIG` (0x10, 0x03) syscall handler
- [ ] Implement `SVC_UART_GET_STATUS` (0x10, 0x04) syscall handler
- [ ] Map HAL status codes to HSX error codes in PSW.E
- [ ] Add parameter validation (port number, buffer bounds)
- [ ] Remove `HSX_ERR_ENOSYS` placeholder for UART syscalls
- [ ] Add VM register marshalling (R0-R3 for args, R0 for return)
- [ ] Implement syscall error handling and status code propagation
- [ ] Add debug trace logging for UART syscall invocations

### 1.3 UART RX Mailbox Emission

**Priority:** HIGH  
**Dependencies:** 1.1, Executive Phase 2 (mailbox system)  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Implement async RX handler thread in `UartDriver`
- [ ] Emit RX data to mailbox `hal:uart:<port>:rx` on byte arrival
- [ ] Implement mailbox message format: `{"port": 0, "data": [0x41, 0x42], "timestamp": 123456}`
- [ ] Add back-pressure handling when mailbox is full (drop oldest or block)
- [ ] Implement rate-limiting for high-throughput RX (batch messages)
- [ ] Add RX event filtering (only emit on complete frames or line boundaries)
- [ ] Implement RX timeout for partial data buffering
- [ ] Add RX error reporting via mailbox (framing errors, overrun)
- [ ] Create integration with executive mailbox subsystem
- [ ] Add configurable mailbox delivery mode (UNICAST/BROADCAST)

### 1.4 UART Unit Tests

**Priority:** HIGH  
**Dependencies:** 1.1, 1.2, 1.3  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Create `python/tests/test_uart_hal.py` test module
- [ ] Test loopback mode: write → read verification
- [ ] Test configuration: baud rate, parity, stop bits settings
- [ ] Test non-blocking write with TX buffer full
- [ ] Test polling read with no data available
- [ ] Test status query returning correct TX/RX queue depths
- [ ] Test RX mailbox emission with expected message format
- [ ] Test back-pressure handling when mailbox is full
- [ ] Test error conditions: invalid port, buffer overflow
- [ ] Test concurrent access from multiple VM instances
- [ ] Test line buffering mode with newline detection
- [ ] Test RX timeout with partial data
- [ ] Add performance test: throughput measurement
- [ ] Add stress test: sustained high-rate TX/RX
- [ ] Verify syscall error code translation

---

## Phase 2: Executive-Space Foundation - Timer Module

**Goal:** Implement Python mock Timer driver with monotonic tick and periodic timer support.

**Dependencies:** 
- Phase 1 complete
- Executive Phase 4 (scheduler integration for sleep/wake)

**Estimated Timeline:** 2-3 weeks

### 2.1 Python Mock Timer Driver

**Priority:** CRITICAL  
**Dependencies:** None  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Create `python/hal/timer_hal.py` module structure
- [ ] Implement `TimerDriver` class with monotonic counter
- [ ] Implement `timer_get_tick()` returning 64-bit microsecond counter
- [ ] Implement `timer_get_tick_freq()` returning ticks per second
- [ ] Implement `timer_create(id, interval_us, periodic)` for timer registration
- [ ] Implement `timer_cancel(id)` to stop active timer
- [ ] Use `time.monotonic_ns()` for high-resolution desktop simulation
- [ ] Implement periodic timer firing with ±1% accuracy target
- [ ] Add one-shot timer support (fires once and auto-cancels)
- [ ] Implement timer manager thread for expiry detection
- [ ] Add timer registry with max 32 concurrent timers
- [ ] Implement timer ID allocation and recycling
- [ ] Add timer expiry callback mechanism
- [ ] Create timer capability structure (`hal_timer_caps_t`)
- [ ] Add timer overflow handling for 64-bit rollover (after 584,000 years)

### 2.2 Timer Syscall Dispatching

**Priority:** CRITICAL  
**Dependencies:** 2.1  
**Estimated Effort:** 2-3 days

**Todo:**
- [ ] Add Timer module (0x12) to VM syscall dispatcher
- [ ] Implement `SVC_TIMER_GET_TICK` (0x12, 0x01) syscall handler
- [ ] Implement `SVC_TIMER_GET_TICK_FREQ` (0x12, 0x02) syscall handler
- [ ] Implement `SVC_TIMER_CREATE` (0x12, 0x03) syscall handler
- [ ] Implement `SVC_TIMER_CANCEL` (0x12, 0x04) syscall handler
- [ ] Handle 64-bit tick value return in R0:R1 register pair
- [ ] Add parameter validation (timer ID bounds, interval > 0)
- [ ] Implement timer ID allocation tracking in VM state
- [ ] Remove `HSX_ERR_ENOSYS` placeholder for Timer syscalls
- [ ] Add syscall error handling for timer resource exhaustion

### 2.3 Timer Expiry Mailbox Emission

**Priority:** HIGH  
**Dependencies:** 2.1, 2.2, Executive Phase 2  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Emit timer expiry event to mailbox `hal:timer:<id>` on timer fire
- [ ] Implement mailbox message format: `{"timer_id": 5, "timestamp": 123456, "fired_count": 10}`
- [ ] Add periodic timer auto-rearm after mailbox emission
- [ ] Implement one-shot timer auto-cancel after first fire
- [ ] Add timer accuracy tracking (actual vs. expected interval)
- [ ] Implement timer event batching for high-frequency timers (>100Hz)
- [ ] Add back-pressure handling if mailbox delivery is blocked
- [ ] Create timer expiry callback registration API
- [ ] Add timer statistics reporting (fires, overruns, accuracy)

### 2.4 Timer Sleep Integration

**Priority:** MEDIUM  
**Dependencies:** 2.1, 2.2, Executive Phase 4 (scheduler)  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Implement `timer_sleep_us(duration)` suspending VM execution
- [ ] Integrate with Executive scheduler for context switching during sleep
- [ ] Add wake-up event emission to scheduler on sleep expiry
- [ ] Implement sleep cancellation on external events (mailbox, interrupt)
- [ ] Add sleep precision measurement (actual vs. requested duration)
- [ ] Implement sleep queue priority ordering (soonest expiry first)
- [ ] Add sleep timeout handling for bounded waits
- [ ] Create integration tests with scheduler wait/wake

### 2.5 Timer Unit Tests

**Priority:** HIGH  
**Dependencies:** 2.1, 2.2, 2.3  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Create `python/tests/test_timer_hal.py` test module
- [ ] Test monotonic tick accuracy (±100µs over 1 second)
- [ ] Test tick frequency reporting matches implementation
- [ ] Test periodic timer firing at correct intervals
- [ ] Test one-shot timer fires once and auto-cancels
- [ ] Test timer cancellation stops future fires
- [ ] Test timer ID allocation and recycling
- [ ] Test timer resource exhaustion (32 concurrent timers)
- [ ] Test timer mailbox emission with correct format
- [ ] Test timer accuracy under high system load
- [ ] Test 64-bit tick overflow handling (simulated)
- [ ] Test concurrent timer creation/cancellation
- [ ] Add stress test: 32 timers at different frequencies
- [ ] Verify syscall error code translation

---

## Phase 3: Executive-Space Foundation - FRAM Module

**Goal:** Implement Python mock FRAM driver with persistent storage and wear tracking.

**Dependencies:** 
- Phase 1-2 complete
- ValCmd Phase 6 (persistence layer integration)

**Estimated Timeline:** 2-3 weeks

### 3.1 Python Mock FRAM Driver

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Create `python/hal/fram_hal.py` module structure
- [ ] Implement `FramDriver` class with memory-backed storage
- [ ] Implement `fram_read(address, buffer, length)` for block reads
- [ ] Implement `fram_write(address, data, length)` for block writes
- [ ] Implement `fram_get_size()` returning total FRAM capacity (default 32KB)
- [ ] Implement `fram_get_wear(address)` returning write count for address
- [ ] Use JSON file for persistence (survives host restarts)
- [ ] Implement wear leveling tracking per 256-byte block
- [ ] Add CRC calculation helpers for data integrity verification
- [ ] Implement write protection zones (optional)
- [ ] Add FRAM capacity configuration (8KB, 32KB, 128KB profiles)
- [ ] Implement address alignment requirements (4-byte aligned)
- [ ] Add atomic write operations (all-or-nothing)
- [ ] Create FRAM capability structure (`hal_fram_caps_t`)
- [ ] Implement background persistence flush to disk

### 3.2 FRAM Syscall Dispatching

**Priority:** HIGH  
**Dependencies:** 3.1  
**Estimated Effort:** 2-3 days

**Todo:**
- [ ] Add FRAM module (0x13) to VM syscall dispatcher
- [ ] Implement `SVC_FRAM_READ` (0x13, 0x01) syscall handler
- [ ] Implement `SVC_FRAM_WRITE` (0x13, 0x02) syscall handler
- [ ] Implement `SVC_FRAM_GET_SIZE` (0x13, 0x03) syscall handler
- [ ] Implement `SVC_FRAM_GET_WEAR` (0x13, 0x04) syscall handler
- [ ] Add parameter validation (address bounds, length > 0)
- [ ] Implement memory safety checks (prevent buffer overflows)
- [ ] Remove `HSX_ERR_ENOSYS` placeholder for FRAM syscalls
- [ ] Add write protection enforcement
- [ ] Implement atomic write transaction support

### 3.3 FRAM Persistence Integration

**Priority:** MEDIUM  
**Dependencies:** 3.1, 3.2, ValCmd Phase 6  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Integrate FRAM HAL with ValCmd persistence layer
- [ ] Implement value serialization to FRAM storage
- [ ] Add value restoration on boot from FRAM
- [ ] Implement FRAM manifest for value metadata (OIDs, types, locations)
- [ ] Add partition table for multiple value namespaces
- [ ] Implement garbage collection for deleted values
- [ ] Add FRAM compaction to reclaim space
- [ ] Create backup/restore APIs for FRAM contents
- [ ] Implement FRAM encryption (optional)
- [ ] Add integrity verification on read (CRC checks)

### 3.4 FRAM Unit Tests

**Priority:** HIGH  
**Dependencies:** 3.1, 3.2  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Create `python/tests/test_fram_hal.py` test module
- [ ] Test read/write with various data patterns
- [ ] Test persistence across driver restarts (JSON file survives)
- [ ] Test wear count tracking per block
- [ ] Test address bounds checking
- [ ] Test atomic write operations (all-or-nothing)
- [ ] Test write protection zones
- [ ] Test CRC verification on read
- [ ] Test FRAM capacity limits (write to full)
- [ ] Test concurrent access from multiple VM instances
- [ ] Test wear leveling distribution
- [ ] Add stress test: sustained write patterns
- [ ] Test FRAM compaction and garbage collection
- [ ] Verify syscall error code translation

---

## Phase 4: User-Space HAL Library Foundation

**Goal:** Implement user-space library wrappers for UART, Timer, FRAM syscalls with mailbox management.

**Dependencies:** 
- Phase 1-3 complete
- Toolchain Phase 2 (C library build support)

**Estimated Timeline:** 3-4 weeks

### 4.1 User-Space UART Library

**Priority:** HIGH  
**Dependencies:** Phase 1 complete  
**Estimated Effort:** 5-6 days

**Todo:**
- [ ] Create `lib/hsx_uart.c` implementing user-space UART API
- [ ] Implement `hsx_uart_write(port, data, length)` wrapping `SVC_UART_WRITE`
- [ ] Implement `hsx_uart_read_poll(port, buffer, length)` wrapping `SVC_UART_READ_POLL`
- [ ] Implement `hsx_uart_config(port, config)` wrapping `SVC_UART_CONFIG`
- [ ] Implement `hsx_uart_printf(port, format, ...)` convenience wrapper
- [ ] Implement `hsx_uart_open_rx_mailbox(port)` for async RX
- [ ] Implement `hsx_uart_on_rx(port, callback)` callback registration
- [ ] Add RX event loop polling mailbox `hal:uart:<port>:rx`
- [ ] Implement RX buffer management (circular buffer)
- [ ] Add line-oriented read: `hsx_uart_read_line(port, buffer, max)`
- [ ] Implement timeout support for blocking reads
- [ ] Add TX buffer management for large writes
- [ ] Implement chunked write for data > 256 bytes
- [ ] Add status query API: `hsx_uart_get_status(port, status)`
- [ ] Create error code translation from syscall returns

### 4.2 User-Space Timer Library

**Priority:** HIGH  
**Dependencies:** Phase 2 complete  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Create `lib/hsx_timer.c` implementing user-space Timer API
- [ ] Implement `hsx_timer_get_tick()` wrapping `SVC_TIMER_GET_TICK`
- [ ] Implement `hsx_timer_get_tick_freq()` wrapping `SVC_TIMER_GET_TICK_FREQ`
- [ ] Implement `hsx_timer_sleep_us(duration)` for blocking delays
- [ ] Implement `hsx_timer_sleep_ms(duration)` millisecond convenience wrapper
- [ ] Implement `hsx_timer_create(interval, periodic, callback)` with mailbox management
- [ ] Implement `hsx_timer_cancel(id)` wrapping `SVC_TIMER_CANCEL`
- [ ] Add timer expiry callback mechanism polling `hal:timer:<id>` mailbox
- [ ] Implement timer manager thread for event loop
- [ ] Add timer statistics API: `hsx_timer_get_stats(id, stats)`
- [ ] Implement deadline timer: `hsx_timer_deadline(timestamp)`
- [ ] Add elapsed time helper: `hsx_timer_elapsed_us(start_tick)`
- [ ] Implement timer accuracy measurement and reporting
- [ ] Create timeout wrapper: `hsx_timer_with_timeout(duration, func, args)`

### 4.3 User-Space FRAM Library

**Priority:** HIGH  
**Dependencies:** Phase 3 complete  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Create `lib/hsx_fram.c` implementing user-space FRAM API
- [ ] Implement `hsx_fram_read(address, buffer, length)` wrapping `SVC_FRAM_READ`
- [ ] Implement `hsx_fram_write(address, data, length)` wrapping `SVC_FRAM_WRITE`
- [ ] Implement `hsx_fram_get_size()` wrapping `SVC_FRAM_GET_SIZE`
- [ ] Implement `hsx_fram_get_wear(address)` wrapping `SVC_FRAM_GET_WEAR`
- [ ] Add CRC helpers: `hsx_fram_write_with_crc(address, data, length)`
- [ ] Implement atomic transaction: `hsx_fram_begin_transaction() / commit() / abort()`
- [ ] Add key-value API: `hsx_fram_put(key, value) / get(key, value)`
- [ ] Implement FRAM allocator for dynamic storage management
- [ ] Add metadata helpers for value serialization
- [ ] Implement backup API: `hsx_fram_backup(buffer)` / `restore(buffer)`
- [ ] Add wear balancing hints for write patterns
- [ ] Implement FRAM fill: `hsx_fram_fill(address, value, length)`
- [ ] Add FRAM compare: `hsx_fram_compare(addr1, addr2, length)`

### 4.4 Library Build Integration

**Priority:** HIGH  
**Dependencies:** 4.1, 4.2, 4.3, Toolchain Phase 2  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Add `libhsx_hal.a` build target to `python/hsx-cc-build.py`
- [ ] Compile `lib/hsx_uart.c`, `lib/hsx_timer.c`, `lib/hsx_fram.c` to object files
- [ ] Archive object files into `libhsx_hal.a` static library
- [ ] Add library installation to standard HSX toolchain distribution
- [ ] Update linker script to include `libhsx_hal.a` in user programs
- [ ] Add HAL library path to `hsx-cc` search directories
- [ ] Create HAL library versioning and compatibility checks
- [ ] Add library dependency declarations (requires `libhsx_mailbox.a`)
- [ ] Implement library size optimization (strip unused functions)
- [ ] Add build profile selection (full HAL vs. minimal subset)

### 4.5 User-Space Integration Tests

**Priority:** HIGH  
**Dependencies:** 4.1, 4.2, 4.3, 4.4  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Create example app `examples/hal_uart_echo.c` using `hsx_uart_printf`
- [ ] Create example app `examples/hal_timer_blink.c` using periodic timer
- [ ] Create example app `examples/hal_fram_persist.c` using key-value storage
- [ ] Test library linking with `hsx-cc` toolchain
- [ ] Test user-space callback execution for UART RX events
- [ ] Test user-space callback execution for timer expiry events
- [ ] Test concurrent HAL library usage from multiple apps
- [ ] Test error handling and status code propagation
- [ ] Test mailbox event delivery latency (<10ms)
- [ ] Create integration test suite running example apps
- [ ] Test HAL library with HXE v2 metadata and declarative features
- [ ] Add performance benchmarks for syscall overhead
- [ ] Test library behavior under resource exhaustion

---

## Phase 5: Extended Mock Drivers - CAN, FS, GPIO

**Goal:** Implement Python mock drivers for CAN, Filesystem, and GPIO peripherals.

**Dependencies:** 
- Phase 1-4 complete
- Provisioning Phase 5 (CAN transport integration)

**Estimated Timeline:** 4-5 weeks

### 5.1 Python Mock CAN Driver

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 6-7 days

**Todo:**
- [ ] Create `python/hal/can_hal.py` module structure
- [ ] Implement `CanDriver` class with simulated CAN bus
- [ ] Implement `can_tx(frame)` for sending CAN frames
- [ ] Implement `can_config(bitrate, mode)` for bus configuration
- [ ] Implement `can_set_filter(id, mask)` for RX filtering
- [ ] Implement `can_get_status()` returning bus state, error counters
- [ ] Support 11-bit and 29-bit CAN identifiers
- [ ] Implement CAN frame structure: `{id, dlc, data[8], timestamp}`
- [ ] Add simulated CAN bus connecting multiple nodes (socket-based)
- [ ] Implement CAN error frames (bus-off, error passive, error active)
- [ ] Add CAN acceptance filters with mask matching
- [ ] Implement TX priority arbitration (higher ID wins)
- [ ] Add RX buffer with configurable size (default 64 frames)
- [ ] Implement CAN loopback mode for testing
- [ ] Add CAN bus statistics (frames sent/received, errors)

### 5.2 CAN Syscall Dispatching

**Priority:** MEDIUM  
**Dependencies:** 5.1  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Add CAN module (0x11) to VM syscall dispatcher
- [ ] Implement `SVC_CAN_TX` (0x11, 0x01) syscall handler
- [ ] Implement `SVC_CAN_CONFIG` (0x11, 0x02) syscall handler
- [ ] Implement `SVC_CAN_SET_FILTER` (0x11, 0x03) syscall handler
- [ ] Implement `SVC_CAN_GET_STATUS` (0x11, 0x04) syscall handler
- [ ] Add parameter validation (frame DLC ≤ 8, ID bounds)
- [ ] Implement CAN frame marshalling from VM registers to driver
- [ ] Remove `HSX_ERR_ENOSYS` placeholder for CAN syscalls
- [ ] Add TX queue management for pending frames
- [ ] Implement CAN error code translation

### 5.3 CAN RX Mailbox Emission

**Priority:** MEDIUM  
**Dependencies:** 5.1, 5.2  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Emit CAN RX frame to mailbox `hal:can:rx` on frame arrival
- [ ] Implement mailbox message format: `{"id": 0x123, "dlc": 8, "data": [...], "timestamp": 123456}`
- [ ] Add RX filter matching before mailbox emission
- [ ] Implement back-pressure handling when mailbox is full
- [ ] Add RX event batching for high CAN bus utilization (>80%)
- [ ] Implement CAN error frame emission to separate mailbox `hal:can:error`
- [ ] Add configurable RX delivery mode (UNICAST per filter, BROADCAST)
- [ ] Create integration with Provisioning transport layer

### 5.4 User-Space CAN Library

**Priority:** MEDIUM  
**Dependencies:** 5.1, 5.2, 5.3  
**Estimated Effort:** 5-6 days

**Todo:**
- [ ] Create `lib/hsx_can.c` implementing user-space CAN API
- [ ] Implement `hsx_can_tx(frame)` wrapping `SVC_CAN_TX`
- [ ] Implement `hsx_can_config(bitrate, mode)` wrapping `SVC_CAN_CONFIG`
- [ ] Implement `hsx_can_set_filter(id, mask, callback)` with mailbox management
- [ ] Implement `hsx_can_open_rx_mailbox()` for async RX
- [ ] Implement `hsx_can_on_frame(callback)` callback registration
- [ ] Add chunked transfer API: `hsx_can_send_chunked(data, length)`
- [ ] Implement CAN RX event loop polling `hal:can:rx` mailbox
- [ ] Add CAN error callback: `hsx_can_on_error(callback)`
- [ ] Implement CAN status query: `hsx_can_get_status(status)`
- [ ] Add CAN bus recovery API: `hsx_can_recover_bus()`
- [ ] Implement CAN frame timestamp extraction
- [ ] Add CAN broadcast API for provisioning

### 5.5 Python Mock Filesystem Driver

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 6-7 days

**Todo:**
- [ ] Create `python/hal/fs_hal.py` module structure
- [ ] Implement `FsDriver` class with host filesystem mapping
- [ ] Implement `fs_open(path, mode)` returning file descriptor
- [ ] Implement `fs_read(fd, buffer, length)` for reading
- [ ] Implement `fs_write(fd, data, length)` for writing
- [ ] Implement `fs_close(fd)` closing file descriptor
- [ ] Implement `fs_listdir(path)` returning directory entries
- [ ] Implement `fs_delete(path)` removing files
- [ ] Implement `fs_rename(old_path, new_path)` renaming files
- [ ] Implement `fs_mkdir(path)` creating directories
- [ ] Map virtual filesystem paths to host directory (e.g., `/hsx` → `~/.hsx/vfs`)
- [ ] Implement file descriptor table (max 32 open files)
- [ ] Add file metadata support (size, timestamp, permissions)
- [ ] Implement directory iteration with cursor state
- [ ] Add filesystem capacity limits (configurable quota)

### 5.6 Filesystem Syscall Dispatching

**Priority:** MEDIUM  
**Dependencies:** 5.5  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Add FS module (0x14) to VM syscall dispatcher
- [ ] Implement `SVC_FS_OPEN` (0x14, 0x01) syscall handler
- [ ] Implement `SVC_FS_READ` (0x14, 0x02) syscall handler
- [ ] Implement `SVC_FS_WRITE` (0x14, 0x03) syscall handler
- [ ] Implement `SVC_FS_CLOSE` (0x14, 0x04) syscall handler
- [ ] Implement `SVC_FS_LISTDIR` (0x14, 0x05) syscall handler
- [ ] Implement `SVC_FS_DELETE` (0x14, 0x06) syscall handler
- [ ] Implement `SVC_FS_RENAME` (0x14, 0x07) syscall handler
- [ ] Implement `SVC_FS_MKDIR` (0x14, 0x08) syscall handler
- [ ] Add parameter validation (path length, FD bounds)
- [ ] Implement file descriptor lifecycle management
- [ ] Remove `HSX_ERR_ENOSYS` placeholder for FS syscalls

### 5.7 User-Space Filesystem Library

**Priority:** MEDIUM  
**Dependencies:** 5.5, 5.6  
**Estimated Effort:** 5-6 days

**Todo:**
- [ ] Create `lib/hsx_fs.c` implementing user-space FS API
- [ ] Implement `hsx_fs_open(path, mode)` wrapping `SVC_FS_OPEN`
- [ ] Implement `hsx_fs_read(fd, buffer, length)` wrapping `SVC_FS_READ`
- [ ] Implement `hsx_fs_write(fd, data, length)` wrapping `SVC_FS_WRITE`
- [ ] Implement `hsx_fs_close(fd)` wrapping `SVC_FS_CLOSE`
- [ ] Implement `hsx_fs_listdir(path, callback)` with directory iteration
- [ ] Implement `hsx_fs_delete(path)` wrapping `SVC_FS_DELETE`
- [ ] Implement `hsx_fs_rename(old, new)` wrapping `SVC_FS_RENAME`
- [ ] Implement `hsx_fs_mkdir(path)` wrapping `SVC_FS_MKDIR`
- [ ] Add convenience APIs: `hsx_fs_read_file(path, buffer)`, `hsx_fs_write_file(path, data)`
- [ ] Implement file buffering for small reads/writes
- [ ] Add file metadata API: `hsx_fs_stat(path, stat)`
- [ ] Implement path normalization and validation
- [ ] Add file locking support (optional)

### 5.8 Python Mock GPIO Driver

**Priority:** LOW  
**Dependencies:** None  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Create `python/hal/gpio_hal.py` module structure
- [ ] Implement `GpioDriver` class with virtual pin state
- [ ] Implement `gpio_read(pin)` returning pin state (0/1)
- [ ] Implement `gpio_write(pin, value)` setting pin state
- [ ] Implement `gpio_config(pin, mode)` configuring input/output/pull-up/pull-down
- [ ] Implement `gpio_set_interrupt(pin, edge, callback)` for edge detection
- [ ] Support 32 virtual GPIO pins (0-31)
- [ ] Implement interrupt edge detection (rising, falling, both)
- [ ] Add GPIO state visualization for desktop simulation
- [ ] Implement GPIO port read/write (8 pins at once)
- [ ] Add GPIO debouncing simulation (configurable delay)
- [ ] Implement GPIO interrupt latency simulation

### 5.9 GPIO Syscall and User-Space Library

**Priority:** LOW  
**Dependencies:** 5.8  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Add GPIO module (0x15) to VM syscall dispatcher
- [ ] Implement `SVC_GPIO_READ`, `SVC_GPIO_WRITE`, `SVC_GPIO_CONFIG`, `SVC_GPIO_SET_INTERRUPT`
- [ ] Emit GPIO interrupt events to mailbox `hal:gpio:<pin>`
- [ ] Create `lib/hsx_gpio.c` implementing user-space GPIO API
- [ ] Implement `hsx_gpio_read(pin)`, `hsx_gpio_write(pin, value)`, `hsx_gpio_config(pin, mode)`
- [ ] Implement `hsx_gpio_on_interrupt(pin, callback)` with mailbox management
- [ ] Add convenience APIs: `hsx_gpio_toggle(pin)`, `hsx_gpio_pulse(pin, duration)`
- [ ] Remove `HSX_ERR_ENOSYS` placeholder for GPIO syscalls

### 5.10 Extended Drivers Unit Tests

**Priority:** MEDIUM  
**Dependencies:** 5.1-5.9  
**Estimated Effort:** 5-6 days

**Todo:**
- [ ] Create `python/tests/test_can_hal.py` test module
- [ ] Test CAN TX/RX with loopback mode
- [ ] Test CAN filter matching with various IDs and masks
- [ ] Test CAN error frame generation and handling
- [ ] Create `python/tests/test_fs_hal.py` test module
- [ ] Test file operations (open, read, write, close)
- [ ] Test directory operations (listdir, mkdir, delete, rename)
- [ ] Test filesystem capacity limits and quota enforcement
- [ ] Create `python/tests/test_gpio_hal.py` test module
- [ ] Test GPIO read/write with various pin configurations
- [ ] Test GPIO interrupt edge detection
- [ ] Test GPIO debouncing behavior
- [ ] Add integration tests for CAN chunked transfers
- [ ] Add integration tests for filesystem-based provisioning

---

## Phase 6: HAL Capability Discovery

**Goal:** Implement runtime capability negotiation and detection.

**Dependencies:** 
- Phase 1-5 complete

**Estimated Timeline:** 2 weeks

### 6.1 Capability Structure Definition

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Todo:**
- [ ] Define `hal_caps_t` structure in `include/hsx_hal_types.h`
- [ ] Add bitfield for enabled modules (UART, CAN, Timer, FRAM, FS, GPIO)
- [ ] Add buffer size fields (UART RX, CAN RX, max open files)
- [ ] Add limit fields (max timers, max GPIO pins)
- [ ] Add feature flags (flow control, CAN extended ID, PWM GPIO)
- [ ] Add HAL version information (major, minor, patch)
- [ ] Add platform identification string (e.g., "python-mock", "avr-atmega328")
- [ ] Define capability query functions per module
- [ ] Add capability JSON serialization for tooling

### 6.2 Capability Discovery Syscall

**Priority:** HIGH  
**Dependencies:** 6.1  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Implement `SVC_HAL_GET_CAPS` (0x10, 0x00) syscall handler
- [ ] Populate `hal_caps_t` from active driver capabilities
- [ ] Return capabilities structure in VM memory region
- [ ] Implement per-module capability query: `SVC_<MODULE>_GET_CAPS`
- [ ] Add capability caching in VM state (avoid repeated queries)
- [ ] Implement capability change notification on driver init/shutdown
- [ ] Add debug logging for capability queries

### 6.3 User-Space Capability API

**Priority:** HIGH  
**Dependencies:** 6.1, 6.2  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Implement `hsx_hal_get_caps()` in `lib/hsx_hal.c`
- [ ] Implement per-module capability queries: `hsx_uart_get_caps()`, etc.
- [ ] Add capability check helpers: `hsx_hal_has_module(module_id)`
- [ ] Implement feature detection: `hsx_uart_has_flow_control()`
- [ ] Add graceful degradation APIs for unsupported features
- [ ] Implement capability string formatting for diagnostics
- [ ] Add capability comparison for version compatibility

### 6.4 Capability Discovery Tests

**Priority:** MEDIUM  
**Dependencies:** 6.1, 6.2, 6.3  
**Estimated Effort:** 2-3 days

**Todo:**
- [ ] Test capability query returns correct Python mock driver capabilities
- [ ] Test per-module capability queries match driver state
- [ ] Test capability caching avoids redundant syscalls
- [ ] Test graceful degradation when features are unsupported
- [ ] Test capability version compatibility checks
- [ ] Add capability matrix documentation for all platforms

---

## Phase 7: Standalone VM HAL Shim

**Goal:** Implement lightweight HAL for standalone VM deployments without executive.

**Dependencies:** 
- Phase 1-6 complete

**Estimated Timeline:** 2-3 weeks

### 7.1 Standalone HAL Dispatch Layer

**Priority:** MEDIUM  
**Dependencies:** Phase 1-5  
**Estimated Effort:** 5-6 days

**Todo:**
- [ ] Implement `hal_dispatch(module, function, args)` in VM
- [ ] Route HAL syscalls directly to mock drivers without executive forwarding
- [ ] Add standalone mode detection (no executive connection)
- [ ] Implement fallback to lightweight HAL shim when executive unavailable
- [ ] Add HAL initialization sequence for standalone mode
- [ ] Implement capability fallback (`HAL_STATUS_UNSUPPORTED` → `HSX_ERR_ENOSYS`)
- [ ] Add standalone mode configuration (which modules are enabled)
- [ ] Create standalone VM build profile with minimal HAL subset

### 7.2 Standalone VM Integration Tests

**Priority:** MEDIUM  
**Dependencies:** 7.1  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Create standalone VM test cases without executive
- [ ] Test stdout redirection via UART HAL in standalone mode
- [ ] Test sleep delays via Timer HAL in standalone mode
- [ ] Test value persistence via FRAM HAL in standalone mode
- [ ] Test filesystem operations via FS HAL in standalone mode
- [ ] Add performance comparison: standalone vs. executive-attached
- [ ] Test graceful degradation when HAL module unavailable
- [ ] Verify standalone mode does not require executive dependencies

---

## Phase 8: C Port - Embedded Drivers

**Goal:** Port executive-space HAL drivers to C for embedded targets (AVR, STM32, ARM).

**Dependencies:** 
- Phase 1-7 complete
- Executive Phase 6 (C port)
- VM Phase 2 (C port)

**Estimated Timeline:** 6-8 weeks

### 8.1 C HAL Infrastructure

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 5-6 days

**Todo:**
- [ ] Create `c/exec/hal/` directory structure
- [ ] Define C HAL interface in `c/exec/hal/hal.h`
- [ ] Implement `hal_init()` initialization sequence
- [ ] Implement `hal_caps_t` population from platform drivers
- [ ] Define HAL driver registration API
- [ ] Implement ISR callback registration framework
- [ ] Add platform-specific driver hooks (AVR, STM32, ARM)
- [ ] Create HAL module enable/disable build flags
- [ ] Implement HAL error code translation to HSX errors

### 8.2 C UART Driver (AVR)

**Priority:** HIGH  
**Dependencies:** 8.1  
**Estimated Effort:** 7-8 days

**Todo:**
- [ ] Implement `c/exec/hal/uart_hal.c` for AVR targets
- [ ] Configure UART registers (UBRR, UCSRA, UCSRB, UCSRC) for baud rate, parity
- [ ] Implement `hal_uart_write()` with polling TX
- [ ] Implement `hal_uart_read_poll()` with polling RX
- [ ] Implement ISR-driven UART RX with interrupt handler `USART_RX_vect`
- [ ] Buffer RX data in circular buffer (256 bytes)
- [ ] Emit RX events to mailbox from ISR context (safe mailbox API)
- [ ] Add TX interrupt support for non-blocking writes
- [ ] Implement flow control (RTS/CTS) if hardware supports
- [ ] Add UART error detection (framing, overrun, parity)
- [ ] Create AVR UART platform abstraction for multiple UART ports
- [ ] Add baud rate calculation macros for various F_CPU values

### 8.3 C Timer Driver (AVR)

**Priority:** HIGH  
**Dependencies:** 8.1  
**Estimated Effort:** 6-7 days

**Todo:**
- [ ] Implement `c/exec/hal/timer_hal.c` for AVR targets
- [ ] Configure Timer1 for 16-bit high-resolution counter
- [ ] Implement `hal_timer_get_tick()` reading TCNT1 with overflow counter
- [ ] Implement ISR `TIMER1_OVF_vect` for 64-bit tick extension
- [ ] Implement `hal_timer_create()` registering periodic timers
- [ ] Use Timer2 for periodic timer interrupt generation
- [ ] Emit timer expiry events to mailbox from ISR context
- [ ] Implement timer queue priority ordering (soonest expiry first)
- [ ] Add timer cancellation support
- [ ] Implement sleep integration with power-down mode
- [ ] Add timer accuracy compensation for ISR overhead

### 8.4 C FRAM Driver (AVR)

**Priority:** HIGH  
**Dependencies:** 8.1  
**Estimated Effort:** 6-7 days

**Todo:**
- [ ] Implement `c/exec/hal/fram_hal.c` for AVR targets
- [ ] Integrate I2C/SPI driver for FRAM access (e.g., FM24CL64B)
- [ ] Implement `hal_fram_read()` with I2C read transaction
- [ ] Implement `hal_fram_write()` with I2C write transaction
- [ ] Add wear leveling tracking in FRAM metadata region
- [ ] Implement atomic write with staging buffer
- [ ] Add CRC verification on read for data integrity
- [ ] Implement FRAM capacity detection at init
- [ ] Add write protection zone configuration
- [ ] Optimize I2C timing for FRAM access speed

### 8.5 C HAL Build System Integration

**Priority:** HIGH  
**Dependencies:** 8.1-8.4  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Add C HAL drivers to `c/exec/Makefile`
- [ ] Create HAL profile selection (desktop mock, AVR, STM32, ARM)
- [ ] Add module enable/disable flags (`-DHAL_ENABLE_UART`, etc.)
- [ ] Link C HAL with executive and VM builds
- [ ] Add platform-specific driver selection at build time
- [ ] Implement HAL library versioning
- [ ] Add HAL driver size optimization (strip unused functions)
- [ ] Create HAL build configuration documentation

### 8.6 Hardware-in-Loop Tests

**Priority:** MEDIUM  
**Dependencies:** 8.1-8.5  
**Estimated Effort:** 5-6 days

**Todo:**
- [ ] Create AVR hardware test rig with UART loopback
- [ ] Test UART TX/RX with physical loopback cable
- [ ] Measure UART RX ISR latency (<100µs target)
- [ ] Test UART throughput (115200 baud sustained)
- [ ] Create Timer accuracy test with oscilloscope
- [ ] Measure timer tick accuracy (±10µs over 1 second)
- [ ] Test FRAM read/write with physical FRAM chip
- [ ] Measure FRAM write latency (<5ms target)
- [ ] Test ISR-driven mailbox emission reliability
- [ ] Add stress test: all HAL modules operating concurrently

---

## Phase 9: Executive Integration & Provisioning

**Goal:** Integrate HAL with executive services for provisioning, stdio, and persistence.

**Dependencies:** 
- Phase 1-8 complete
- Provisioning Phases 5-6 (transport bindings, persistence)
- ValCmd Phase 6 (persistence layer)

**Estimated Timeline:** 3-4 weeks

### 9.1 Executive HAL Initialization

**Priority:** HIGH  
**Dependencies:** Phase 1-6  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Add `hal_init()` call to executive startup in `python/execd.py`
- [ ] Initialize all HAL drivers (UART, CAN, Timer, FRAM, FS, GPIO)
- [ ] Register HAL ISR callbacks with executive event system
- [ ] Populate HAL capabilities structure
- [ ] Add HAL module enable/disable configuration
- [ ] Implement HAL health check (verify drivers initialized)
- [ ] Add HAL shutdown sequence for clean termination
- [ ] Create HAL status reporting API for executive

### 9.2 Provisioning Transport Integration

**Priority:** HIGH  
**Dependencies:** 9.1, Provisioning Phase 5  
**Estimated Effort:** 6-7 days

**Todo:**
- [ ] Integrate CAN HAL with Provisioning CAN transport binding
- [ ] Implement CAN broadcast protocol for HXE image loading
- [ ] Integrate UART HAL with Provisioning UART streaming transport
- [ ] Implement UART chunked transfer protocol
- [ ] Integrate FS HAL with Provisioning filesystem loader
- [ ] Implement SD card manifest parsing via FS HAL
- [ ] Add transport-layer error handling and retry logic
- [ ] Implement provisioning progress reporting via HAL events
- [ ] Test end-to-end provisioning workflows (CAN, UART, SD)

### 9.3 ValCmd Persistence Integration

**Priority:** HIGH  
**Dependencies:** 9.1, ValCmd Phase 6  
**Estimated Effort:** 5-6 days

**Todo:**
- [ ] Integrate FRAM HAL with ValCmd persistence layer
- [ ] Implement value serialization to FRAM storage
- [ ] Add value restoration on boot from FRAM
- [ ] Implement FRAM partition table for value namespaces
- [ ] Add garbage collection for deleted values
- [ ] Implement FRAM compaction to reclaim space
- [ ] Add backup/restore APIs for value persistence
- [ ] Test value persistence across system restarts

### 9.4 Executive Stdio Redirection

**Priority:** MEDIUM  
**Dependencies:** 9.1  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Redirect executive stdout/stderr to UART HAL
- [ ] Implement console I/O via UART port 0
- [ ] Add line buffering for console output
- [ ] Implement console input via UART RX mailbox
- [ ] Add console command processing (optional)
- [ ] Implement log level filtering for UART output
- [ ] Add timestamp prefixes to console output
- [ ] Test console I/O performance and reliability

### 9.5 Executive Integration Tests

**Priority:** HIGH  
**Dependencies:** 9.1-9.4  
**Estimated Effort:** 5-6 days

**Todo:**
- [ ] Test provisioning workflow via CAN broadcast
- [ ] Test provisioning workflow via UART streaming
- [ ] Test provisioning workflow via SD filesystem
- [ ] Test value persistence via FRAM across restarts
- [ ] Test executive console I/O via UART
- [ ] Test HAL event delivery to executive mailbox system
- [ ] Test concurrent HAL operations from multiple VMs
- [ ] Add stress test: sustained provisioning + value updates + console I/O

---

## Phase 10: Advanced Features & Polish

**Goal:** Implement advanced HAL features and optimizations.

**Dependencies:** 
- Phase 1-9 complete

**Estimated Timeline:** 3-4 weeks

### 10.1 UART Flow Control

**Priority:** LOW  
**Dependencies:** Phase 1, Phase 8  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Implement RTS/CTS hardware handshaking in Python mock driver
- [ ] Implement RTS/CTS in C UART driver for AVR
- [ ] Add flow control configuration API: `uart_config(port, {flow_control: true})`
- [ ] Implement automatic RTS assertion on RX buffer threshold
- [ ] Add CTS monitoring for TX flow control
- [ ] Test high-throughput scenarios with flow control enabled
- [ ] Measure throughput improvement vs. no flow control

### 10.2 Advanced CAN Features

**Priority:** LOW  
**Dependencies:** Phase 5  
**Estimated Effort:** 5-6 days

**Todo:**
- [ ] Implement CAN bus error counters (TX, RX)
- [ ] Implement bus-off recovery with automatic restart
- [ ] Add advanced filter chaining (multiple filter rules)
- [ ] Implement CAN TX priority queuing (higher ID wins)
- [ ] Add CAN timestamp synchronization for distributed logging
- [ ] Implement CAN error passive/active state machine
- [ ] Add CAN diagnostic API: `can_get_diagnostics(stats)`

### 10.3 FRAM Wear Leveling

**Priority:** LOW  
**Dependencies:** Phase 3, Phase 8  
**Estimated Effort:** 5-6 days

**Todo:**
- [ ] Implement advanced wear leveling with block rotation
- [ ] Add dynamic bad block remapping
- [ ] Implement wear histogram tracking
- [ ] Add wear prediction and early warning
- [ ] Implement FRAM compaction scheduler
- [ ] Add FRAM health monitoring API
- [ ] Test wear leveling distribution over 100k writes

### 10.4 GPIO PWM Output

**Priority:** LOW  
**Dependencies:** Phase 5  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Implement PWM output mode for GPIO pins
- [ ] Add PWM configuration: frequency, duty cycle
- [ ] Implement hardware PWM using AVR Timer0/Timer2
- [ ] Add software PWM fallback for pins without hardware support
- [ ] Implement PWM phase control for multi-channel sync
- [ ] Add PWM API: `hsx_gpio_pwm_set(pin, frequency, duty_cycle)`

### 10.5 Multi-Threaded HAL

**Priority:** LOW  
**Dependencies:** Phase 1-8, Executive Phase 7 (multi-threading)  
**Estimated Effort:** 6-7 days

**Todo:**
- [ ] Add driver mutexes for concurrent HAL access
- [ ] Implement thread-safe UART TX/RX operations
- [ ] Add thread-safe CAN TX/RX operations
- [ ] Implement thread-safe FRAM read/write operations
- [ ] Add thread-safe FS operations
- [ ] Implement thread-safe timer management
- [ ] Test concurrent HAL access from multiple VM instances
- [ ] Measure performance overhead of locking

---

## Phase 11: Documentation & Testing

**Goal:** Create comprehensive documentation and test suite for HAL module.

**Dependencies:** 
- Phase 1-10 complete

**Estimated Timeline:** 2-3 weeks

### 11.1 HAL Porting Guide

**Priority:** HIGH  
**Dependencies:** Phase 8  
**Estimated Effort:** 4-5 days

**Todo:**
- [ ] Write HAL porting guide for adding new MCU platforms
- [ ] Document driver interface contract for each module
- [ ] Create platform driver template files
- [ ] Add platform-specific driver examples (AVR, STM32, ARM)
- [ ] Document ISR callback registration requirements
- [ ] Add build system integration guide
- [ ] Create HAL capability matrix (which features per platform)
- [ ] Add porting checklist and verification steps

### 11.2 User-Space Library Guide

**Priority:** HIGH  
**Dependencies:** Phase 4  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Write user-space library usage guide
- [ ] Create example applications for each HAL module
- [ ] Document callback registration and event handling patterns
- [ ] Add error handling best practices
- [ ] Document library linking and build configuration
- [ ] Create API reference documentation
- [ ] Add performance considerations and optimization tips

### 11.3 Executive Integration Guide

**Priority:** MEDIUM  
**Dependencies:** Phase 9  
**Estimated Effort:** 3-4 days

**Todo:**
- [ ] Write executive integration guide for HAL driver invocation
- [ ] Document HAL initialization sequence
- [ ] Add event emission integration patterns
- [ ] Document provisioning transport integration
- [ ] Add persistence layer integration guide
- [ ] Create HAL health check and monitoring guide

### 11.4 Mock Driver Guide

**Priority:** MEDIUM  
**Dependencies:** Phase 1-5  
**Estimated Effort:** 2-3 days

**Todo:**
- [ ] Document Python mock driver behavior and limitations
- [ ] Add mock driver configuration guide
- [ ] Document desktop simulation capabilities
- [ ] Create mock driver testing guide
- [ ] Add mock driver performance characteristics

### 11.5 Comprehensive Test Suite

**Priority:** HIGH  
**Dependencies:** Phase 1-10  
**Estimated Effort:** 6-7 days

**Todo:**
- [ ] Create comprehensive unit test suite (all modules)
- [ ] Add integration tests (cross-module interactions)
- [ ] Create stress tests (high-load scenarios)
- [ ] Add hardware-in-loop tests (real hardware validation)
- [ ] Implement continuous integration for HAL tests
- [ ] Add performance regression tests
- [ ] Create test coverage reporting
- [ ] Document test execution and interpretation

---

## Definition of Done (DoD)

### Phase 1-3 (Executive-Space Foundation) Complete When:
- [ ] Python mock drivers implemented for UART, Timer, FRAM
- [ ] All syscalls dispatch correctly to HAL drivers
- [ ] Mailbox event emission works for UART RX, Timer expiry
- [ ] Unit tests pass for all three drivers
- [ ] VM no longer returns `ENOSYS` for modules 0x10, 0x12, 0x13
- [ ] Integration tests verify event delivery latency <10ms

### Phase 4 (User-Space Library) Complete When:
- [ ] User-space libraries implemented for UART, Timer, FRAM
- [ ] `libhsx_hal.a` builds and links successfully
- [ ] Example apps demonstrate library usage
- [ ] Callback mechanisms work for async events
- [ ] Integration tests verify end-to-end functionality
- [ ] Library API documentation complete

### Phase 5 (Extended Drivers) Complete When:
- [ ] Python mock drivers implemented for CAN, FS, GPIO
- [ ] All syscalls dispatch for modules 0x11, 0x14, 0x15
- [ ] User-space libraries complete for all three modules
- [ ] Mailbox emission works for CAN RX, GPIO interrupts
- [ ] Unit tests pass for all extended drivers
- [ ] Integration tests verify chunked transfers and file operations

### Phase 6-7 (Capability & Standalone) Complete When:
- [ ] `HAL_GET_CAPS` syscall returns correct capabilities
- [ ] Per-module capability queries implemented
- [ ] Standalone VM HAL shim works without executive
- [ ] Graceful degradation for unsupported features
- [ ] Standalone VM tests pass (stdout, sleep, persistence)
- [ ] Capability documentation complete

### Phase 8 (C Port) Complete When:
- [ ] C HAL drivers implemented for UART, Timer, FRAM on AVR
- [ ] ISR-driven RX handling works reliably
- [ ] Build system supports multiple platforms (AVR, STM32, ARM)
- [ ] Hardware-in-loop tests pass on real AVR hardware
- [ ] Performance metrics meet targets (ISR latency <100µs, UART throughput 115200 baud)
- [ ] C port documentation complete

### Phase 9 (Executive Integration) Complete When:
- [ ] HAL integrated with provisioning transport layer
- [ ] HAL integrated with ValCmd persistence layer
- [ ] Executive stdio redirects to UART HAL
- [ ] End-to-end provisioning workflows work (CAN, UART, SD)
- [ ] Value persistence works across system restarts
- [ ] Integration stress tests pass

### Phase 10-11 (Advanced Features & Documentation) Complete When:
- [ ] Advanced features implemented (flow control, CAN error handling, wear leveling, PWM)
- [ ] Multi-threaded HAL works with concurrent access
- [ ] HAL porting guide complete
- [ ] User-space library guide complete
- [ ] Executive integration guide complete
- [ ] Comprehensive test suite passes (unit, integration, stress, HIL)
- [ ] Test coverage >90% for all HAL modules

### Overall Module Complete When:
- [ ] All 11 phases completed
- [ ] Both Python mock and C embedded drivers implemented for all 6 modules
- [ ] User-space libraries complete and documented
- [ ] Executive integration complete (provisioning, persistence, stdio)
- [ ] Standalone VM mode fully functional
- [ ] All tests passing (2000+ test cases)
- [ ] All documentation complete (porting guide, library guide, integration guide)
- [ ] Hardware-in-loop validation complete on target hardware
- [ ] Performance metrics meet design specifications
- [ ] Zero ENOSYS returns for HAL syscalls in normal operation

---

**Last Updated:** 2025-11-01  
**Total Estimated Effort:** 20-24 weeks (5-6 months)  
**Critical Path:** Phase 1 → Phase 4 → Phase 5 → Phase 8 → Phase 9

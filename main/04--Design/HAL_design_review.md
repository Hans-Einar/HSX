# HAL Design Review - Interface Approaches

**Status:** BRAINSTORM | **Date:** 2025-10-31 | **Owner:** HSX Core

> **Purpose:** This document serves as a notebook to brainstorm and analyze different approaches for the HAL (Hardware Abstraction Layer) interface in the HSX system. We explore syscall-based and mailbox-based approaches with their pros and cons.

## Context

Based on [04.08--HAL.md](04.08--HAL.md), the HAL is designed as a portability abstraction layer that:
- Provides thin wrappers around platform-specific drivers (UART, CAN, timers, GPIO, FRAM, FS)
- Supports two deployment modes: executive-attached and standalone VM
- Currently interfaces through syscalls (SVC instructions)

The key question: **Should the HAL interface with the Executive/VM through syscalls (SVC) or mailboxes?**

## Current State Analysis

### Existing Syscall Infrastructure

From [docs/abi_syscalls.md](../../docs/abi_syscalls.md), we currently have:

**Module 0x01 - Task control and stdio**
- `TASK_EXIT` (fn 0x00) - Exit task
- `UART_WRITE` (fn 0x01) - Write to UART

**Module 0x02 - CAN transport**
- `CAN_TX` (fn 0x00) - Transmit CAN frame

**Module 0x04 - Virtual filesystem**
- `FS_OPEN`, `FS_READ`, `FS_WRITE`, `FS_CLOSE`, `FS_LISTDIR`, `FS_DELETE`, `FS_RENAME`, `FS_MKDIR`

**Module 0x05 - Mailbox subsystem**
- `MAILBOX_OPEN`, `MAILBOX_BIND`, `MAILBOX_SEND`, `MAILBOX_RECV`, `MAILBOX_PEEK`, `MAILBOX_TAP`, `MAILBOX_CLOSE`

### Existing Mailbox Infrastructure

From [04.03--Mailbox.md](04.03--Mailbox.md), mailboxes provide:
- Deterministic task-to-task and host-to-task IPC
- Blocking/non-blocking semantics with timeout support
- Multiple delivery modes (single-reader, fan-out, taps)
- Integration with executive scheduler for wait/wake transitions
- Namespace support (`svc:`, `pid:`, `app:`, `shared:`)

## Option 1: Syscall-Based HAL Interface

### Description
HAL modules are accessed through dedicated SVC instructions. Each HAL module (UART, CAN, GPIO, TIMER, FRAM, etc.) has its own module ID (0x10-0x16 as defined in 04.08--HAL.md) with functions mapped to specific operations.

### Implementation Model

```text
Application Code
    ↓ SVC 0x10, fn (UART operation)
    ↓
MiniVM SVC Trap
    ↓
Executive SVC Dispatcher
    ↓
HAL Module (UART)
    ↓
Platform Driver
```

### Pros

1. **Direct and Efficient**
   - Minimal overhead: single instruction trap to handler
   - Deterministic execution path
   - Low latency for time-critical operations (GPIO, timers)
   - Synchronous execution model is easy to reason about

2. **Consistency with Existing Design**
   - Filesystem operations already use syscalls (module 0x04)
   - GPIO and CAN already have syscalls defined
   - Fits naturally with the MiniVM SVC architecture
   - Executive already has SVC dispatcher infrastructure

3. **Clear Separation of Concerns**
   - HAL is clearly a "system service" layer
   - Natural privilege boundary (user space → kernel space)
   - Executive maintains control over all hardware access
   - Easy to enforce security policies at syscall boundary

4. **Resource Management**
   - Executive can track HAL resource usage per task
   - Can enforce quotas and rate limits
   - Easy to implement capabilities-based access control
   - Clear ownership model for hardware resources

5. **Standalone VM Support**
   - Standalone VM can implement minimal HAL syscall shim directly
   - No need for mailbox infrastructure in minimal deployments
   - Simpler for single-task embedded scenarios
   - Smaller code footprint for constrained targets

6. **Debugging and Traceability**
   - Syscall traps are easily traceable in debugger
   - Clear entry/exit points for instrumentation
   - Existing trace infrastructure captures SVC events
   - Stack traces show syscall boundaries clearly

### Cons

1. **Blocking Semantics**
   - Syscalls are typically synchronous/blocking
   - Task blocks until HAL operation completes
   - May need complex timeout handling in HAL layer
   - Can't easily "subscribe" to events (e.g., GPIO edge, CAN frame arrival)

2. **No Native Pub/Sub Model**
   - Difficult to implement "wait for multiple HAL events"
   - Application must poll or use complex state machines
   - Can't easily fan-out hardware events to multiple tasks
   - Requires additional infrastructure for event notification

3. **Executive Complexity**
   - Executive must handle all HAL syscalls
   - Large switch/dispatch table for all HAL operations
   - Executive becomes a bottleneck for HAL operations
   - More code in executive (potential bloat on MCU)

4. **Limited Composability**
   - Hard to chain or combine HAL operations
   - Can't easily build higher-level abstractions
   - Each operation requires a separate syscall
   - Difficult to implement async patterns

5. **Interrupt Handling Complexity**
   - Async hardware events (GPIO interrupt, CAN RX) need special handling
   - Either poll (inefficient) or implement callback mechanism
   - Callback mechanism requires mailbox-like infrastructure anyway
   - Wake-on-interrupt requires executive scheduler integration

## Option 2: Mailbox-Based HAL Interface

### Description
HAL modules present themselves as mailbox endpoints. Applications interact with hardware by sending/receiving messages through mailboxes bound to HAL services.

### Implementation Model

```text
Application Code
    ↓ MAILBOX_SEND to "hal:uart"
    ↓
Mailbox Subsystem
    ↓
HAL Module (UART) - mailbox handler
    ↓
Platform Driver
```

### Pros

1. **Unified Communication Model**
   - Same pattern for IPC and HAL access
   - Follows the stdio model (stdout/stderr via mailboxes)
   - Consistent API surface for applications
   - Developers learn one communication paradigm

2. **Native Async/Event Support**
   - Mailboxes naturally support blocking with timeout
   - Task can wait on multiple mailboxes (HAL events + IPC)
   - Executive scheduler already handles mailbox wait/wake
   - Fan-out mode allows multiple tasks to receive hardware events

3. **Elegant Event Model**
   - GPIO edge triggers → message to subscribed mailbox
   - CAN frame arrival → message to `hal:can:rx` mailbox
   - Timer expiry → message to task mailbox
   - Application can be dormant until event arrives
   - Natural pub/sub pattern for hardware events

4. **Composability**
   - Can build higher-level HAL abstractions easily
   - Middleware can intercept/transform HAL messages
   - Easy to implement filtering and routing
   - Can layer protocols on top of HAL mailboxes

5. **Flexibility**
   - Non-blocking operations via `MAILBOX_RECV` with `timeout=POLL`
   - Blocking with timeout naturally supported
   - Can peek at pending HAL events without consuming
   - Tap mode allows debugging/monitoring of HAL traffic

6. **Namespace Integration**
   - HAL services fit naturally into `shared:hal:*` namespace
   - Per-task HAL mailboxes in `pid:<n>:hal:*` namespace
   - Consistent with overall mailbox naming scheme
   - Easy to discover and enumerate HAL services

7. **Executive Simplification**
   - Executive doesn't need special HAL syscall handlers
   - HAL modules register as mailbox endpoints
   - Mailbox subsystem handles routing and buffering
   - Executive's role is purely message passing

8. **Instrumentation**
   - Mailbox events already emit trace data
   - HAL traffic visible in debugger's mailbox view
   - Can tap HAL mailboxes for monitoring
   - Easier to debug complex async flows

### Cons

1. **Performance Overhead**
   - Mailbox send/recv has more overhead than direct syscall
   - Message copying required (payload into mailbox ring buffer)
   - Multiple memory copies for each HAL operation
   - May be too slow for high-frequency operations (e.g., bit-banging GPIO)

2. **Complexity for Simple Operations**
   - Simple operations (read GPIO pin) become message exchanges
   - Need to format message, send, wait for reply
   - More code in application for basic HAL use
   - Overkill for synchronous request/response patterns

3. **Memory Usage**
   - Each HAL service needs mailbox descriptor
   - Ring buffers for each HAL endpoint consume RAM
   - Pending messages consume buffer space
   - May exhaust mailbox descriptors on constrained MCU

4. **Synchronization Challenges**
   - HAL operations that must be atomic are harder to implement
   - Request/response pattern requires correlation (sequence numbers)
   - Error handling more complex (reply message with error code)
   - Harder to enforce "exclusive access" to hardware

5. **Bootstrap Problem**
   - How do mailboxes themselves work if HAL is via mailboxes?
   - Circular dependency if console output requires mailbox which requires HAL
   - May need hybrid approach: critical HAL via syscalls, rest via mailboxes
   - Complicates standalone VM scenario

6. **Standalone VM Challenges**
   - Standalone VM needs full mailbox infrastructure
   - Can't have minimal HAL-only deployment
   - Larger code footprint for simple use cases
   - More RAM required for mailbox state

7. **Unclear Ownership Model**
   - Which task "owns" a HAL resource?
   - How to handle exclusive access (e.g., I2C bus)?
   - How to prevent resource starvation?
   - May need additional access control layer

## Hybrid Approach: Syscalls for Operations, Mailboxes for Events

### Description
Combine the best of both worlds:
- **Syscalls for synchronous HAL operations** (write UART, read GPIO, configure timers)
- **Mailboxes for async events and notifications** (GPIO interrupt, CAN RX, timer expiry)

### Implementation Model

```text
Synchronous path:
Application → SVC 0x10, fn → Executive → HAL → Driver

Async path:
Driver interrupt → HAL → Mailbox message → Task wakes from WAIT_MBX
```

### Pros

1. **Best of Both Worlds**
   - Low overhead for synchronous operations
   - Elegant async event model
   - Tasks can wait on both HAL events and IPC
   - Efficient for common cases, powerful for complex cases

2. **Natural Fit for Hardware Model**
   - Synchronous: "set GPIO high", "write UART byte", "read ADC"
   - Async: "wake me when GPIO edge", "notify on CAN frame", "timer callback"
   - Maps well to hardware interrupt model
   - Intuitive for developers with embedded background

3. **Incremental Migration**
   - Can start with syscalls (current design)
   - Add mailbox events as needed
   - Applications choose which model to use
   - Backward compatible

4. **Resource Efficiency**
   - Syscalls for fast path (no mailbox overhead)
   - Mailboxes only for events (low frequency)
   - Can tune memory usage based on event needs
   - Minimal impact on constrained targets

5. **Clear Semantics**
   - Syscall = "do this now" (imperative)
   - Mailbox = "notify me when" (reactive)
   - Easy to teach and understand
   - Matches mental model of hardware interaction

### Cons

1. **Dual Interface Complexity**
   - Applications must understand two patterns
   - More documentation and examples needed
   - May be confusing which approach to use
   - Two code paths to maintain and debug

2. **Implementation Complexity**
   - HAL modules must support both interfaces
   - Executive must handle both syscalls and mailbox routing
   - More complex to test all combinations
   - Potential for subtle bugs at boundary

3. **Inconsistency**
   - Some HAL operations via syscalls, some via mailboxes
   - Where to draw the line?
   - May lead to arguments about "right" approach
   - Harder to maintain consistency across HAL modules

## Considerations for Specific HAL Modules

### UART (Module 0x10)
- **Write:** Syscall (synchronous, low overhead)
- **Read:** Could be either:
  - Syscall with blocking/polling (simple, like `read()`)
  - Mailbox for RX (allows wait-on-data, fits stdio model)
- **Recommendation:** Hybrid - syscall for TX, optional mailbox for RX

### CAN (Module 0x11)
- **Transmit:** Syscall (send and done)
- **Receive:** Mailbox (frames arrive asynchronously)
- **Filters:** Syscall to configure
- **Recommendation:** Hybrid - syscall for TX and config, mailbox for RX

### GPIO (Module 0x15)
- **Read/Write:** Syscall (fast, synchronous)
- **Interrupts:** Mailbox (edge detection, change notification)
- **Recommendation:** Hybrid - syscall for I/O, mailbox for interrupts

### Timer (Module 0x12)
- **Sleep:** Syscall (existing `EXEC_SLEEP_MS`)
- **Read tick:** Syscall (fast)
- **Periodic callback:** Mailbox (timer expiry → message)
- **Recommendation:** Hybrid - syscall for sleep/tick, mailbox for callbacks

### FRAM/Storage (Module 0x13)
- **Read/Write:** Syscall (synchronous operations)
- **Recommendation:** Syscall only (no async events)

### Filesystem (Module 0x14)
- **Current:** All syscalls (open, read, write, close)
- **Could use mailboxes for:** Async file I/O, file change notifications
- **Recommendation:** Keep syscalls for now (matches POSIX model)

## Application Perspective

### Should HSX Apps Know About CAN?

**Arguments For (Apps should know about CAN):**
1. CAN is often application-level protocol (CANopen, J1939)
2. Applications may need to construct specific CAN frames
3. Direct access allows custom protocols and diagnostics
4. Embedded developers expect to work with CAN directly

**Arguments Against (Abstract CAN away):**
1. CAN is a transport layer, apps shouldn't care
2. Higher-level protocols (value/command service) should use CAN internally
3. Makes applications less portable
4. Security: apps shouldn't have raw CAN access

**Recommendation:** 
- Provide both layers:
  - **Low-level CAN syscall** for specialized applications (diagnostics, bootloader)
  - **High-level value/command service** for typical applications (uses CAN internally)
- Most HSX apps use value/command, but CAN is available if needed
- Use capability flags to restrict CAN access in production builds

## Dormant Tasks and Event-Driven Model

One compelling feature of mailboxes is the ability to have tasks remain dormant until a hardware event occurs:

```c
// Task waits for GPIO edge on pin 5
int gpio_events = mailbox_open("hal:gpio:5", MBX_MODE_RDONLY);
while (1) {
    // Task is WAIT_MBX state, consuming no CPU
    mailbox_recv(gpio_events, &msg, sizeof(msg), MBX_TIMEOUT_INFINITE);
    
    // Woken by GPIO interrupt
    if (msg.data[0] == GPIO_EDGE_RISING) {
        handle_button_press();
    }
}
```

This is much more elegant than:
```c
// Polling approach (wastes CPU)
while (1) {
    if (gpio_read(5) == HIGH) {
        handle_button_press();
        while (gpio_read(5) == HIGH) {} // wait for release
    }
    sleep_ms(10); // Still wastes 100 Hz wake-ups
}
```

**Conclusion:** The mailbox approach enables truly event-driven applications that can remain dormant until hardware events occur, which is essential for low-power embedded systems.

## Recommendations

### Short Term (Current Development)
1. **Keep syscall-based HAL interface** for synchronous operations
   - Continue with modules 0x10-0x16 as defined in 04.08--HAL.md
   - Implement UART write, CAN TX, GPIO read/write, timer tick as syscalls
   - Maintain simplicity for standalone VM scenario

2. **Add mailbox-based event channels** for async hardware events
   - Define namespace convention: `hal:uart:rx`, `hal:can:rx`, `hal:gpio:<pin>`
   - HAL modules post events to these mailboxes when interrupts occur
   - Applications can subscribe using existing mailbox API

3. **Use mailbox model for stdio** (already planned)
   - `svc:stdout`, `svc:stderr` remain mailbox-based
   - Aligns with shell interaction model
   - Provides natural buffering and fan-out

### Medium Term (After Basic HAL Working)
1. **Document patterns** for common use cases
   - Synchronous HAL operations (syscalls)
   - Event-driven HAL (mailboxes)
   - Hybrid patterns (command via syscall, response via mailbox)

2. **Implement capability discovery**
   - `HAL_GET_CAPS` syscall returns available modules and features
   - Applications query capabilities at runtime
   - Graceful degradation when features unavailable

3. **Add optional high-level abstractions**
   - Build async I/O library on top of basic HAL
   - Provide event loop / reactor pattern for complex apps
   - Keep it optional (apps can use low-level HAL directly)

### Long Term (Production Hardening)
1. **Security and access control**
   - Capability-based access to HAL modules
   - Per-task permissions for CAN, GPIO, etc.
   - Audit logging of HAL operations

2. **Performance optimization**
   - Zero-copy paths for high-bandwidth operations
   - DMA integration for UART/SPI
   - Batch operations to reduce syscall overhead

3. **Standardization**
   - Define canonical HAL message formats
   - Document ABI stability guarantees
   - Version negotiation for HAL API

## MCU Implementation Notes

### Linked HAL Modules
On MCU targets (AVR, ARM), the HAL should be compiled and linked into the Executive binary:

```text
Executive binary structure:
├── Core Executive (scheduler, syscall dispatcher, mailbox manager)
├── HAL Interface Layer (syscall handlers, mailbox endpoints)
├── HAL Modules (UART, CAN, GPIO, Timer, FRAM)
│   ├── Platform-specific drivers (AVR UART, STM32 CAN, etc.)
│   └── Common HAL logic
└── MiniVM (instruction decoder, register file, memory)
```

**Benefits:**
- Single flash image for deployment
- No dynamic linking overhead
- Compile-time optimization across boundaries
- Deterministic memory layout

**Build System:**
- Use Makefiles or CMake to select HAL modules based on target
- Conditional compilation for optional modules (e.g., CAN only if hardware present)
- Link-time optimization (LTO) to eliminate unused code

### Python Implementation
Python reference implementation uses Python modules:

```text
platforms/python/
├── host_vm.py (MiniVM + Executive)
├── mailbox.py (Mailbox manager)
├── hal/
│   ├── __init__.py
│   ├── uart_hal.py (Mock UART using sockets or files)
│   ├── can_hal.py (Mock CAN using virtual bus)
│   ├── gpio_hal.py (Mock GPIO using simulated pins)
│   └── timer_hal.py (Uses time.monotonic())
```

**Benefits:**
- Easy to develop and test HAL logic
- Can mock hardware for CI/CD
- Interactive REPL for experimentation
- Cross-platform (Linux, macOS, Windows)

**Approach:**
- HAL modules register handlers with Executive
- Executive dispatches syscalls to HAL Python methods
- HAL can post mailbox messages for events (using Python threading)

## Open Questions

1. **How to handle HAL initialization?**
   - Should applications call `HAL_INIT` syscall?
   - Or should Executive initialize HAL modules at boot?
   - What about per-task HAL state (e.g., open UART handles)?

2. **What's the memory model for HAL buffers?**
   - Do HAL modules allocate from shared pool or have dedicated buffers?
   - How to handle DMA buffers (need physical address)?
   - What about cache coherency on ARM?

3. **How to handle HAL errors?**
   - Return codes in R0 (current model)?
   - Errno-style per-task error variable?
   - Error messages via mailbox?
   - All of the above?

4. **Should HAL modules be hot-pluggable?**
   - Can Executive load/unload HAL modules at runtime?
   - Or are they statically linked?
   - Implications for flash/RAM usage?

5. **How to handle multiple instances?**
   - What if hardware has 3 UARTs?
   - Module ID per instance (0x10, 0x11, 0x12)?
   - Or single module with instance parameter?
   - Mailbox namespace: `hal:uart0`, `hal:uart1`, etc.?

6. **What about DMA and hardware buffering?**
   - Should HAL expose DMA directly to apps?
   - Or hide behind syscall/mailbox interface?
   - How to handle scatter-gather DMA?

7. **Power management integration?**
   - How to put hardware to sleep when idle?
   - HAL should track usage and idle times?
   - Integration with task scheduler sleep states?

## Summary

Both syscall and mailbox approaches have merit. The **hybrid approach** offers the best balance:

- ✅ **Syscalls for synchronous operations** - efficient, simple, fits existing design
- ✅ **Mailboxes for async events** - elegant, powerful, enables event-driven apps
- ✅ **Consistent with existing infrastructure** - filesystem is syscalls, stdio is mailboxes
- ✅ **Flexible for different use cases** - simple apps use syscalls, complex apps use events
- ✅ **Implementable in stages** - start with syscalls, add mailbox events later

**Next Steps:**
1. Continue implementing HAL syscalls as defined in 04.08--HAL.md
2. Design mailbox event message formats for HAL notifications
3. Prototype GPIO interrupt → mailbox flow
4. Document application patterns in HAL usage guide
5. Implement Python HAL modules for testing

---

**References:**
- [04.08--HAL.md](04.08--HAL.md) - HAL Design Specification
- [04.03--Mailbox.md](04.03--Mailbox.md) - Mailbox Subsystem Design
- [04.02--Executive.md](04.02--Executive.md) - Executive Design
- [docs/abi_syscalls.md](../../docs/abi_syscalls.md) - Syscall ABI Documentation

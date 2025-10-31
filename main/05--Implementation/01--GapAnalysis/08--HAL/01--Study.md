# Gap Analysis Study: HAL (Hardware Abstraction Layer)

**Design Document:** [04.08--HAL](../../../04--Design/04.08--HAL.md) (267 lines)  
**Study Date:** 2025-10-31  
**Status:** Initial Analysis

## 1. Scope Recap

The HAL design specifies a portability abstraction layer for hardware peripherals required by MiniVM and executive. Covers UART (0x10), CAN (0x11), Timer (0x12), FRAM (0x13), FS (0x14), and GPIO (0x15) modules with two-layer architecture:
- **Executive-space HAL**: Syscall handlers and interrupt-driven event emission to mailboxes
- **User-space HAL**: Application libraries (`libhsx_hal.a`) wrapping syscalls and mailboxes with convenient APIs

Supports two deployment modes: executive-attached (SVC forwarded to executive) and standalone VM (lightweight HAL shim). Design emphasizes thin wrappers with no autonomous scheduling or business logic—all policy lives in executive/application layers.

**Traceability:** DR-1.1, DR-1.3, DR-5.1, DR-5.3, DR-6.1, DR-7.1, DG-1.4, DG-5.1, DG-5.2, DG-5.3, DG-6.1, DG-6.2, DG-6.3, DG-7.3

---

## 2. Current Implementation

**What exists today?**

**User-space HAL headers (796 total lines):**
- `include/hsx_uart.h` (140 lines) - UART API definitions, config structures
- `include/hsx_can.h` (106 lines) - CAN frame structures, filter config
- `include/hsx_timer.h` (97 lines) - Timer tick, sleep, periodic timer APIs
- `include/hsx_gpio.h` (110 lines) - GPIO read/write, interrupt config
- `include/hsx_fs.h` (107 lines) - Filesystem open/read/write/close APIs
- `include/hsx_fram.h` (69 lines) - Persistent storage read/write, wear APIs
- `include/hsx_mailbox.h` (128 lines) - Mailbox API (separate subsystem)
- `include/hsx_hal_types.h` (39 lines) - Common HAL type definitions

**Executive-space HAL:**
- **NONE** - No implementation files in `python/`, `platforms/`, or C source directories
- VM returns `HSX_ERR_ENOSYS` for all HAL syscalls (modules 0x10-0x15) at `platforms/python/host_vm.py:1165`

**Tests:**
- **NONE** - No HAL-specific tests found in `python/tests/`

**Tools/scripts:**
- **NONE** - No HAL-specific tooling

**Documentation:**
- Design spec: `main/04--Design/04.08--HAL.md` (267 lines)
- User-space library spec referenced: `main/05--Implementation/HAL/hsx_app_library.md` (file exists per design)
- Architecture: `main/03--Architecture/03.08--HAL.md`

**Summary:** Only API headers exist (796 lines defining user-space interfaces). Entire HAL implementation—both executive-space drivers and user-space library wrappers—is missing. VM returns `ENOSYS` for all HAL syscalls.

---

## 3. Missing or Partial Coverage

**Open Items** (features designed but not yet implemented):

**Executive-Space HAL Modules (All Missing):**
1. **UART module (0x10)** - No syscall handlers (`UART_WRITE`, `UART_READ_POLL`, `UART_CONFIG`, `UART_GET_STATUS`), no RX mailbox emission (`hal:uart:0:rx`)
2. **CAN module (0x11)** - No syscall handlers (`CAN_TX`, `CAN_CONFIG`, `CAN_SET_FILTER`, `CAN_GET_STATUS`), no RX mailbox emission (`hal:can:rx`)
3. **Timer module (0x12)** - No syscall handlers (`TIMER_GET_TICK`, `TIMER_GET_TICK_FREQ`, `TIMER_CREATE`, `TIMER_CANCEL`), no periodic timer mailbox emission
4. **FRAM module (0x13)** - No syscall handlers (`FRAM_READ`, `FRAM_WRITE`, `FRAM_GET_SIZE`, `FRAM_GET_WEAR`), no wear leveling logic
5. **FS module (0x14)** - No syscall handlers (`FS_OPEN`, `FS_READ`, `FS_WRITE`, `FS_CLOSE`, `FS_LISTDIR`, `FS_DELETE`, `FS_RENAME`, `FS_MKDIR`)
6. **GPIO module (0x15)** - No syscall handlers (`GPIO_READ`, `GPIO_WRITE`, `GPIO_CONFIG`, `GPIO_SET_INTERRUPT`), no interrupt mailbox emission
7. **Capability discovery** - No `HAL_GET_CAPS` syscall, no `hal_caps_t` runtime detection
8. **HAL initialization** - No `hal_init()` sequence, no driver registration, no ISR callback setup
9. **Python mock drivers** - No desktop simulation drivers (socket for CAN, loopback UART, memory-backed FRAM)

**User-Space HAL Libraries (All Missing):**
10. **libhsx_hal.a implementation** - No C source files wrapping syscalls (`hsx_uart.c`, `hsx_can.c`, `hsx_timer.c`, `hsx_gpio.c`, `hsx_fs.c`, `hsx_fram.c`)
11. **Mailbox event handling** - No user-space mailbox open/management for async events (UART RX, CAN RX, GPIO interrupts, timer expiry)
12. **Callback mechanisms** - No event-driven callback registration APIs
13. **Helper functions** - No convenience wrappers like `hsx_uart_printf()`, `hsx_can_send_chunked()`
14. **Error handling** - No status code translation, retry logic helpers

**Integration & Testing:**
15. **VM HAL dispatch** - No `hal_dispatch(module, function, args)` bridging layer for standalone mode
16. **Executive HAL integration** - No HAL invocation from executive commands (provisioning, stdio, persistence)
17. **Unit tests** - No per-module tests with mock drivers (loopback UART, simulated CAN, memory FRAM)
18. **Integration tests** - No standalone VM syscall tests (stdout, sleep, val.persist)
19. **Hardware-in-loop tests** - No ISR latency, throughput validation tests

**Deployment & Portability:**
20. **Build system** - No HAL profile selection (desktop mock vs. MCU C drivers), no module enable/disable flags
21. **MCU drivers** - No AVR/STM32/ARM platform-specific driver wrappers
22. **ISR integration** - No interrupt-driven RX handling, no mailbox posting from ISRs
23. **Standalone VM shim** - No lightweight HAL for single-program deployments without executive

**Deferred Features** (intentionally postponed; should be tracked):

1. **Advanced CAN features** - Error counters, bus recovery, advanced filter chaining (basic CAN TX/RX priority)
2. **UART flow control** - RTS/CTS hardware handshaking (basic TX/RX first)
3. **GPIO advanced modes** - Analog input, PWM output (digital I/O first)
4. **FRAM wear management** - Advanced wear leveling algorithms (basic read/write first)
5. **FS advanced operations** - Symlinks, permissions, quotas (basic CRUD first)
6. **Multi-threaded HAL** - Thread-safe driver access with mutexes (single-threaded first)

**Documentation Gaps** (missing READMEs, usage guides):

1. **HAL porting guide** - No documentation for adding new MCU platform drivers
2. **User-space library guide** - No examples showing how apps use `libhsx_hal.a` APIs
3. **Executive integration doc** - No guide for executive developers calling HAL drivers
4. **Mock driver guide** - No documentation for desktop simulation driver behavior

---

## 4. Next Actions

**Phase 1: Executive-Space Foundation (Python Mock Drivers)**
1. Implement Python mock UART driver with loopback mode in `python/hal/uart_hal.py`
2. Implement Python mock Timer driver with monotonic counter in `python/hal/timer_hal.py`
3. Implement Python mock FRAM driver with memory-backed storage in `python/hal/fram_hal.py`
4. Add HAL syscall dispatching to VM (`platforms/python/host_vm.py`) for modules 0x10-0x12, 0x13
5. Implement `HAL_GET_CAPS` syscall returning Python mock capabilities
6. Create unit tests for UART mock driver (loopback, config, status)
7. Create unit tests for Timer mock driver (tick accuracy, sleep delays)
8. Create unit tests for FRAM mock driver (read/write, persistence)

**Phase 2: Executive-Space Mailbox Integration**
9. Implement UART RX mailbox emission to `hal:uart:0:rx` from mock driver
10. Implement Timer periodic timer mailbox emission to `hal:timer:<id>`
11. Add executive HAL initialization in `python/execd.py` calling `hal_init()`
12. Create integration tests for UART RX events via mailbox
13. Create integration tests for periodic timer events via mailbox

**Phase 3: User-Space Library Implementation**
14. Implement `lib/hsx_uart.c` wrapping UART syscalls and mailbox management
15. Implement `lib/hsx_timer.c` wrapping Timer syscalls and mailbox management
16. Implement `lib/hsx_fram.c` wrapping FRAM syscalls
17. Add callback registration APIs for async events (`hsx_uart_on_rx`, `hsx_timer_on_expiry`)
18. Create `libhsx_hal.a` build target in toolchain (`python/hsx-cc-build.py`)
19. Create example app using `hsx_uart_printf()` and callback-based RX
20. Create integration tests for user-space library linking and execution

**Phase 4: Extended Mock Drivers (CAN, FS, GPIO)**
21. Implement Python mock CAN driver with simulated bus in `python/hal/can_hal.py`
22. Implement Python mock FS driver with host filesystem mapping in `python/hal/fs_hal.py`
23. Implement Python mock GPIO driver with virtual pins in `python/hal/gpio_hal.py`
24. Add syscall dispatching for modules 0x11 (CAN), 0x14 (FS), 0x15 (GPIO)
25. Implement CAN RX and GPIO interrupt mailbox emission
26. Implement user-space libraries `lib/hsx_can.c`, `lib/hsx_fs.c`, `lib/hsx_gpio.c`
27. Create unit tests for CAN, FS, GPIO mock drivers
28. Create integration tests for CAN chunked transfers, FS directory operations, GPIO interrupts

**Phase 5: Standalone VM HAL Shim**
29. Implement `hal_dispatch()` layer in VM for standalone mode (DR-1.3, DG-1.4)
30. Route HAL syscalls to mock drivers without executive forwarding
31. Add standalone VM test cases (stdout redirection, sleep, val.persist)
32. Validate capability fallback (`HAL_STATUS_UNSUPPORTED` → `HSX_ERR_ENOSYS`)

**Phase 6: MCU C Port (Embedded Drivers)**
33. Port executive-space UART HAL to C (`c/exec/hal/uart_hal.c`) targeting AVR
34. Port Timer HAL to C with AVR timer registers (`c/exec/hal/timer_hal.c`)
35. Port FRAM HAL to C with I2C/SPI driver integration (`c/exec/hal/fram_hal.c`)
36. Implement ISR-driven UART RX with mailbox posting from interrupt context
37. Implement ISR-driven GPIO interrupt handling
38. Add build system HAL profile selection (desktop mock, AVR, STM32, ARM)
39. Create hardware-in-loop tests for AVR UART latency, throughput

**Phase 7: Executive Integration & Provisioning**
40. Integrate HAL into executive provisioning service for CAN/SD/UART loaders (coordinates with [07--Provisioning](../07--Provisioning/01--Study.md))
41. Integrate FRAM HAL into ValCmd persistence layer (coordinates with [04--ValCmd](../04--ValCmd/01--Study.md))
42. Integrate FS HAL for HXE v2 metadata loading (coordinates with [05--Toolchain](../05--Toolchain/01--Study.md))
43. Add executive stdio redirection through UART HAL
44. Create integration tests for provisioning workflows (CAN broadcast, UART streaming)

**Phase 8: Advanced Features & Polish**
45. Implement UART flow control (RTS/CTS) for high-throughput scenarios
46. Implement advanced CAN error handling (bus-off recovery, error counters)
47. Implement FRAM wear leveling with block rotation
48. Implement GPIO PWM output mode
49. Add multi-threaded HAL with driver mutexes for concurrent access

**Phase 9: Documentation & Testing**
50. Write HAL porting guide for new MCU platforms
51. Write user-space library usage guide with examples
52. Write executive integration guide for HAL driver invocation
53. Create comprehensive test suite (unit, integration, stress, hardware-in-loop)
54. Add HAL capability matrix documentation (which modules/features per platform)

**Cross-References:**
- **Coordinates with:**
  - [01--VM](../01--VM/01--Study.md) - HAL syscall dispatching, standalone VM shim
  - [02--Executive](../02--Executive/01--Study.md) - Executive-space driver integration, event emission
  - [03--Mailbox](../03--Mailbox/01--Study.md) - Async event delivery via mailboxes
  - [04--ValCmd](../04--ValCmd/01--Study.md) - FRAM persistence for value storage
  - [05--Toolchain](../05--Toolchain/01--Study.md) - User-space library build, HXE v2 metadata
  - [07--Provisioning](../07--Provisioning/01--Study.md) - CAN/UART/SD transport layer integration
- **Blocks:**
  - [07--Provisioning](../07--Provisioning/01--Study.md) - Provisioning requires all transport HAL modules (CAN, UART, FS)
  - [04--ValCmd](../04--ValCmd/01--Study.md) - ValCmd persistence requires FRAM HAL module
- **Blocked by:**
  - None (HAL is foundational layer with no upstream dependencies)

---

**Last Updated:** 2025-10-31  
**Status:** Complete subsystem missing - only API headers exist

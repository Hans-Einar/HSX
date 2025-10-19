# HSX Specification v2
*(Merged architecture, runtime, and execution model — October 2025)*

---

## 1. Overview

HSX (HansEinar eXecutive) is a hybrid virtual machine and executive system for running C or assembly-based tasks on both host simulators and embedded hardware.  
It is composed of a **VM Core**, a **C-based Executive (kernel)**, and a **backend interface** for platform-specific I/O.

### Goals
- Provide deterministic, minimal overhead task scheduling.
- Support cooperative and preemptive multitasking.
- Expose a consistent syscall API for devices, streams, and interprocess communication.
- Enable compilation from ANSI C → LLVM → HSX bytecode (.hxe).
- Allow the same C codebase to run on both the **Python host VM** and **native AVR/embedded targets**.

---

## 2. Execution Model

The HSX system is divided into four conceptual layers:

```
┌──────────────┐
│ Host VM Core │  ← (Python / native backend)
└──────┬───────┘
       │ SVC Trap (syscall entry)
┌──────▼──────┐
│ HSX Exec    │  ← C-based microkernel (scheduler, IPC, memory)
├─────────────┤
│ Kernel      │  → scheduler, heap, signal delivery
├─────────────┤
│ Drivers     │  → UART, CAN, FS, timers (C interfaces)
└──────┬──────┘
       │ Syscalls
┌──────▼──────┐
│ User Tasks  │  → shell, telemetry, logging, etc.
└─────────────┘
```

- **VM Core** — Executes HSX instructions (registers, memory, SVC trap). May be written in Python (simulator) or C++ (native).
- **HSX Executive** — Runs in C on top of the VM, managing memory, processes, and IPC.
- **Drivers** — Interface-based C modules that abstract UART, CAN, FS, timers, etc.
- **User Tasks** — Normal programs linked against the syscall ABI.

---

## 3. Boot and Init Sequence

1. VM loads `.hxe` image.
2. Entry point executes `_hsx_init()` inside the executive.
3. The kernel initializes:
   - Heap allocator and stack regions
   - Scheduler structures (ready/sleep queues)
   - Device driver tables
   - Initial tasks (init, telemetry, etc.)
4. The **init task** spawns configured applications via `exec()` calls.
5. If a console is detected, `shell.hxe` is launched as a user process.

---

## 4. Kernel Services

### 4.1 Scheduler
Supports cooperative round-robin by default. Preemption can be added later through timer interrupts.

### 4.2 Process Control
| Function | Description |
|-----------|--------------|
| `exec(path)` | Load and start a .hxe program from storage. |
| `kill(pid)` | Terminate a process immediately. |
| `wait(pid)` | Wait for process to exit, return status. |
| `yield()` | Voluntary context switch. |
| `exit(status)` | Terminate current process. |

### 4.3 Memory Manager
- Fixed-region heap per system with optional arenas per task.
- Allocations from heap via `malloc`, `calloc`, `free` (custom implementation).
- Protection through cooperative convention (no MMU).

### 4.4 Streams (stdio)
| FD | Meaning | Typical Binding |
|----|----------|----------------|
| 0 | stdin | UART RX / CAN input |
| 1 | stdout | UART TX / log file |
| 2 | stderr | UART TX / error channel |

---

## 5. System Calls

System calls are triggered by **SVC (Supervisor Call)** instructions.  
Each call is identified by `mod` and `fn` fields.

| Module | Code | Purpose |
|---------|------|----------|
| 0x1 | EXIT | terminate current task |
| 0x2 | CAN | send/receive CAN frames |
| 0x3 | SYS | process control, exec, kill, wait |
| 0x4 | FS | file I/O, open, read, write |
| 0x5 | MBX | mailbox IPC |
| 0x6 | VAL | shared value registry |
| 0x7 | CMD | external commands (remote control) |
| 0x8 | STDIO | read/write streams |
| 0xE | MATH | sin/cos/exp (optional libm mode) |

---

## 6. Device and Backend Interfaces

### UART Interface (example)
```c
typedef struct {
    void (*write)(const uint8_t *buf, size_t len);
    size_t (*read)(uint8_t *buf, size_t len);
    void (*flush)(void);
} hsx_uart_t;
```
Each backend implements this structure and registers it with the kernel.

### CAN Interface
Similar to UART but transmits/receives HSX_CAN_Frame structs.

### Filesystem Interface
Mountable driver model with open/read/write functions. The host VM maps this to local files.

---

## 7. IPC: Mailboxes and Values

### Mailboxes
- Asynchronous communication queues between tasks.
- Kernel-managed circular buffers with event notifications.

### Values
- Shared float16 or int32 variables registered by name.
- Used for exposing state to UART/CAN or remote monitoring.

---

## 8. Build and Toolchain Integration

Toolchain path:
```
C → LLVM IR → hsx-llc.py → .mvasm → asm.py → .hxe → host_vm.py
```
- `.mvasm` : human-readable assembly for HSX ISA.
- `.hxe` : binary executable with header, code, data, and CRC.
- `.hxo` : intermediate object files for linking (planned).

Makefiles will handle building examples under `examples/tests/` and generate `.hxe` into per-test `build/` directories.

---

## 9. Portability and Backends

The HSX Executive is written in standard C for portability.  
Backends can be provided for:

| Platform | Backend | Description |
|-----------|----------|-------------|
| Python VM | host_vm.py | Debugging, logging, full introspection |
| AVR/ATmega | avr-gcc + native HAL | Executes directly on MCU with same syscall ABI |
| Linux / POSIX | native C backend | Bridges HSX syscalls to standard OS calls |

Each platform provides hardware drivers via interfaces but reuses the same executive logic.

---

## 10. Future Milestones
- Preemptive scheduling with timer interrupts
- Dynamic memory protection / isolation
- Persistent FS and device driver registration
- Networking via CAN-over-bridge
- Native C port for embedded AVR hardware

---
© 2025 Hans Einar Øverjordet — HSX Project


# HSX Executive and Virtual Machine Specification — Version 2

## Overview
The HSX system is a hybrid between a **virtual machine (VM)** and an **executive kernel**. 
It is designed for embedded devices such as AVR microcontrollers, providing portable execution 
of “domain applications” written in C and compiled through the HSX toolchain into `.hxe` binaries.

HSX separates into two main layers:

1. **HSX Virtual Machine (VM)** — Executes machine instructions, manages registers and memory.
2. **HSX Executive (Executive Kernel)** — Manages scheduling, tasks, mailboxes, and syscalls.

This design allows HSX applications to run identically across hardware and simulated environments.

---

## HSX Virtual Machine

### Responsibilities
- Executes HSX instruction set (MVASM).
- Maintains memory map and register windows.
- Handles instruction decoding, arithmetic, logic, branching, and FPU ops (F16/F32).
- Provides syscall entry (SVC) as the interface to the executive or host backend.

### Register Model
All HSX registers reside in memory. The VM references a **register base pointer** (RBP) that defines 
the memory region representing the active register file. 

Context switching in the executive simply updates the VM’s RBP to point to another task’s register block — 
no copying required.

```text
struct VMState {
    uint16_t pc;
    uint16_t reg_base;  // pointer to active register window
    uint8_t  flags;
};
```

Switching tasks is done by reassigning `vm.reg_base` to another region of memory.

### Syscall Interface
Syscalls (`SVC`) trigger VM traps. The VM passes `mod`, `fn`, and register state to the backend handler.  
Modules are grouped by function — e.g. FS (0x4), CAN (0x2), Mailbox (0x5), and so on.

The backend may handle these directly (native code on AVR, Python simulation) or pass them to the Executive.

---

## HSX Executive

### Purpose
The Executive acts as the operating system for HSX applications. It runs within the VM, in C, and controls:
- Task management and scheduling.
- IPC and Mailboxes.
- Memory allocation and process management.
- Dispatch of syscalls to devices, filesystem, and CAN.

### Memory Model
All code and data live in a shared address space. Each task gets its own **register window** and **stack region**.  
The Executive maintains a task table mapping task IDs to these regions.

| Field | Description |
|--------|--------------|
| `pid` | Process ID |
| `state` | Ready / Running / Waiting |
| `reg_base` | Base address for register window |
| `stack_ptr` | Current stack pointer |
| `mailbox_mask` | Accessible mailbox handles |

---

## 📨 Mailbox Subsystem

### Overview
Mailboxes are shared kernel-managed message queues that enable inter-process communication.  
They are inspired by RSX-11 and VMS mailboxes, but simplified for embedded systems.

Mailboxes are owned and managed by the Executive — not by individual HSX applications.

### Data Model
| Field | Description |
|--------|--------------|
| `id` | Mailbox handle |
| `name` | Optional symbolic name |
| `owner_pid` | PID of creating process |
| `capacity` | Number of messages |
| `queue[]` | Message descriptors (size, sender, payload pointer) |
| `read_idx` / `write_idx` | Circular buffer indices |
| `wait_list` | Tasks blocked on receive |

### Syscalls (Module 0x5)

| Syscall | Description |
|----------|--------------|
| `MAILBOX_CREATE(name, capacity)` | Creates or opens a mailbox |
| `MAILBOX_SEND(handle, ptr, len)` | Sends a message |
| `MAILBOX_RECV(handle, ptr, maxlen)` | Receives a message (may block) |
| `MAILBOX_PEEK(handle)` | Checks if message is available |
| `MAILBOX_CLOSE(handle)` | Closes a mailbox handle |

### Scheduling Integration
If a task blocks on `MAILBOX_RECV()`, the Executive sets its state to **waiting**.  
When a message arrives, the sender signals the scheduler, which places the waiting task in the ready queue.

Because the VM uses register-base switching, resuming the task only requires setting `vm.reg_base` to its register block.

---

## Scheduler
- **Mode:** Cooperative round-robin (upgradeable to pre-emptive with timer SVCs).
- **Context Switch:** Performed by swapping register base pointer and stack pointer.
- **Yield Mechanism:** Tasks can call `SVC_YIELD()` to allow others to run.

---

## Device Drivers and Syscalls

The Executive uses existing SVC module numbers to map system calls to the underlying hardware.

| Module | Purpose | Example |
|----------|----------|----------|
| `0x1` | System | Exit, sleep, time |
| `0x2` | CAN | CAN TX/RX |
| `0x3` | OS / Exec | Process control (exec, kill, wait) |
| `0x4` | FS | File read/write |
| `0x5` | Mailbox | Interprocess communication |
| `0x6` | UART | Serial console I/O |

Each module may be backed by host functions in Python or native C code on embedded targets.

---

## HSX OS and Native Integration

The Executive may be compiled both:
1. **As part of the HSX VM (for simulation)** — implemented in Python, running `.hxe` applications.  
2. **As native C code** on AVR — integrated with hardware peripherals for CAN, UART, and SD card.

Applications written for HSX can therefore run unmodified across hardware and virtual targets.

---

## Portability and HAL Layer

The hardware abstraction layer (HAL) defines interfaces for:
- UART, CAN, and Filesystem
- Timers and Sleep
- Memory allocation and interrupts

Each HAL function is defined in C headers so the same Executive code can be recompiled for different MCU architectures.

---

## Example Integration Flow

1. **VM Startup** — Initialize memory and load Executive.
2. **Executive Init** — Create kernel mailboxes, init scheduler, spawn domain apps.
3. **Task Switch** — Executive updates `vm.reg_base` → new register window.
4. **Syscall Trap** — `SVC` instruction transfers control to the Executive.
5. **Mailbox Event** — Task A sends message → Task B wakes up.
6. **Shutdown / Exit** — Executive terminates and signals VM halt.

---

## Summary

| Component | Responsibility |
|-------------|----------------|
| VM | Executes code, provides hardware abstraction |
| Executive | Schedules, manages memory, handles IPC |
| Mailboxes | Enable async inter-task communication |
| Syscalls | Bridge between app and Executive or hardware |
| HAL | Enables portability across hardware targets |

---

**HSX Executive v2 Summary:**  
- Unified register-based context switching.  
- Shared mailbox IPC subsystem.  
- Native + VM hybrid architecture.  
- Portable HAL for embedded and host environments.  

# HSX Specification (Hans System Executive)

### Overview
**HSX** is a lightweight bytecode executive for embedded and simulated systems. It combines a deterministic executive, a register‑based VM, and an event‑driven IPC mechanism built around mailboxes and f16‑based values.

---

## 1. Architecture

```
 ┌────────────┐      ┌────────────┐
 │  Shell.hxe │─────▶│ HSX Exec   │
 │  (CLI)     │◀────┤ Scheduler  │
 └────────────┘      └────────────┘
        │                  │
        │     SVC Calls    ▼
        │         ┌────────────────────┐
        │         │ HAL Modules (FS,   │
        │         │ SPI, UART, CAN...) │
        │         └────────────────────┘
        │
        │ Mailboxes & Events
        ▼
 ┌──────────────┐
 │ Other Tasks  │
 │ sensor.hxe   │
 │ logger.hxe   │
 └──────────────┘
```

### Components
| Layer | Description |
|--------|-------------|
| **VM Core** | Executes bytecode (.hxe) in a 16‑register Harvard model. |
| **Executive** | Manages task list, scheduling, mailboxes, and event signals. |
| **HAL** | Provides system services: FS, UART, CAN, SPI, I2C, GPIO, ADC, PWM. |
| **Shell** | User‑facing command interpreter over UART or CAN. |
| **FS** | PetitFAT/LittleFS interface for loading .hxe programs and data. |

---

## 2. File Format (.hxe)

| Field | Size | Description |
|--------|------|--------------|
| Magic | 4 | `HSXE` (0x48535845) |
| Version | 2 | Format version |
| Flags | 2 | Execution attributes |
| Entry | 4 | Byte offset of entry point |
| Code length | 4 | Number of bytes of code |
| RO length | 4 | Read‑only data section size |
| BSS size | 4 | Zero‑init RAM size |
| Capabilities | 4 | Required HAL capabilities |
| CRC32 | 4 | File integrity |

---

## 3. VM Core ISA

### Register Model
- 16 general registers `R0..R15` (32‑bit each)
- `R14` used as frame pointer, `R15` as stack pointer
- Flags register (Z, N, C, V)

### Immediate & Memory Model
- Harvard: code in NOR/FRAM, data in RAM/FRAM.
- Load/store are word‑addressed (32‑bit) plus `LDB/LDH/STB/STH`.
- Absolute control-flow instructions (`JMP`, `JZ`, `JNZ`) zero-extend their 12-bit immediate and jump within the 0x0000–0x0FFF code window.
- Relative control flow (`CALL`) treats the 12-bit immediate as a signed word offset (`<<2`) from the selected base register/PC, preserving backwards jumps.

### Instruction Groups
| Group | Mnemonics |
|--------|------------|
| Move/Load/Store | `LDI, LDI32, LD, ST, LDB, LDH, STB, STH, MOV` |
| Arithmetic | `ADD, SUB, MUL, DIV, AND, OR, XOR, NOT` |
| Compare/Branch | `CMP, JMP, JZ, JNZ, CALL, RET` |
| Stack | `PUSH, POP` |
| Float16 Ops | `I2F, F2I, FADD, FSUB, FMUL, FDIV` |
| System | `SVC mod,fn` |

### f16 (Half Precision)
- 1 sign bit, 5 exponent bits, 10 mantissa bits.
- Stored in the **low 16 bits** of a register.
- Used as the default type for *values* exposed to or exchanged between tasks.

---

## 4. SVC Modules

| Module | mod | Functions (fn) |
|---------|-----|----------------|
| **0x0 TIME** | 0 | `get_cycles` |
| **0x1 UART** | 0 | `tx(ptr,len)` |
| **0x2 CAN** | 0 | `tx(id,ptr,len)` |
| **0x4 FS** | 0..13 | open, read, write, close, list, delete, rename, mkdir |
| **0x5 MBX** | 0..6 | mailbox API |
| **0x6 EVT** | 0..N | event registration and signaling |

---

## 5. Mailbox System (MBX)

Mailboxes provide asynchronous, deterministic inter‑task communication. Each mailbox is a FIFO buffer identified by a name.

### Structure
```c
struct HSX_Mailbox {
    char     name[8];
    uint8_t* buffer;
    uint16_t size;
    uint16_t head, tail;
    uint8_t  waiting_tid;
};
```

### SVC Interface (mod=0x5)
| fn | Call | Description |
|----|------|-------------|
| 0 | `mbx.create(name, size)` | Create mailbox. R0=handle. |
| 1 | `mbx.delete(name)` | Delete by name. |
| 2 | `mbx.write(name, ptr, len)` | Append message. Blocks if full. |
| 3 | `mbx.read(name, ptr, max)` | Read next message. Blocks if empty. |
| 4 | `mbx.poll(name)` | R0=available bytes. |
| 5 | `mbx.wait(name, mask)` | Wait for data or event. |
| 6 | `mbx.signal(name, mask)` | Signal and wake waiting tasks. |

---

## 6. Event System (EVT)

Each task has an **event mask**. Events can originate from:
- Mailboxes (data ready)
- Timers
- Drivers (UART RX, CAN RX)
- External interrupts

```c
#define EVT_MAILBOX  0x01
#define EVT_TIMER    0x02
#define EVT_CANRX    0x04
#define EVT_UART_RX  0x08
```

Scheduler checks event masks on each tick. Tasks transition:
`WAIT_EVENT → READY` when signaled.

---

## 7. Memory Model

| Region | Storage | Usage |
|---------|----------|-------|
| Flash/NOR | Program code (.hxe) | Nonvolatile executable storage |
| FRAM | Extended data / persistent values | Fast nonvolatile RAM |
| SRAM | Stack, task runtime | Fast volatile memory |
| SD / FS | Files, configs, logs | Optional external storage |

### Caching
- L1: SRAM (active code pages)
- L2: FRAM (swappable task segments)

DMA and IRQ can prefetch FRAM/NOR pages into SRAM cache blocks while CPU executes.

---

## 8. Scheduler

- Cooperative with optional preemption.
- Round‑robin ready queue.
- Blocking calls (`mbx.read`, `wait_event`) yield CPU.

---

## 9. Shell

Command interface over UART or CAN. Handles:
- `ps`, `kill`, `start`, `stop`, `list`, `load`.
- Sends signals (Halt, Kill, USR1/USR2) to tasks.

---

## 10. f16 Value System (foundation)

All inter‑task data and exposed parameters are stored as **f16 values**. This ensures:
- Consistent 16‑bit representation.
- Compact communication over CAN/UART.
- Predictable numeric range for control and sensing.

```c
typedef uint16_t hsx_value_t; // IEEE 754 half precision
```

Future tasks can register **named values** accessible via mailbox or external query:
```
SVC mod=0x7, fn=0  // value.get(name)  -> f16
SVC mod=0x7, fn=1  // value.set(name, f16)
SVC mod=0x7, fn=2  // command.exec(name)
```

---

## 11. Example: Sensor Task

```asm
.entry
; Periodically read sensor and post f16 value
LDI   R1, name_sensor
.loop:
    SVC 0x700       ; value.get or read ADC
    F2I  R2, R1
    LDI  R3, buf
    ST   [R3+0], R2
    LDI  R4, 2
    SVC  0x502       ; mbx.write(sensor)
    SVC  0x002       ; can.tx(buf)
    JMP  .loop
```

---

## 12. Summary

**HSX** combines:
- Deterministic multitasking (executive core)
- Portable register‑VM (.hxe bytecode)
- Event‑driven IPC via mailboxes
- Unified f16 data representation

It forms a foundation for distributed embedded systems with structured, low‑overhead task cooperation.


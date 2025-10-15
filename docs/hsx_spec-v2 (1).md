# HSX Specification v2
*(Merged architecture, runtime, and execution model — updated 2025‑10‑06)*

---

## 1. Overview

HSX (HansEinar eXecutive) is a hybrid **virtual machine + executive** for running portable applications (“HSX apps”) on both host simulators and embedded targets (e.g., AVR128DA28). HSX apps are shipped as `.hxe` bytecode images. A small native **Executive** provides scheduling, process control, syscalls, and device access.

This revision clarifies a **no‑VM‑shell** deployment: the VM is embedded as a scheduled native task, while a **native shell** (outside the VM) controls HSX apps (start/stop/list/signals).

### Goals
- Deterministic, low‑overhead runtime with **fast native syscalls**.
- Load/reload **domain apps from SD** at runtime on Harvard MCUs.
- Single “core” firmware for many devices; behavior changes by swapping `.hxe` apps.
- Easy porting: Executive written in standard C/C++, HAL via small interfaces.
- Identical behavior under a **Python “native” host** for development and testing.

---

## 2. Execution Model

Layers and flow:

```
┌───────────────────┐
│  Native Shell     │  ← User CLI (outside VM)
└─────────┬─────────┘
          │  control (ps/exec/kill/stdio)
┌─────────▼─────────┐
│  HSX Executive    │  ← C microkernel: scheduler, IPC, memory
├───────────────────┤
│  Drivers (HAL)    │  ← UART, CAN, FS, Timers (interfaces)
└─────────┬─────────┘
          │  SVC (syscalls) — fast native trap
┌─────────▼─────────┐
│     HSX VM        │  ← executes .hxe bytecode slices
└─────────┬─────────┘
          │
┌─────────▼─────────┐
│   HSX Apps (.hxe) │  ← domain logic, portable
└───────────────────┘
```

**No VM shell:** HSX apps do not provide an interactive shell. The **native shell** controls apps via Executive APIs. HSX stdio is routed to native devices by the Executive (e.g., stdout→UART/log; stdin optional).

---

## 3. Boot & Init

1) Core firmware boots native Executive; registers HAL drivers.  
2) Executive initializes scheduler, fixed memory pools, and device tables.  
3) Executive optionally starts configured HSX apps from SD (“init list”).  
4) Native shell is available to the user to manage HSX apps live.

---

## 4. Scheduling

### 4.1 Cooperative slices (default)
- System tick (e.g., **10 ms**) calls `hsx_run_slice(task)` for the READY task.  
- Each HSX task carries an instruction **budget** per tick (e.g., 5k steps).  
- Tasks become SLEEP/READY/ZOMBIE via syscalls (`sleep`, `yield`, `exit`).

### 4.2 Optional preemption (later)
- Timer ISR sets a quantum‐expired flag. VM checks at safe points and returns to the scheduler to switch tasks.

---

## 5. Memory Model (fragmentation‑safe)

- **Task arenas**: Each HSX task receives a **fixed contiguous block** (stack + heap). On kill/restart the block is reused wholesale.  
- **Mailbox pool**: Fixed‑size message descriptors in a circular pool (power‑of‑two).  
- **Value table**: Fixed registry of named values (f16/i32) with hashed names.  
- **FS, CAN, UART**: native ring buffers; no dynamic allocation in steady state.  
- Avoid `malloc/free` in the hot path; prefer arenas and slabs.

---

## 6. Syscalls (SVC)

All syscalls are **native** (fast) and defined by `(mod, fn)`. HSX apps invoke `SVC` and pass arguments in registers/memory.

| Module | Code | Area | Examples |
|---|---|---|---|
| EXIT | 0x01 | program exit | `EXIT(status)` |
| CAN  | 0x02 | can bus     | `TX`, `RX`, `STATUS` |
| FS   | 0x04 | filesystem  | `OPEN`, `READ`, `WRITE`, `CLOSE`, `LIST` |
| MBX  | 0x05 | mailboxes   | `CREATE`, `SEND`, `RECV`, `POLL` |
| VAL  | 0x06 | values      | `GET`, `SET`, `ENUM` (f16/i32), FRAM persist |
| EXEC | 0x07 | processes   | `EXEC`, `EXIT`, `YIELD`, `SLEEP_MS`, `KILL`, `WAIT`, `GETPID`, `TASKLIST` |
| FD   | 0x0A | stdio/fd    | `OPENFD_DEV`, `DUP2`, `WRITE(fd,buf,len)`, `READ(fd,buf,len)`, `SETSTDIO` |
| MATH | 0x0E | math (dev)  | `sinf`, `cosf`, `expf` → dev‑mode host math |

> **Stdio policy:** Default per‑task mapping is `stdin=/dev/null`, `stdout=uart0`, `stderr=uart0`. Native shell can rebind via `SETSTDIO`.

---

## 7. Executive API (native C/C++)

### 7.1 Process control
```c
typedef int32_t hsx_pid_t;

typedef struct {
  uint32_t pc, sp;
  uint32_t r[16];
  void* code_base;
  void* data_base;
  uint32_t time_slice_steps;
  uint8_t state;   // READY/RUN/SLEEP/ZOMBIE
  int fd[8];       // 0=stdin,1=stdout,2=stderr, others
} hsx_task_t;

hsx_pid_t exec_spawn(const char* path, int fd0, int fd1, int fd2);
int       exec_exit(int status);
int       exec_kill(hsx_pid_t pid, int sig);
int       exec_wait(hsx_pid_t pid, int* status_out);
int       exec_yield(void);
int       exec_sleep_ms(uint32_t ms);
```

### 7.2 FD/STDIO
```c
int fd_open_dev(const char* name); // "uart0","can0","null","pipe:name"
int fd_write(int fd, const void* p, int n);
int fd_read(int fd, void* p, int n);
int fd_dup2(int oldfd, int newfd);
int fd_setstdio(hsx_pid_t pid, int fd0, int fd1, int fd2);
```

---

## 8. HAL Interfaces (portable)

Backends implement small **vtables** and register at boot.

```c
typedef struct {
  int  (*open_dev)(const char* name);
  int  (*write)(int fd, const void* p, int n);
  int  (*read)(int fd, void* p, int n);
  int  (*dup2)(int oldfd, int newfd);
} hsx_stdio_vtbl_t;

typedef struct {
  int  (*open)(const char* path, int flags);
  int  (*read)(int fd, void* p, int n);
  int  (*write)(int fd, const void* p, int n);
  int  (*close)(int fd);
  int  (*list)(const char* dir,
               void* ctx,
               void (*on_entry)(void* ctx, const char* name, int is_dir));
} hsx_fs_vtbl_t;

void hsx_register_stdio(const hsx_stdio_vtbl_t*);
void hsx_register_fs(const hsx_fs_vtbl_t*);
```

Additional drivers (CAN, timers, GPIO, ADC/PWM) follow the same pattern.

---

## 9. No‑VM‑Shell Mode

- VM has **no internal shell**.  
- Native shell (outside VM) issues management commands:  
  - `hsx ps` → list HSX tasks (pid, state, cpu, stdio)  
  - `hsx exec /apps/foo.hxe` → spawn app (optionally set stdio bindings)  
  - `hsx kill <pid> [SIGTERM|SIGKILL]`  
  - `hsx stdio <pid> in=<dev> out=<dev> err=<dev>`  
  - `hsx val get/set <name> [value]`  
  - `hsx mbx send <mbx> <hexdata>`

This keeps **performance high** and reduces VM complexity while still providing full operability.

---

## 10. Python “Native” Prototype (host)

For development, we embed the same model in Python:

**Requirements:**
- In `host_vm.py`: a cooperative **task table** and `hsx_run_slice()` that steps N instructions.
- **SVC tables** for EXEC (0x07), FD (0x0A), FS (0x04), CAN (0x02), VAL (0x06), MBX (0x05), MATH (0x0E).
- A **native shell** (Python CLI) with commands: `ps`, `exec`, `kill`, `stdio`, `val`, `mbx`, `run Nms`.
- **Stdout piping**: HSX task writes go to shell console; optionally tee to file.
- **Filesystem**: map to a local host folder for `/apps` mounting.
- **Signals**: Cooperatively delivered at syscall/step boundaries.

This simulates the AVR deployment precisely while being easy to test and script.

---

## 11. Toolchain

```
C → LLVM IR → hsx-llc.py → .mvasm → asm.py → .hxe → host_vm.py
```
- ISA is f16‑native with f32 math via runtime where needed. See `HSX_FLOAT_ARCHITECTURE.md` and `HSX_F16_GUIDE.md`.
- `.hxo` relocatable object/linker is planned; current flow emits final `.hxe` with header & CRC.

---

## 12. Security & Isolation (future)

- Optional memory bounds checks on loads/stores per task arena.
- Time quotas & watchdog to prevent runaway tasks.
- Capability tokens for FS/FD to restrict app privileges.

---

## 13. Roadmap (excerpt)

- [ ] Python “native” shell + task manager (this spec)
- [ ] Mailbox & Value pools (native) with syscalls (0x05/0x06)
- [ ] AVR Executive (C) using FatFs/UART/CAN drivers
- [ ] Preemption via timer tick (optional)
- [ ] Linker & `.hxo` support
- [ ] Doxygen docs and CI for examples/tests

---

© 2025 Hans Einar Øverjordet — HSX Project

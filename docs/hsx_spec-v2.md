# HSX Specification v2
*(Merged architecture, runtime, and execution model – updated 2025-10-06)*

---

## 1. Overview
HSX (HansEinar Executive) is a hybrid of a **virtual machine (VM)** and a **native executive kernel** that executes portable `.hxe` applications on both embedded targets (e.g. AVR128DA28) and host simulators. Applications are written in C, compiled to LLVM IR, lowered to MVASM, assembled into `.hxe`, and executed by the VM. A compact executive—written in C—provides scheduling, process control, IPC, and device access.

Key characteristics:
- Deterministic runtime with fast native syscalls.
- Pluggable device backends (UART, CAN, FS, timers) via small HAL interfaces.
- Identical behaviour on host (Python prototype) and hardware builds.
- Domain apps can be swapped at runtime from removable storage.

This revision promotes a **native shell / control plane outside the VM**: HSX apps do not embed their own shell; a supervisor process (native or host-side) manages HSX tasks via executive APIs.

---

## 2. Layered Architecture
```
+-------------------------------+
¦ Native Shell / Supervisor     ¦  ? CLI or service that manages HSX tasks (exec, ps, kill)
+-------------------------------+
                ¦ control plane
+---------------?---------------+
¦ HSX Executive (C microkernel) ¦  ? scheduler, memory arenas, IPC, syscalls
+-------------------------------¦
¦ HAL Drivers                   ¦  ? UART, CAN, FS, timers, GPIO
+-------------------------------+
                ¦ SVC traps (fast)
+---------------?---------------+
¦ HSX VM Core                   ¦  ? executes MVASM instructions from .hxe images
+-------------------------------+
                ¦
+---------------?---------------+
¦ HSX Applications (.hxe)       ¦  ? domain logic, portable modules
+-------------------------------+
```

The VM is intentionally shell-less; interactive control is provided by the native shell. Standard I/O for HSX tasks is routed by the executive (e.g., stdout?UART/log, stdin optional).

---

## 3. Virtual Machine Core

### Responsibilities
- Decode and execute MVASM instructions (integer, logical, control flow, and F16/F32 ops).
- Maintain PC, flags, and general-purpose registers.
- Provide fast syscall entry (`SVC`) into the executive or host backend.
- Map instruction/data memory and expose register windows for context switching.

### Register Windows
All architectural registers live in RAM. The VM keeps a **register base pointer (RBP)** identifying the active window:
```
struct VMState {
    uint16_t pc;
    uint16_t reg_base;  // base address of current register window
    uint8_t  flags;
};
```
Context switches simply retarget `reg_base` (no copying). Each task owns a slice of memory containing its registers, stack, and heap region.

### Syscall Trap
`SVC imm12` splits into module + function fields (`mod = imm[11:8]`, `fn = imm[7:0]`). The VM captures argument registers (R0–R3) and forwards the trap to native handlers (Python host or C executive).

---

## 4. Executive Kernel

### Purpose
The executive runs inside the VM (compiled C) and implements:
- Process/task table, ready queues, and scheduling.
- Memory arenas (task stacks/heaps, mailbox pool, value table).
- Syscall dispatch to HAL drivers (FS, UART, CAN) and higher-level services (mailboxes, values, exec).
- IPC via mailbox subsystem and shared value registry.

### Process Descriptor
```
typedef int32_t hsx_pid_t;


typedef struct {
  uint32_t pc;            // stored separately from reg window
  uint32_t psw;           // flags / condition bits (mirror of VM.flags)
  uint32_t reg_base;      // base pointer in VM memory for general-purpose regs
  uint32_t stack_base;    // base pointer in VM memory for stack frame
  uint32_t stack_limit;   // guard for overflow checks
  uint32_t time_slice_cycles;  // scheduler quantum in VM cycles
  uint32_t accounted_cycles;   // lifetime CPU accounting for load metrics
  uint8_t  state;         // READY/RUN/SLEEP/ZOMBIE
  uint8_t  priority;      // 0 (highest)..255 (lowest)
  uint16_t reserved;
  int      fd[8];         // 0=stdin,1=stdout,2=stderr...
} hsx_task_t;
```

### VM Context Model
- **Register window indirection:** the VM always reads/writes `R0..R15` via `reg_base + N*4`. Swapping `reg_base` repoints the register bank without copying.
- **Stack relocation:** the guest-visible SP is computed as `stack_base + (vm.sp & 0xFFFF)`. Swapping `stack_base` yields an O(1) context switch.
- **Context switch API:** the executive updates `pc`, `psw`, `reg_base`, and `stack_base` then calls `vm.step()` (or a multi-step loop). Python exposes `set_context()`; C mirrors this with `hsx_vm_load_context()`.
- **Isolation:** each task’s memory arena (stack/heap) is disjoint. `stack_limit` enables overflow detection and debugging.

### Scheduling Model
- **Round-robin with quanta:** each runnable task receives a configurable quantum in VM cycles. When exhausted, the executive preempts and requeues the task.
- **Priority weights:** priorities map to quantum length. Higher priority -> larger quantum (e.g., 0 -> 1000 steps, 10 -> 100). This keeps the Python and C implementations aligned.
- **Tick vs tickless:** the default host executive uses a soft tick (run N steps, reschedule). On hardware a timer ISR can raise a quantum-expired flag so the VM yields at the next safe point. A tickless policy picks the minimum of (remaining quantum, time-to-next-event).
- **Accounting:** the executive accumulates `accounted_cycles` per task to report CPU usage/load averages to shell clients.
- Tasks may `yield`, `sleep_ms`, `wait`, `exec_exit`, or block on mailbox receive; the executive moves them between READY/RUN/SLEEP queues accordingly.

### Memory Strategy
- Fixed arenas per task (stack+heap) reclaimed on `kill`/`exit`.
- Mailbox pool implemented as circular buffers with fixed descriptors.
- Value table storing named f16/i32 values (optionally backed by FRAM).
- Avoid heap fragmentation; prefer static pools/slabs.

### IPC: Mailboxes (module 0x05)
Mailboxes remain kernel-owned circular queues built on the static descriptor pool from the previous revision. This update formalizes handle namespaces, message framing, shell mirroring, and back-pressure so the executive, stdio shim, and HSX applications share a consistent contract.

**Descriptor pool**
- Preallocated descriptors back power-of-two ring buffers (default 64-byte payload, configurable at bind time).
- Descriptors track owner PID for private channels or a namespace tag (`svc`, `app`, `shared`) for globally named mailboxes.

**Handles and namespaces**
- `MAILBOX_OPEN` resolves `pid:<pid>` handles for per-task control channels created at spawn.
- Named channels use the `svc:name` and `app:name` namespaces (for example `svc:stdio.out`, `app:telemetry`). Access control is enforced via bind flags.
- Handles are small integers scoped to the calling task; they remain valid until `MAILBOX_CLOSE`.

**Message frame**
- Each entry stores a fixed header (`struct hsx_mbx_msg { uint16_t len; uint16_t flags; uint16_t src_pid; uint16_t channel; }`) followed by payload bytes. Payload length is clamped to the descriptor capacity minus the header size.
- Flag bits include `MBX_FL_STDOUT`, `MBX_FL_STDERR`, and `MBX_FL_OOB` so stdio and control traffic can share the transport without ambiguity.

**Scheduling interactions**
- `MAILBOX_RECV` on an empty queue moves the task to `WAIT_MBX`. The syscall accepts a timeout in scheduler ticks (`0` = poll, `>0` = bounded wait, `0xFFFF` = infinite).
- `MAILBOX_SEND` wakes exactly one waiter per descriptor. Remaining waiters stay in FIFO order. Non-blocking sends return `HSX_E_WOULDBLOCK` when the ring is full.
- Blocking sends respect the same timeout semantics; a timeout transitions the task back to READY with an error code.

**Shell and stdio integration**
- The executive may register passive taps (`MAILBOX_TAP`) to mirror traffic to the shell or telemetry sinks without consuming the message.
- Default channels created at spawn are `svc:stdio.in`, `svc:stdio.out`, `svc:stdio.err`, and `pid:<pid>` (control). The HSX stdio shim maps `stdin`/`stdout`/`stderr` onto these handles and exposes `listen`/`send` shell commands for operator interaction.
- Trace hooks record `{timestamp, src_pid, dst_handle, flags, len}` when tracing is enabled, providing visibility into inter-task communication.

This design reuses the prior circular-buffer implementation while extending the naming model and stdio routing needed by the multi-task executive.

---
## 5. Syscall Modules
The canonical mapping for this revision is as follows. HSX tasks use the FD abstraction; there is no dedicated UART syscall module - the executive decides where stdio is routed (UART, CAN, log file, etc.).

| Module | Code | Area        | Examples |
|--------|------|-------------|----------|
| EXIT   | 0x01 | Program exit / status | `EXIT(status)`
| CAN    | 0x02 | CAN bus             | `TX`, `RX`, `STATUS`
| EXEC   | 0x07 | Process control     | `EXEC`, `EXIT`, `YIELD`, `SLEEP_MS`, `KILL`, `WAIT`, `GETPID`, `TASKLIST`
| FS     | 0x04 | Filesystem          | `OPEN`, `READ`, `WRITE`, `CLOSE`, `LIST`
| MBX    | 0x05 | Mailboxes / IPC     | `OPEN`, `BIND`, `SEND`, `RECV`, `TAP`
| VAL    | 0x06 | Value table         | `GET`, `SET`, `ENUM` (f16/i32), optional FRAM persist
| FD     | 0x0A | File descriptors / stdio | `OPENFD_DEV`, `WRITE(fd,buf,len)`, `READ`, `DUP2`, `SETSTDIO`
| MATH   | 0x0E | Optional dev math   | `sinf`, `cosf`, `expf` (host/dev tools)

Arguments pass in R0–R3 (additional buffers via pointers); results return in R0. The executive may extend the table with experimental modules, but apps should rely only on the IDs above for portable behaviour.

---

## 6. Standard Interfaces

### Process Control (EXEC module)
```
hsx_pid_t exec_spawn(const char* path, int fd0, int fd1, int fd2);
int       exec_exit(int status);
int       exec_kill(hsx_pid_t pid, int sig);
int       exec_wait(hsx_pid_t pid, int* status_out);
int       exec_yield(void);
int       exec_sleep_ms(uint32_t ms);
```

### File Descriptor / STDIO (FD module)
```
int fd_open_dev(const char* name);           // "uart0", "can0", "null", "pipe:name"
int fd_write(int fd, const void* p, int n);
int fd_read(int fd, void* p, int n);
int fd_dup2(int oldfd, int newfd);
int fd_setstdio(hsx_pid_t pid, int fd0, int fd1, int fd2);
```
Default binding: stdin=/dev/null, stdout/stderr=uart0. The supervisor can rebind via `fd_setstdio`. On the Python executive `pipe:` devices are backed by the mailbox channels described above (`svc:stdio.*` per PID), so stdio and IPC share a single transport.

### Mailboxes (MBX module)
| Call | Description |
|------|-------------|
| `MAILBOX_OPEN(target, flags)` | Resolve `pid:<pid>` or named channel and return a handle; creates default stdio mailboxes on first use. |
| `MAILBOX_BIND(name, capacity, mode)` | Create or attach to a named mailbox (`svc:`/`app:`) with the requested capacity and access policy. |
| `MAILBOX_SEND(handle, ptr, len, flags, timeout)` | Enqueue a message; blocks or returns `HSX_E_WOULDBLOCK` depending on timeout semantics. |
| `MAILBOX_RECV(handle, ptr, maxlen, flags, timeout)` | Dequeue a message; supports poll/timeout semantics and returns message metadata. |
| `MAILBOX_PEEK(handle, info_out)` | Report pending message length, flag bits, and queue depth without consuming data. |
| `MAILBOX_TAP(handle, enable)` | Register or remove a passive mirror for shell or telemetry listeners. |
| `MAILBOX_CLOSE(handle)` | Release the handle; descriptors recycle when the final owner closes. |

Shell commands `listen [pid|channel]` and `send <pid> [channel] <data>` map onto the mailbox API to surface task stdio in the executive shell.

---## 7. HAL / Driver Vtables
Drivers register small vtables with the executive at boot:
```
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
  int  (*list)(const char* dir, void* ctx,
               void (*on_entry)(void* ctx, const char* name, int is_dir));
} hsx_fs_vtbl_t;

void hsx_register_stdio(const hsx_stdio_vtbl_t*);
void hsx_register_fs(const hsx_fs_vtbl_t*);
```
Other backends (CAN, timers, GPIO) follow the same pattern.

---

## 8. Boot Flow
1. **Native Boot:** Firmware starts, initializes HAL drivers, and launches the executive kernel.
2. **Executive Init:** Sets up scheduler, arenas, mailboxes, value table. Loads auto-start `.hxe` apps (init list).
3. **Shell/Services:** Supervisor process (on host or hardware) connects to exec API to start/stop HSX apps or provide a console. Shell itself is an HSX task only when needed.
4. **App Execution:** Scheduler dispatches HSX tasks, each running slices in the VM. Syscalls bridge to kernel drivers.

---

## 9. Runtime Attachment Modes

The HSX VM supports two modes of operation:

- **Standalone:** No external executive is attached. The VM loads and executes a single `.hxe`, services sleep/yield syscalls internally (time-based delay), and writes stdout/stderr to its configured sinks.
- **Attached:** A remote executive connects via the TCP RPC interface, requests pause, and drives instruction stepping explicitly. When attached, the VM reports exec-related traps (sleep/yield/etc.) to the controller instead of acting on them, so scheduling and wake-ups are handled by the executive. The controller may also read/write registers and memory, single-step, or halt individual tasks.

The executive can relinquish control (detach), after which the VM resumes standalone behaviour. Implementations should provide an RPC handshake (`attach`, `detach`, `step`, `set_mode`) so future tooling remains compatible.

---
## 9. Python Host Prototype
For development, the same architecture runs under `platforms/python/host_vm.py`:
- Cooperative task table, register windows, and instruction budget per slice.
- Exec/FD/FS/CAN/MBX/VAL/MATH modules implemented in Python.
- Native shell with commands `ps`, `exec`, `kill`, `stdio`, `val`, `mbx`, and `run <ms>`.
- Filesystem mapped to host directories for `/apps`.
- Optional dev math functions (module 0x0E) for `sin/cos/exp`.

The new `--exec-root` flag lets the host VM enumerate payload `.hxe` files and run them via an exec syscall shim—mirroring the embedded design.

---

## 10. Toolchain Recap
```
C source ? clang -emit-llvm ? hsx-llc.py ? .mvasm ? asm.py ? .hxe ? host_vm.py
```
`.hxo` relocatables and linker support are under active development; current flow emits final `.hxe` with HSXE header (magic 0x48535845, version 0x0001, CRC32).

---

## 11. Security & Isolation (Future Work)
- Optional memory bounds checks on loads/stores within task arenas.
- Watchdog/time quotas to kill runaway tasks.
- Capability tokens for FS/FD access control.
- Stronger separation between user tasks and executive (MPU/MMU on capable MCUs).

---

## 12. Roadmap Snapshot
- [ ] Finalize syscall module numbering (resolve 0x07 vs 0x03, 0x0A vs 0x06 conflict).
- [ ] Complete Python “native” shell + task manager (ps/exec/kill/stdio).
- [ ] Mailbox & value pools with FRAM persistence.
- [ ] AVR executive port using FatFs/UART/CAN drivers.
- [ ] Optional preemption via timer tick.
- [ ] Linker & `.hxo` pipeline.
- [ ] Doxygen / docs automation.

---













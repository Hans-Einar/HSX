# HSX Specification v2
*(Merged architecture, runtime, and execution model - updated 2025-10-06)*

---

## 1. Overview
HSX (HansEinar Executive) is a hybrid of a **virtual machine (VM)** and a **native executive kernel** that executes portable `.hxe` applications on both embedded targets (e.g. AVR128DA28) and host simulators. Applications are written in C, compiled to LLVM IR, lowered to MVASM, assembled into `.hxe`, and executed by the VM. A compact executive--written in C--provides scheduling, process control, IPC, and device access.

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
| Native Shell / Supervisor     |  ? CLI or service that manages HSX tasks (exec, ps, kill)
+-------------------------------+
                | control plane
+---------------?---------------+
| HSX Executive (C microkernel) |  ? scheduler, memory arenas, IPC, syscalls
+-------------------------------|
| HAL Drivers                   |  ? UART, CAN, FS, timers, GPIO
+-------------------------------+
                | SVC traps (fast)
+---------------?---------------+
| HSX VM Core                   |  ? executes MVASM instructions from .hxe images
+-------------------------------+
                |
+---------------?---------------+
| HSX Applications (.hxe)       |  ? domain logic, portable modules
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
`SVC imm12` splits into module + function fields (`mod = imm[11:8]`, `fn = imm[7:0]`). The VM captures argument registers (R0-R3) and forwards the trap to native handlers (Python host or C executive).
### Calling Convention
HSX uses a register-first calling convention with a spill-to-stack extension so functions can accept an arbitrary number of word-sized arguments without bespoke glue. All general-purpose registers (`R0`-`R15`) are 32-bit.

#### Register classes
- `R0` – primary return value, caller-saved. Multi-word results extend into `R1` and `R2`.
- `R1`, `R2`, `R3` – first three argument registers, caller-saved. Callers place the first three words of argument data here.
- `R4`, `R5`, `R6`, `R7` – callee-saved general registers. Callees must restore these if they modify them.
- `R8`, `R9`, `R10`, `R11` – caller-saved temporaries. The compiler/runtime may freely use them across calls.
- `R12`, `R13`, `R14`, `R15` – reserved for platform/ABI extensions (frame pointer, TLS, scratch) and are caller-saved unless a specific profile documents otherwise.
- `SP` – dedicated stack pointer (not part of the `R0`-`R15` window). The VM enforces 4-byte alignment for every call boundary.

#### Argument placement
1. Word-sized integer, pointer, and floating-point arguments are placed in `R1`, `R2`, then `R3` in left-to-right order.
2. Narrower integers (`i1`, `i8`, `i16`) are sign- or zero-extended to 32 bits according to the originating language semantics before being written to the register or stack slot. `half` (f16) arguments occupy the lower 16 bits of the slot with the upper bits cleared.
3. Aggregates larger than 32 bits are passed by reference: the caller materialises the object in memory and passes a pointer (consuming one argument slot). Small structs/unions that fit in 32 bits may be passed by value.
4. Overflow arguments (starting with argument #4) are written to the caller's stack frame in 4-byte words.

#### Overflow stack layout
- The caller pushes overflow arguments (starting with the highest index) using `PUSH`; the VM decrements `SP` by 4 for each word.
- `CALL` pushes the return address after the overflow arguments, so the callee observes the layout below (stack grows downward, lowest addresses at the bottom of the diagram).
- After the callee returns, the caller pops the overflow slots (or otherwise increments `SP`) to restore its original stack depth.

```
; higher addresses (larger addresses)
| caller locals / saved regs |
|----------------------------|
| argument #6 (word)         |  SP + 12
| argument #5 (word)         |  SP + 8
| argument #4 (word)         |  SP + 4
| return address             |  SP + 0  <-- SP value on entry
| callee frame ...           |
; lower addresses (smaller addresses)
```

The callee may create a traditional frame by saving callee-saved registers and adjusting `SP` downward. Leaf functions that do not touch overflow slots are free to leave `SP` unchanged.

#### Variadic functions
- Named parameters follow the normal register/stack rules. The caller then continues to push additional arguments so they appear immediately after the last named stack argument.
- Callees expecting varargs must copy any register arguments they wish to treat as part of the vararg list into the stack save area before iterating.
- Both the Python VM and native toolchain will synthesise a `va_list` shim that points at the first stacked slot, matching the layout shown above.

#### Toolchain status
- The Python VM implements `PUSH`/`POP` alongside `CALL`, so compiled code and hand-written MVASM can manage stack slots for overflow arguments without bespoke helpers.
- `python/hsx-llc.py` now emits `PUSH`/`POP` sequences to spill arguments four and beyond and keeps the caller stack balanced after the call returns.
- Hand-written MVASM should adopt the same pattern (`PUSH` overflow arguments, `CALL`, then `POP` to unwind) so that runtime helpers (`hsx_stdio_*`, mailbox wrappers, SVC shims) observe a consistent layout at `[SP + 4]`, `[SP + 8]`, and so on.

This ABI keeps three-argument syscalls fast while guaranteeing a deterministic path for argument #4 and beyond. Once the compiler and libraries adopt the spill logic, existing helpers can remove ad-hoc buffers and rely on the shared calling convention.


---

## 4. Executive Kernel

### Purpose
The executive runs alongside the VM (native firmware on-device or the host \execd\ process) and implements:
- Process/task table, ready queues, and scheduling.
- Memory arenas (task stacks/heaps, mailbox pool, value table).
- Syscall dispatch to HAL drivers (FS, UART, CAN) and higher-level services (mailboxes, values, exec).
- IPC via the mailbox subsystem and shared value registry.

The VM itself remains single-task. The executive selects which task runs by updating the active register/stack bases and then invoking \m.step()\. When no executive is attached, the VM defaults to a single foreground task with local stdio/mailbox shims.
### Process Descriptor
```
typedef int32_t hsx_pid_t;


typedef struct {
  uint32_t pc;            // stored separately from reg window
  uint32_t psw;           // flags / condition bits (mirror of VM.flags)
  uint32_t reg_base;      // base pointer in VM memory for general-purpose regs
  uint32_t stack_base;    // base pointer in VM memory for stack frame
  uint32_t stack_limit;   // guard for overflow checks
  uint32_t time_slice_steps;   // scheduler weight (instructions per rotation)
  uint32_t accounted_steps;    // lifetime instruction count for load metrics
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
- **No bulk snapshot:** register windows live in VM RAM, so swapping `reg_base`/`stack_base` is sufficient; the executive does not copy register files between tasks.
- **Isolation:** each task's memory arena (stack/heap) is disjoint. `stack_limit` enables overflow detection and debugging.

### Scheduling Model
- **Round-robin, single instruction:** each runnable task executes exactly one HSX instruction per scheduler turn. After the instruction retires, the executive rotates to the next READY task.
- **Priority weights:** `time_slice_steps` can increase the number of consecutive instructions a task receives before rotating. The default host configuration sets this to `1` for strict fairness.
- **Tick vs tickless:** the host executive optionally runs in a soft tick (auto step N instructions repeatedly). Hardware ports can use a timer interrupt to request reschedule when a quantum expires or the next event fires.
- **Accounting:** the executive accumulates `accounted_steps` per task to report instruction usage / load averages to shell clients.
- Tasks may `yield`, `sleep_ms`, `wait`, `exec_exit`, or block on mailbox receive; the executive moves them between READY/RUN/SLEEP queues accordingly.

#### Executive stepping controls
- `clock start` / `clock stop` toggle the background loop that repeatedly issues `vm.step()`.
- `clock step [steps]` (or the legacy `step [steps]`) retires a precise number of guest instructions. Without arguments the command uses the configured batch size; adding `-p <pid>` restricts execution to a single task.
- Shell status output tracks the cumulative `accounted_steps` per task along with manual/auto step counters, making deterministic replay straightforward.

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
- Named channels use the `svc:name`, `app:name`, and `shared:name` namespaces (for example `svc:stdio.out`, `app:telemetry`, `shared:events`).

#### Mailbox namespace rules
- `svc:` descriptors are provisioned per task (`svc:stdio.*`) but may be accessed cross-task with an explicit `@<pid>` suffix (`svc:stdio.out@5`). Binding the bare name yields the caller’s private channel.
- `app:` descriptors without a suffix are global and reusable. Any task (including PID 0 / host) that calls `MAILBOX_BIND` or `MAILBOX_OPEN` on `app:<name>` receives the same descriptor. Use `app:<name>@<pid>` to create a PID-scoped variant with private ownership.
- `shared:` descriptors are always global and are the only namespace that supports fan-out semantics (`HSX_MBX_MODE_FANOUT[_DROP|_BLOCK]`). Suffixes are ignored.
- Access control and delivery policy are governed by the bind mode mask (`HSX_MBX_MODE_RDWR`, `*_FANOUT_*`, `HSX_MBX_MODE_TAP`).
- Handles are small integers scoped to the calling task; they remain valid until `MAILBOX_CLOSE`. Multiple handles can reference the same descriptor and inherit its namespace/fan-out behaviour.

The shell mirrors the namespace model: `mbox shared`, `mbox ns app`, or `mbox pid 7` surface filtered descriptor snapshots, while `listen`/`send` forward to `MAILBOX_OPEN`/`SEND` using the same naming rules.

**Message frame**
- Each entry stores a fixed header (`struct hsx_mbx_msg { uint16_t len; uint16_t flags; uint16_t src_pid; uint16_t channel; }`) followed by payload bytes. Payload length is clamped to the descriptor capacity minus the header size.
- Flag bits include `MBX_FL_STDOUT`, `MBX_FL_STDERR`, and `MBX_FL_OOB` so stdio and control traffic can share the transport without ambiguity.

**Blocking semantics**
- `MAILBOX_RECV` with an empty queue transitions the task to WAIT_MBX. The executive parks the task until a sender enqueues data, or a timeout (poll/finite/infinite) expires.
- `MAILBOX_SEND` wakes exactly one waiter per descriptor on successful enqueue; additional waiters remain queued. Non-blocking sends report `HSX_MBX_STATUS_WOULDBLOCK`.
- The VM reports wait/wake events (`mailbox_wait`, `mailbox_wake`, `mailbox_timeout`) so an attached executive can update run queues. In standalone mode the VM simply keeps the task paused until a message arrives.

**Scheduling interactions**
- The executive observes mailbox events and schedules tasks accordingly; standalone mode performs the same transitions internally.
- Blocking sends respect the same timeout semantics; a timeout transitions the task back to READY with an error code.



**Profiles**
- Embedded targets can enable only the `svc:` namespace plus per-task control mailboxes to conserve RAM; optional features such as taps or `shared:` mailboxes are host-prototype extras.
- Regardless of profile, blocking receive semantics remain available so HSX tasks can sleep until messages arrive without consuming VM cycles.

**Shell and stdio integration**
- The executive may register passive taps (`MAILBOX_TAP`) to mirror traffic to the shell or telemetry sinks without consuming the message.
- Default channels created at spawn are `svc:stdio.in`, `svc:stdio.out`, `svc:stdio.err`, and `pid:<pid>` (control). The HSX stdio shim maps `stdin`/`stdout`/`stderr` onto these handles and exposes `listen`/`send` shell commands for operator interaction.
- Shell access to another task's stdio uses an explicit pid suffix (e.g. `svc:stdio.out@5`); without a suffix the call resolves to the caller's private channel.
- Shell commands `listen` and `send` wrap the mailbox OPEN/SEND/RECV calls to stream stdout and inject stdin from the executive shell.
- The `mbox` shell command uses `mailbox_snapshot()` and supports namespace filters (`mbox shared`, `mbox ns app`, `mbox pid 3`) to surface global descriptors such as `app:` and `shared:` mailboxes.
- Calling convention: mailbox traps place arguments in `R1..R5` (see table below) and return a status code in `R0`; when `MAILBOX_RECV` succeeds and an info pointer is provided, the executive writes a `hsx_mailbox_recv_info` record before returning.
- Status codes and MAILBOX_* function IDs are sourced from `include/hsx_mailbox.h`; syscalls return status in `R0` (0 = ok) with result values placed in `R1`-`R3` depending on the call.
- Trace hooks record `{timestamp, src_pid, dst_handle, flags, len}` when tracing is enabled, providing visibility into inter-task communication.
- Constants live in `include/hsx_mailbox.h`; Python tooling scrapes the header so both runtimes stay aligned.

This design reuses the prior circular-buffer implementation while extending the naming model and stdio routing needed by the multi-task executive.

**Mailbox ABI reference**

| Call            | `R1`            | `R2`            | `R3`           | `R4`            | `R5`                         |
|-----------------|-----------------|-----------------|----------------|-----------------|------------------------------|
| `MAILBOX_OPEN`  | `target_ptr`    | `flags`         | —              | —               | —                            |
| `MAILBOX_BIND`  | `target_ptr`    | `capacity`      | `mode`         | —               | —                            |
| `MAILBOX_SEND`  | `handle`        | `payload_ptr`   | `length`       | `flags`         | `channel`                    |
| `MAILBOX_RECV`  | `handle`        | `buffer_ptr`    | `max_length`   | `timeout`       | `info_ptr` (nullable)        |
| `MAILBOX_PEEK`  | `handle`        | —               | —              | —               | —                            |
| `MAILBOX_TAP`   | `handle`        | `enable` (0/1)  | —              | —               | —                            |
| `MAILBOX_CLOSE` | `handle`        | —               | —              | —               | —                            |

Timeout semantics (`MAILBOX_SEND`/`MAILBOX_RECV`):
- `HSX_MBX_TIMEOUT_POLL` (`0x0000`): do not block; return `HSX_MBX_STATUS_NO_DATA` / `HSX_MBX_STATUS_WOULDBLOCK`.
- `0x0001..0xFFFE`: relative timeout in milliseconds (host VM prototype).
- `HSX_MBX_TIMEOUT_INFINITE` (`0xFFFF`): block until data is available.

On successful `MAILBOX_RECV`, if `info_ptr` is non-null the executive writes a `hsx_mailbox_recv_info` structure containing `{status, length, flags, channel, src_pid}` before returning control to the task.

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

Arguments pass in R0-R3 (additional buffers via pointers); results return in R0. The executive may extend the table with experimental modules, but apps should rely only on the IDs above for portable behaviour.

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

The new `--exec-root` flag lets the host VM enumerate payload `.hxe` files and run them via an exec syscall shim--mirroring the embedded design.

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
---

## 12. Roadmap Snapshot
- [ ] Finalize syscall module numbering (resolve 0x07 vs 0x03, 0x0A vs 0x06 conflict).
- [ ] Complete Python "native" shell + task manager (ps/exec/kill/stdio).
- [ ] Mailbox & value pools with FRAM persistence.
- [ ] AVR executive port using FatFs/UART/CAN drivers.
- [ ] Optional preemption via timer tick.
- [ ] Linker & `.hxo` pipeline.
- [ ] Doxygen / docs automation.

---





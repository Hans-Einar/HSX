# HSX Model — Executive + VM Integration

## Overview
HSX combines a virtual machine (VM) instruction set and a native “Executive” kernel into a single hybrid system. The VM executes bytecode, while the Executive provides process control, scheduling, I/O, and syscalls. Together, they form a **microkernel-style runtime**.

---

## Architecture Layers

| Layer | Role | Runs Native? | Description |
|-------|------|---------------|-------------|
| **VM Core** | Bytecode execution | Yes | Interprets instructions, manages registers, handles SVC traps |
| **Executive (Kernel)** | Process mgmt, scheduling, syscall dispatch | Yes | Provides task control, memory management, stdio routing, signals |
| **Drivers (HAL)** | UART, CAN, FS, timers | Yes | Fast device access, tied to native backend |
| **Shell / User Apps** | CLI, telemetry, tools | No (bytecode) | HSX programs using syscalls |

---

## Design Principles

- **Syscalls are native** — handled by backend for speed and determinism.
- **Executive is minimal** — only policy, no device logic.
- **Shell is just another app** — not required for system startup.
- **Flat memory model for now** — cooperative multitasking, later MMU simulation possible.

---

## Syscall Overview

| Module | Area | Description | Example Functions |
|---------|------|--------------|------------------|
| `0x01` | UART | Serial I/O | `WRITE`, `READ`, `WRITE_INT`, `WRITE_F16` |
| `0x02` | FS | File operations | `OPEN`, `READ`, `WRITE`, `CLOSE`, `LIST` |
| `0x03` | CAN | CAN bus access | `TX`, `RX`, `STATUS` |
| `0x07` | Exec | Process control | `EXEC`, `EXIT`, `KILL`, `WAIT`, `YIELD`, `SLEEP_MS` |
| `0x0A` | FD / Stdio | Stream I/O | `WRITE(fd,buf,len)`, `READ(fd,buf,len)`, `DUP2`, `SETSTDIO` |

---

## Executive Responsibilities

### Scheduler
- Cooperative round-robin (preemptive later)
- Keeps ready/sleep queues
- Handles yield/sleep calls

### Process Control
```c
typedef int32_t hsx_pid_t;

typedef struct {
  uint32_t pc, sp;
  uint32_t regs[16];
  uint8_t prio, state;
  int fd[8]; // stdin=0, stdout=1, stderr=2
} hsx_pcb_t;

hsx_pid_t hsx_exec(const char* path, const char* argv[], int argc, int fd0, int fd1, int fd2);
void hsx_exit(int status);
int  hsx_kill(hsx_pid_t pid, int sig);
int  hsx_wait(hsx_pid_t pid, int* status_out);
void hsx_yield(void);
void hsx_sleep_ms(uint32_t ms);
```

### FD/STDIO Management
```c
int hsx_fd_open_dev(const char* name);
int hsx_fd_write(int fd, const void* p, int n);
int hsx_fd_read(int fd, void* p, int n);
int hsx_fd_dup2(int oldfd, int newfd);
int hsx_fd_setstdio(hsx_pid_t pid, int fd0, int fd1, int fd2);
```

---

## Execution Model

1. Boot code initializes Executive.
2. Executive sets up heap, stack, process table, and devices.
3. Loads and runs `init` process (which may start shell, telemetry, etc.).
4. User tasks are created via `exec()` and run cooperatively.
5. Tasks call syscalls through SVC instructions (handled natively).

---

## Host VM Parity

The host Python VM simulates the same behavior:
- Implements syscall tables for UART, FS, CAN, Exec, FD.
- Each process has its own PCB (Python dict).
- Cooperative scheduling through cycle budgets or yield points.

---

## Example — Shell App (HSX Bytecode)

```c
int main(void) {
  char line[64];
  for (;;) {
    int n = sys_read(0, line, sizeof(line));
    if (n <= 0) { sys_sleep_ms(50); continue; }
    if (starts_with(line, "ps")) sys_tasklist();
    else if (starts_with(line, "exec ")) sys_exec(arg, argv, ...);
    else if (starts_with(line, "kill ")) sys_kill(pid, SIGTERM);
  }
}
```

---

## Preemption (Future)

- Add timer tick interrupt via VM or native ISR.
- Each tick triggers a call to `scheduler_tick()`.
- Time slicing enabled for fairness.

---

## Signals

| Signal | Meaning |
|---------|----------|
| `SIGTERM` | Graceful shutdown |
| `SIGKILL` | Immediate termination |
| `SIGUSR1/2` | User-defined actions |

---

## Next Steps

1. Define Exec + FD syscalls in `SYSCALLS.md`.
2. Add scheduler + PCB logic to host VM (Python).
3. Port same logic to native C.
4. Create loader for `.hxe` in native C.
5. Implement `init` process and optional shell autospawn.
6. Add preemption and signal delivery.

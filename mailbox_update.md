# HSX Mailbox System Update Plan

**Status:** Analysis complete — implementation pending  
**Author:** ChatGPT (for Hans Einar Øverjordet)  
**Purpose:** This document summarizes the current state of the HSX mailbox system, outlines missing functionality, and provides detailed TODO steps required to make `examples/demos/mailbox` (producer/consumer) work.

---

## 1. Overview

The **mailbox system** is intended to provide lightweight inter-process communication (IPC) within the HSX virtual machine.  
Each process has private mailboxes (`pid:`), while **shared namespaces** should allow cross-process communication.

### Implemented Namespaces
| Prefix | Namespace | Implemented | Purpose |
|---------|------------|--------------|----------|
| `svc:`  | Service    | ✅ | System-level mailboxes (stdio, logging, etc.) |
| `pid:`  | Process    | ✅ | One per PID (private) |
| `app:`  | Application | ⚠️ Stub only | Intended for app-local IPC within same app context |
| `shared:` | Shared   | ❌ Not implemented | Intended for global shared mailboxes accessible to all |

---

## 2. Current Problem

The demo in `examples/demos/mailbox` (`producer.c` and `consumer.c`) fails because:
- Both processes call `hsx_mailbox_open("shared:test")`.
- The current implementation **ignores the namespace** and creates private mailboxes **owned by each process**.
- The `consumer` cannot see the mailbox created by the `producer`.
- The `mbox` shell command lists only PID and SVC mailboxes — **no shared mailboxes are ever created or visible**.

---

## 3. Design Intent (from docs)

Based on review of:

- `docs/hsx_spec-v2.md`
- `docs/agents.md`
- `docs/milestones.md`

### Intended Behavior

> Shared mailboxes (`shared:`) should be globally accessible message queues shared between multiple processes.  
> Application mailboxes (`app:`) should be local to one app but may be visible to child processes spawned by it.

In `docs/milestones.md`:
> *Implement mailbox namespaces: app:, pid:, shared:, svc:*  
> Only `svc:` and `pid:` are functional as of v0.3.

---

## 4. What’s Missing / Broken

### A. Missing Features
1. **Namespace awareness**
   - The mailbox open/create functions don’t check for `"app:"` or `"shared:"` prefixes.
2. **Global shared mailbox table**
   - All mailboxes are stored per-process; none are truly global.
3. **Visibility filtering**
   - The shell `mbox` command filters by `owner_pid`, excluding shared mailboxes.
4. **Shared ownership**
   - No concept of owner `pid=0` or global access flag exists.
5. **Synchronization**
   - Shared mailboxes lack mutual exclusion for concurrent access (optional for v1).
6. **Documentation alignment**
   - The implementation diverges from the spec; `shared:` is declared but not functional.

---

## 5. Required Changes

### Core (C Code)
| File | Function | Change Summary |
|------|-----------|----------------|
| `src/core/hsx_mailbox.c` | `hsx_mailbox_open()` | Parse prefixes: `"shared:"`, `"app:"`, `"pid:"`, `"svc:"` |
|  | `hsx_mailbox_find()` | Split into `find_local()` and `find_global()` |
|  | `hsx_mailbox_create()` | Support creating shared mailboxes in global table |
|  | `hsx_mailbox_list()` | Show shared mailboxes regardless of PID |
|  | `hsx_mailbox_delete()` | Ensure shared deletion doesn’t affect other PIDs |
| `include/hsx_mailbox.h` | Struct + constants | Add `namespace` enum/type, define `HSX_MBOX_NS_SHARED`, `HSX_MBOX_NS_APP` |

---

## 6. Implementation Plan

### Step 1 – Add Namespace Support
- Define:
  ```c
  typedef enum {
      HSX_MBOX_NS_SVC,
      HSX_MBOX_NS_PID,
      HSX_MBOX_NS_APP,
      HSX_MBOX_NS_SHARED
  } hsx_mbox_ns_t;
  ```
- Add `hsx_mbox_ns_t ns;` to `hsx_mailbox_t`.

- Extend `hsx_mailbox_open()`:
  ```c
  if (strncmp(name, "shared:", 7) == 0)
      ns = HSX_MBOX_NS_SHARED;
  else if (strncmp(name, "app:", 4) == 0)
      ns = HSX_MBOX_NS_APP;
  ...
  ```

### Step 2 – Create Global Shared Mailbox Table
- Add static global array or list:
  ```c
  static hsx_mailbox_t shared_mailboxes[HSX_MBOX_MAX_SHARED];
  ```
- Implement helper:
  ```c
  hsx_mailbox_t* hsx_mailbox_find_global(const char* name);
  hsx_mailbox_t* hsx_mailbox_create_global(const char* name, uint16_t mode);
  ```

### Step 3 – Modify `hsx_mailbox_list()`
- Include shared mailboxes:
  ```c
  if (m->ns == HSX_MBOX_NS_SHARED ||
      m->ns == HSX_MBOX_NS_SVC ||
      m->owner_pid == pid)
      print_mbox(m);
  ```

### Step 4 – Adjust Ownership
- Shared mailboxes: `owner_pid = 0` (system).
- App mailboxes: `owner_pid = current_app_pid` (if implemented later).

### Step 5 – Verify Demo
1. Rebuild HSX VM and demo:
   ```bash
   make clean && make
   cd examples/demos/mailbox && make
   ```
2. Run consumer first:
   ```
   hsx load examples/demos/build/mailbox/consumer.hxe
   ```
3. Run producer:
   ```
   hsx load examples/demos/build/mailbox/producer.hxe
   ```
4. Check:
   ```
   hsx> mbox
   ```
   Expected:
   ```
   ID  Namespace  Owner  Depth  Bytes  Mode   Name
   -----------------------------------------------
   ...
   9   shared      0      1     26  0x0003  shared:test
   ```
5. Confirm message arrives in consumer.

### Step 6 – (Optional) Add Mutex/Lock
- For concurrent write/read safety:
  - Add spinlock or atomic flag in `hsx_mailbox_t`.
  - Wrap `read`/`write` operations.

---

## 7. Shell Integration

Update `hsx_shell_cmd_mbox()` to:
- Print namespace properly.
- Optionally add subcommands:
  - `mbox shared` — list only shared mailboxes
  - `mbox pid <n>` — list mailboxes of another process (requires privilege)

---

## 8. Verification Checklist

| Test | Expected Result |
|------|-----------------|
| `mbox` shows shared mailbox | ✅ |
| Producer writes, consumer reads | ✅ |
| Multiple consumers read same queue | ✅ (future) |
| App vs Shared namespace separation | ✅ |
| No crash if process exits | ✅ |
| Shared mailbox persists until explicitly deleted | ✅ |

---

## 9. Future Work

- `app:` namespace for intra-app messaging (not global)
- Persistence (keep shared mailboxes across program restarts)
- Asynchronous notification (events when mailbox gets new data)
- CLI tools for `mbox create`, `mbox rm`, etc.
- Support for `hsx_mailbox_sendto(pid, msg)` wrapper using shared infrastructure

---

## 10. Summary

| Area | Status | Action |
|-------|---------|--------|
| `svc:` / `pid:` | ✅ Working | None |
| `app:` | ⚠️ Declared, unused | Implement later |
| `shared:` | ❌ Missing core logic | Implement as global table |
| `examples/demos/mailbox` | 🚫 Nonfunctional | Will work once shared namespace is globalized |
| Documentation | ⚠️ Out of sync | Update `hsx_spec-v2.md` after implementation |

---

**Outcome:**  
Once the global `shared:` namespace is implemented and included in the mailbox list and lookup, the `producer` and `consumer` demos will function as intended — sending and receiving messages through a truly shared mailbox.


Mailbox Usage Patterns
======================

This guide expands on the mailbox design in `main/04--Design/04.03--Mailbox.md`
and the HXE metadata format in `docs/hxe_format.md`. It walks through the most
common communication patterns, shows how to provision declarative mailboxes, and
provides code snippets for both HSX applications and the executive shell.

Terminology
-----------

| Term | Meaning |
|------|---------|
| *Descriptor* | Kernel object that owns the mailbox ring buffer and delivery policy. |
| *Handle* | Task-local reference returned by `MAILBOX_BIND` or `MAILBOX_OPEN`. |
| *Namespace* | Prefix that scopes a descriptor (`svc:`, `pid:`, `app:`, `shared:`). |
| *Mode* | Access mask composed from `HSX_MBX_MODE_*` constants (read/write, fan-out, tap). |

Quick Reference: Namespaces
---------------------------

| Namespace | Typical Use | Notes |
|-----------|-------------|-------|
| `pid:<pid>` | Per-task control channels | Created automatically for each task. |
| `svc:<name>` | Executive owned services (stdio, control) | Optional `@<pid>` suffix binds another task's instance (`svc:stdio.out@5`). |
| `app:<name>` | Application-wide channels | Shared across all tasks unless suffixed with `@<pid>`. |
| `shared:<name>` | Broadcast telemetry and taps | Only namespace that allows fan-out modes. |

Pattern 1: Single-Reader Control Channel
---------------------------------------

Use this when exactly one consumer should drain the mailbox (for example a CLI
task reading commands from tooling).

### Declarative provisioning

```jsonc
{
  "version": 1,
  "mailboxes": [
    {
      "target": "app:control",
      "capacity": 96,
      "mode": "RDWR"
    }
  ]
}
```

### HSX application snippet

```c
#include "hsx_mailbox.h"

static const char *kControlTarget = "app:control";

void control_task(void) {
    int handle = hsx_mailbox_bind(kControlTarget, 96, HSX_MBX_MODE_RDWR);
    if (handle < 0) {
        // Retry later or escalate; descriptors may be temporarily exhausted.
        return;
    }

    uint8_t buffer[64];
    for (;;) {
        int status = hsx_mailbox_recv(handle, buffer, sizeof(buffer),
                                      HSX_MBX_TIMEOUT_INFINITE);
        if (status == HSX_MBX_STATUS_OK) {
            process_command(buffer);
        } else if (status == HSX_MBX_STATUS_TIMEOUT) {
            continue;  // keep waiting
        } else {
            // Handle NO_DATA (poll), INVALID_HANDLE, etc.
            break;
        }
    }
}
```

### Executive shell walkthrough

```
# Attach to the VM and confirm provisioning
exec> load build/apps/control_demo.hxe
exec> mbox ns app

# Send a command to the control task
exec> send app:control "status"
```

Pattern 2: Fan-Out Telemetry Broadcast
--------------------------------------

Shared telemetry streams benefit from fan-out so multiple consumers can receive
updates without blocking the producer.

### Declarative provisioning

```jsonc
{
  "version": 1,
  "mailboxes": [
    {
      "target": "shared:metrics",
      "capacity": 192,
      "mode": "RDWR|FANOUT_DROP",
      "bindings": [
        {"pid": 0, "flags": 0x0001},   // executive tap
        {"pid": 3, "flags": 0x0001}    // background logger
      ]
    }
  ]
}
```

### Producer snippet

```c
int tx_handle = hsx_mailbox_bind("shared:metrics", 192,
                                 HSX_MBX_MODE_RDWR | HSX_MBX_MODE_FANOUT_DROP);
if (tx_handle >= 0) {
    send_metric(tx_handle, "temp_c", latest_temp());
}
```

### Consumer snippet

```c
int rx_handle = hsx_mailbox_open("shared:metrics", HSX_MBX_MODE_RDONLY);
if (rx_handle >= 0) {
    uint8_t payload[128];
    while (hsx_mailbox_recv(rx_handle, payload, sizeof(payload),
                            HSX_MBX_TIMEOUT_POLL) == HSX_MBX_STATUS_OK) {
        log_metric(payload);
    }
}
```

### Operational tips

- Choose `FANOUT_DROP` to prevent slow subscribers from stalling the producer.
- Use the executive shell: `exec> mbox shared` to confirm each subscriber’s
  `last_seq` is advancing. Slow subscribers will emit `mailbox_backpressure`
  events when drops occur.

Pattern 3: Tap Monitoring for Stdio
-----------------------------------

Tap mode duplicates traffic without consuming it. This is ideal for mirroring
stdout to tooling while keeping the owning task unaffected.

### Declarative provisioning

```jsonc
{
  "version": 1,
  "mailboxes": [
    {
      "target": "svc:stdio.out@5",
      "mode": "RDWR|TAP",
      "bindings": [
        {"pid": 0, "flags": 0x0004}    // executive mirror
      ]
    }
  ]
}
```

### Executive shell walkthrough

```
exec> tap svc:stdio.out@5 on        # enable passive tap
exec> listen svc:stdio.out@5        # mirror stdout for task 5
exec> tap svc:stdio.out@5 off       # release tap when done
```

### Application considerations

- Taps never consume the message, so the owner sees identical behaviour.
- Rate limiting (configured via mailbox profiles) ensures the tap cannot starve
  the owner. Use `mailbox_snapshot` to inspect tap drop counters.

Blocking vs Polling
-------------------

Mailbox operations rely on the timeout parameter:

| Constant | Value | Behaviour |
|----------|-------|-----------|
| `HSX_MBX_TIMEOUT_POLL` | `0x0000` | Return immediately with `HSX_MBX_STATUS_NO_DATA` (recv) or `HSX_MBX_STATUS_WOULDBLOCK` (send). |
| `1..0xFFFE` | Relative milliseconds | Block for at most the requested duration. |
| `HSX_MBX_TIMEOUT_INFINITE` | `0xFFFF` | Block until data is available. |

Polling example:

```c
int status = hsx_mailbox_recv(handle, buf, sizeof(buf), HSX_MBX_TIMEOUT_POLL);
if (status == HSX_MBX_STATUS_NO_DATA) {
    // Perform other work before trying again.
}
```

Hybrid strategy:

1. Attempt a poll to process any backlog without blocking.
2. Switch to a finite timeout (for example 10 ms) to sleep briefly when idle.
3. Fall back to infinite wait for long-lived background workers.

Error-Handling Patterns
-----------------------

| Status code | Typical cause | Recommended action |
|-------------|---------------|--------------------|
| `HSX_MBX_STATUS_NO_DESCRIPTOR` | Descriptor pool exhausted | Release unused descriptors; review resource profile quotas. |
| `HSX_MBX_STATUS_WOULDBLOCK` | Send queue full in blocking mode | Retry with backoff or enable `FANOUT_DROP`. |
| `HSX_MBX_STATUS_NO_DATA` | Poll receive without pending messages | Switch to a blocking timeout when idle. |
| `HSX_MBX_STATUS_MSG_TOO_LARGE` | Payload exceeds descriptor capacity | Resize the mailbox (`capacity`) or fragment the message. |
| `HSX_MBX_STATUS_TIMEOUT` | Timeout expired before completion | Inspect event logs (`mailbox_timeout`) and adjust timeouts. |
| `HSX_MBX_STATUS_INVALID_HANDLE` | Handle closed or never opened | Re-bind/open the descriptor; ensure handles are per-task. |

For each error, the executive emits corresponding events (`mailbox_exhausted`,
`mailbox_backpressure`, `mailbox_timeout`) that can be monitored via the
event stream or shell `events` command.

Tutorial: End-to-End Request/Reply
----------------------------------

This walkthrough combines the patterns above to implement a simple request/
reply service between two HSX tasks.

1. **Declare the channel** in the HXE metadata:

   ```jsonc
   {
     "version": 1,
     "mailboxes": [
       {"target": "app:rpc", "capacity": 128, "mode": "RDWR"}
     ]
   }
   ```

2. **Responder task** binds the mailbox and waits forever:

   ```c
   int rpc_handle = hsx_mailbox_bind("app:rpc", 128, HSX_MBX_MODE_RDWR);
   for (;;) {
       uint8_t payload[96];
       if (hsx_mailbox_recv(rpc_handle, payload, sizeof(payload),
                            HSX_MBX_TIMEOUT_INFINITE) == HSX_MBX_STATUS_OK) {
           uint8_t reply[32];
           size_t reply_len = build_reply(payload, reply);
           hsx_mailbox_send(rpc_handle, reply, reply_len, 0, 0);
       }
   }
   ```

3. **Requester task** polls briefly, then blocks:

   ```c
   int rpc = hsx_mailbox_open("app:rpc", HSX_MBX_MODE_RDWR);
   uint8_t request[] = "ping";
   hsx_mailbox_send(rpc, request, sizeof(request), 0, 0);

   uint8_t reply[32];
   int status = hsx_mailbox_recv(rpc, reply, sizeof(reply), 10);
   if (status == HSX_MBX_STATUS_TIMEOUT) {
       status = hsx_mailbox_recv(rpc, reply, sizeof(reply),
                                 HSX_MBX_TIMEOUT_INFINITE);
   }
   ```

4. **Verify via shell**:

   ```
   exec> load build/apps/rpc_demo.hxe
   exec> mbox ns app
   exec> listen app:rpc --limit 5
   ```

5. **Monitor events**:

   ```
   exec> events --follow --filter mailbox
   ```

This sequence demonstrates how the producer and consumer interact, how to mix
polling with blocking waits, and how to observe the system through the shell.

Additional Resources
--------------------

- Design reference: `main/04--Design/04.03--Mailbox.md`
- ABI reference: `docs/abi_syscalls.md`
- Metadata format: `docs/hxe_format.md`
- Executive protocol events: `docs/executive_protocol.md`

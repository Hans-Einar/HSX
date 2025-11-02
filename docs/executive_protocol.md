Executive Shell Protocol
========================

This document describes the JSON-over-TCP protocol spoken between the HSX
executive daemon (`python/execd.py`) and shell clients (`python/shell_client.py`,
`python/blinkenlights.py`, or custom tooling).

Connection
----------

- Transport: TCP (default `127.0.0.1:9998`).
- Messages: one JSON object per line (UTF-8, `\n` terminator).
- Every request must include a `"cmd"` string and a protocol `"version"` (currently `1`).
- Successful responses have `{"version": 1, "status": "ok", ...}`; failures use
  `{"version": 1, "status": "error", "error": "message"}`.
- If the executive receives an unsupported version it returns
  `{"version": 1, "status": "error", "error": "unsupported_version:<n>"}` without
  executing the command.
- The `restart` command returns immediately; the targeted process shuts down after
  replying and then re-executes the same command line. Clients should expect the TCP
  connection to drop shortly after issuing the request.

Core Commands
-------------

| Command | Request Payload | Response Payload | Notes |
|---------|-----------------|------------------|-------|
| `ping` | `{ "version": 1, "cmd": "ping" }` | `{ "version": 1, "status": "ok", "reply": "pong" }` | Connectivity check. |
| `info` | `{ "version": 1, "cmd": "info" [, "pid": n] }` | `{ "version": 1, "status": "ok", "info": { ... } }` | Omitting `pid` returns global state/task list; specifying `pid` adds `selected_registers`. |
| `attach` | `{ "version": 1, "cmd": "attach" }` | `{ "version": 1, "status": "ok", "info": { ... } }` | Pauses VM and marks tasks as attached. |
| `detach` | `{ "version": 1, "cmd": "detach" }` | `{ "version": 1, "status": "ok", "info": { ... } }` | Releases VM control. |
| `load` | `{ "version": 1, "cmd": "load", "path": "/abs/app.hxe" }` | `{ "version": 1, "status": "ok", "image": { "pid": <int>, "app_name": "...", "allow_multiple_instances": true, "metadata": { ... } } }` | Loads `.hxe` into VM (works while attached). Metadata is summarised for v2 images. |
| `exec` | Same as `load` | Same as `load` | Alias used by shell clients. |
| `ps` | `{ "version": 1, "cmd": "ps" }` | `{ "version": 1, "status": "ok", "tasks": {"tasks": [...], "current_pid": n} }` | Returns scheduler snapshot (task list + active pid). |
| `clock` | `{ "version": 1, "cmd": "clock" }` | `{ "version": 1, "status": "ok", "clock": { ... } }` | Reports clock status (state, mode, throttle metadata, rate, auto/manual counters). |
| `clock` | `{ "version": 1, "cmd": "clock", "op": "start" }` | `{ "version": 1, "status": "ok", "clock": { ... } }` | Starts the auto-step clock loop (alias `op: "run"`). |
| `clock` | `{ "version": 1, "cmd": "clock", "op": "stop" }` | `{ "version": 1, "status": "ok", "clock": { ... } }` | Stops the auto-step clock loop (alias `op: "halt"`). |
| `clock` | `{ "version": 1, "cmd": "clock", "op": "step", "steps": 500 [, "pid": 2] }` | `{ "version": 1, "status": "ok", "result": { "executed": n, ... }, "clock": { ... } }` | Retires the requested number of guest instructions; add `pid` to restrict scheduling to a single task. |
| `clock` | `{ "version": 1, "cmd": "clock", "op": "rate", "rate": 10 }` | `{ "version": 1, "status": "ok", "clock": { ... } }` | Sets auto-loop rate in Hz (`0` = unlimited). |
| `step` | `{ "version": 1, "cmd": "step", "steps": 500 [, "pid": 2] }` | `{ "version": 1, "status": "ok", "result": { ... }, "clock": { ... } }` | Alias for `clock` `op: "step"`; honours the same `steps`/`pid` fields. |
| `trace` | `{ "version": 1, "cmd": "trace", "pid": 1, "mode": "on" }`<br>`{ "version": 1, "cmd": "trace", "pid": 1, "op": "export", "limit": 32 }` | `{ "version": 1, "status": "ok", "trace": { "pid": 1, "enabled": true, "buffer_size": 256 } }`<br>`{ "version": 1, "status": "ok", "trace": { "pid": 1, "capacity": 256, "count": 64, "returned": 32, "format": "hsx.trace/1", "records": [ { "seq": 17, "pc": 4096, "opcode": 57005, "ts": 1730512345.12, "changed_regs": ["R0"], "mem_access": {"op": "read", "address": 12288, "width": 4} }, ... ] } }` | Enable/disable instruction tracing or fetch the most recent trace records for a task. When no `mode` is supplied the executive toggles the existing state; `op: "export"` returns the per-task ring buffer (optionally limited via `limit`). |
| `trace.import` | `{ "version": 1, "cmd": "trace", "pid": 1, "op": "import", "records": [ { "seq": 200, "pc": 4096, "opcode": 57005 } ], "replace": true }` | `{ "version": 1, "status": "ok", "trace": { "pid": 1, "count": 1, "returned": 1, "format": "hsx.trace/1", "records": [ { ... } ] } }` | Import trace records captured offline. `replace` defaults to `true`; pass `false` (or CLI `--append`) to extend the current buffer. |
| `trace.config` | `{ "version": 1, "cmd": "trace", "op": "config", "changed_regs": "off" }`<br>`{ "version": 1, "cmd": "trace", "op": "config", "buffer_size": 512 }` | `{ "version": 1, "status": "ok", "trace": { "changed_regs": false } }`<br>`{ "version": 1, "status": "ok", "trace": { "buffer_size": 512 } }` | Configure trace behaviour; `changed_regs` controls whether register diffs are emitted in `trace_step` events, and `buffer_size` adjusts the per-task trace ring (set to `0` to disable retention). |
| `bp` | `{ "version": 1, "cmd": "bp", "op": "set", "pid": 1, "addr": 4096 }` | `{ "version": 1, "status": "ok", "pid": 1, "breakpoints": [4096] }` | Manage per-task breakpoints (`op`: `list`/`set`/`clear`/`clear_all`). |
| `vm_trace_last` | `{ "version": 1, "cmd": "vm_trace_last" [, "pid": 1] }` | `{ "version": 1, "status": "ok", "trace": { "pid": 1, "pc": 4096, "next_pc": 4100, "opcode": 57005, "flags": 3, "regs": [ ... ], "mem_access": { ... } } }` | Returns the last executed instruction snapshot (PC/opcode/flags/regs and optional memory-access metadata). |
| `disasm` | `{ "version": 1, "cmd": "disasm", "pid": 1 [, "addr": 0x1000, "count": 8, "mode": "cached" ] }` | `{ "version": 1, "status": "ok", "disasm": { ... } }` | Disassemble a slice of task memory. |
The `step`/`clock step` responses include an optional `trace_last` object mirroring the `vm_trace_last` payload so tools can poll trace data even when `trace_step` events are disabled.
| `sym` | `{ "version": 1, "cmd": "sym", "op": "addr", "pid": 1, "address": 4096 }` | `{ "version": 1, "status": "ok", "symbol": { ... } }` | Symbol table helpers (`op`: `info`/`addr`/`name`/`line`/`load`). |
| `symbols` | `{ "version": 1, "cmd": "symbols", "pid": 1 [, "type": "functions", "offset": 0, "limit": 20 ] }` | `{ "version": 1, "status": "ok", "symbols": { ... } }` | List symbols for a task with optional filtering/pagination. |
| `stack` | `{ "version": 1, "cmd": "stack", "pid": 1 [, "max": 8] }` | `{ "version": 1, "status": "ok", "stack": { ... } }` | Reconstructs the PID stack (`max` frames; defaults to executive limit). |
| `pause` | `{ "version": 1, "cmd": "pause", "pid": 1 }` | `{ "version": 1, "status": "ok", "task": { ... } }` | Pauses the specified task (global pause if `pid` omitted). |
| `resume` | `{ "version": 1, "cmd": "resume", "pid": 1 }` | `{ "version": 1, "status": "ok", "task": { ... } }` | Resumes the specified task (global resume if `pid` omitted). |
| `kill` | `{ "version": 1, "cmd": "kill", "pid": 1 }` | `{ "version": 1, "status": "ok", "task": { ... } }` | Stops auto loop, resets VM, removes task. |
| `dumpregs` | `{ "version": 1, "cmd": "dumpregs", "pid": 1 }` | `{ "version": 1, "status": "ok", "registers": { ... } }` | Includes core regs plus optional `context` metadata (base pointers, quantum, priority). |
| `vm_reg_get` | `{ "version": 1, "cmd": "vm_reg_get", "reg": 7 [, "pid": 1] }` | `{ "version": 1, "status": "ok", "pid": 1, "reg": 7, "value": 305419896 }` | Reads a single register (defaults to the currently active PID when `pid` omitted). |
| `vm_reg_set` | `{ "version": 1, "cmd": "vm_reg_set", "reg": 7, "value": 305419896 [, "pid": 1] }` | `{ "version": 1, "status": "ok", "pid": 1, "reg": 7, "value": 305419896 }` | Writes a single register via the VM controller; honours PID argument like `vm_reg_get`. |
| `peek` | `{ "version": 1, "cmd": "peek", "pid": 1, "addr": 0x200, "length": 32 }` | `{ "version": 1, "status": "ok", "data": "...hex..." }` | Reads memory from task snapshot (hex string). |
| `poke` | `{ "version": 1, "cmd": "poke", "pid": 1, "addr": 0x200, "data": "0011" }` | `{ "version": 1, "status": "ok" }` | Writes memory into task snapshot. |
| `sched` | `{ "version": 1, "cmd": "sched", "pid": 1, "priority": 5, "quantum": 2000 }` | `{ "version": 1, "status": "ok", "task": { ... } }` | Updates per-task priority and/or quantum slice. |
| `restart` | `{ "version": 1, "cmd": "restart", "targets": ["vm","exec"] }` | `{ "version": 1, "status": "ok", "restart": { ... } }` | Requests restart of VM and/or exec processes (defaults to both when omitted). |
| `shutdown` | `{ "version": 1, "cmd": "shutdown" }` | `{ "version": 1, "status": "ok" }` | Asks executive server to exit. |
| `session.open` | `{ "version": 1, "cmd": "session.open", "client": "hsxdbg", "capabilities": {"features":["events","stack"], "max_events":256}, "pid_lock": 1 }` | `{ "version": 1, "status": "ok", "session": { "id": "<uuid>", "heartbeat_s": 30, "features": ["events","stack"], "pid_lock": 1 } }` | Negotiate capabilities, optional PID locks, and heartbeat interval. |
| `session.keepalive` | `{ "version": 1, "cmd": "session.keepalive", "session": "<id>" }` | `{ "version": 1, "status": "ok" }` | Refresh idle timer; required at least once per heartbeat interval. |
| `session.close` | `{ "version": 1, "cmd": "session.close", "session": "<id>" }` | `{ "version": 1, "status": "ok" }` | Release locks, cancel event subscriptions, and free session resources. |
| `events.subscribe` | `{ "version": 1, "cmd": "events.subscribe", "session": "<id>", "filters": {"pid":[1,3], "categories":["trace_step","debug_break"]} }` | Stream of newline-delimited event objects; initial reply `{ "version":1, "status":"ok", "events":{"max":256} }`. | Opens long-lived event stream; see “Event Streaming” below. |
| `events.unsubscribe` | `{ "version": 1, "cmd": "events.unsubscribe", "session": "<id>" }` | `{ "version": 1, "status": "ok" }` | Stop event delivery for the session. |
| `events.ack` | `{ "version": 1, "cmd": "events.ack", "session": "<id>", "seq": 2048 }` | `{ "version": 1, "status": "ok" }` | Inform executive that events <= `seq` have been processed (optional for eager reclamation). |

Clock status payloads expose additional telemetry beyond the base running flag:

- `mode`: qualitative state of the auto-loop (`active`, `rate`, `sleep`, `throttled`, `idle`, `paused`, `stopped`).
- `throttled` / `throttle_reason`: whether the scheduler is intentionally slowed (e.g. all tasks blocked on mailboxes).
- `last_wait_s`: most recent sleep duration scheduled by the auto loop.

Task Model
----------

- The executive maintains an in-memory task table keyed by PID.
- PID `0` reserves the image that was already loaded when the executive
  attaches to a running VM.
- `load`/`exec` create new tasks with incrementing PIDs and resume execution.
- `kill` clears the VM instance and removes the task entry.
- Task entries include `state` (`running`, `ready`, `paused`, `stopped`, `terminated`),
  `pc`, `sleep_pending`, and metadata fields such as `program` and `stdout`.
- `ps` responses include the active PID (`current_pid`) so clients can highlight the
  task currently mapped into the VM engine.
- `peek`/`poke` operate on the stored task snapshot; when a task is reactivated the
  modified memory is restored before execution resumes.
- `info` responses include the task list; adding `"pid": n` to the request also returns
  the corresponding register snapshot under `selected_registers`.
- The `restart` command accepts target names (`vm`, `exec`); the shell handles its own
  restart locally when requested.

Error Handling
--------------

- Missing required fields yield `status: "error"` with a validation message.
- Underlying VM errors (e.g., `no image loaded`, `unknown pid`) are surfaced as
  error strings.
- Clients should treat any non-`ok` status as fatal for that operation.

Example Session
---------------

```
> {"version":1,"cmd":"attach"}
< {"version":1,"status":"ok","info":{"program":"/path/main.hxe",...}}

> {"version":1,"cmd":"load","path":"/tmp/demo.hxe"}
< {"version":1,"status":"ok","image":{"pid":1,"entry":0,"code_len":96,"app_name":"demo","allow_multiple_instances":false,"metadata":{"sections":3,"values":2,"commands":1,"mailboxes":1}}}

> {"version":1,"cmd":"ps"}
< {"version":1,"status":"ok","tasks":{"tasks":[{"pid":0,"state":"running","app_name":"vm"},{"pid":1,"state":"running","app_name":"demo","metadata":{"values":2,"commands":1,"mailboxes":1}}],"current_pid":0}}

> {"cmd":"pause","pid":1}
< {"status":"ok","task":{"pid":1,"state":"paused",...}}
```

Clients are encouraged to reuse TCP connections and throttle polling (`info`,
`ps`, `dumpregs`) to avoid hammering the executive.

### Metadata summary (HXE v2)

- The `load` response contains an `image.metadata` object for v2 images. The executive currently reports the number of sections and pre-registered resources (`values`, `commands`, `mailboxes`).
- `ps`/`info` task entries echo the resolved `app_name` and include a lightweight `metadata` summary when declarative resources were present. These counts reflect the registries active inside the executive after preprocessing and can be used by debugger clients to decide whether to query additional detail.
- Declarative mailboxes are bound during load via the existing mailbox manager, so subsequent mailbox RPCs (`mailbox_snapshot`, `mailbox_bind`, etc.) treat metadata-driven mailboxes exactly like runtime-created instances.
- `mailbox_snapshot` responses include a `stats` object summarising descriptor usage (active vs. maximum), memory footprint (bytes used/available), aggregate queue depth, and per-PID handle counts alongside the per-descriptor list.

Debugger Sessions & Event Streaming
-----------------------------------

1. **Open a session**
   ```json
   {
     "version": 1,
     "cmd": "session.open",
     "client": "hsxdbg",
     "capabilities": {
       "features": ["events","stack","watch"],
       "max_events": 256
     },
     "pid_lock": 2
   }
   ```
   Response:
   ```json
   {
     "version": 1,
     "status": "ok",
     "session": {
       "id": "2deab3e2-1c6d-4eab-a52c-9c5f4fcf8c79",
       "heartbeat_s": 30,
       "features": ["events","stack","watch"],
       "pid_lock": 2
     }
   }
   ```
   - `pid_lock` is optional; omit or set to `null` for passive (read-only) monitoring.
   - Unsupported capabilities are returned in `session.warnings` (e.g., `unsupported_feature:watch`).
   - Out-of-range requests are clamped; warnings such as `heartbeat_clamped:<value>` or `max_events_clamped:<value>` accompany the negotiated values.
   - The response echoes the negotiated `max_events` depth for the event queue.

2. **Subscribe to events**
   ```json
   {
     "version": 1,
     "cmd": "events.subscribe",
     "session": "2deab3e2-1c6d-4eab-a52c-9c5f4fcf8c79",
     "filters": {
       "pid": [2],
       "categories": ["debug_break", "trace_step", "scheduler", "mailbox"],
       "since_seq": null
     }
   }
   ```
   Reply (one-time):
   ```json
   {
     "version": 1,
     "status": "ok",
     "events": {
       "token": "sub-934d5016",
       "max": 512,
       "retention_ms": 5000,
       "cursor": 42,
       "pending": 0,
       "high_water": 0,
       "drops": 0
     }
   }
   ```
   `pending` counts events that have been delivered but not yet acknowledged, `high_water` captures the largest backlog observed for the subscription, and `drops` reports how many queue overflows have been trimmed on this connection.

   Then the executive streams JSON events, one per line:
   ```json
   {"seq":17,"ts":1739730951.512,"type":"debug_break","pid":2,"data":{"pc":4096,"symbol":"main.loop","reason":"BRK"}}
   ```

3. **Acknowledge events (optional)**
   ```json
   {
     "version": 1,
     "cmd": "events.ack",
     "session": "2deab3e2-1c6d-4eab-a52c-9c5f4fcf8c79",
     "seq": 32
   }
   ```
   Reply:
   ```json
   {
     "version": 1,
     "status": "ok",
     "events": {
       "pending": 12,
       "high_water": 80,
       "drops": 1,
       "last_ack": 32
     }
   }
   ```
   Acknowledgements advance the subscriber cursor. The executive evicts events once every subscriber has ACKed past the sequence or when the retention timer expires (default 5 seconds). Clients that cannot keep up must still ACK to advertise their new high-water mark; otherwise the executive emits `warning` events with reason `slow_consumer`, and if the backlog keeps growing it sends `slow_consumer_drop` before tearing the subscription down. Both warnings include the current `pending`, `high_water`, and `drops` counters so tooling can surface precise back-pressure diagnostics.

4. **Unsubscribe / close**
   ```json
   { "version": 1, "cmd": "events.unsubscribe", "session": "<id>" }
   ```
   ```json
   { "version": 1, "cmd": "session.close", "session": "<id>" }
   ```
   - Each subscription reply includes a `token`. The executive automatically tears down the stream when the TCP connection closes, when `events.unsubscribe` is called, or when the owning session expires.

Task state events
~~~~~~~~~~~~~~~~~

- Every task transition generates a `task_state` event with the shape:
  ```json
  {
    "type": "task_state",
    "pid": 1,
    "data": {
      "prev_state": "running",
      "new_state": "paused",
      "reason": "debug_break",
      "details": {
        "pc": 8192,
        "phase": "pre"
      }
    }
  }
  ```
  - `prev_state` and `new_state` mirror the scheduler-level state strings reported by `ps`.
  - `reason` captures why the transition occurred. The executive emits at least the following reasons: `loaded`, `debug_break`, `sleep`, `mailbox_wait`, `mailbox_wake`, `timeout`, `returned`, and `killed`. Additional reasons such as `resume`, `user_pause`, or other tooling-specific annotations may be added over time; clients must tolerate unknown values.
  - `details` is optional metadata that may include mailbox descriptors/handles, timeout status codes, or exit status information for `returned` transitions.
- When a task disappears from the snapshot (e.g., after `kill` or normal exit) the executive emits a final `task_state` with `new_state: "terminated"` so observers can retire stale UI entries cleanly.

Session ownership and PID locks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Include the `session` identifier with commands that mutate task state (pause/resume/kill, PID-scoped `clock`/`step`, `trace`, `reload`, `poke`, `sched`, mailbox operations, `send`, etc.).
- When a PID is locked by another session the executive replies with `{"status":"error","error":"pid_locked:<pid>"}`. Sessionless callers receive the same error.
- Missing or expired sessions return `{"status":"error","error":"session_required"}`. Use `session.keepalive` to refresh active sessions; timed-out sessions release their locks automatically.

Breakpoint management
~~~~~~~~~~~~~~~~~~~~~~

- `bp list <pid>` returns the current breakpoint list for a task (`{"pid": <pid>, "breakpoints": [...]}`).
- `bp set <pid> <addr>` adds a breakpoint (addresses accept decimal or 0x-prefixed values).
- `bp clear <pid> <addr>` removes a breakpoint; `bp clearall <pid>` removes every breakpoint owned by the task.
- Breakpoint mutation commands require ownership of the PID via `session.open` locking; observers may still issue `bp list`.
- Breakpoints are programmed into the underlying VM debug engine; if the guest task exits the executive automatically discards stale breakpoint state.

Symbol lookup
~~~~~~~~~~~~~

- `sym info <pid>` reports whether a symbol table is loaded for the task (and provides the current path/count).
- `sym addr <pid> <addr>` resolves the nearest symbol at/before `addr`, returning the offset inside the symbol.
- `sym name <pid> <symbol>` returns symbol metadata by name; `sym line` maps addresses to source lines (when present).
- `sym load <pid> <path>` reloads symbols from an explicit file. By default the executive loads `<program>.sym` from the same directory as the HXE image after `load/exec`.
- Symbol operations are read-only for observers; `sym load` requires PID ownership so that debugger sessions do not clobber each other's settings.

Symbol enumeration
~~~~~~~~~~~~~~~~~~

- `symbols list <pid> [--type functions|variables|all] [--offset N] [--limit N]` lists entries from the cached symbol table. The response includes `count`, `offset`, and `limit` metadata so clients can paginate.
- `type` filters by symbol kind (`functions` restricts to type `function`; `variables` shows everything else). `offset` skips the first `N` entries and `limit` caps the number returned (default: return all remaining entries).
- Each returned symbol entry mirrors the `.sym` schema (`name`, `address`, `size`, `type`, `file`, `line`), enabling tooling to populate menus, autocompletion, or sidebars without re-parsing the `.sym` file.

Memory layout
~~~~~~~~~~~~

- `memory regions <pid>` reports the segments the executive knows about for a task. The response contains a `regions` array with entries describing each segment (`name`, `type`, `start`, `end`, `length`, `permissions`), along with optional `source` (e.g. `hxe` or `vm`) and `details` metadata (such as the current stack pointer).
- The executive derives the load-time segments (code, rodata, bss) from the HXE header captured during `load/exec`, and augments them with runtime regions reported by the VM (register window, stack allocation). Regions are clamped to the HSX 64 KiB address space.
- Observers can invoke the command without holding the PID lock; the data is read-only.

Watch expressions
~~~~~~~~~~~~~~~~~

- `watch list <pid>` returns all active watches for a task (`id`, `expr`, `type`, `address`, `length`, `value`, and optional `symbol`).
- `watch add <pid> <expr> [--type address|symbol] [--length N]` registers a watch. Expressions default to auto-detect (parse as integer address or resolve symbol name via the loaded `.sym`). The executive samples the watch target immediately and stores the initial value.
- `watch remove <pid> <id>` deletes a previously registered watch. Mutation commands require PID ownership via `session.open` locking.
- Watchers monitor the specified memory region (default 4 bytes) after each VM step. When the value changes the executive emits a `watch_update` event containing the old/new hex payloads, address, length, and expression metadata.

Stack reconstruction
~~~~~~~~~~~~~~~~~~~~

- `stack info <pid> [frames]` walks the saved frame pointers for the task and returns the frames still resident on the stack. The optional `frames` (RPC field `max`) clamps the number of frames to decode; the executive enforces an upper bound of 64 frames.
- Each response contains:
  ```json
  {
    "pid": 1,
    "frames": [
      {
        "index": 0,
        "pc": 4096,
        "sp": 32752,
        "fp": 32760,
        "return_pc": 4176,
        "func_name": "main",
        "func_addr": 4096,
        "func_offset": 0,
        "line_num": 42,
        "symbol": { "...": "..." },
        "line": { "...": "..." }
      }
    ],
    "truncated": false,
    "errors": [],
    "stack_base": 32768,
    "stack_limit": 32768,
    "stack_low": 32768,
    "stack_high": 36864,
    "initial_sp": 32752,
    "initial_fp": 32760
  }
  ```
- `frames[*].symbol` echoes the resolved symbol entry (when a `.sym` table is available). `func_name`, `func_addr`, and `func_offset` are promoted from this entry for convenience, and `line` / `line_num` are filled when line mappings exist.
- `return_pc` is the caller instruction pointer recovered from the stack. Leaf frames with no saved return PC leave this field `null`.
- `errors` accumulates diagnostics when the executive aborts a walk early (e.g. unaligned frame pointer, out-of-range stack address, failed memory read, or a detected FP cycle). `truncated: true` indicates the walk terminated prematurely due to these errors or because the frame limit was reached.
- The current implementation assumes tasks follow the HSX ABI convention that uses R7 as the frame pointer and stores `[prev_fp, return_pc]` at `fp`. Tasks compiled without frame pointers may report a single frame containing the current program counter.

Disassembly
~~~~~~~~~~~

- `disasm <pid> [addr] [count] [--mode on-demand|cached]` decodes instructions from task memory. `addr` defaults to the current PC if omitted and `count` defaults to eight instructions. `--mode cached` reuses the most recent listing for the address/count pair (when available) without re-reading VM memory.
- Responses look like:
  ```json
  {
    "pid": 1,
    "address": 32768,
    "count": 6,
    "requested": 8,
    "mode": "cached",
    "cached": true,
    "truncated": false,
    "bytes_read": 28,
    "data": "01100230…",
    "instructions": [
      {
        "index": 0,
        "pc": 32768,
        "size": 4,
        "mnemonic": "LDI",
        "operands": "R1 <- 0x123",
        "symbol": {"name": "main", "address": 32768, "offset": 0},
        "line": {"file": "main.c", "line": 42}
      },
      {
        "index": 1,
        "pc": 32772,
        "size": 8,
        "mnemonic": "LDI32",
        "operands": "R2 <- 0xDEADBEEF",
        "extended_word": 3735928559
      }
    ]
  }
  ```
- Each instruction entry includes the decoded `mnemonic`, operands, raw words (`word` / `extended_word`), and any available symbol/line annotations. Branch instructions report `target`/`target_symbol` when the immediate matches a known address.
- Cached responses set `cached: true`; the server maintains a small per-task cache that is invalidated whenever a task reloads or changes.

### Event object schema

| Field | Type | Description |
|-------|------|-------------|
| `seq` | uint64 | Monotonic sequence number (per executive instance). Values never repeat within a process lifetime. |
| `ts` | float | Seconds since epoch (UTC). |
| `type` | string | Event category (`trace_step`, `debug_break`, `scheduler`, `mailbox_send`, `mailbox_recv`, `watch_update`, `stdout`, `stderr`, `warning`, etc.). |
| `pid` | int or `null` | PID associated with the event (`null` for global events). |
| `data` | object | Event payload (schema depends on `type`). Unknown keys must be ignored for forward compatibility. |

Typical payloads:

- `trace_step`: `{ "pc": <uint32>, "next_pc": <uint32>, "opcode": <string>, "flags": <string?>, "regs": [<uint32> x16], "steps": <uint64?>, "changed_regs": ["R0", "PSW"]?, "mem_access": { "op": "read|write", "address": <uint32>, "width": <uint16?>, "value": <uint32?> }? }`
- `debug_break`: `{ "pc": <uint32>, "reason": "BRK" | "virtual", "breakpoint_id": <int?> }`
- `scheduler`: `{ "state": "switch", "prev_pid": <int>, "next_pid": <int?>, "reason": "quantum_expired|sleep|wait_mbx|paused|killed", "quantum_remaining": <int?>, "prev_state": <string?>, "post_state": <string?>, "next_state": <string?>, "executed": <int?>, "source": "auto|manual", "details": { ... }? }`
- `mailbox_send`: `{ "descriptor": <int>, "handle": <int>, "length": <int>, "flags": <uint16>, "channel": <uint16>, "src_pid": <int> }`
- `mailbox_recv`: `{ "descriptor": <int>, "handle": <int>, "length": <int>, "flags": <uint16>, "channel": <uint16>, "src_pid": <int> }`
- `mailbox_wait`: `{ "descriptor": <int>, "handle": <int>, "timeout": <uint16> }`
- `mailbox_wake`: `{ "descriptor": <int>, "handle": <int>, "status": <uint16>, "length": <int>, "flags": <uint16>, "channel": <uint16>, "src_pid": <int> }`
- `mailbox_timeout`: `{ "descriptor": <int>, "handle": <int>, "status": <uint16>, "length": <int>, "flags": <uint16>, "channel": <uint16>, "src_pid": <int> }`
- `mailbox_overrun`: `{ "descriptor": <int>, "pid": <int>, "dropped_seq": <int>, "dropped_length": <int>, "dropped_flags": <uint16>, "channel": <uint16>, "reason": <string>, "queue_depth": <int> }`
- `mailbox_error`: `{ "fn": <int>, "error": <string>, "status": <uint16?> }`
- `watch_update`: `{ "watch_id": <string>, "value": <string>, "formatted": <string?> }`
- `stdout` / `stderr`: `{ "text": <string> }`
- `warning`: `{ "message": <string>, "category": <string> }`

`trace_step.data.changed_regs` is optional and, when present, lists the architectural registers that changed relative to the previous step for the same PID. Register names follow the `R<N>` convention with `PSW` used for the processor status word; the program counter is omitted (it advances on every instruction) so consumers can focus on meaningful state deltas without post-filtering. Clients may use the list to highlight deltas without diffing the full register file.
`trace_step.data.mem_access` (when present) captures the last memory transaction performed by the instruction, including the resolved address, width in bytes, and the value read or written.

`scheduler` events fire whenever the executive hands control to a different PID (including transitions to `null` when the run queue empties). The `reason` field enumerates the cause: `quantum_expired` (round-robin rotation), `sleep` (task issued a sleep request), `wait_mbx` (blocking mailbox call), `paused` (user or debugger intervention), and `killed` (task exited or was forcibly removed). When a task shuts down cleanly the event still uses `killed`; `post_state` reports `terminated` or is omitted if the PID disappears entirely. `quantum_remaining` reflects the unused portion of the outgoing PID's configured quantum. `prev_state` mirrors the scheduler state before the switch, `post_state` captures the new state assigned to the outgoing PID, and `next_state` reports the incoming PID's state snapshot. `executed` records the instruction count the VM reported for the triggering step and `source` indicates whether the tick came from the auto-runner or a manual `step/clock`. Additional diagnostic fields may appear under `details`; clients must ignore keys they do not understand.

### Back-pressure & errors

- Each subscriber negotiates a buffer depth (`events.max`); default is 512 events with a 5 s retention window. The executive stores events once in a ring buffer and tracks per-subscriber cursors to avoid duplicating payloads.
- Clients MUST ACK monotonically increasing sequence numbers. Missing ACKs cause the executive to stall delivery after the negotiated depth; once stalled for `retention_ms` the executive emits a `warning` event (`data.reason: "backpressure"`) and drops the oldest entries before resuming.
- Dropped events generate `type:"warning"` entries with `data.reason:"event_dropped"` and `data.seq` set to the first missing sequence so clients can resynchronise via `since_seq`.
- Observer sessions (no `pid_lock`) share the same queue semantics but never block owners. When the queue is exhausted observers are unsubscribed before owner sessions are affected.
- Invalid categories trigger `status:"error","error":"unsupported_category:<name>"`.
- Missing or expired sessions return `session_required`.
- After disconnection clients should resume with `since_seq` set to the last processed sequence to avoid gaps. If the requested range was evicted the executive replies with `status:"error","error":"seq_evicted"` so clients can perform a full refresh.

Clients must continue sending `session.keepalive` within the advertised heartbeat interval (default 30 seconds). Inactivity causes the executive to close the session and release PID locks automatically. Observer sessions that lapse simply stop receiving events; owner sessions incur `pid_lock` release notifications so tooling can warn the user.


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
| `load` | `{ "version": 1, "cmd": "load", "path": "/abs/app.hxe" }` | `{ "version": 1, "status": "ok", "image": { "pid": <int>, ... } }` | Loads `.hxe` into VM (works while attached). |
| `exec` | Same as `load` | Same as `load` | Alias used by shell clients. |
| `ps` | `{ "version": 1, "cmd": "ps" }` | `{ "version": 1, "status": "ok", "tasks": {"tasks": [...], "current_pid": n} }` | Returns scheduler snapshot (task list + active pid). |
| `clock` | `{ "version": 1, "cmd": "clock" }` | `{ "version": 1, "status": "ok", "clock": { ... } }` | Reports clock status (state, mode, throttle metadata, rate, auto/manual counters). |
| `clock` | `{ "version": 1, "cmd": "clock", "op": "start" }` | `{ "version": 1, "status": "ok", "clock": { ... } }` | Starts the auto-step clock loop (alias `op: "run"`). |
| `clock` | `{ "version": 1, "cmd": "clock", "op": "stop" }` | `{ "version": 1, "status": "ok", "clock": { ... } }` | Stops the auto-step clock loop (alias `op: "halt"`). |
| `clock` | `{ "version": 1, "cmd": "clock", "op": "step", "steps": 500 [, "pid": 2] }` | `{ "version": 1, "status": "ok", "result": { "executed": n, ... }, "clock": { ... } }` | Retires the requested number of guest instructions; add `pid` to restrict scheduling to a single task. |
| `clock` | `{ "version": 1, "cmd": "clock", "op": "rate", "rate": 10 }` | `{ "version": 1, "status": "ok", "clock": { ... } }` | Sets auto-loop rate in Hz (`0` = unlimited). |
| `step` | `{ "version": 1, "cmd": "step", "steps": 500 [, "pid": 2] }` | `{ "version": 1, "status": "ok", "result": { ... }, "clock": { ... } }` | Alias for `clock` `op: "step"`; honours the same `steps`/`pid` fields. |
| `trace` | `{ "version": 1, "cmd": "trace", "pid": 1, "mode": "on" }` | `{ "version": 1, "status": "ok", "trace": { "pid": 1, "enabled": true } }` | Enable or disable instruction tracing for a task (`mode` optional to toggle). |
| `pause` | `{ "version": 1, "cmd": "pause", "pid": 1 }` | `{ "version": 1, "status": "ok", "task": { ... } }` | Pauses the specified task (global pause if `pid` omitted). |
| `resume` | `{ "version": 1, "cmd": "resume", "pid": 1 }` | `{ "version": 1, "status": "ok", "task": { ... } }` | Resumes the specified task (global resume if `pid` omitted). |
| `kill` | `{ "version": 1, "cmd": "kill", "pid": 1 }` | `{ "version": 1, "status": "ok", "task": { ... } }` | Stops auto loop, resets VM, removes task. |
| `dumpregs` | `{ "version": 1, "cmd": "dumpregs", "pid": 1 }` | `{ "version": 1, "status": "ok", "registers": { ... } }` | Includes core regs plus optional `context` metadata (base pointers, quantum, priority). |
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
< {"version":1,"status":"ok","image":{"pid":1,"entry":0,"code_len":96,...}}

> {"version":1,"cmd":"ps"}
< {"version":1,"status":"ok","tasks":{"tasks":[{"pid":0,"state":"running"},{"pid":1,"state":"running"}],"current_pid":0}}

> {"cmd":"pause","pid":1}
< {"status":"ok","task":{"pid":1,"state":"paused",...}}
```

Clients are encouraged to reuse TCP connections and throttle polling (`info`,
`ps`, `dumpregs`) to avoid hammering the executive.

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
   { "version": 1, "status": "ok", "events": { "max": 256 } }
   ```
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
   Acknowledgements allow the executive to reclaim buffer slots without waiting for timeouts. If clients do not send ACKs, events expire after the configured retention window (default 5 seconds).

4. **Unsubscribe / close**
   ```json
   { "version": 1, "cmd": "events.unsubscribe", "session": "<id>" }
   ```
   ```json
   { "version": 1, "cmd": "session.close", "session": "<id>" }
   ```

### Event object schema

| Field | Type | Description |
|-------|------|-------------|
| `seq` | uint64 | Monotonic sequence number (per executive instance). |
| `ts` | float | Seconds since epoch (UTC). |
| `type` | string | Event category (`trace_step`, `debug_break`, `scheduler`, `mailbox_send`, `mailbox_recv`, `watch_update`, `stdout`, `stderr`, `warning`, etc.). |
| `pid` | int or `null` | PID associated with the event (`null` for global events). |
| `data` | object | Event payload (schema depends on `type`). Unknown keys must be ignored for forward compatibility. |

Typical payloads:

- `trace_step`: `{ "pc": <uint32>, "opcode": <string>, "flags": <string?> }`
- `debug_break`: `{ "pc": <uint32>, "reason": "BRK" | "virtual", "breakpoint_id": <int?> }`
- `scheduler`: `{ "state": "READY|RUNNING|WAIT_MBX|SLEEPING|PAUSED|RETURNED", "prev_pid": <int?>, "next_pid": <int?> }`
- `mailbox_send` / `mailbox_recv`: `{ "descriptor": <int>, "length": <int>, "flags": <uint16>, "channel": <uint16> }`
- `watch_update`: `{ "watch_id": <string>, "value": <string>, "formatted": <string?> }`
- `stdout` / `stderr`: `{ "text": <string> }`
- `warning`: `{ "message": <string>, "category": <string> }`

### Back-pressure & errors

- Each subscriber negotiates a buffer depth (`max_events`); default is 256 events.
- When buffers fill, the executive drops oldest events and emits a `warning` event with `reason: "backpressure"`.
- Invalid categories trigger `status:"error","error":"unsupported_category:<name>"`.
- Missing or expired sessions return `session_required`.
- After disconnection clients should resume with `since_seq` set to the last processed sequence to avoid gaps.

Clients must continue sending `session.keepalive` within the advertised heartbeat interval (default 30 seconds). Inactivity causes the executive to close the session and release PID locks automatically.

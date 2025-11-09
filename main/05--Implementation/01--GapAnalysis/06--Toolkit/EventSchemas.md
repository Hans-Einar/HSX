# hsxdbg Event Schemas

This reference records the typed events emitted by the executive and parsed by
`python/hsxdbg/events.py`.  The payloads originate from the JSON protocol
described in `docs/executive_protocol.md` §5.2.  Every event shares the common
envelope:

- `seq` (int) – Executive sequence number (monotonic per server instance).
- `ts` (float) – Event timestamp (seconds since epoch).
- `type` (str) – Event category.
- `pid` (int|null) – Task identifier when applicable.
- `data` (object) – Category-specific payload described below.

`parse_event()` converts the raw envelope into typed dataclasses so debugger
front ends can rely on strong field names.

## TraceStepEvent

Fields extracted from `data`:

| Field | Type | Description |
| --- | --- | --- |
| `pc` | int? | Program counter before the instruction |
| `next_pc` | int? | Next PC when the VM reports it |
| `opcode` | int? | Decoded opcode byte |
| `flags` | int? | PSW after execution |
| `regs` | list<int>? | Register snapshot (R0–R15), masked to 32‑bit |
| `changed_regs` | list<str> | Register names that changed since last step |
| `mem_access` | dict? | Optional memory access metadata |

## DebugBreakEvent

- `pc` – Location of the break.
- `reason` – String reason (e.g. `BRK`, `bp_hit`).
- `symbol` – Current symbol when available.

## SchedulerEvent

- `prev_pid` / `next_pid` – Task switch participants.
- `reason` – Scheduler reason string (see executive doc).
- `state` – Post-state or transition summary.

## TaskStateEvent

- `prev_state` / `new_state` – Scheduler-level states.
- `reason` – Derived reason (mailbox wait, returned, etc.).

## MailboxEvent

Emitted for `mailbox_wait`, `mailbox_wake`, `mailbox_send`, `mailbox_recv`,
`mailbox_timeout`, and `mailbox_error`.

- `descriptor` – Target mailbox name.
- `handle` – Integer handle identifier.
- `length` – Payload length when applicable.
- `channel` – Channel/index metadata.
- `flags` – Mode flags.

## WatchUpdateEvent

- `watch_id` – Integer handle returned by `watch add`.
- `expr` – Original expression string.
- `length` – Watched length (bytes).
- `old_value` / `new_value` – Hex string payloads.
- `address` – Concrete address (if resolvable).

## StdStreamEvent

Represents `stdout` / `stderr` streaming data:

- `stream` – Literal "stdout" or "stderr".
- `text` – UTF‑8 string contents.

## WarningEvent

- `reason` – Warning identifier (e.g. `slow_consumer`).
- `details` – Remaining payload entries (`subscription`, `pending`, etc.).

## BaseEvent

For unrecognised categories, `parse_event()` returns `BaseEvent` exposing the
original `data` object so future event types can be consumed without requiring
immediate hsxdbg upgrades.

## Integration Notes

- `SessionManager` pipes raw executive events through `parse_event()` before
  handing them to `EventBus` subscribers.
- `EventBus.start()` can be used to pump events in the background; manually
  calling `pump()` is still supported for deterministic tests.
- Front ends should prefer the typed dataclasses rather than inspecting raw
  JSON to minimise breakage when new fields appear.

# Mailbox Implementation Plan

## Scope
- Implement mailbox subsystem covering delivery modes (single-reader, fan-out, tap) and wait/wake integration (DR-6.1, DG-6.1–6.4).
- Provide SVC handlers for module 0x05 (`OPEN/BIND/SEND/RECV/PEEK/TAP/CLOSE`) with back-pressure policies (DR-6.1, DG-6.2).
- Emit mailbox-related events for debugger/tooling (`mailbox_send`, `mailbox_recv`, `mailbox_timeout`) (DR-8.1, DG-5.2).

## Preconditions
- Executive scheduler/event system available to block/unblock PIDs (DR-5.1, DG-5.1).
- Shared ABI table (`shared/abi_syscalls.md`) defines module 0x05 function IDs.
- Resource budgets for descriptor pools configured per `shared/resource_budgets.md` (DR-5.2).

## Postconditions
- Mailbox module exposes a reusable library (to be split later) with deterministic semantics and status codes matching `docs/abi_syscalls.md`.
- Events integrate with executive stream and CLI tooling; drop/overrun warnings logged.
- Module-level tests (see `(6)/system/Mailbox_tests.md`) validate delivery modes, timeouts, overflow policies.

## Public Interfaces
| Func | SVC ID | R1 | R2 | R3 | R4 | R5 | Returns | Errors/Notes |
|------|--------|----|----|----|----|----|---------|--------------|
| `MAILBOX_OPEN` | `0x0500` | target_ptr | flags | – | – | – | `status`, `handle` | `ENOENT`, invalid namespace. |
| `MAILBOX_BIND` | `0x0501` | target_ptr | capacity | mode_mask | – | – | `status`, `descriptor` | `ENOMEM` when pool exhausted. |
| `MAILBOX_SEND` | `0x0502` | handle | payload_ptr | length | flags | channel | `status`, bytes_sent | `EAGAIN` / `ETIMEDOUT` depending on policy. |
| `MAILBOX_RECV` | `0x0503` | handle | buffer_ptr | max_len | timeout | info_ptr | `status`, bytes_read | `ETIME`, `ENODATA`. |
| `MAILBOX_PEEK` | `0x0504` | handle | – | – | – | – | `status`, depth/bytes | Non-destructive. |
| `MAILBOX_TAP` | `0x0505` | handle | enable | – | – | – | `status` | Enable/disable tap list. |
| `MAILBOX_CLOSE` | `0x0506` | handle | – | – | – | – | `status` | Releases handle; descriptor GC when refcount zero. |

## Implementation Notes
- Use descriptor structs defined in `(3.3)mailbox.md`; maintain waiters + taps + seq numbers.
- Back-pressure: respect `FANOUT_BLOCK` / `FANOUT_DROP`; log `overrun` events when packets dropped (refactorNotes mailbox section).
- Ensure stdio mailboxes (`svc:stdio.in/out/err`) follow DG-6.4 policy.
- Provide hooks for tracing (`mailbox_wait/wake`) to scheduler.

## Playbook
- [ ] Port mailbox manager from Python executive into dedicated module doc (no code yet; plan API + data).
- [ ] Define error/status enums shared with tooling.
- [ ] Document memory footprint knobs (descriptor count, ring size) tied to resource budgets.

## Tests
- See `(6)/system/Mailbox_tests.md` for delivery/timeout/overflow scenarios and fixtures.

## Commit Log
- _Pending_.

## Traceability
- **DR:** DR-5.1, DR-5.2, DR-6.1, DR-8.1.
- **DG:** DG-5.1–5.3, DG-6.1–6.4, DG-8.2.
- **DO:** DO-6.a (future namespace extensions).

# Mailbox Test Plan

## DR Coverage
- DR-6.1: Delivery semantics (first-reader, all-readers, tap) + back-pressure policies.
- DR-5.1 / DR-5.2: Scheduler wait/wake + resource budgets.
- DR-8.1: Event emission for tooling (mailbox_* events).

## Test Matrix
| Area | Test | Notes |
|------|------|-------|
| Delivery modes | Simulate first/all/tap readers consuming messages | Ensure semantics match (3.3) doc.
| Back-pressure | Fill ring buffer under FANOUT_BLOCK vs FANOUT_DROP | Expect block vs EAGAIN/overrun events.
| Timeout/Wait | MAILBOX_RECV with timeout, confirm scheduler transitions | Validate WAIT_MBX ? READY paths.
| Event stream | Trigger send/recv/timeouts and inspect emitted events | Must match executive_protocol. |

## Fixtures / Mocks
- Place sample payloads under (6)/fixtures/mailbox/ (TBD).
- Use scheduler mock (in (6)/mocks) to simulate wake notifications.

# Executive Test Plan

## DR Coverage
- DR-5.1–5.3: Scheduler fairness, resource budgets, persistence workflows.
- DR-8.1: Session/event streaming (subscribe, ack, reconnect).
- DR-2.5: EXEC_GET_VERSION handshake.

## Test Matrix
| Area | Test | Notes |
|------|------|-------|
| Scheduler contract | Step-per-instruction, PID rotation checks | Compare against DG-5.4 expectations. |
| Event stream | Subscribe -> send events -> ack/drop scenarios | Validate warning + recovery. |
| Resource telemetry | Simulate low-memory targets, confirm warnings | Ties into docs/resource_budgets.md. |
| Persistence | Provisioning + FRAM rollback tests | Aligns with provisioning module cases. |

## Tooling
- Python pytest integration harness (python/tests/test_exec_smoke.py + new suites).
- Manual CLI smoke for session attach/detach.

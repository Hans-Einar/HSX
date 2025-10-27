# HAL Implementation Plan (UART/CAN/FRAM/FS/GPIO/Timers)

## Scope
- Document HAL-facing syscall domains: UART (0x10), CAN (0x11), FRAM (0x12), FS (0x13), GPIO (0x14), Timers (0x15), Timebase (0x16) (see `shared/abi_syscalls.md`).
- Define thin abstraction layers so Executive can delegate hardware work without embedding logic.

## Preconditions
- Hardware drivers (platform layer) expose non-blocking APIs; resource budgets available for buffers.
- Security/policy doc (`shared/security.md`) to govern access where needed.

## Postconditions
- Clear syscall contracts for each HAL domain; ready for future code extraction.
- Test plans in `(6)` cover each domain with mocks/fixtures.

## Public Interfaces (summary)
| Domain | Key Funcs | Notes |
|--------|-----------|-------|
| UART (`0x10`) | `UART_CONFIG`, `UART_READ`, `UART_WRITE` | Essential for provisioning relay + CLI; include baud/config flags. |
| CAN (`0x11`) | `CAN_TX`, `CAN_RX`, `CAN_CONFIG` | Used by provisioning + value transport. |
| FRAM (`0x12`) | `FRAM_READ`, `FRAM_WRITE`, `FRAM_ERASE`, `FRAM_STAT` | Backing store for persistence DR-5.3. |
| FS (`0x13`) | `FS_OPEN`, `FS_READ`, `FS_WRITE`, `FS_LISTDIR`, `FS_DELETE` | Simple virtual FS for manifests/logs. |
| GPIO (`0x14`) | `GPIO_CONFIG`, `GPIO_SET`, `GPIO_GET`, `PWM_SET` | Optional HAL utilities. |
| Timers (`0x15`) | `TIMER_ALLOC`, `TIMER_START`, `TIMER_STOP`, `TIMER_WAIT` | Provides deterministic waits/timeouts. |
| Timebase (`0x16`) | `TIME_NOW`, `TIME_SLEEP_UNTIL`, `TIME_RATE` | Unified time reference for scheduler + modules.

## Implementation Notes
- Keep HAL modules as no-op documentation until hardware port begins; note expected buffer sizes and error codes.
- Link to resource budgets for memory footprints.
- Provide mock strategy for `(6)/mocks` to test HAL-dependent modules.

## Playbook
- [ ] Flesh out per-domain syscall tables (args, return, errors, time base) once spec finalised.
- [ ] Coordinate with provisioning + toolbox modules that consume these APIs.

## Tests
- See `(6)/system/HAL_tests.md` once defined; leverage mocks to simulate hardware responses.

## Commit Log
- _Pending_.

## Traceability
- **DR:** DR-1.1, DR-5.2, DR-5.3, DR-6.1 (when using UART/CAN for IPC).
- **DG:** DG-6.x, DG-7.3, DG-5.3 (time base).
- **DO:** DO-mailbox-ns (if HAL adds new namespaces).

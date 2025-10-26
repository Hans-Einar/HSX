# HAL Test Plan

## DR Coverage
- DR-1.1 / DR-5.2 / DR-5.3: HAL services for transports + persistence.
- DR-6.1: Mailbox-backed stdio requires UART/CAN shims.

## Test Matrix
| Domain | Test | Notes |
|--------|------|-------|
| UART | Configure/read/write sequences using mocks | Validate baud config & buffering. |
| CAN | TX/RX frame flow with filters | Ensure integration with provisioning/vector tests. |
| FRAM | Read/write/erase cycles with CRC | Align with persistence layout. |
| FS | Open/write/list ops using RAM-backed FS | Optional but document behaviour. |
| GPIO/Timers | Basic config + timer waits | Provide deterministic mocks for exec tests. |

## Fixtures / Mocks
- HAL mocks reside under (6)/mocks/hal/ (TBD).

# ABI Syscalls Catalogue

> Authoritative list of syscall modules/functions referenced by implementation docs. IDs TBD unless noted. Update here first, then propagate to design/exec/toolchain.

| Module | ID (hex) | Namespace / Domain | Key Functions / Notes |
|--------|---------|---------------------|-----------------------|
| Executive Control | 0x06 (fixed) | exec_core | GET_VERSION, SCHED_CTRL, SESSION_OPEN/CLOSE, SLEEP_MS, YIELD. Dispatcher remains in Executive. |
| Mailbox | 0x05 | mailbox | OPEN, BIND, SEND, RECV, PEEK, TAP, CLOSE. Semantics in mailbox module spec (DR-6.1). |
| Value Registry | 0x07 | al | REGISTER, LOOKUP, GET, SET, LIST, SUB, PERSIST. FP16 payloads + auth policy. |
| Command Registry | 0x08 | cmd | REGISTER, LOOKUP, CALL_SYNC, CALL_ASYNC, HELP. Token/pin enforcement. |
| UART (reserved) | 0x10 | uart | CONFIG, READ, WRITE. Hooks into HAL drivers. |
| CAN (reserved) | 0x11 | can | TX, RX, CONFIG_FILTERS. For provisioning + value transport. |
| FRAM / EEPROM (reserved) | 0x12 | ram | READ, WRITE, ERASE, STAT. Supports DR-5.3 persistence. |
| File/Storage (reserved) | 0x13 | s | OPEN, READ, WRITE, LISTDIR, DELETE. Lightweight object store for manifests/logs. |
| GPIO (reserved) | 0x14 | gpio | CONFIG_PIN, SET, GET, PWM. |
| Timers (reserved) | 0x15 | 	imers | ALLOC, START, STOP, WAIT. Provides consistent time base (DG-timebase). |
| Timebase / Clock (reserved) | 0x16 | 	imebase | NOW, SLEEP_UNTIL, GET_FREQ. Aligns with scheduler DR-5.1. |
| Provisioning (reserved) | 0x17 | prov | IMAGE_STATUS, LOAD, ABORT, FRAM_CHECK. Leverages provisioning module. |

*Reminder:* module IDs >= 0x10 are reserved for HAL/provisioning. Update this table before adding new SVC handlers.

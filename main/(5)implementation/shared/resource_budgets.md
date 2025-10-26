# Resource Budgets Snapshot

Source: docs/resource_budgets.md. Implementation modules must cite target budgets:

| Target | Exec (flash/RAM) | MiniVM (flash/RAM) | Mailbox pool | Stack per PID | Notes |
|--------|------------------|--------------------|--------------|--------------|-------|
| AVR128DA28 | =28 KiB / =5.5 KiB | =10 KiB / =1 KiB | ~16 descriptors (64 B ring, =1 KiB metadata) | 1.5 KiB default | Remaining headroom ˜ 8 KiB SRAM after HEOS baseline. |
| Cortex-M4 | TBD (256–512 KiB flash, 64–128 KiB RAM) | TBD | Scale descriptor pool; use CCM RAM when available | Configurable via linker script | Use AVR numbers as minimum acceptance. |

*Action:* Whenever module allocates RAM/flash, document expected footprint vs this table. Update when sizing data becomes available.

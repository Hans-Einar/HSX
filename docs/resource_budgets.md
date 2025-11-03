# HSX Resource Budgets (Draft)

> Working notes to keep the HSX executive + MiniVM within target device limits. Numbers below are estimates until we have C builds and on-target profiling data. Update as measurements arrive.

## Target profiles

| Target | Flash (program) | SRAM (data) | Non-volatile (FRAM/EEPROM) | Notes |
|--------|-----------------|-------------|----------------------------|-------|
| AVR128DA28 (HEOS host) | 128 KiB | 16 KiB | 4–8 KiB FRAM (external) | Existing HEOS shell + CAN + FS stack currently consumes ≈50% of flash/SRAM. Remaining headroom must host the HSX executive, MiniVM, and app arenas. |
| Cortex-M4 (future expansion) | 256–512 KiB | 64–128 KiB | 16–64 KiB FRAM/Flash | Provides more breathing room; treat AVR budgets as the limiting case for v1. |

## Budget assumptions (AVR128DA28)

- **Baseline usage (legacy HEOS stack):**
  - Flash: ~60 KiB (CLI, CAN, FS, boot scaffolding).
  - SRAM: ~8 KiB (CLI buffers, filesystem cache, CAN queues).
  - Leaves ~68 KiB flash and ~8 KiB SRAM for HSX features.
- **HSX executive + MiniVM targets (to validate post-port):**
  - Flash: ≤ 28 KiB (scheduler, mailbox manager, value/command adapters, VM core).
    - Executive control plane & mailbox HAL: ≤ 14 KiB.
    - MiniVM interpreter + ISA tables: ≤ 10 KiB.
    - Glue/bootstraps: ≤ 4 KiB.
  - SRAM: ≤ 5.5 KiB runtime footprint.
    - Executive state (task table, mailbox descriptors, scheduler accounting): ≤ 2 KiB.
    - MiniVM core (register window, instruction decode scratch): ≤ 1 KiB.
    - Shared buffers (mailbox payload staging, filesystem shim): ≤ 1 KiB.
    - Misc (event queue, RPC staging): ≤ 1.5 KiB.
- **HSX application arenas (per PID):**
  - Code/data image stored in flash (HSXE). For AVR, plan ≤ 8 KiB flash per app to keep updates manageable.
  - RAM per task:
    - Register bank: 64 bytes (16 × 32-bit) aligned.
    - Stack: 1.5 KiB default (configurable 1–4 KiB).
    - Mailbox handles/value bindings: ≤ 256 bytes.
  - With four concurrent PIDs the SRAM cost is ≈ 4 × (64 B + 1.5 KiB + 256 B) ≈ 7.3 KiB. That fits inside the remaining SRAM budget if the executive core holds to ≤ 5.5 KiB.

### Overheads & buffers

- Mailbox descriptor pool: start with 16 descriptors × 64 B metadata ≈ 1 KiB SRAM. Each message buffer lives in caller-owned RAM; no global payload copies beyond staging.
- Mailbox quotas: embedded profile enforces ≤16 descriptors and ≤8 handles per task; host prototype defaults to 256 descriptors and a 64 handle-per-task ceiling. Both limits are configurable via the Python `MailboxManager` profile knobs (`max_descriptors`, `handle_limit_per_pid`).
- Exhaustion handling: when the CLI reports `descriptor pool: exhausted` or `mailbox_exhausted` events appear, close surplus mailboxes/taps or increase the active profile limits before retrying the operation.

### Mailbox profile defaults

| Profile  | Descriptors | Handle limit / PID | Default capacity | Notes |
|----------|-------------|--------------------|------------------|-------|
| desktop  | 256         | 64                 | 64 bytes         | Development hosts; ample descriptors for tooling and taps. |
| embedded | 16          | 8                  | 64 bytes         | AVR reference budget; mirrors Section 4.6 fairness requirements. |

Set `HSX_MAILBOX_PROFILE=embedded` (or pass `mailbox_profile="embedded"` to `VMController`) to apply the constrained profile. Override any field by supplying a custom dict—for example `{ "max_descriptors": 32, "handle_limit_per_pid": 12 }` for mid-range MCUs.
- Event stream buffer: cap at 256 events × 16 B ≈ 4 KiB on desktop builds; shrink to 64 events × 12 B (~768 B) on AVR.
- FS cache: reuse existing HEOS buffer (already counted in baseline). Avoid duplicate buffers inside the HSX port.

### Value/command registry budgets

- Desktop reference builds target 256 values, 128 commands, and a 16 KiB string table. The embedded profile trims these to the design minimums (64 / 16 / 2 KiB) to stay within SRAM limits.
- The executive now exposes `val.stats` and `cmd.stats` RPCs; poll them during long-running tests to watch occupancy and string usage without instrumenting guest code.
- Warnings are logged via the `hsx.valcmd` logger when utilisation crosses ~80 % of capacity and clear automatically once usage falls below ~70 %.
- Maintain ≥20 % headroom in shipping profiles so descriptor churn and transient allocations never hit hard limits mid-flight.

## Action items / validation plan

| Task | Owner | When | Notes |
|------|-------|------|-------|
| Instrument current HEOS image sizes (map file / `avr-size`) | Firmware | Pre-port | Confirms baseline usage (Flash/SRAM). |
| Build MiniVM + executive C skeleton, measure `.text`, `.data`, `.bss` | Runtime | During port | Verify ≤ 28 KiB flash / 5.5 KiB SRAM target; adjust budgets or trim features. |
| Tune per-task stack size by scenario | Runtime/FW | During integration | Provide configuration knobs; document “typical” (1.5 KiB) vs maximum supported. |
| Confirm mailbox descriptor pool sizing under stress | Runtime | Post-port | Increase/decrease descriptor count as long as total SRAM stays within budget. |
| Track FRAM usage by `val.persist` | Runtime/FW | During value subsystem port | Ensure keys + persisted payloads stay within available non-volatile space (reserve ≤ 2 KiB initially). |

## Future extensions

- Cortex-M budget table mirroring the AVR table once we settle on concrete MCU SKUs.
- Per-profile linker scripts capturing stack/heap/mailbox arena reservations.
- Automation hook (post-build) to dump section sizes and compare against budget thresholds; fail CI if limits exceeded.

## Open questions

- Should we carve out shared RAM for mailbox payload staging or rely entirely on per-task buffers?
- How many concurrent HSX apps do we need on AVR vs Cortex-M deployments (impacts stack/arena totals)?
- HSX apps will be provisioned from CAN/SD at boot; we do **not** reserve flash for persistent HSXE copies on AVR targets. Leave only a small staging buffer (≤ 1 KiB) for integrity checks during load.
- Final timeout/error code addition (`HSX_MBX_STATUS_TIMEOUT`) may require per-task timer bookkeeping—keep space reserved in the executive state block (estimated 128 B).

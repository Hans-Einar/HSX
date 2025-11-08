# HSX Standard Library (`hsx_std`)

The `hsx_std` package bundles declarative metadata (values, commands, and
mailboxes) plus small helper stubs that can be linked into any HSX
application.  It is intended to capture the “always available” interfaces
that multiple binaries rely on (build information, reset hooks, log
channels, …) so every project does not have to duplicate the same
`#pragma` directives.

## Contents

| Artifact | Purpose |
|----------|---------|
| `stdlib.mvasm` | MVASM module containing the actual metadata directives and helper routines. |
| `include/hsx_stdlib.h` | Public constants documenting the reserved group/value/command identifiers plus helper prototypes. |

### Standard values (group `0xF0`)

| Value ID | Name | Flags | Notes |
|----------|------|-------|-------|
| `0x01` | `sys.version` | RO | Encodes the semantic version of the application (initialised to 0.0). |
| `0x02` | `sys.build` | RO | Build/timestamp slot; tooling can patch the initial value at link/provision time. |
| `0x03` | `sys.uptime` | RO | Intended for publishing uptime/heartbeat data. |
| `0x04` | `sys.health` | RW | Generic health indicator (0.0..1.0). |

### Standard commands (group `0xF0`)

| Command ID | Name | Handler | Description |
|------------|------|---------|-------------|
| `0x10` | `sys.reset` | `hsx_std_reset` | Gracefully exits the current task by issuing the `TASK_EXIT` trap. |
| `0x11` | `sys.noop` | `hsx_std_noop` | Placeholder command that simply returns success. |

### Standard mailboxes

| Target | Capacity | Mode |
|--------|----------|------|
| `svc:log` | 128 bytes | `RDWR | FANOUT_DROP` — shared logging ring for the executive. |
| `app:telemetry` | 96 bytes | `RDWR` — optional per-application telemetry channel. |

## Using the library

1. Add the `lib/hsx_std` directory to your include path (or rely on the repo
   default which already contains `include/`).
2. Pass `lib/hsx_std/stdlib.mvasm` as an extra input when linking.  The
   helper `build_hxe.py` already exposes `--extra <path>` for this usage:

   ```bash
   python build_hxe.py \
     --asm python/asm.py \
     --linker python/hld.py \
     --main build/app/main.mvasm \
     --extra lib/hsx_std/stdlib.mvasm \
     --out build/app/main.hxe
   ```

3. Include `hsx_stdlib.h` from C payloads if you need the reserved group or
   OID constants:

   ```c
   #include "hsx_stdlib.h"

   uint16_t sys_reset_oid = HSX_STD_OID_SYS_RESET;
   ```

No additional code is required—linking the MVASM module adds the metadata to
the final `.hxe`.  The helper stubs (`hsx_std_reset`, `hsx_std_noop`) are
available as callable symbols should a payload need to invoke them directly.

## Notes

- The current implementation only embeds metadata and very small assembly
  helpers.  Runtime upkeep of the value entries (updating uptime, stamping
  version strings, etc.) will arrive once the value/command SVCs are wired
  up in the executive.
- The MVASM specification referenced `stdlib.mvasm`; that document now points
  to this directory.

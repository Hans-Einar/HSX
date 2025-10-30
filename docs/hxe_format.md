# HXE Format Specification (Draft)

> SDP Reference: 2025-10 Main Run (Design Playbook #11)

## Purpose
Document the canonical `.hxe` executable layout so toolchain, provisioning, and runtime implementations remain aligned. This spec supports DR-3.1 (deterministic artefacts), DR-5.3 (persistence metadata), and DR-2.5 (ABI/versioning).

## Header Layout
All multi-byte fields use big-endian unless stated otherwise.

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0x00   | 4    | `magic` | ASCII `HSXE` (0x48 0x53 0x58 0x45). |
| 0x04   | 2    | `version` | Format version (initially 0x0001). |
| 0x06   | 2    | `flags` | Bitfield (bit 0: manifest presence, bit 1: allow_multiple_instances). |
| 0x08   | 4    | `entry` | Entry point offset (relative to code). |
| 0x0C   | 4    | `code_len` | Bytes in code section (aligned to 4). |
| 0x10   | 4    | `ro_len` | Bytes in read-only data section (aligned to 4). |
| 0x14   | 4    | `bss_size` | Bytes of zeroed data at runtime. |
| 0x18   | 4    | `req_caps` | Capability bitmask (HAL requirements, features). |
| 0x1C   | 4    | `crc32` | CRC over header (0x00–0x1F) + code + rodata. |
| 0x20   | 32   | `app_name` | Null-terminated ASCII app name (max 31 chars + null). |

Immediately following the header (now 64 bytes):
1. `code` section (`code_len` bytes) – executable text.
2. `rodata` section (`ro_len` bytes) – read-only data.
3. Optional embedded manifest (see below) if `flags & 0x01` is set.

## Alignment & Compatibility
- Header size fixed at 64 bytes (expanded from 32 to accommodate app_name).
- `code_len` and `ro_len` must be multiples of 4. Loader should reject unaligned lengths.
- `entry` must fall within `[0, code_len)`.
- Increment `version` whenever incompatible changes occur. Older loaders must verify `version` and fail gracefully with `unsupported_version:<n>`.

## Header Flags (`flags` at offset 0x06)
| Bit | Meaning |
|-----|---------|
| 0   | Manifest presence: If set, embedded manifest follows rodata section. |
| 1   | Allow multiple instances: If set, multiple instances of this app can be loaded simultaneously. |
| 2-15| Reserved for future use. |

**Multiple Instance Naming Convention:**
- When `allow_multiple_instances` flag (bit 1) is **not set** and an app with the same `app_name` is already loaded, the loader returns `EEXIST` error.
- When `allow_multiple_instances` flag (bit 1) is **set** and an app with the same `app_name` is already loaded, the executive appends `_#0`, `_#1`, `_#2`, etc. to create unique instance names.
- Example: If `motor_controller` is loaded twice with allow_multiple_instances=true, the instances become `motor_controller_#0` and `motor_controller_#1`.

## CRC Procedure
- Compute CRC32 (polynomial 0x04C11DB7) over:
  - Header bytes 0x00–0x1F (excluding app_name at 0x20-0x3F).
  - Code section.
  - Rodata section.
- Store result at header offset 0x1C. Loader validates CRC before executing.

## Capability Flags (`req_caps`)
Reserved bit assignments (examples):

| Bit | Meaning |
|-----|---------|
| 0   | Requires mailbox subsystem. |
| 1   | Requires value/command subsystem. |
| 2   | Requires provisioning FRAM access. |
| 3   | Requires CAN transport. |
| 4   | Requires UART transport. |
| ... | Extend as needed; document additions here. |

## Embedded Manifest (Optional)
If `flags` indicates manifest presence, append a length-prefixed structure after `rodata`:

| Field | Description |
|-------|-------------|
| `manifest_len` (4 bytes) | Size of manifest payload (big-endian). |
| `manifest` (JSON/TOML) | Contains provisioning metadata (FRAM keys, target PID, default values, mailbox names, version). |

Manifest guidelines:
- Provide `pid`, `image_name`, `version`, `required_caps`, `fram_keys` array.
- Each FRAM entry: `{ "key": 0x1234, "mode": "load"|"save"|"loadsave", "length": 16, "crc": <optional> }`.
- Provisioning doc [04.07--Provisioning.md](../main/04--Design/04.07--Provisioning.md) references this schema.

## Toolchain Responsibilities
- `hsx-llc` / `asm.py` produce `.hxo` objects consumed by linker.
- Linker `hld.py` assembles `.hxe` header, sections, CRC, and optional manifest.
- `docs/abi_syscalls.md` & `shared/abi_syscalls.md` supply capability IDs referenced in manifests.

## Loader Responsibilities
- Validate magic/version/CRC before loading.
- Allocate code/rodata/bss based on header fields.
- Apply capability checks (`req_caps`) against hardware/executive features.
- Expose manifest data to provisioning and persistence modules.

## References
- [main/04--Design/04.05--Toolchain.md](../main/04--Design/04.05--Toolchain.md)
- `docs/asm.md` (assembler CLI + metadata output)
- [main/04--Design/04.07--Provisioning.md](../main/04--Design/04.07--Provisioning.md)
- [main/05--Implementation/toolchain/formats/hxe.md](../main/05--Implementation/toolchain/formats/hxe.md)
- [main/05--Implementation/system/Provisioning.md](../main/05--Implementation/system/Provisioning.md)

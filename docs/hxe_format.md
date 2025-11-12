# HXE Format Specification (Draft)

> SDP Reference: 2025-10 Main Run (Design Playbook #11)

## Purpose
Document the canonical `.hxe` executable layout so toolchain, provisioning, and runtime implementations remain aligned. This spec supports DR-3.1 (deterministic artefacts), DR-5.3 (persistence metadata), and DR-2.5 (ABI/versioning).

## Format Versions

### Version 0x0001 (Legacy)
Original 32-byte header format. Deprecated.

### Version 0x0002 (Current)
Extended header with declarative registration sections for values, commands, and mailboxes.

## Header Layout (Version 0x0002)
All multi-byte fields use big-endian unless stated otherwise.

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0x00   | 4    | `magic` | ASCII `HSXE` (0x48 0x53 0x58 0x45). |
| 0x04   | 2    | `version` | Format version (0x0002 for current). |
| 0x06   | 2    | `flags` | Bitfield (bit 0: manifest presence, bit 1: allow_multiple_instances). |
| 0x08   | 4    | `entry` | Entry point offset (relative to code). |
| 0x0C   | 4    | `code_len` | Bytes in code section (aligned to 4). |
| 0x10   | 4    | `ro_len` | Bytes in read-only data section (aligned to 4). |
| 0x14   | 4    | `bss_size` | Bytes of zeroed data at runtime. |
| 0x18   | 4    | `req_caps` | Capability bitmask (HAL requirements, features). |
| 0x1C   | 4    | `crc32` | CRC over header (0x00–0x1F) + code + rodata + metadata sections. |
| 0x20   | 32   | `app_name` | Null-terminated ASCII app name (max 31 chars + null). |
| 0x40   | 4    | `meta_offset` | Byte offset to metadata section table (0 if none). |
| 0x44   | 4    | `meta_count` | Number of metadata section entries. |
| 0x48   | 24   | `reserved` | Reserved for future extensions (must be zero). |

**Total header size: 96 bytes (0x60)**

**Version 0x0002 additions**
- `app_name` carries the canonical program name reported via `ps`/`info`. Whitespace is stripped and the executive truncates longer names to 31 bytes.
- `flags` bit 1 (`FLAG_ALLOW_MULTIPLE`) controls instance policy. When the bit is cleared, the executive rejects additional loads with the same `app_name`. When set, the executive auto-suffixes `_#N` to create unique instance names.
- `meta_offset` / `meta_count` enable the metadata section table described below. Loaders must reject tables that overlap the code or rodata segments.

Immediately following the header:
1. `code` section (`code_len` bytes) – executable VM code. The executive must expose this segment as immutable: disassemblers (`disasm.read`) fetch words directly from the code image (or host VM `read_code`) rather than from writable task RAM to guarantee instruction listings reflect the deployed binary.
2. `rodata` section (`ro_len` bytes) – read-only data.
3. Metadata sections (`.value`, `.cmd`, `.mailbox`) if `meta_count > 0`.
4. Optional embedded manifest if `flags & 0x01` is set.

## Alignment & Compatibility
- Header size fixed at 96 bytes for version 0x0002.
- Version 0x0001 loaders must reject version 0x0002 with `unsupported_version:2` error.
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

## Metadata Section Table
If `meta_count > 0`, a section table appears at `meta_offset` with this format:

**Section Table Entry (16 bytes each):**
| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0x00   | 4    | `section_type` | Type: 1=`.value`, 2=`.cmd`, 3=`.mailbox`. |
| 0x04   | 4    | `section_offset` | Byte offset from HXE start to section data. |
| 0x08   | 4    | `section_size` | Size of section data in bytes. |
| 0x0C   | 4    | `entry_count` | Number of entries in this section. |

## Declarative Registration Sections

### `.value` Section (type=1)
Defines values to be registered by executive before VM execution. Each entry:

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0x00   | 1    | `group_id` | Group identifier (0-255). |
| 0x01   | 1    | `value_id` | Value identifier within group (0-255). |
| 0x02   | 1    | `flags` | RO, Persist, Sticky, Pin, Bool flags. |
| 0x03   | 1    | `auth_level` | Authorization level (0=public, 1-255=restricted). |
| 0x04   | 2    | `init_value` | Initial f16 value. |
| 0x06   | 2    | `name_offset` | Offset to name string in string table (0=none). |
| 0x08   | 2    | `unit_offset` | Offset to unit string (0=none). |
| 0x0A   | 2    | `epsilon` | Min change threshold (f16). |
| 0x0C   | 2    | `min_val` | Range minimum (f16). |
| 0x0E   | 2    | `max_val` | Range maximum (f16). |
| 0x10   | 2    | `persist_key` | FRAM key (0=no persistence). |
| 0x12   | 2    | `group_name_offset` | Offset to group name string (0 = none). |

**Entry size: 20 bytes**

- **Executive handling:** Each `(group_id,value_id)` pair must be unique. The loader rejects values outside `0..255`. Absent strings resolve to `None`. The executive stores the raw f16 values (`init_raw`, `epsilon_raw`, `min_raw`, `max_raw`) while also exposing the decoded float fields. When `persist_key` is non-zero the runtime flags the value for FRAM persistence via `val.persist`.
- **Pre-registration:** During image load the executive automatically registers each value with the runtime registry, applies the `init_value`, and synthesises name/unit/range/persist descriptors from the metadata. Duplicate registrations or invalid string offsets abort the load.
- **Validation:** Duplicate IDs or malformed string offsets cause the load to fail. The executive ignores entries when the section is omitted.
- **Change filtering:** When `epsilon` is non-zero, updates within the epsilon band are ignored (no notifications or persistence). When `rate_ms` is non-zero, repeated updates within the window return `EBUSY` and must be retried once the suppression interval elapses.

### `.cmd` Section (type=2)
Defines commands to be registered. Each entry:

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0x00   | 1    | `group_id` | Group identifier. |
| 0x01   | 1    | `cmd_id` | Command identifier within group. |
| 0x02   | 1    | `flags` | Pin flag (requires auth token). |
| 0x03   | 1    | `auth_level` | Authorization level. |
| 0x04   | 4    | `handler_offset` | Code offset to handler function. |
| 0x08   | 2    | `name_offset` | Offset to name string (0=none). |
| 0x0A   | 2    | `help_offset` | Offset to help text (0=none). |
| 0x0C   | 4    | `reserved_hi:group_name_offset` | Lower 16 bits: group name string offset (0 = none). Upper 16 bits reserved. |

**Entry size: 16 bytes**

- **Executive handling:** Commands share the same `(group_id,value_id)` namespace as values. The `handler_offset` points to the VM entry point (relative to the code section). The executive enforces uniqueness and records the supplied names/help strings for debugger shells. Flags/auth levels map directly to the command SVC policy (`HSX_CMD_FL_PIN`, etc.).
- **Pre-registration:** Every `.cmd` entry is registered before the VM begins executing. The runtime preserves `handler_offset` for future dispatch, applies PIN/auth flags, and exposes descriptor metadata to RPC/HXE tooling. Errors (duplicate IDs, bad strings) cause the load to fail.

### `.mailbox` Section (type=3)
Defines mailboxes to be created before the VM starts running. HXE v2 uses a UTF-8 JSON payload:

```jsonc
{
  "version": 1,
  "mailboxes": [
    {
      "target": "app:telemetry",
      "capacity": 96,
      "mode": "RDWR",           // simple single-reader mailbox bound to app PID 2
      "owner_pid": 2
    },
    {
      "target": "shared:metrics",
      "capacity": 192,
      "mode": "RDWR|FANOUT_DROP", // fan-out telemetry stream (drop oldest on overflow)
      "bindings": [
        {"pid": 0, "flags": 0x0001},   // executive tap for dashboards
        {"pid": 3, "flags": 0x0001}    // background logger subscribes
      ]
    },
    {
      "target": "svc:stdio.out@5",
      "mode": "RDWR|TAP",          // declare tap for task 5 stdout mirroring
      "bindings": [
        {"pid": 0, "flags": 0x0004}
      ]
    },
    {
      "target": "pid:5",
      "capacity": 64,
      "mode": "RDWR",
      "bindings": [
        {"pid": 0, "flags": 0x0001}    // executive control channel (stdin)
      ]
    }
  ]
}
```

Each entry object supports the following fields (all optional unless noted):

| Field | Type | Description |
|-------|------|-------------|
| `target` | string (**required**) | Mailbox name with namespace prefix (`svc:`, `pid:`, `app:`, `shared:`). |
| `capacity` | integer | Requested ring capacity in bytes. Omit or set to `0` for the default (`HSX_MBX_DEFAULT_RING_CAPACITY`). |
| `mode_mask` | integer | `HSX_MBX_MODE_*` bit-mask. Defaults to `HSX_MBX_MODE_RDWR` when not provided. |
| `owner_pid` | integer | Declares the owning PID (used by provisioning tooling; optional). |
| `bindings` | array<object> | Declarative binding hints. Each object must include `pid` (int) and may specify `flags` or other module-defined attributes. |
| `reserved` | any | Reserved for future use. Preserved verbatim in metadata snapshots. |

The loader validates the JSON structure, normalises numeric fields, and rejects duplicate mailbox names. Declarative bindings are stored for higher-level tooling but are not acted upon during image load yet.

- **Precreation:** The Python loader binds each declared mailbox before the task runs. Creation results are surfaced both in the load response (`mailbox_creation`) and in `metadata._mailbox_creation`, and each metadata entry is updated with the resolved `descriptor`, `queue_depth`, and `mode_mask`.

### Declarative Mailbox Pragmas

HSX source files declare mailbox metadata with a C-style pragma:

```c
#pragma hsx_mailbox(target="app:telemetry", capacity=96, mode="RDWR|FANOUT")
```

- `target` (required) follows the same namespace rules as the JSON schema (`svc:`, `pid:`, `app:`, `shared:`).
- Optional fields (`capacity`, `mode_mask`, `mode`, `owner_pid`, `bindings`) mirror the JSON object. The `mode` string supports `RDONLY`, `WRONLY`, `RDWR`, `FANOUT`, `FANOUT_DROP`, `FANOUT_BLOCK`, and `TAP`, combined with `|`.
- The Clang → LLVM pipeline lowers the pragma to a comment in the IR: `; #pragma hsx_mailbox(...)`. `hsx-llc.py` detects these directives and emits matching `.mailbox { ... }` MVASM entries, which the assembler/linker convert into the HXE `.mailbox` section described above.

#### Example scenarios

- **Simple IPC (`app:telemetry`)** - single-reader mailbox provisioned for the owning PID. Use when a task exposes a control channel to tooling or other tasks.
- **Fan-out broadcast (`shared:metrics`)** - shared namespace with `FANOUT_DROP` ensures producers never block; older entries are discarded when subscribers lag.
- **Tap monitoring (`svc:stdio.out@5`)** - enable the `TAP` mode to duplicate stdout to the executive without starving the owner. Combine with tap rate limits configured in the mailbox profile.
- **Stdio redirection (`pid:5`)** - declare the per-task control mailbox so provisioning can pre-bind stdin/stdout handles on load.

**Tuning tips:**
- Keep capacities power-of-two multiples of the default (64B) for predictable SRAM usage. Fan-out mailboxes must account for the largest payload multiplied by the number of subscribers.
- Reserve `shared:` namespace for telemetry and logging. Use `app:` for intra-application channels and `svc:` for executive-owned plumbing (stdio, control).
- When taps are involved, prefer `FANOUT_DROP` or tap-specific rate limits to protect the owner’s throughput.

Legacy (pre-v2) images may still encode `.mailbox` entries as fixed-size binary structures:

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0x00   | 4    | `name_offset` | Offset to mailbox name string. |
| 0x04   | 2    | `queue_depth` | Requested capacity (`0` = default). |
| 0x06   | 2    | `flags` | Mode mask (`HSX_MBX_MODE_*`). |
| 0x08   | 8    | `reserved` | Reserved for future use. |

**Entry size: 16 bytes**

Images authored with the legacy format continue to load; the parser automatically falls back to the struct layout when the payload does not contain JSON.

- **Executive handling:** the executive validates each mailbox record and calls `mailbox_bind` with the normalised `target`, `capacity` (if non-zero), and `mode_mask`. Declarative bindings and owner metadata are stored in the executive registry for later phases. Duplicate mailbox names within the same image abort the load.

### String Table
Each section may reference a string table located at the end of that section. String offsets are relative to the section start. Strings are null-terminated UTF-8.

## CRC Procedure
- Compute CRC32 (polynomial 0x04C11DB7) over:
  - Header bytes 0x00–0x1F (excluding app_name and meta fields).
  - Code section.
  - Rodata section.
  - All metadata sections.
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

## Declarative Registration: Toolchain Preprocessor Directives

The toolchain processes preprocessor directives in HXE source code to generate metadata sections:

```c
// Value declaration
#pragma hsx_value(motor_speed, group=1, id=5, flags=PERSIST, init=0.0, \
                  min=0.0, max=100.0, unit="rpm")

// Command declaration  
#pragma hsx_command(reset_controller, group=1, id=10, handler=do_reset, \
                    help="Reset motor controller")

// Mailbox declaration
#pragma hsx_mailbox(motor_status, depth=8, flags=SHARED)
```

Flags supplied to pragmas may be written symbolically (`flags=PERSIST|PIN`), and auth levels accept the tokens `PUBLIC`, `USER`, `ADMIN`, and `FACTORY`. The command `handler=` parameter accepts either a literal offset or the name of a text-section symbol; the linker resolves symbol names to final code offsets.

**Preprocessing flow:**
1. Compiler frontend (clang) parses pragma directives and emits special metadata annotations.
2. `hsx-llc` or assembler collects annotations and generates `.value`/`.cmd`/`.mailbox` section data.
3. Linker `hld.py` merges metadata sections, builds section table, updates header fields.
4. Executive preprocesses sections during load, strips them before VM execution.

**Benefits:**
- Zero VM cycles for initialization
- No registration code in VM memory
- Declarative, compile-time checked metadata
- Executive knows all requirements before app starts

## Toolchain Responsibilities
- `hsx-llc` / `asm.py` process pragma directives and generate metadata sections.
- Linker `hld.py` assembles `.hxe` with header (v0x0002), code/rodata, metadata sections, section table, CRC, and optional manifest.
- `docs/abi_syscalls.md` & `shared/abi_syscalls.md` supply capability IDs referenced in manifests.

## Executive/Provisioning Responsibilities
- Validate magic/version/CRC before loading.
- **Preprocess metadata sections**: Parse `.value`, `.cmd`, `.mailbox` sections and register entries with app's PID.
- The Python executive rejects duplicate values/commands/mailboxes, ensures all IDs are byte-sized, and binds mailboxes before exposing the app to the VM. Mailbox binds reuse the existing mailbox manager so metadata-driven resources appear identical to runtime-created bindings.
- **Strip metadata sections** before loading code/rodata/bss to VM (or VM ignores them).
- Allocate code/rodata/bss based on header fields for VM execution.
- Apply capability checks (`req_caps`) against hardware/executive features.
- Expose manifest data to provisioning and persistence modules.

## References
- [main/04--Design/04.05--Toolchain.md](../main/04--Design/04.05--Toolchain.md)
- `docs/asm.md` (assembler CLI + metadata output)
- [main/04--Design/04.07--Provisioning.md](../main/04--Design/04.07--Provisioning.md)
- [main/05--Implementation/toolchain/formats/hxe.md](../main/05--Implementation/toolchain/formats/hxe.md)
- [main/05--Implementation/system/Provisioning.md](../main/05--Implementation/system/Provisioning.md)

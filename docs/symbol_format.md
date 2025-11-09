# HSX Symbol File Format (.sym)

## Overview

Linking with `python/hld.py` and the `--emit-sym` flag produces a JSON
sidecar describing the debug symbols for the resulting `.hxe`. The file is
designed for consumption by debuggers and the executive so the structure is
stable and versioned.

```json
{
  "version": 1,
  "hxe_path": "app.hxe",
  "hxe_crc": 3512153456,
  "symbols": {
    "functions": [],
    "variables": [],
    "labels": {}
  },
  "instructions": [],
  "memory_regions": []
}
```

## Top-Level Fields

| Field | Type | Notes |
| --- | --- | --- |
| `version` | integer | Schema version. Current value: `1`. |
| `hxe_path` | string | Path (as provided to the linker) of the linked HXE. |
| `hxe_crc` | integer | CRC32 of the emitted HXE file. Useful for validating matched binaries. |
| `symbols` | object | Aggregated symbol tables (see below). |
| `instructions` | array | Instruction-level debug data. |
| `memory_regions` | array | Memory layout summary for debugger UIs. |

## `symbols.functions`

Each function entry records relocated addresses and metadata derived from
debug info:

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | User-facing function name. |
| `linkage_name` | string or null | Mangled/IR linkage name when available. |
| `address` | integer | Relocated entry address (byte address). |
| `size` | integer | Function span in bytes (inclusive MVASM ordinals × 4). |
| `file` | string or null | Source filename. |
| `line` | integer or null | Source line where the function is defined. |

## `symbols.variables`

Variables describe resolved data symbols (currently global data exports).

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | Variable symbol. |
| `address` | integer | Relocated address. |
| `size` | integer | Size in bytes (0 when unknown). |
| `scope` | string | Scope descriptor (`"global"` for exported data). |
| `type` | string or null | Reserved for future typing information. |

## `symbols.labels`

`labels` is a mapping of relocated addresses (hex string with `0x` prefix)
to a list of label names at that address. Entries are sorted by address.

## `instructions`

Each entry describes a single emitted MVASM instruction after relocation:

| Field | Type | Notes |
| --- | --- | --- |
| `pc` | integer | Relocated program counter (byte address). |
| `word` | integer | Encoded instruction word (big-endian). |
| `mvasm_line` | integer | Line number in the MVASM listing. |
| `ordinal` | integer | Instruction ordinal within the compilation unit. |
| `function` | string or null | Function containing the instruction. |
| `file` | string or null | Source filename. |
| `directory` | string or null | Source directory (if available). |
| `file_id` | string or null | LLVM metadata reference for the source file. |
| `line` / `column` | integer or null | Source location information. |

## `memory_regions`

Describes contiguous regions in the linked image.

| Field | Type | Notes |
| --- | --- | --- |
| `name` | string | Human-friendly region name (`code`, `rodata`, …). |
| `type` | string | Region classification (`text`, `data`, etc.). |
| `start` | integer | Start address of the region. |
| `end` | integer | End address (inclusive). |

Future revisions may extend the schema; consumers must check the `version`
field and ignore unknown fields to remain forward compatible.

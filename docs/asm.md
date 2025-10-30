# HSX Assembler (`asm.py`) Overview

> SDP Reference: 2025-10 Main Run (Design Playbook #11)

This document captures the behaviour and artefacts emitted by the HSX MVASM assembler so toolchain and tooling teams can rely on a stable CLI surface and metadata schema.

## CLI Summary

| Flag | Description |
|------|-------------|
| `-o/--output <path>` | Required. Destination path for output file. |
| `--emit-hxe` | Emit a final executable (`.hxe`) directly. Default is to emit `.hxo` object files. |
| `--dump-json` | When producing `.hxe`, also invoke `python/disassemble.py` to create a JSON listing (`<output>.json`). |
| `--dump-bytes` | Print encoded instruction words to stdout (debug only). |
| `--verbose` | Print entry point, code/rodata sizes, and import/export summaries. |

**Default Behavior (v0.2):** The assembler now emits `.hxo` object files by default, following standard toolchain practice. The linker (`hld.py`) is responsible for creating final `.hxe` executables from one or more object files. This ensures a single, consistent path for executable creation and simplifies the assembler.

For backward compatibility or convenience, use `--emit-hxe` to generate executables directly (legacy mode).

## `.hxo` Object Schema (Default Output)

The intermediate object is a UTF-8 JSON document written by `write_hxo_object`. Field definitions:

| Field | Type | Description |
|-------|------|-------------|
| `version` | int | Schema version (currently `1`). |
| `entry` | int | Entry point offset (word address) relative to the text section. |
| `entry_symbol` | string or `null` | Symbol that supplied the entry point, if any. |
| `code` | array[int] | List of 32-bit instruction words (big-endian when serialized to `.hxe`). |
| `rodata` | string | Hex-encoded read-only data blob (`""` when absent). |
| `externs` | array[string] | Symbols referenced but defined elsewhere. |
| `imports` | array[string] | Modules/files pulled via `.import` directives. |
| `relocs` | array<object> | Fixups that the linker must resolve. Each entry contains `type`, `offset`, `section`, `symbol`, and `kind` (e.g., `lo16`, `hi16`, `off16`). |
| `symbols` | object | Exported symbols keyed by name (`{ "foo": {"section":"text","offset":16} }`). |
| `local_symbols` | object | Full symbol table used for debugging or listings. Each value includes `section`, `offset`, and `abs_addr`. |

The linker (`python/hld.py`) is responsible for resolving `relocs`, merging sections, computing the HXE header, and appending manifests as described in `docs/hxe_format.md`.

## JSON Listing (`--dump-json`)

When `--dump-json` is set (only valid when producing `.hxe`), the assembler runs:

```
python/disassemble.py <output>.hxe --mvasm <source.mvasm> -o <output>.json
```

The disassembler emits a JSON document with three top-level keys:

```json
{
  "header": { ... },
  "instructions": [ ... ],
  "symbols": { ... }
}
```

### `header`

Matches the binary header defined in `docs/hxe_format.md` (`magic`, `version`, `flags`, `entry`, `code_len`, `ro_len`, `bss_size`, `req_caps`, `crc32`). Values are integers to avoid endianness ambiguity.

### `instructions`

Each instruction entry contains:

| Field | Description |
|-------|-------------|
| `pc` | Byte offset within the code section. |
| `word` | Encoded 32-bit instruction (unsigned int). |
| `mnemonic` | Resolved opcode name (e.g., `ADD`, `SVC`, `LDI32`). |
| `rd`, `rs1`, `rs2` | Register indices (0–15). |
| `imm` | Signed 12-bit immediate (with sign extension applied). |
| `imm_raw` | Unsigned 12-bit immediate as encoded. |
| `imm_effective` | Immediate after opcode-specific adjustments (e.g., unsigned for branch targets). |
| `extended_imm` | Second word for `LDI32` sequences (optional). |
| `operands` | Preformatted operand string used by CLI/TUI disassemblers. |
| `target` | Optional label resolved from the original `.mvasm` source (only when `--mvasm` points to the same file). |

### `symbols`

Derived from the source file to retain contextual metadata:

- `labels_text`: mapping `byte_offset -> [label, ...]` within the `.text` section.
- `labels_data`: mapping `byte_offset -> [label, ...]` within `.data`.
- `data_entries`: array of `(offset, directive, values)` tuples describing `.byte/.half/.word` directives encountered in `.data`.

Tooling (debugger, IDE integrations) can consume this JSON to show annotated disassemblies without having to parse MVASM directly.

## Relationship to Packaging

- `docs/hxe_format.md` remains the canonical binary specification. This document only describes the textual/JSON artefacts emitted alongside `.hxe`.
- The upcoming packaging workflow (`make package`/`make release`) should bundle both the `.hxe` binaries and their optional JSON listings so shell/debugger tooling can offer source-level context.
- Future metadata additions (value/command descriptor dumps) should extend this document rather than altering the `.hxe` header to keep compatibility risks low.

## Example

```bash
python/asm.py examples/tests/test_vm_exit/main.mvasm \
  -o build/test_vm_exit.hxe \
  --dump-json \
  --verbose
```

Outputs:
1. `build/test_vm_exit.hxe` (binary executable per `docs/hxe_format.md`).
2. `build/test_vm_exit.json` (disassembly listing with header + instruction metadata).
3. Console summary: entry point, word counts, extern/import lists (when `--verbose`).

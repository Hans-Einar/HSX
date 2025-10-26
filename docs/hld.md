# hld.py - HSX Linker & Packer

> SDP Reference: 2025-10 Main Run (Design Playbook #11)

## Purpose
`python/hld.py` links one or more `.hxo` objects into a final `.hxe` executable. It also acts as a pass-through packer when given a single `.hxe`. This document defines the CLI surface, object expectations, and linking algorithm so build scripts and tooling can rely on consistent behaviour.

## CLI Summary

| Flag | Description |
|------|-------------|
| `inputs` | One or more `.hxo` files. A single `.hxe` may be provided for pass-through copying. Mixing `.hxo` and `.hxe` is rejected. |
| `-o/--output <path>` | Required destination `.hxe`. |
| `-v/--verbose` | Print entry address, word counts, rodata size, and export list after linking/copying. |

Examples:
```
python/hld.py foo.hxo bar.hxo -o app.hxe
python/hld.py existing.hxe -o copy.hxe   # pass-through
```

## Input Expectations
- `.hxo` files must follow the schema documented in `docs/asm.md` (`code`, `rodata`, `symbols`, `relocs`, etc.).
- Each module may declare `externs`/`imports` and an optional `entry_symbol`.
- Sections are limited to `.text` and `.data` (rodata). BSS is not yet emitted by the assembler, so the linker only concatenates code/rodata and relies on `docs/hxe_format.md` for header fields.

## Linking Algorithm
1. **Load Objects:** parse JSON, normalise instruction words to 32-bit ints, and decode rodata hex.
2. **Assign Bases:** compute `code_base` and `ro_base` offsets for each object (word-aligned code, byte-aligned rodata).
3. **Build Global Symbol Table:**
   - For every exported symbol, record absolute address (code offset or `RODATA_BASE + ro_offset`).
   - Reject duplicates immediately.
4. **Resolve Imports:** ensure each `.import` entry has a matching symbol. Missing references abort linking.
5. **Apply Relocations:**
   - Code relocations patch immediate fields (`imm12`, `imm32`, `jump`, `mem`) using `set_imm12` from the assembler.
   - PC-relative relocations account for the instruction’s absolute address.
   - Rodata relocations write bytes/halves/words into the combined buffer.
6. **Choose Entry Point:**
   - Prefer `_start` if exported.
   - Otherwise, use the first module’s `entry_symbol`.
   - Fall back to the first module’s numeric `entry` field.
7. **Emit `.hxe`:**
   - Concatenate patched code/rodata, compute CRC, and write header via `write_hxe` (see `docs/hxe_format.md`).
   - Verbose mode prints a short summary for tooling logs.

If a single `.hxe` is provided without `.hxo` inputs, the tool copies it to `--output` (optionally printing details when `-v` is set). This keeps packaging scripts simple when no relinking is required.

## Error Handling
- Mixing `.hxo` and `.hxe` inputs results in exit code 2.
- Duplicate exports, unresolved imports, or relocations referencing unknown symbols raise descriptive `ValueError`s.
- PC-relative relocations must maintain word alignment; violations surface as explicit errors.

## Integration & Future Work
- `docs/asm.md` describes the object schema consumed here; any change to `.hxo` must be reflected in both documents.
- Planned enhancements include manifest embedding (per `docs/hxe_format.md`), capability bit propagation, and FRAM/resource budget enforcement.
- Packaging (`make package`/`make release`) should call `hld.py` for deterministic builds and archive the verbose summary as part of the SDP evidence trail.

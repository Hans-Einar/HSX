# Toolchain - Implementation Notes

Use this log to capture each session. Keep entries concise yet thorough so the next agent can resume without context loss.

## Session Template

```
## YYYY-MM-DD - Name/Initials (Session N)

### Scope
- Plan item / phase addressed:
- Design sections reviewed:

### Work Summary
- Key decisions & code changes:
- Design updates filed/applied:

### Testing
- Commands executed + results:
- Issues encountered:

### Next Steps
- Follow-ups / blockers:
- Reviews or coordination required:
```

Append sessions chronologically and ensure every entry references the relevant design material and documents the executed tests.

## 2025-11-05 - Codex (Session 1)

### Focus
- Task(s) tackled: Phase 2.4 planning for `.mailbox` metadata emission across the toolchain (llvm->mvasm->hxo/hxe).
- Dependencies touched: Reviewed design doc 04.05--Toolchain.md, current `hsx-llc.py`, `asm.py`, and `hld.py`.

### Status
- DONE

### Details
- Current state: toolchain lacks any metadata handling; neither `hsx-llc`, `asm.py`, nor `hld.py` recognise `.value/.cmd/.mailbox` directives. Phase 2 will therefore introduce the entire metadata path.
- Proposed approach:
  - **MVASM directive syntax:** allow JSON payloads to minimise bespoke parsing. e.g. `.mailbox {"target":"app:telemetry","capacity":128,"mode_mask":"FANOUT|RDWR","owner_pid":2,"bindings":[{"pid":2,"flags":"STDOUT"}]}`.
  - **hsx-llc:** capture `#pragma hsx_mailbox(...)` and emit the directive with a normalised JSON object (mode strings expanded to constants).
  - **asm.py:** detect `.mailbox` lines, parse the trailing JSON via `json.loads`, validate required keys, and append structured entries to the HXO metadata blob (storing verbatim JSON for string tables when we add values/commands).
  - **hld.py:** merge mailbox metadata arrays from all HXO inputs, deduplicate identical targets, and write a consolidated JSON payload into the HXE `.mailbox` section, aligning with the loader's expectations (version=1 object with `"mailboxes": [...]`).
- Planned tests:
  1. Unit tests around assembler parsing (valid + malformed JSON, option combinations).
  2. Linker integration test: two HXO inputs each contributing mailboxes should merge cleanly and produce a single `.mailbox` section.
  3. End-to-end build sample (C pragma -> hsx-cc-build) asserting resulting HXE metadata matches loader schema and that `platforms/python/host_vm.py` pre-creates the mailboxes.
- Follow-up actions / hand-off notes:
  - Track implementation in Session 2 (below); additional work remains for pragma extraction in `hsx-llc` and value/command metadata.

## 2025-11-05 - Codex (Session 2)

### Focus
- Task(s) tackled: Implement Phase 2.4 `.mailbox` metadata pipeline (assembler directives -> HXO -> linker -> HXE) plus documentation/tests.
- Dependencies touched: `python/asm.py`, `python/hld.py`, `python/tests/test_vm_stream_loader.py`, `python/tests/test_linker*.py`, `docs/MVASM_SPEC.md`.

### Status
- DONE

### Details
- Summary of code changes / key decisions:
  - Added JSON-based `.mailbox` directive handling in `asm.py`, captured metadata in `LAST_METADATA`, and emitted it in `.hxo` objects.
  - Extended `hsx-llc.py` to recognise `#pragma hsx_mailbox(...)` in LLVM IR (via comment directives) and emit `.mailbox { ... }` MVASM directives.
  - Reworked the linker to produce HXE v2 images in-place (header v0x0002, metadata table, CRC) and merge mailbox metadata across modules.
  - Updated streaming loader tests to build real HXE images through the toolchain, ensuring `VMController` pre-creates declared mailboxes, and documented the directive in MVASM spec.
- Tests run (commands + result):
  - `C:/appz/miniconda/envs/py312/python.exe -m pytest python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py`
  - `C:/appz/miniconda/envs/py312/python.exe -m pytest python/tests/test_asm_sections.py python/tests/test_vm_exit.py`
- Follow-up actions / hand-off notes:
- Extend `hsx-llc` to emit `.mailbox` directives from pragmas and mirror this work for `.value`/`.cmd` sections in subsequent phases.

## 2025-11-07 - Codex (Session 3)

### Scope
- Plan item / phase addressed: Phase 2 metadata pipeline (pragma extraction, directive emission, assembler/linker integration) for values & commands.
- Design sections reviewed: 04.05--Toolchain.md §4.2.1–4.2.3, docs/hxe_format.md declarative registration, docs/MVASM_SPEC.md directives.

### Work Summary
- Expanded `hsx-llc.py` to parse `#pragma hsx_value` / `#pragma hsx_command`, normalise flags/auth tokens, and emit `.value`/`.cmd` JSON directives alongside existing `.mailbox` entries. Updated MVASM spec and design docs with the new directive details.
- Taught `python/asm.py` to parse `.value`/`.cmd` directives (JSON object/array), validate parameters, coerce types, and include the metadata in HXO objects. Added helpers for flag/auth parsing and extended `LAST_METADATA`.
- Enhanced `python/hld.py` metadata merger to resolve command handler symbols to code offsets, allowing linker-side resolution when directives reference handler names. Cleaned up metadata before encoding.
- Added regression tests covering the new directive flow end-to-end (`test_hsx_llc_mailbox` value/command scenario, `test_vm_stream_loader` using directives, linker/assembler suites) and documented behaviour in `docs/MVASM_SPEC.md` and `docs/hxe_format.md`.

### Testing
- `python -m pytest python/tests/test_hsx_llc_mailbox.py python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py python/tests/test_asm_sections.py`

### Next Steps
- Document pragma-to-LLVM metadata mapping details and outline the helper pipeline for later debug metadata work (Phase 2.2 documentation task).
- Begin planning Phase 3 debug metadata extraction once value/command pipeline lands in review.

## 2025-11-07 - Codex (Session 4)

### Scope
- Plan item / phase addressed: Phase 3.1 Function-Level Debug Metadata
- Design sections reviewed: 04.05--Toolchain.md §4.2.1, main/05--Implementation/toolchain/debug-metadata.md

### Work Summary
- Updated `hsx-llc.parse_ir` to accumulate `!DIFile` / `!DISubprogram` metadata (including multi-line definitions), capturing filenames, directories, and start-line info. Function definitions now retain their associated `!dbg !<id>` references.
- Added helper parsing utilities and surfaced a `debug` section in the parsed IR containing files, subprograms, and function summaries.
- Introduced regression coverage (`python/tests/test_hsx_llc_debug.py`) verifying that function/file metadata is extracted correctly for downstream debug tooling. Documented the new IR metadata in the debug-metadata implementation guide.

### Testing
- `python -m pytest python/tests/test_hsx_llc_debug.py python/tests/test_hsx_llc_mailbox.py python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py python/tests/test_asm_sections.py`

### Next Steps
- Implement the `--emit-debug` flag to persist the collected metadata into `.dbg` sidecar files (Phase 3.2).

## 2025-11-07 - Codex (Session 5)

### Scope
- Plan item / phase addressed: Phase 3.2 `--emit-debug` flag / .dbg generation
- Design sections reviewed: 04.05--Toolchain.md §4.2.1, toolchain/debug-metadata.md schema

### Work Summary
- Added a module-level debug metadata cache in `hsx-llc.py` and enriched `compile_ll_to_mvasm` to track MVASM line spans per function.
- Introduced the `--emit-debug` CLI flag writing a `.dbg` JSON file (versioned payload with `files`/`functions` arrays) and added helpers/tests verifying both direct usage and CLI invocation.
- Documented emitted fields (including `mvasm_start_line`/`mvasm_end_line`) in the debug metadata guide.

### Testing
- `python -m pytest python/tests/test_hsx_llc_debug.py`
- `python -m pytest python/tests/test_hsx_llc_mailbox.py python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py python/tests/test_asm_sections.py python/tests/test_valcmd_registry.py`

### Next Steps
- Phase 3.3: capture instruction-level mappings (`!DILocation`) and extend `.dbg` / `.sym` outputs accordingly.

## 2025-11-08 - Codex (Session 6)

### Scope
- Plan item / phase addressed: Phase 3.3 instruction mapping (line_map + llvm_to_mvasm)
- Design sections reviewed: 04.05--Toolchain §4.2.1, toolchain/debug-metadata.md schema, Implementation Plan Phase 3.3 checklist

### Work Summary
- Extended `parse_ir` to collect `!DILocation`/`!DILexicalBlock` nodes and preserved per-instruction debug IDs through lowering, including phi pruning.
- Refactored `lower_function` to emit instruction metadata (inst IDs, dbg IDs) and propagate tags through MVASM emission and peephole optimizations; added `_optimize_movs` helper so metadata survives MOV folding/elimination.
- Emitted `line_map` and `llvm_to_mvasm` arrays in `LAST_DEBUG_INFO` / `.dbg` output with file/column context, updated docs and implementation plan checklist, and captured instruction order for downstream symbol generation.
- Added regression coverage in `test_hsx_llc_debug.py` asserting the new mappings, and refreshed debug metadata documentation to describe the richer schema.

### Testing
- `python -m pytest python/tests/test_hsx_llc_debug.py`
- `python -m pytest python/tests/test_opt_movs.py python/tests/test_opt_peephole_extra.py`

### Next Steps
- Phase 3.4: enrich `.dbg` with variable metadata and begin linker `.sym` integration once symbol layout work resumes.

## 2025-11-08 - Codex (Session 7)

### Scope
- Plan item / phase addressed: Phase 3.4 `--emit-sym` linker integration
- Design sections reviewed: 04.05--Toolchain §4.2.1–4.2.3, toolchain/debug-metadata.md, Implementation Plan 3.4 checklist

### Work Summary
- Augmented `hsx-llc` line mapping to track MVASM ordinals, annotate functions with start/end ordinals, and emit ordinal data inside `line_map` / `llvm_to_mvasm` entries for downstream address resolution.
- Extended linker CLI with `--debug-info`/`--emit-sym`/`--app-name` options, associated `.dbg` files per object, and synthesized `.sym` payloads (functions, instructions, labels, memory regions) using relocated addresses; helper `_generate_symbol_payload` writes the symbol JSON alongside HXE.
- Updated debug metadata documentation and plan checklists, added HSX builder compatibility, and introduced regression tests covering `.sym` generation plus updated debug expectations.

### Testing
- `python -m pytest python/tests/test_hsx_llc_debug.py`
- `python -m pytest python/tests/test_linker.py python/tests/test_import_unresolved.py python/tests/test_hsx_cc_build.py`

### Next Steps
- Phase 3.5: finalize `.sym` schema (variables, instruction mnemonics, region enrichment) and document consumer expectations.

## 2025-11-08 - Codex (Session 8)

### Scope
- Plan item / phase addressed: Phase 3.5 Symbol File Schema Finalization
- Design sections reviewed: 04.05--Toolchain §4.2.3, new `docs/symbol_format.md`, Implementation Plan 3.5 checklist

### Work Summary
- Added MVASM ordinal propagation to linker symbol generation, enriched instruction records, and surfaced proto variable entries for exported data symbols.
- Authored `docs/symbol_format.md` describing the versioned `.sym` schema, refreshed debug-metadata reference examples, and reasoned through schema stability expectations.
- Expanded regression tests to assert the presence of new fields (`ordinal`, `variables`, `memory_regions`), ensuring HSX builder flows continue to emit debug artefacts.

### Testing
- `python -m pytest python/tests/test_hsx_llc_debug.py`
- `python -m pytest python/tests/test_linker.py python/tests/test_import_unresolved.py python/tests/test_hsx_cc_build.py`

### Next Steps
- Phase 4.1: integrate `-fdebug-prefix-map` handling to stabilise source paths within emitted debug metadata.

## 2025-11-08 - Codex (Session 9)

### Scope
- Plan item / phase addressed: Phase 4.1 Source Path Handling
- Design sections reviewed: 04.05--Toolchain §4.2.4, toolchain/debug-metadata.md, Implementation Plan 4.1 checklist

### Work Summary
- Added automatic `-fdebug-prefix-map` calculation in `hsx-cc-build.py`, surfaced the mapping via `HSX_DEBUG_PREFIX_MAP` / `DEBUG_PREFIX_MAP`, and ensured all child commands inherit the environment.
- Documented usage guidance in the debug-metadata implementation doc so Makefile builds can reuse the exported mapping.
- Extended builder tests to validate the flag, the propagated environment, and kept regression suite green.

### Testing
- `python -m pytest python/tests/test_hsx_cc_build.py`

### Next Steps
- Phase 4.2: generate `sources.json` consistently for debug builds using the remapped paths.

## 2025-11-08 - Codex (Session 10)

### Scope
- Plan item / phase addressed: Phase 4.2 Generate sources.json
- Design sections reviewed: 04.05--Toolchain §4.2.4, docs/sources_json.md, Implementation Plan 4.2 checklist

### Work Summary
- Normalised builder source discovery to recurse through the project, skip the build directory, and de-duplicate results before use.
- Enhanced `generate_sources_json` to emit sorted relative paths, absolute paths, optional prefix map metadata, and to rely on the normalised source list for both direct and Make-driven builds.
- Authored `docs/sources_json.md` describing the schema, and expanded unit tests to cover deduplication, outside-root handling, Make integrations, and env propagation.

### Testing
- `python -m pytest python/tests/test_hsx_cc_build.py`

### Next Steps
- Phase 4.3: validate debugger path resolution using the emitted `sources.json` in varied build locations.

## 2025-11-08 - Codex (Session 11)

### Scope
- Plan item / phase addressed: Phase 4.3 Test Path Resolution
- Design sections reviewed: 04.05--Toolchain §4.2.4, docs/sources_json.md, Implementation Plan 4.3 checklist

### Work Summary
- Introduced `python/source_map.py` to load `sources.json`, apply prefix-map rewrites, and resolve source paths against alternate roots.
- Added unit coverage (`python/tests/test_source_map.py`) simulating relocated builds and prefix-map rewrites, and expanded builder tests to ensure make-driven debug builds emit `sources.json` by default.
- Documented consumer usage in the source map guide and closed out Phase 4.3 tasks.

### Testing
- `python -m pytest python/tests/test_source_map.py`
- `python -m pytest python/tests/test_hsx_cc_build.py`

### Next Steps
- Phase 5 planning (to be confirmed) or integration with debugger tooling consuming `source_map.SourceMap`.

## 2025-11-08 - Codex (Session 12)

### Scope
- Plan item / phase addressed: Phase 4.4 Document Workflow
- Design sections reviewed: 04.05--Toolchain §4.2.4, docs/toolchain.md, docs/sources_json.md, Implementation Plan 4.4 checklist

### Work Summary
- Authored `docs/portable_debug_workflow.md` capturing direct builds, Makefile integration, custom scripting, troubleshooting, and a hands-on tutorial for portable debug artefacts.
- Cross-referenced the new guide from `docs/toolchain.md` and updated the Phase 4.4 checklist/notes/git log.

### Testing
- Documentation-only update (no code paths affected).

### Next Steps
- Begin Phase 5 ISA work (shift/ADC/SBC opcode additions) or coordinate with VM team before implementation.

## 2025-11-08 - Codex (Session 13)

### Scope
- Plan item / phase addressed: Phase 5.1 Shift Opcode Lowering
- Design sections reviewed: docs/MVASM_SPEC.md (shift semantics), hsx-llc lowering pipeline

### Work Summary
- Added `shl`/`lshr`/`ashr` lowering paths in `hsx-llc.py`, mapping LLVM shift operations to `LSL`/`LSR`/`ASR` MVASM instructions with register or immediate operands.
- Created regression coverage (`python/tests/test_hsx_llc_shift.py`) verifying both register-based and immediate shifts emit the expected instructions and helper loads.

### Testing
- `python -m pytest python/tests/test_hsx_llc_shift.py`

### Next Steps
- Continue Phase 5 with carry arithmetic lowering (`ADC`/`SBC`) and opcode table sync.

## 2025-11-08 - Codex (Session 14)

### Scope
- Plan item / phase addressed: Phase 5.2 carry arithmetic lowering (initial support)
- Design sections reviewed: docs/MVASM_SPEC.md (carry semantics), LLVM overflow intrinsics

### Work Summary
- Lowered `llvm.uadd.with.overflow.i32` into MVASM `ADD`/`ADC` sequences, producing both sum and carry values so multi-word addition can cascade through hardware flags.
- Added `ret i1` handling and `extractvalue` support in `hsx-llc` for the overflow structs, plus regression coverage (`python/tests/test_hsx_llc_carry.py`).

### Testing
- `python -m pytest python/tests/test_hsx_llc_shift.py python/tests/test_hsx_llc_carry.py`

### Next Steps
- Extend lowering to subtraction with borrow (`llvm.usub.with.overflow`) and sync opcode tables/assembler docs before Phase 5.3 checklist closes.

## 2025-11-08 - Codex (Session 15)

### Scope
- Plan item / phase addressed: Phase 5.2 carry arithmetic (assembler/disassembler/tests) + `llvm.usub.with.overflow`
- Design sections reviewed: MVASM spec §ALU flags, hsx-llc lowering helpers

### Work Summary
- Implemented lowering for `llvm.usub.with.overflow.i32`, generating `SUB` + `SBC` + shift sequences producing a boolean borrow flag; reused overflow tracking map for both add/sub flows.
- Added unit tests exercising the lowering paths (`python/tests/test_hsx_llc_carry.py`) and assembler parsing/encoding for `ADC`/`SBC` (`python/tests/test_asm_adc_sbc.py`), and updated MVASM spec with usage patterns.

### Testing
- `python -m pytest python/tests/test_hsx_llc_shift.py python/tests/test_hsx_llc_carry.py python/tests/test_asm_adc_sbc.py`

### Next Steps
- Phase 5.3: final opcode table audit and documentation / validation tests.

## 2025-11-08 - Codex (Session 16)

### Scope
- Plan item / phase addressed: Phase 5.3 Update Opcode Table
- Design sections reviewed: docs/MVASM_SPEC.md (§Opcode table), 04.05--Toolchain design, platforms/python/host_vm.py opcode dispatch

### Work Summary
- Consolidated opcode definitions in `python/opcodes.py` and updated both `python/asm.py` and `python/disasm_util.py` to consume the shared table, eliminating divergent dictionaries.
- Added regression tests ensuring assembler/disassembler share the mapping, the VM executes every defined opcode, and the MVASM spec table stays in sync (`python/tests/test_opcode_table.py`).
- Refreshed `docs/MVASM_SPEC.md` to reference the canonical table, updated the toolchain implementation plan Phase 5.3 checklist, and recorded commit hashes in the git log.

### Testing
- `PYTHONPATH=. pytest python/tests/test_opcode_table.py python/tests/test_asm_adc_sbc.py python/tests/test_hsx_llc_shift.py python/tests/test_hsx_llc_carry.py`

### Next Steps
- Proceed to Phase 5.4 to broaden opcode execution tests (integration / edge cases).

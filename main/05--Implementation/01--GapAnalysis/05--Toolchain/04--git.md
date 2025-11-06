# Git Log - Toolchain Implementation

> File name: `04--git.md`. Use this log to capture branch, commits, and PR status for the Toolchain implementation track.

## Branch
- Name: `<branch-name>`
- Created on: `<YYYY-MM-DD>`
- Owner: `<team or lead>`
- Based on commit: `<commit-id>`

## Commit Log
| Date | Commit hash | Message | Author | Notes |
| --- | --- | --- | --- | --- |
| 2025-11-05 | `5a47e6b` | `toolchain: add .mailbox directive support and emit HXE v2 metadata` | Codex | Tests: `C:/appz/miniconda/envs/py312/python.exe -m pytest python/tests/test_hsx_llc_mailbox.py python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py python/tests/test_asm_sections.py python/tests/test_vm_exit.py` |
| 2025-11-07 | `6ef1480` | `toolchain: add value/command pragma pipeline (.value/.cmd directives, assembler/linker integration)` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_mailbox.py python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py python/tests/test_asm_sections.py` |
| 2025-11-07 | `1665ea7` | `toolchain: parse DISubprogram/DIFile metadata for debug phase 1` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_debug.py python/tests/test_hsx_llc_mailbox.py python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py python/tests/test_asm_sections.py` |
| 2025-11-07 | `bdc1653` | `toolchain: add --emit-debug flag and .dbg writer (functions/files)` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_debug.py python/tests/test_hsx_llc_mailbox.py python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py python/tests/test_asm_sections.py python/tests/test_valcmd_registry.py` |
| 2025-11-08 | `916e45c` | `toolchain: linker --emit-sym and debug ordinals` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_debug.py python/tests/test_linker.py python/tests/test_import_unresolved.py python/tests/test_hsx_cc_build.py` |
| 2025-11-08 | `916e45c` | `toolchain: finalize .sym schema + docs` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_debug.py python/tests/test_linker.py python/tests/test_import_unresolved.py python/tests/test_hsx_cc_build.py` |
| 2025-11-08 | `1685a65` | `toolchain: add debug prefix map plumbing` | Codex | Tests: `python -m pytest python/tests/test_hsx_cc_build.py` |
| 2025-11-08 | `1bcea80` | `toolchain: normalize sources.json generation and docs` | Codex | Tests: `python -m pytest python/tests/test_hsx_cc_build.py` |
| 2025-11-08 | `e5e14ef` | `toolchain: add sources.json resolver + relocation tests` | Codex | Tests: `python -m pytest python/tests/test_source_map.py python/tests/test_hsx_cc_build.py` |
| 2025-11-08 | `b00077d` | `toolchain: document portable debug workflow` | Codex | Tests: _n/a (docs only)_ |
| 2025-11-08 | `e237910` | `toolchain: add hsx-llc shift lowering + tests` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_shift.py` |
| 2025-11-08 | `0bf8fb5` | `toolchain: lower llvm.{uadd,usub}.with.overflow` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_shift.py python/tests/test_hsx_llc_carry.py python/tests/test_asm_adc_sbc.py` |
| 2025-11-08 | `b2d491f` | `toolchain: emit instruction line_map and llvm_to_mvasm metadata` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_debug.py python/tests/test_opt_movs.py python/tests/test_opt_peephole_extra.py` |
| 2025-11-08 | `9954599` | `toolchain: centralize opcode table and sync docs/tests` | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_opcode_table.py python/tests/test_asm_adc_sbc.py python/tests/test_hsx_llc_shift.py python/tests/test_hsx_llc_carry.py` |
| 2025-11-08 | `4d457fb` | `toolchain: broaden opcode tests (shift/div disasm, validation)` | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_asm_shift_div.py python/tests/test_disasm_new_opcodes.py python/tests/test_opcode_table.py python/tests/test_asm_adc_sbc.py python/tests/test_vm_shift_ops.py python/tests/test_vm_div.py` |
| 2025-11-08 | `414471a` | `toolchain: enforce deterministic outputs and add reproducibility tests` | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_build_determinism.py python/tests/test_asm_shift_div.py python/tests/test_disasm_new_opcodes.py python/tests/test_opcode_table.py` |
| 2025-11-08 | `1beb517` | `toolchain: improve register allocation heuristics and expose metrics` | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_register_allocation_metrics.py python/tests/test_asm_shift_div.py python/tests/test_disasm_new_opcodes.py python/tests/test_opcode_table.py` |

## Pull Request
- PR URL / ID: `<link or ID>`
- Status: `<status>`
- Reviewers: `<names>`
- Merge date: `<YYYY-MM-DD or TBD>`
- Notes: `<follow-up items>`

## Additional Notes
- Update this file whenever new commits land or PR state changes.
- Link CI runs, code reviews, or related issues as the implementation progresses.
- 2025-11-07: Phase 1 checklist reconciled; no functional changes (documentation-only update).

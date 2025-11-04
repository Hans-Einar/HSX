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
| 2025-11-07 | `<pending>` | `toolchain: add value/command pragma pipeline (.value/.cmd directives, assembler/linker integration)` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_mailbox.py python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py python/tests/test_asm_sections.py` |
| 2025-11-07 | `<pending>` | `toolchain: parse DISubprogram/DIFile metadata for debug phase 1` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_debug.py python/tests/test_hsx_llc_mailbox.py python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py python/tests/test_asm_sections.py` |
| 2025-11-07 | `<pending>` | `toolchain: add --emit-debug flag and .dbg writer (functions/files)` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_debug.py python/tests/test_hsx_llc_mailbox.py python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py python/tests/test_asm_sections.py python/tests/test_valcmd_registry.py` |
| 2025-11-08 | `<pending>` | `toolchain: linker --emit-sym and debug ordinals` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_debug.py python/tests/test_linker.py python/tests/test_import_unresolved.py python/tests/test_hsx_cc_build.py` |
| 2025-11-08 | `<pending>` | `toolchain: finalize .sym schema + docs` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_debug.py python/tests/test_linker.py python/tests/test_import_unresolved.py python/tests/test_hsx_cc_build.py` |
| 2025-11-08 | `<pending>` | `toolchain: add debug prefix map plumbing` | Codex | Tests: `python -m pytest python/tests/test_hsx_cc_build.py` |
| 2025-11-08 | `<pending>` | `toolchain: normalize sources.json generation and docs` | Codex | Tests: `python -m pytest python/tests/test_hsx_cc_build.py` |
| 2025-11-08 | `<pending>` | `toolchain: add sources.json resolver + relocation tests` | Codex | Tests: `python -m pytest python/tests/test_source_map.py python/tests/test_hsx_cc_build.py` |
| 2025-11-08 | `<pending>` | `toolchain: document portable debug workflow` | Codex | Tests: _n/a (docs only)_ |
| 2025-11-08 | `<pending>` | `toolchain: add hsx-llc shift lowering + tests` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_shift.py` |
| 2025-11-08 | `<pending>` | `toolchain: lower llvm.uadd.with.overflow via ADC` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_shift.py python/tests/test_hsx_llc_carry.py` |
| 2025-11-08 | `<pending>` | `toolchain: emit instruction line_map and llvm_to_mvasm metadata` | Codex | Tests: `python -m pytest python/tests/test_hsx_llc_debug.py python/tests/test_opt_movs.py python/tests/test_opt_peephole_extra.py` |

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

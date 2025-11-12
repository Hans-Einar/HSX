# Git Log - vscode debugger Implementation

> File name: `04--git.md`. Use this log to capture branch, commits, and PR status for the vscode debugger implementation track.

## Branch
- Name: `Implementation/vscode`
- Created on: `2025-11-09`
- Owner: `Debugger Team`
- Based on commit: `6b5be80` (Session Resilience & Symbols)

## Commit Log
| Date | Commit hash | Message | Author | Notes |
| --- | --- | --- | --- | --- |
| 2025-11-09 | `6b5be80` | `Session Resilience & Symbols` | Hans Einar | Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dap_symbol_mapper.py` |
| 2025-11-09 | `95fe9e6` | `vscode-dap: implement Phase 3 (stack/scopes/variables)` | Hans Einar | Tests: `PYTHONPATH=. pytest python/tests/test_hsxdbg_cache.py python/tests/test_hsxdbg_commands.py python/tests/test_hsxdbg_session.py python/tests/test_hsx_dap_watch.py python/tests/test_hsx_dap_breakpoints.py python/tests/test_hsx_dap_stacktrace.py python/tests/test_hsx_dap_scopes.py python/tests/test_hsx_dap_variables.py python/tests/test_hsx_dap_symbol_mapper.py` |
| 2025-11-11 | `36ed765` | `Cleanup Legacy hsxdbg/hsx_dap tests; Phase 5 foundations` | Codex | Tests: `python -m pytest python/tests/` |
| 2025-11-11 | `77cf0b1` | `Phase 1 kickoff: shared backend + symbol reuse` | Codex | Tests: `python -m pytest python/tests/test_hsx_dbg_backend.py python/tests/test_hsx_dbg_symbols.py python/tests/test_hsx_dbg_commands.py python/tests/test_hsx_dbg_history.py python/tests/test_hsx_dbg_scripts.py` |
| 2025-11-11 | `907405f` | `Backend + Adapter` | Codex | Tests: `python -m pytest python/tests/test_hsx_dbg_backend.py python/tests/test_hsx_dbg_symbols.py python/tests/test_hsx_dbg_commands.py python/tests/test_hsx_dbg_history.py python/tests/test_hsx_dbg_scripts.py` |

## Pull Request
- PR URL / ID: `<link or ID>`
- Status: `<status>`
- Reviewers: `<names>`
- Merge date: `<YYYY-MM-DD or TBD>`
- Notes: `<follow-up items>`

## Additional Notes
- Update this file whenever new commits land or PR state changes.
- Link CI runs, code reviews, or related issues as the implementation progresses.
- Pending: Lightweight DAP harness tests (`python -m pytest python/tests/test_hsx_dap_harness.py`) now cover both the
  initial adapter wiring and the reconnection path that reapplies breakpoints after a dropped session; include alongside
  the backend/executive session pytest targets before landing the commit.

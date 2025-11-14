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
| 2025-11-11 | `3fce2af` | `Session lifecyle + DAP harness` | Codex | Tests: `python -m pytest python/tests/test_hsx_dap_harness.py python/tests/test_hsx_dbg_backend.py python/tests/test_executive_session_helpers.py` |
| 2025-11-12 | `c8c9671` | `Phase 6: remote breakpoint telemetry + disassembly refresh` | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dap_harness.py::test_remote_breakpoint_sync_emits_telemetry python/tests/test_hsx_dap_harness.py::test_stopped_event_emits_disassembly_telemetry` |
| 2025-11-14 | `5e33630` | `Phase 9: DAP capability + writeMemory fixes` | Codex | Tests: `python -m pytest python/tests/test_hsx_dbg_backend.py python/tests/test_hsx_dap_harness.py` |
| 2025-11-14 | `52623c1` | `VS Code stop + memory UX` | Codex | Tests: `npm --prefix vscode-hsx run compile && python -m pytest python/tests/test_hsx_dap_harness.py` |
| 2025-11-14 | `822cd39` | `Phase 11: debug-state rename + session scaffold` | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dbg_backend.py python/tests/test_hsx_dap_harness.py python/tests/test_shell_client.py python/tests/test_executive_sessions.py` |
| 2025-11-14 | `pending` | `Phase 11: session-backed reconnect + auto-reattach` | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dbg_backend.py python/tests/test_hsx_dap_harness.py` |
| 2025-11-13 | `b818e52` | `Phase 0/1 gap-analysis worklog` | Codex | Tests: `pytest python/tests/test_hsx_dap_harness.py` |
| 2025-11-13 | `60fd930` | `Phase 2: pause + task-state sync` | Codex | Tests: `pytest python/tests/test_hsx_dap_harness.py` |
| 2025-11-13 | `bc2f749` | `Phase 3: event + cache coverage` | Codex | Tests: `pytest python/tests/test_hsx_dap_harness.py` |

## Pull Request
- PR URL / ID: `<link or ID>`
- Status: `<status>`
- Reviewers: `<names>`
- Merge date: `<YYYY-MM-DD or TBD>`
- Notes: `<follow-up items>`

## Additional Notes
- Update this file whenever new commits land or PR state changes.
- Link CI runs, code reviews, or related issues as the implementation progresses.
- Pending: Lightweight DAP harness tests (`python -m pytest python/tests/test_hsx_dap_harness.py`) now cover launch,
  stackTrace/scopes, source/function breakpoints (using golden fixtures), and the reconnection path that reapplies
  breakpoints/watches; include these plus backend/executive session pytest targets before landing the status bar +
  breakpoint parity commit.

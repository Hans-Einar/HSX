# Git Log - Debugger Implementation

> File name: `04--git.md`. Use this log to capture branch, commits, and PR status for the Debugger implementation track.

## Branch
- Name: `Implementation/vscode`
- Created on: `2025-11-11`
- Owner: `Debugger team`
- Based on commit: `165595b`

## Commit Log
| Date | Commit hash | Message | Author | Notes |
| --- | --- | --- | --- | --- |
| 2025-11-11 | 165595b | hsx-dbg scaffolding (Phase 1.1-1.3) | Codex | Tests: `PYTHONPATH=. python python/hsx_dbg.py --command "help"; PYTHONPATH=. python python/hsx_dbg.py --command "status"` |
| 2025-11-11 | 6d8c81f | Attach/detach/info commands & plan sync | Codex | Tests: `PYTHONPATH=. python python/hsx_dbg.py --command "help"; PYTHONPATH=. python python/hsx_dbg.py --command "attach"; PYTHONPATH=. python python/hsx_dbg.py --command "info"` |
| 2025-11-11 | 0c5bfb4 | ps command + metadata output | Codex | Tests: `PYTHONPATH=. python python/hsx_dbg.py --command "ps"; PYTHONPATH=. python python/hsx_dbg.py --command "ps 1"; PYTHONPATH=. python python/hsx_dbg.py --json --command "ps"` |
| 2025-11-11 | 94849c5 | pause/continue/step controls | Codex | Tests: `PYTHONPATH=. python python/hsx_dbg.py --command "pause 1"; PYTHONPATH=. python python/hsx_dbg.py --command "continue 1"; PYTHONPATH=. python python/hsx_dbg.py --command "step 1 5"; PYTHONPATH=. python python/hsx_dbg.py --json --command "step 1 2"` |
| 2025-11-11 | 0662c80 | finish Phase 1/2 (aliases/observer/session info) | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dbg_commands.py` |
| 2025-11-11 | df988f7 | add symbol-aware breakpoint/watch commands | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dbg_commands.py` |
| 2025-11-11 | 044962d | begin Phase 4 (stack/watch UI, symbols path) | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dbg_commands.py` |
| 2025-11-11 | bb0f9d0 | Phase 4 updates (memory/disasm polish) | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dbg_commands.py` |
| 2025-11-11 | 34ea6a3 | Phase 4 progress (gdb-style mem examine) | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dbg_commands.py` |
| 2025-11-11 | b991694 | Phase 5.1/5.2 completion (completion + history) | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dbg_commands.py python/tests/test_hsx_dbg_history.py python/tests/test_hsx_dbg_completion.py` |
| 2025-11-11 | (pending) | Phase 5.4 error handling improvements | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_executive_session_helpers.py python/tests/test_hsx_dbg_commands.py python/tests/test_hsx_dbg_history.py python/tests/test_hsx_dbg_scripts.py python/tests/test_hsx_dbg_completion.py` |
| 2025-11-12 | fc1bee5 | Phase 7.1 – Disassembly pipeline fixes | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_executive_sessions.py::test_disasm_read_basic python/tests/test_executive_sessions.py::test_disasm_read_falls_back_when_code_rpc_missing python/tests/test_hsx_dap_harness.py::test_disassembly_formatting_accepts_operand_strings` |
| 2025-11-12 | 806d2e5 | Phase 7.2/7.3 – around_pc RPC + adapter prep | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_executive_sessions.py::test_disasm_read_basic python/tests/test_executive_sessions.py::test_disasm_read_falls_back_when_code_rpc_missing python/tests/test_executive_sessions.py::test_disasm_read_around_pc_mode python/tests/test_hsx_dap_harness.py::test_disassembly_formatting_accepts_operand_strings` |
| 2025-11-12 | 3cd80ce | Phase 7 completion (docs + telemetry) | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_executive_sessions.py::test_disasm_read_basic python/tests/test_executive_sessions.py::test_disasm_read_falls_back_when_code_rpc_missing python/tests/test_executive_sessions.py::test_disasm_read_around_pc_mode python/tests/test_hsx_dap_harness.py::test_disassembly_formatting_accepts_operand_strings` |
| 2025-11-12 | 3ea1fe3 | Phase 8 kickoff (PID resiliency + instruction BPs) | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dap_harness.py python/tests/test_executive_sessions.py::test_disasm_read_basic` |

## Pull Request
- PR URL / ID: `<link or ID>`
- Status: `<status>`
- Reviewers: `<names>`
- Merge date: `<YYYY-MM-DD or TBD>`
- Notes: `<follow-up items>`

## Additional Notes
- Next focus: Phase 5 scripting support (`-x` files) and error handling polish before starting the DAP refactor. Tests: `PYTHONPATH=. pytest python/tests/test_hsx_dbg_commands.py python/tests/test_hsx_dbg_history.py python/tests/test_hsx_dbg_completion.py`.
- Update this file whenever new commits land or PR state changes.
- Link CI runs, code reviews, or related issues as the implementation progresses.

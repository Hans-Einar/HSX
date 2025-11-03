# Git Log - ValCmd Implementation

> File name: `04--git.md`. Use this log to capture branch, commits, and PR status for the ValCmd implementation track.

## Branch
- Name: `Implementation/System`
- Created on: `2025-11-03`
- Owner: `Hans Einar Overjordet`
- Based on commit: `68a53ab`

## Commit Log
| Date | Commit hash | Message | Author | Notes |
| --- | --- | --- | --- | --- |
| 2025-11-03 | `df02983` | `valcmd: align registry with design spec` | Hans Einar | Tests: `PYTHONPATH=. pytest python/tests/test_valcmd_registry.py python/tests/test_valcmd_svc_integration.py` |
| 2025-11-03 | `a179dcf` | `valcmd: wire VALUE/CMD SVC handlers` | Hans Einar | Tests: `PYTHONPATH=. pytest python/tests/test_valcmd_registry.py python/tests/test_valcmd_svc_integration.py` |
| 2025-11-03 | `0d55937` | `valcmd: mailbox notifications + async results` | Hans Einar | Tests: `Not recorded (commit message)` |
| 2025-11-06 | `0a93cf3` | `valcmd: event stream + exec RPC surface` | Codex | Tests: `PYTHONPATH=. pytest python/tests/test_valcmd_registry.py python/tests/test_valcmd_svc_integration.py python/tests/test_executive_sessions.py -k "describe or snapshot or val_api or cmd_api"` |
| 2025-11-06 | _pending_ | `valcmd: resource tracking + RPC stats` | Codex | Tests: `python -m pytest python/tests/test_valcmd_registry.py -k stats -v`, `python -m pytest python/tests/test_valcmd_svc_integration.py -k stats -v`, `python -m pytest python/tests/test_executive_sessions.py -k stats -v`, `python -m pytest python/tests/test_host_vm_cli.py`, `python -m pytest python/tests/test_ir_half_main.py` |
| 2025-11-06 | _pending_ | `valcmd: enforce PIN + async dispatch` | Codex | Tests: `python -m pytest python/tests/test_valcmd_registry.py -k command_call -v`, `python -m pytest python/tests/test_valcmd_svc_integration.py -v`, `python -m pytest python/tests/test_host_vm_cli.py`, `python -m pytest python/tests/test_ir_half_main.py` |
| <YYYY-MM-DD> | <commit-hash> | <short message> | <author> | Tests: `<command>` |

## Pull Request
- PR URL / ID: `<link or ID>`
- Status: `<status>`
- Reviewers: `<names>`
- Merge date: `<YYYY-MM-DD or TBD>`
- Notes: `<follow-up items>`

## Additional Notes
- Update this file whenever new commits land or PR state changes.
- Link CI runs, code reviews, or related issues as the implementation progresses.
- 2025-11-06: Host VM CLI regression (`nargs="x"`) fixed locally; validated with `python -m pytest python/tests/test_host_vm_cli.py` and `python -m pytest python/tests/test_ir_half_main.py`.
- 2025-11-06: PIN-secured commands now require token validators; async completions are dispatched via the registry's executor hook.

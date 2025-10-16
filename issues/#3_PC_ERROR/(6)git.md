# Git Log — #3 JMP immediate sign-extension corrupts PC

## Branch
- Name: `#3_PC_ERROR`
- Created on: `2025-10-16`
- Owner: `Hans Einar`
- Based on commit: `afc408a9c7fbf1fbef98b60b88e22dc1067284da`

## Commit Log
| Date | Commit hash | Message | Author | Notes |
| --- | --- | --- | --- | --- |
| 2025-10-16 | fa113a2 | Fix unsigned jump immediates and add regression coverage | Hans Einar | Runtime/disasm/test updates; `pytest python/tests/test_vm_jump_immediates.py` |

## Pull Request
- PR URL / ID: `<pending>`
- Status: `open`
- Reviewers: `<pending>`
- Merge date: `<pending>`
- Notes: `Awaiting remediation plan approval.`

## Additional Notes
- Link CI runs and regression tests once the fix branch is created.
- Update this file after each commit lands under the issue branch.
- Pending changes (not yet committed): clock throttling resumption + shell telemetry (`python/execd.py`, `python/shell_client.py`, `python/blinkenlights.py`, docs). Tests: `pytest python/tests/test_vm_pause.py python/tests/test_mailbox_wait.py python/tests/test_shell_client.py`.

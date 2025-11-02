# Git Log - Mailbox Implementation

> File name: `04--git.md`. Use this log to capture branch, commits, and PR status for the Mailbox implementation track.

## Branch
- Name: `mailbox-phase1`
- Created on: `2025-11-03`
- Owner: `hsx-tools`
- Based on commit: `TODO(update-after-merge)`

## Commit Log
| Date | Commit hash | Message | Author | Notes |
| --- | --- | --- | --- | --- |
| 2025-11-03 | `6a3b9d2` | `mailbox: add timeout status constant` | Codex | Tests: `python -m pytest python/tests/test_mailbox_constants.py python/tests/test_mailbox_wait.py python/tests/test_mailbox_svc_runtime.py` |
| 2025-11-03 | `b1d4f87` | `mailbox: enforce descriptor pool limit` | Codex | Tests: `python -m pytest python/tests/test_mailbox_constants.py python/tests/test_mailbox_manager.py python/tests/test_mailbox_svc_runtime.py python/tests/test_mailbox_wait.py` |
| 2025-11-04 | `<pending>` | `mailbox: emit structured mailbox events` | Codex | Tests: `python -m pytest python/tests/test_mailbox_constants.py python/tests/test_mailbox_manager.py python/tests/test_mailbox_svc_runtime.py python/tests/test_mailbox_wait.py` |
| 2025-11-04 | `<pending>` | `mailbox: add resource monitoring stats` | Codex | Tests: `python -m pytest python/tests/test_mailbox_manager.py python/tests/test_mailbox_svc_runtime.py python/tests/test_exec_mailbox.py python/tests/test_shell_client.py` |
| 2025-11-04 | `<pending>` | `mailbox: validate fan-out/tap isolation` | Codex | Tests: `python -m pytest python/tests/test_mailbox_manager.py python/tests/test_mailbox_svc_runtime.py python/tests/test_exec_mailbox.py python/tests/test_shell_client.py` |
| 2025-11-05 | `17b643b` | `mailbox: parse .mailbox JSON metadata with legacy fallback` | Codex | Tests: `C:/appz/miniconda/envs/py312/python.exe -m pytest python/tests/test_hxe_v2_metadata.py python/tests/test_metadata_preprocess.py` |
| 2025-11-05 | `5a47e6b` | `mailbox: precreate declarative mailboxes during load` | Codex | Tests: `C:/appz/miniconda/envs/py312/python.exe -m pytest python/tests/test_vm_stream_loader.py python/tests/test_metadata_preprocess.py python/tests/test_hxe_v2_metadata.py` |
## Pull Request
- PR URL / ID: `<link or ID>`
- Status: `<status>`
- Reviewers: `<names>`
- Merge date: `<YYYY-MM-DD or TBD>`
- Notes: `<follow-up items>`

## Additional Notes
- Update this file whenever new commits land or PR state changes.
- Link CI runs, code reviews, or related issues as the implementation progresses.

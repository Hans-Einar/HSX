# Mailbox Implementation Notes

Use this file to record progress per session.

## Template

```
## YYYY-MM-DD - Name/Initials (Session N)

### Focus
- Task(s) tackled: ...
- Dependencies touched: ...

### Status
- TODO / IN PROGRESS / DONE / BLOCKED

### Details
- Summary of code changes / key decisions.
- Tests run (commands + result).
- Follow-up actions / hand-off notes.
```

Start new sections chronologically. Keep notes concise but actionable so the next agent can resume quickly.

## 2025-11-03 - Codex (Session 1)

### Focus
- Task(s) tackled: Phase 1.1 timeout status integration across header, VM controller, and docs.
- Dependencies touched: `include/hsx_mailbox.h`, `platforms/python/host_vm.py`, docs, pytest coverage.

### Status
- DONE

### Details
- Summary of code changes / key decisions:
  - Added `HSX_MBX_STATUS_TIMEOUT` constant and surfaced it through the Python constant loader.
  - Mailbox wait expirations now return the TIMEOUT code, populate info structs, and emit `mailbox_timeout` events with the new status.
  - Refreshed `docs/abi_syscalls.md` to document the new behaviour and removed the stale TODO.
- Tests run (commands + result):
  - `C:/appz/miniconda/envs/py312/python.exe -m pytest python/tests/test_mailbox_constants.py python/tests/test_mailbox_wait.py python/tests/test_mailbox_svc_runtime.py` (pass).
- Follow-up actions / hand-off notes:
  - Phase 1.2 should introduce the descriptor exhaustion status (`HSX_MBX_STATUS_NO_DESCRIPTOR`) and associated handling.

## 2025-11-03 - Codex (Session 2)

### Focus
- Task(s) tackled: Phase 1.2 descriptor exhaustion handling (status constant, manager limit enforcement, SVC mapping, docs/tests).
- Dependencies touched: `include/hsx_mailbox.h`, `python/mailbox.py`, `platforms/python/host_vm.py`, mailbox unit/runtime tests, ABI docs.

### Status
- DONE

### Details
- Summary of code changes / key decisions:
  - Introduced `HSX_MBX_STATUS_NO_DESCRIPTOR` and wired it through the Python constant loader, mailbox manager, and executive SVC handler.
  - Added a configurable descriptor pool limit to `MailboxManager`, returning the new status when the pool is exhausted and surfacing the code via `MailboxError`.
  - Extended unit and SVC runtime tests to cover descriptor exhaustion, and updated documentation to describe the new status code.
- Tests run (commands + result):
  - `C:/appz/miniconda/envs/py312/python.exe -m pytest python/tests/test_mailbox_constants.py python/tests/test_mailbox_manager.py python/tests/test_mailbox_svc_runtime.py python/tests/test_mailbox_wait.py` (pass).
- Follow-up actions / hand-off notes:
  - Phase 1.3 should define and emit the mailbox event payloads now that status plumbing is in place.

## 2025-11-04 - Codex (Session 3)

### Focus
- Task(s) tackled: Phase 1.3 mailbox event integration (send/recv/wait/wake/timeout/overrun) and schema documentation.
- Dependencies touched: `platforms/python/host_vm.py`, `python/mailbox.py`, executive event handling/tests, `docs/executive_protocol.md`.

### Status
- DONE

### Details
- Summary of code changes / key decisions:
  - Standardised mailbox events to include descriptor/handle/src metadata and added an overrun signal from the manager hook.
  - Wired the mailbox manager to emit instrumentation through the controller, ensured wake/timeout events carry handle/status, and refreshed protocol docs.
  - Added targeted pytest coverage exercising send/recv/wait/wake/timeout/overrun event payloads.
- Tests run (commands + result):
  - `C:/appz/miniconda/envs/py312/python.exe -m pytest python/tests/test_mailbox_constants.py python/tests/test_mailbox_manager.py python/tests/test_mailbox_svc_runtime.py python/tests/test_mailbox_wait.py` (pass).
- Follow-up actions / hand-off notes:
  - Next step: Phase 1.4 resource monitoring APIs (descriptor/queue metrics exposed via snapshot/RPC).

## 2025-11-04 - Codex (Session 4)

### Focus
- Task(s) tackled: Phase 1.4 resource monitoring APIs (descriptor/handle stats, RPC reporting, CLI summary).
- Dependencies touched: python/mailbox.py, platforms/python/host_vm.py, python/execd.py, python/shell_client.py, docs/tests.

### Status
- DONE

### Details
- Summary of code changes / key decisions:
  - Added esource_stats() on the mailbox manager and exposed aggregated metrics (capacity, handles, queue depth) through VM/Executive RPC and shell output.
  - Extended mailbox snapshots with stats, updated shell formatting, and refreshed protocol docs.
  - Added pytest coverage for stats reporting across manager/unit/integration layers.
- Tests run (commands + result):
  - C:/appz/miniconda/envs/py312/python.exe -m pytest python/tests/test_mailbox_manager.py python/tests/test_mailbox_svc_runtime.py python/tests/test_exec_mailbox.py python/tests/test_shell_client.py (pass).
- Follow-up actions / hand-off notes:
  - Ready to begin Phase 1.5 fan-out reclamation validation.


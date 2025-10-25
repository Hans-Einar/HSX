# HSX Shell Implementation Plan

## DR/DG Alignment
- DR-8.1 / DG-8.1: Shell must interoperate with debugger session/event RPCs.
- DR-6.1 / DG-6.4: Shell listen/stdio commands respect mailbox semantics and reserved channels.
- DR-7.1 / DG-7.4: Value/command commands honour numeric addressing + security policies.

## Implementation Notes
- Update python/shell_client.py to call new session APIs (attach/detach vs hsxdbg).
- Ensure mailbox listen paths handle event categories (trace, scheduler) with filtering/back-pressure messaging.
- Keep JSON mode output stable; add version flag to detect feature availability.
- Reference refactorNotes entry for CLI modernization + event stream alignment.

## Playbook (Implementation)
- [ ] Wire shell attach/detach to PID lock aware RPCs.
- [ ] Add commands for session.open/events.subscribe diagnostics.
- [ ] Document fallback paths for legacy servers (no event stream).

## Commit Log
- _Pending_: record shell changes + DR references as commits land.

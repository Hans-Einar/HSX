# HSX Shell Test Plan

## DR Coverage
- DR-8.1: CLI attaches via new session/event APIs.
- DR-6.1 / DR-7.1: Mailbox/value/command commands respect semantics + security.

## Test Matrix
| Area | Test | Notes |
|------|------|-------|
| Session attach | CLI ttach/detach exercises PID locks | Ensure older servers gracefully fallback. |
| Event feed | dbg listen equivalent streaming events | Validate filters + drop warnings. |
| Value/command | al/cmd commands with auth flags | Mirror DR-7.1 policy. |

## Tooling
- CLI integration tests (e.g., pexpect).



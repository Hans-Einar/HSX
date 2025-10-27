# Value & Command Test Plan

## DR Coverage
- DR-7.1: Auth levels / PIN tokens for al.set / cmd.call.
- DR-7.3: Persistence (val.persist) integration.
- DR-3.1: Metadata emission for tooling.

## Test Matrix
| Area | Test | Notes |
|------|------|-------|
| Registration | Register values/commands until capacity hit | Ensure proper status codes + reuse behaviour.
| Auth policy | Attempt unauthorized set/call operations | Expect EPERM and logged warnings.
| Epsilon/rate limit | Repeated al.set with small deltas | Ensure change detection + events.
| Persistence | Toggle al.persist, simulate FRAM load/save | Align with persistence_layout doc.
| Async command | cmd.call_async returning via mailbox | Verify payload (oid,rc) delivered.

## Fixtures / Mocks
- Value/command descriptors stored under (6)/fixtures/valcmd/.
- Mailbox mock for async responses.

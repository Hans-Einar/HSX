# Debugger Test Plan

## DR Coverage
- DR-8.1: Session/event streaming, PID locks, UI integration.

## Test Matrix
| Area | Test | Notes |
|------|------|-------|
| Session lifecycle | Open -> subscribe -> close flows | Verify locks + keepalive. |
| Back-pressure | Flood events, ensure client handles drop warnings + resync | Validate events.ack usage. |
| Panels | Simulate event mix, assert Textual widgets update | Covers registers, watch, trace, scheduler panels. |

## Tooling
- Async integration tests using mocked executive server; snapshot tests for Textual UI.


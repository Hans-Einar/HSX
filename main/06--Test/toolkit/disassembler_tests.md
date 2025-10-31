# Disassembler Test Plan

## DR Coverage
- DR-3.1: Consumes debug metadata accurately.
- DR-8.1: Integrates with event-driven tooling (panel updates).

## Test Matrix
| Area | Test | Notes |
|------|------|-------|
| Symbol resolution | Feed listing sidecar, check UI output | Validate address->symbol mapping. |
| Event updates | Simulate trace events updating highlight | Ensure panel updates without lag. |

## Tooling
- hsxdbg unit tests mocking state cache and panels.


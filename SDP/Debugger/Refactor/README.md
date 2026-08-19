# Debugger Refactor Registry

Refactors are spawned from `DBG-GAP-001`. Each product-code Refactor requires its own
worker -> reviewer -> verification -> exact-head sign-off loop.

| ID | Name | Status | Primary dependency |
|---|---|---|---|
| `DBG-RF-001` | DAP Protocol Baseline Stabilization | `verified_pending_master_signoff` | DBG-GAP-001 |
| `DBG-RF-002` | Debugger Controller, State Machine, Stop Epochs | BLOCKED | DBG-DA-001 |
| `DBG-RF-003` | Session/Transport/Event Health/Recovery | BLOCKED | DBG-DA-001 + controller contract |
| `DBG-RF-004` | Symbol/Source/Address/Inspection Model | BLOCKED | DBG-DA-001 + HSX address contract |
| `DBG-RF-005` | Breakpoint/Watch Ownership/Reconciliation | BLOCKED | DBG-RF-002 + DBG-RF-003 |
| `DBG-RF-006` | Lifecycle and Execution/Stepping Semantics | BLOCKED | DBG-RF-002 + DBG-RF-003 + DBG-RF-004 |
| `DBG-RF-007` | Thin Modular DAP Adapter | BLOCKED | DBG-RF-002..006 |
| `DBG-RF-008` | Modular VS Code Extension and Packaging | BLOCKED | DBG-RF-007 |
| `DBG-RF-009` | Product-Path Cross-Platform Verification | BLOCKED | DBG-RF-002..008 |

`DBG-RF-001` is intentionally narrow and may execute before structural design because it
only repairs the protocol/test baseline needed to trust subsequent work.

Its durable Refactor contract is
`001--DAP_Protocol_Baseline_Stabilization/README.md`. Execution is one bounded Slice,
`DBG-SL-001-001-001`, under `Sprints/001--Debugger_Stabilization/`. Steering acceptance is
recorded in issue #36 against PR #49 head
`403d55c621d50212940b4c8668ac20a3cf8519b5`; the Slice may now be assigned to one fresh
bounded worker.

No other Refactor may start product-code implementation until `DBG-DA-001` and the relevant
`DBG-D-*` contracts are accepted and referenced from the workstream's GitHub issue.

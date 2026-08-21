# Debugger Refactor Registry

Refactors are spawned from `DBG-GAP-001`. Each product-code Refactor requires its own
worker -> reviewer -> verification -> exact-head sign-off loop.

| ID | Name | Status | Primary dependency |
|---|---|---|---|
| `DBG-RF-001` | DAP Protocol Baseline Stabilization | COMPLETE at `208063e` | DBG-GAP-001 |
| `DBG-RF-002` | Debugger Controller, State Machine, Stop Epochs | COMPLETE / STEERING ACCEPTED | frozen DBG-D-001/D-003 + shared interface |
| `DBG-RF-003` | Session/Transport/Event Health/Recovery | COMPLETE / STEERING ACCEPTED | frozen DBG-D-002 + shared interface |
| `DBG-RF-004` | Symbol/Source/Address/Inspection Model | ACTIVE / REVIEW 017 PENDING | DBG-D-003/D-004 + HSX-D-001..003 |
| `DBG-RF-005` | Breakpoint/Watch Ownership/Reconciliation | BLOCKED | DBG-RF-002 + DBG-RF-003 + accepted `dbg.resolver-inspection/1` from DBG-RF-004 |
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
`403d55c621d50212940b4c8668ac20a3cf8519b5`. The bounded Slice completed at signed
implementation head `208063e344b767f82790ce579eba6327e2cdd0ce`, passed independent
review `DBG-RVW-001-001-001`, and passed verification `DBG-VER-001-001-001`.

Steering accepted RF-002/RF-003/integration complete and authorized RF-004 only in issue #38
comment `5362514094`. RF-004 executes through frozen Slices `DBG-SL-001-005-001..007` and
`dbg.resolver-inspection/1`. Issue #42 comment `5362515750` durably clarifies that RF-005
depends on RF-004's accepted typed interface; RF-005..RF-009 remain blocked.

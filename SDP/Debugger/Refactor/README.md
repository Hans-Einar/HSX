# Debugger Refactor Registry

Refactors are spawned from GapAnalysis. Each product-code Refactor requires its own
worker -> reviewer -> verification -> exact-head sign-off loop unless an explicit Steering
exception assigns bounded corrective implementation to Master while preserving fresh
independent review and verification.

| ID | Name | Status | Primary dependency |
|---|---|---|---|
| `DBG-RF-001` | DAP Protocol Baseline Stabilization | COMPLETE at `208063e` | DBG-GAP-001 |
| `DBG-RF-002` | Debugger Controller, State Machine, Stop Epochs | COMPLETE / STEERING ACCEPTED | frozen DBG-D-001/D-003 + shared interface |
| `DBG-RF-003` | Session/Transport/Event Health/Recovery | COMPLETE / STEERING ACCEPTED | frozen DBG-D-002 + shared interface |
| `DBG-RF-004` | Symbol/Source/Address/Inspection Model | SUSPENDED AT REVIEW GATE / ROUTING-C REMEDIATION | DBG-D-003/D-004 + HSX-D-001..003 |
| `DBG-RF-005` | Breakpoint/Watch Ownership/Reconciliation | BLOCKED | DBG-RF-002 + DBG-RF-003 + accepted typed resolver/inspection from DBG-RF-004 |
| `DBG-RF-006` | Lifecycle and Execution/Stepping Semantics | BLOCKED | DBG-RF-002 + DBG-RF-003 + DBG-RF-004 |
| `DBG-RF-007` | Thin Modular DAP Adapter | BLOCKED | DBG-RF-002..006 |
| `DBG-RF-008` | Modular VS Code Extension and Packaging | BLOCKED | DBG-RF-007 |
| `DBG-RF-009` | Product-Path Cross-Platform Verification | BLOCKED | DBG-RF-002..008 |
| `DBG-RF-010` | RF-004 Exact CALL-Site Evidence Fence | ACTIVE CORRECTIVE CHILD | DBG-GAP-002 / DBG-F-027 / corrective child of DBG-RF-004 |
| `DBG-RF-011` | RF-004 Explicit Inspection Factory Dependencies | ACTIVE CORRECTIVE CHILD | DBG-GAP-002 / DBG-F-028 / corrective child of DBG-RF-004 |

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
comment `5362514094`. RF-004 subsequently produced frozen candidate head
`514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`, which passed Batch005 execution but received
`REWORK — Routing C` in fresh independent review `DBG-RVW-001-005-037` / issue #38 comment
`5381348250`.

The review is captured by `DBG-CR-002` and `DBG-GAP-002`. Medium findings fan out to
`DBG-RF-010` (Slice005 exact CALL evidence) and `DBG-RF-011` (Slice006 explicit factory
composition). These are corrective children only; they do not renumber or replace the planned
RF-005..009 roadmap. Parent RF-004 remains suspended until the children and bounded Low rework
converge and a fresh exact-head review passes.

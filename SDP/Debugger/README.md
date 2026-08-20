# Debugger SDP

This track owns the HSX debugger as a product subsystem:

- shared debugger core and state/lifecycle policy;
- executive debug/session/event protocol as consumed by debugger clients;
- CLI debugger behavior;
- Debug Adapter Protocol (DAP) translation;
- VS Code extension integration and debugger-specific views;
- source/symbol/stack/watch/disassembly/trace debugging behavior;
- debugger packaging, compatibility, and cross-platform verification.

It does **not** own HSX VM/ISA semantics except where the debugger requires a documented
runtime capability. Those capabilities are dependencies on the `SDP/HSX` track.

## Current phase

The current product baseline originated on `Implementation/vscode`. `DBG-RF-001` completed
the production-path protocol baseline. Steering accepted the reviewed `DBG-A-001..DBG-A-008`
target direction. Coordinated `DBG-ST-006` / `HSX-ST-001..008` portable-runtime contract
work is complete for review. `HSX-RVW-001-001-006` passed exact proposal content
`b57e368…`; the active gate is
`reviewed_package_pending_master_verification_and_issue_decision_packages`. Every `DBG-D-*`
remains proposed and no structural product implementation is authorized.

Read in this order:

1. `Traceability/CurrentIndex.yaml`
2. `02--Study/001--Legacy_Debugger_Baseline.md`
3. `03--Requirements/001--Debugger_Requirements.md`
4. `CodeReview/001--Legacy_VSCode_Debugger/01--CodeReview.md`
5. `GapAnalysis/001--Debugger_Stabilization/01--GapAnalysis.md`
6. `Refactor/README.md`
7. when `DBG-RF-001` is active, `Refactor/001--DAP_Protocol_Baseline_Stabilization/README.md`
8. the active sprint, iteration, and Slice contract under `Sprints/001--Debugger_Stabilization/`
9. for `DBG-DA-001`, Studies `DBG-ST-002..DBG-ST-005`, the proposed Architecture and Design
   documents, and `DBG-ST-006`

`DBG-ST-006` remains the Debugger dependency umbrella. `DBG-RF-002..DBG-RF-009` remain
blocked until Master verification and issue decision packages complete, portable HSX
contracts are accepted, the relevant `DBG-D-*` contracts are frozen by Steering, and explicit
implementation Slices are authorized.

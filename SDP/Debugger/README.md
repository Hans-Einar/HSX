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
the production-path protocol baseline, and the active activity is `DBG-DA-001`: the proposed
modular debugger architecture passed independent exact-head review and awaits Steering
acceptance. No structural product implementation is authorized.

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

`DBG-DA-001` is the active design gate. `DBG-RF-002..DBG-RF-009` remain blocked until issue
#38 records Steering acceptance of the relevant target-state contracts.

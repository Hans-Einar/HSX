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
work is reviewed and verified. `HSX-RVW-001-001-006` and `HSX-VER-001-001-001` passed exact
proposal content `b57e368…`, and Master exact-content sign-off passed. Steering froze the
portable HSX target baseline and `DBG-D-001..010`, then authorized RF-002, RF-003 and one
early integration Slice in #38 comment `5356484309`. Steering accepted that published first
wave complete and authorized RF-004 only in #38 comment `5362514094`.

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

`DBG-ST-006` and `DBG-IT-001-004` are complete. Active work is `DBG-IT-001-005` /
`DBG-RF-004` with frozen Slices `DBG-SL-001-005-001..007` and corrected public-interface
candidate `dbg.resolver-inspection/1` awaiting `DBG-RVW-001-005-013`. Existing Executive behavior remains
`hsx.python-debug-legacy/1`; RF-005..009, Executive/VM/AVR and frontend migration remain
blocked.

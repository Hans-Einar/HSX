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

The current baseline is legacy code on branch `Implementation/vscode`, which is 84
commits ahead of the repository `main` branch. The immediate activity is a formal
legacy CodeReview and GapAnalysis before any broad redesign.

Read in this order:

1. `Traceability/CurrentIndex.yaml`
2. `02--Study/001--Legacy_Debugger_Baseline.md`
3. `03--Requirements/001--Debugger_Requirements.md`
4. `CodeReview/001--Legacy_VSCode_Debugger/01--CodeReview.md`
5. `GapAnalysis/001--Debugger_Stabilization/01--GapAnalysis.md`
6. `Refactor/README.md`

The next structural activity after baseline correctness fixes is
`DBG-DA-001` — an optimal debugger architecture DesignAnalysis that decides what is
reused, adapted, or replaced.

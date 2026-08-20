# HSX Portable Debug Contract Handoff

- Status: STUDIES COMPLETE — MASTER SYNTHESIS ACTIVE
- Coordinator: `HSX-ST-001`, issue #47
- Debugger dependency: `DBG-ST-006`, issue #38
- Iteration: `DBG-IT-001-003`
- Planned review: `HSX-RVW-001-001-001`

## Current objective

Synthesize stable portable contract proposals and conformance fixtures from completed
`HSX-ST-001..HSX-ST-006`, review the exact package, and return to Steering before any Debugger
design freeze or product work.

## Authority

- issue #38 comment `5348190806`;
- issue #47 comment `5348192567`;
- HSX and Debugger CurrentIndex/Relations/Ledgers;
- `DBG-ST-006` and `DBG-IT-001-003`.

## Exact next step

Master allocates stable IDs and synthesizes Requirements/Architecture/Design plus the
`DBG-ST-006` cross-track matrix. Then a fresh reviewer inspects the exact complete package.

## Guards

No product, AVR, `DBG-D-*` freeze, or `DBG-RF-002..DBG-RF-009` implementation is authorized.
The original dirty `Implementation/vscode` worktree remains untouched; controlled work uses
`codex/dbg-st-006`.

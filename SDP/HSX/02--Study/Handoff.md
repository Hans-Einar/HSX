# HSX Portable Debug Contract Handoff

- Status: REVIEW REWORK COMPLETE — FRESH REVIEW PENDING
- Coordinator: `HSX-ST-001`, issue #47
- Debugger dependency: `DBG-ST-006`, issue #38
- Iteration: `DBG-IT-001-003`
- Planned review: `HSX-RVW-001-001-001`

## Current objective

Obtain fresh exact-head review of the corrected portable contract package and `DBG-ST-006`
mapping, then return to Steering before any Debugger design freeze or product work.

## Authority

- issue #38 comment `5348190806`;
- issue #47 comment `5348192567`;
- HSX and Debugger CurrentIndex/Relations/Ledgers;
- `DBG-ST-006` and `DBG-IT-001-003`.

## Exact next step

Commit the corrected Requirements/Architecture/Design and `DBG-ST-006` mapping, then assign
fresh `HSX-RVW-001-001-002` to the exact complete head.

## Review history

- `HSX-RVW-001-001-001` reviewed `5fff403f6668f794b760caf64ef34b4d1ecb4ae3`
  and returned one High plus three Medium findings.
- Master restored opaque target-bound LoadedImageRef identity, phase-linearized exact-step
  semantics, one canonical capability registry, and synchronized cross-track status/Handoff.
- No contract acceptance or implementation authority resulted.

## Guards

No product, AVR, `DBG-D-*` freeze, or `DBG-RF-002..DBG-RF-009` implementation is authorized.
The original dirty `Implementation/vscode` worktree remains untouched; controlled work uses
`codex/dbg-st-006`.

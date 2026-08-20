# HSX Portable Debug Contract Handoff

- Status: CONTRACTS RESYNTHESIZED — FRESH REVIEW PENDING
- Coordinator: `HSX-ST-001`, issue #47
- Debugger dependency: `DBG-ST-006`, issue #38
- Iteration: `DBG-IT-001-003`
- Planned fresh review: `HSX-RVW-001-001-005`

## Current objective

Obtain fresh exact-head `HSX-RVW-001-001-005` of the complete portable contract package and
`DBG-ST-006`, then return a reviewed decision package before any Debugger design freeze or
product work.

## Authority

- issue #38 comment `5348190806`;
- issue #47 comment `5348192567`;
- HSX and Debugger CurrentIndex/Relations/Ledgers;
- `DBG-ST-006` and `DBG-IT-001-003`.

## Exact next step

Commit the complete proposal head and assign `HSX-RVW-001-001-005` to that exact head.

## Master verification

Read-only proposal verification passed: resource oracle 114; address/ABI 40 with one
environment skip; execution 99 plus 7; supplemental ABI 15 plus 7; bundle/source 18 with one
environment skip. Six traceability YAML files, both Ledgers, 36/5/5 stable IDs, ten
DBG mappings, Markdown fences and `git diff --check` passed. This is not independent review.

## Review history

- `HSX-RVW-001-001-001` reviewed `5fff403f6668f794b760caf64ef34b4d1ecb4ae3`
  and returned one High plus three Medium findings.
- Master restored opaque target-bound LoadedImageRef identity, phase-linearized exact-step
  semantics, one canonical capability registry, and synchronized cross-track status/Handoff.
- `HSX-RVW-001-001-002` confirmed all technical closures but required rework for stale
  current review-stage references. Master synchronized them and reserved review attempt 3.
- `HSX-RVW-001-001-003` confirmed the contract package but found three remaining stale
  current-gate statements. Master synchronized them and reserved review attempt 4.
- `HSX-RVW-001-001-004` confirmed prior closure but required routing of unresolved ABI/recipe/
  register and bundle/source canonicalization questions. Master activated ST-007/ST-008.
- `HSX-ST-007` froze the truthful current ABI profile, bounded unwind/location recipe schemas
  and revision-fenced register mutation proposal. `HSX-ST-008` froze the non-recursive
  artifact/load/bundle/binding and exact source-identity proposal. Master synthesized both.
- No contract acceptance or implementation authority resulted.

## Guards

No product, AVR, `DBG-D-*` freeze, or `DBG-RF-002..DBG-RF-009` implementation is authorized.
The original dirty `Implementation/vscode` worktree remains untouched; controlled work uses
`codex/dbg-st-006`.

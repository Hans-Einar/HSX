# HSX Portable Debug Contract Handoff

- Status: REMOTE PUBLICATION VERIFIED — AWAITING STEERING
- Coordinator: `HSX-ST-001`, issue #47
- Debugger dependency: `DBG-ST-006`, issue #38
- Iteration: `DBG-IT-001-003`
- Completed review: `HSX-RVW-001-001-005` — REWORK at
  `84df21d763b73209efd0292990799f469283460a`
- Final fresh review: `HSX-RVW-001-001-006` — PASS
- Verification: `HSX-VER-001-001-001` — PASS
- Master sign-off: PASS on `b57e368f77bb533b09397d633fc92565655e1668`
- Decision package: issue #47 comment `5355340420`
- Cross-track package: issue #38 comment `5355340598`
- Publication blocker: issue #47 comment `5356183884`, issue #38 comment `5356186692`
- Remote branch: `origin/codex/dbg-st-006`
- Fresh-checkout verified remote head: `89cb74a10ce36d8b0f4d0cc60332d3070c2c635f`
- Remote-resolvable proposal content: `b57e368f77bb533b09397d633fc92565655e1668`
- Active gate: `steering_decision_issues_47_38`

## Current objective

The final reviewed/verified/sign-off chain is published and fresh-checkout verified.
Stop and await Steering decisions in issues #47/#38. No proposal-content change, acceptance,
design freeze or implementation dispatch is permitted before a later durable decision.

## Authority

- issue #38 comment `5348190806`;
- issue #47 comment `5348192567`;
- HSX and Debugger CurrentIndex/Relations/Ledgers;
- `DBG-ST-006` and `DBG-IT-001-003`.

## Exact next step

Wait for Steering. If Steering accepts or requests rework, reconstruct the next gate from the
issue comments and CurrentIndex before any design freeze or implementation authorization.

## Remote publication verification

- GitHub resolved full proposal SHA `b57e368f77bb533b09397d633fc92565655e1668`.
- Existing remote branch advanced without force from `c283dd45689c0d9a0f195d3a897d3c5efd78e962`
  to `89cb74a10ce36d8b0f4d0cc60332d3070c2c635f`.
- A fresh clone of that remote head passed 114; 40/1 skip; 99+7; 15+7; 18/1 skip;
  Python+Node 4/4; eight YAML; 63 Ledger records; Markdown; ID/mapping and diff checks.
- Both `c283dd4…→89cb74a…` and the complete proposal range are SDP-only and contain no
  product/runtime/extension/AVR change.

## Master verification

`HSX-VER-001-001-001` passed against proposal content `b57e368…` and review-record head
`ef1f8d8…`: resource oracle 114; address/ABI 40 with one environment skip; execution 99 plus
7; supplemental ABI 15 plus 7; bundle/source 18 with one environment skip; Python+Node golden
vectors 4/4; eight YAML, both Ledgers/57 records, 52 Markdown files, 36/5/5 stable IDs, ten DBG
mappings and diff/scope guards passed.

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
- `HSX-RVW-001-001-005` reviewed exact head `84df21d763b73209efd0292990799f469283460a`
  and returned three Medium findings: undeclared current f16 upper-bit nonconformance,
  non-unique canonical digest bytes, and stale exact-head/Handoff reconstruction. Findings are
  durable in issue #47 comment `5354906185` and issue #38 comment `5354906338`.
- `HSX-RVW-001-001-006` independently reviewed exact proposal content `b57e368f…` plus
  trace-only assignment head `24beb82…` and returned PASS with no Blocking/High/Medium
  findings. Master verification and issue decision packages remain pending.
- No contract acceptance or implementation authority resulted.

## Guards

No product, AVR, `DBG-D-*` freeze, or `DBG-RF-002..DBG-RF-009` implementation is authorized.
The original dirty `Implementation/vscode` worktree remains untouched; controlled work uses
`codex/dbg-st-006`.

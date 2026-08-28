# DBG-RVW-001-005-009 — RF-004 Interface Review Attempt 3

- Status: **REWORK**
- Reviewed exact head: `07f7e16040bec1c225d263c682066f65b173e6aa`
- Remote branch: `origin/codex/dbg-rf-004`
- Review mode: fresh independent, read-only
- Prior reviews: `DBG-RVW-001-005-007`, `DBG-RVW-001-005-008` — REWORK
- Next review: `DBG-RVW-001-005-010`

## Confirmed closures

- review 007 stack-handle ownership and live Relations findings;
- StopEpoch evidence-grade and first-match mismatch matrix;
- variable handles/structural pieces exist, though broader enumeration remained incomplete;
- separate legacy index/provenance exists, though a transitive SourceRef leak remained.

## Findings

1. **High — canonical LoadedImageRef TargetRef projection undefined.** Composite TargetRef had
   no exact scalar mapping to canonical vector 4's `target_ref` value.
2. **High — recipe limit status contradicted HSX-D-002.** Bound exhaustion was a separate
   LIMIT_EXCEEDED status rather than `unsupported(limit_exceeded)`.
3. **High — inspection composition queries incomplete.** Artifact index lacked source/type/
   lexical-scope/variable enumeration, and generic expression results wrongly required a
   variable ID/name.
4. **High — Slice sequencing conflicted with recipe ownership.** Artifact Slice 003 had to
   parse/validate recipe DTOs owned only by later Slice 005.
5. **Medium — legacy no-SourceRef guarantee leaked transitively.** Legacy functions reused
   portable FunctionRecord with optional SourceLocation/SourceRef.

No product finding or accepted DBG/HSX design-change request was reported. Rework remains
within the candidate RF-004 interface/Slice/trace surface.

## Independent evidence

- exact local/tracking/live remote head and clean worktree: PASS;
- base ancestry from `69a54aeb3394d3cd4792bce620748e15bab69f1f`: PASS;
- 26 changed paths, all SDP-only; no product/Executive/VM/AVR/frontend change;
- `git diff --check`: PASS;
- three YAML files and 118-row append-only Ledger: PASS;
- six then-current Slice IDs/paths, 22 Markdown fences/links and RF-004-only authority: PASS;
- issue #38 comment `5362514094` / #42 comment `5362515750`: matched.

This is not product verification or Master sign-off.

## Master disposition

REWORK accepted. Master freezes TargetRef.canonical_ref and exact LoadedImageRef emission,
maps every bound exhaustion to UNSUPPORTED/limit_exceeded, adds source/type/scope/variable
queries plus separate ExpressionValue, introduces early bounded recipe foundation Slice
`DBG-SL-001-005-007`, and adds LegacyFunctionRecord so legacy APIs cannot return SourceRef.
Fresh `DBG-RVW-001-005-010` is required before any product worker.

# DBG-RVW-001-005-017 — RF-004 Interface Review Attempt 10

- Status: **REWORK**
- Reviewed exact head: `cb88b62b7c45ea6ebfe31c40e522daa3adcf8896`
- Remote branch: `origin/codex/dbg-rf-004`
- Review mode: fresh independent, read-only
- Prior interface reviews: `DBG-RVW-001-005-007..010`, `...012..016` — REWORK
- Next review: `DBG-RVW-001-005-018`

## Confirmed closures

LocationRow exact ABI and all review 007..016 binding, descriptor, recipe, query, variable,
lifetime, handle, legacy, ordering and seven-Slice authority findings.

## Findings

1. **High — DebugBindingValidator omitted complete artifact/binding coherence.** It did not
   compare recomputed binding_digest or exact ArtifactRef among LoadedImageRef, bundle ref and
   bundle identity.
2. **High — variable symbol/location schema forced impossible global/local forms.** Variable
   symbols required static address and LocationRow required non-null function/scope, preventing
   normal global and stack/register/constant locals without sentinels.
3. **Medium — RF-004 responsibility diagram/dependency row retained old Slice order.** Recipe
   foundation appeared after artifact/source and inspection omitted Slice 007 dependency.

No product finding or accepted DBG/HSX design-change request was reported.

## Independent evidence

- exact local/tracking/live remote head, clean worktree and base ancestry: PASS;
- 34 SDP-only paths and `git diff --check`: PASS;
- three YAML files and 132-row append-only Ledger: PASS;
- seven Slice mappings/order, Markdown and authority/gate checks: PASS.

This is not product verification or Master sign-off.

## Master disposition

REWORK accepted. Master adds exact ArtifactRef and recomputed binding_digest validator rows,
makes GLOBAL/LOCAL/CONSTANT SymbolRecord addressless and LocationRow function/scope nullable
under exact kind invariants, updates query/join/order/composition behavior, and aligns the
responsibility diagram/inspection dependency. Fresh `DBG-RVW-001-005-018` is required before
any product worker.

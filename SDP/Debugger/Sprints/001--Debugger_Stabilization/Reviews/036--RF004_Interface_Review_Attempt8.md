# DBG-RVW-001-005-015 — RF-004 Interface Review Attempt 8

- Status: **REWORK**
- Reviewed exact head: `18c0a26cad4c2d82e4a23ef0ec3e6409b022cb95`
- Remote branch: `origin/codex/dbg-rf-004`
- Review mode: fresh independent, read-only
- Prior interface reviews: `DBG-RVW-001-005-007..010`, `...012..014` — REWORK
- Next review: `DBG-RVW-001-005-016`

## Confirmed closures

REGISTERS/LOCALS composition; CFA roles/failures; explicit descriptor signatures; unit-based
address/range/arithmetic/byte conversion; every prior identity, lifetime, recipe, query,
legacy, sequencing, ownership and dependency finding.

## Findings

1. **High — public recipe/stack/location entrypoints did not validate descriptor against the
   accepted binding/bundle.** Passing ArchitectureDescriptor alone allowed ref/digest mismatch
   outside InspectionService.create.
2. **Medium — stale/foreign handle classification still matched stale history by opaque epoch
   string rather than complete retained InspectionContext.** A foreign equal-string handle
   conflicted with the Slice's UNKNOWN rule.

No product finding or accepted DBG/HSX design-change request was reported.

## Independent evidence

- exact local/tracking/live remote head and clean worktree: PASS;
- base ancestry from `69a54aeb3394d3cd4792bce620748e15bab69f1f`: PASS;
- 32 SDP-only changed paths, no product/Verification/sign-off scope;
- `git diff --check`: PASS;
- three YAML files and 128-row append-only Ledger: PASS;
- seven Slice mappings/order, Markdown and authority/gate checks: PASS.

This is not product verification or Master sign-off.

## Master disposition

REWORK accepted. Master creates one typed DebugBindingValidator used before artifact,
recipe, stack, location and inspection work; adds exact binding/bundle to recipe evaluation and
index to location evaluation; and makes handle STALE require full retained-context equality,
with foreign equal-string context UNKNOWN. Fresh `DBG-RVW-001-005-016` is required before any
product worker.

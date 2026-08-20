# DBG-RVW-001-005-010 — RF-004 Interface Review Attempt 4

- Status: **REWORK**
- Reviewed exact head: `72b06ad0bae53b70bc3d64edad91591998d2408d`
- Remote branch: `origin/codex/dbg-rf-004`
- Review mode: fresh independent, read-only
- Prior reviews: `DBG-RVW-001-005-007..009` — REWORK
- Next review: `DBG-RVW-001-005-012`

## Confirmed closures

- TargetRef canonical scalar/LoadedImageRef vector mapping and collision rejection;
- HSX canonical artifact/bundle/binding projections;
- `UNSUPPORTED`/`limit_exceeded` bound outcome;
- source/type/scope/variable enumeration and separate ExpressionValue;
- early recipe Slice 007 and seven-Slice execution order;
- LegacyFunctionRecord prevents transitive SourceRef;
- StopEpoch matrix, disjoint ownership, early snapshot/metadata modules and RF-005 gate.

## Findings

1. **High — InspectionService composition/lifetime API not frozen.** Public queries did not
   define dependency injection, epoch/session construction, active-epoch replacement,
   invalidation or persistent handle-store lifetime.
2. **High — variable identity join undefined.** Symbol enumeration used symbol_id while
   LocationRow, expressions, results and handle keys used a separate undefined variable_id.
3. **Medium — observable index order named absent address fields and lacked SymbolKind order.**

No product finding or accepted DBG/HSX design-change request was reported.

## Independent evidence

- exact local/tracking/live remote head, clean worktree and `+0/-0`: PASS;
- base ancestry/merge-base `69a54aeb3394d3cd4792bce620748e15bab69f1f`: PASS;
- 28 SDP-only changed paths; no product/Verification/sign-off path;
- `git diff --check`: PASS;
- three YAML files and 120-row append-only Ledger: PASS;
- seven Slice IDs/paths/order/review/verification mappings: PASS;
- 24 Markdown fences and local-link check: PASS;
- RF-004 only active; RF-005..009 blocked; issue #38/#42 authority matched.

This is not product verification or Master sign-off.

## Master disposition

REWORK accepted. Master freezes explicit InspectionService dependency factory,
open/same/new/conflicting epoch behavior, EpochInspectionSession, handle-store lifecycle,
idempotent invalidation and concurrency linearization; standardizes all variable identity on
SymbolRecord.symbol_id with referential checks; and corrects address fields plus SymbolKind
rank. Because review ID 011 is reserved for Slice 007, fresh interface review is
`DBG-RVW-001-005-012`. No product worker starts before PASS.

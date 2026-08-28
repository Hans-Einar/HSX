# DBG-RVW-001-005-011 — RF-004 Recipe Foundation Review

- Status: **REWORK**
- Product head: `ec75c4eb22333368cbe4847920dc4420fe8231cf`
- Coordination head: `76d44110156b68e63fac448e38847e6cce28a716`
- Interface: `dbg.resolver-inspection/1.2`
- Next review: `DBG-RVW-001-005-033`

## Findings

1. **High — pure component validator accepts malformed postfix/limit rows.** It omits stack
   transitions/finality, constant fit, aggregate dereference count and the 16-piece limit.
2. **Medium — explicit unavailable GPR terminals reject.** UNDEFINED, UNAVAILABLE and
   OPTIMIZED_OUT must produce unavailable evidence.
3. **Medium — exact parsing gaps.** bool/float pass integer fields; unknown unwind schema is
   CORRUPT rather than UNSUPPORTED.
4. **Medium — LocationEvaluator index annotation is `object`.** Frozen signature requires
   forward-referenced `DebugArtifactIndex`.

## Passing evidence

No duplicate definitions or ownership leak. Binding-first, memory-only reads, selected-frame
context, GPR/PSW validation and no fallback/cache/R7 pass. Owned34, Slice00247, broad218+1,
compile/import/export170/41, exact scope, trace and git mechanics pass.

## Master disposition

REWORK accepted. Fresh corrective worker owns the same three files. Add shared abstract postfix
validation, exact limits/parsing/schema classification, unavailable rule support and exact
annotation plus regressions. Fresh review is `DBG-RVW-001-005-033`.

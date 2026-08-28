# DBG-RVW-001-005-018 — RF-004 Interface Review Attempt 11

- Status: **REWORK**
- Reviewed exact head: `08719457a341b01ca8f64ea568e1ab04678dd10d`
- Remote branch: `origin/codex/dbg-rf-004`
- Review mode: fresh independent, read-only
- Prior interface reviews: `DBG-RVW-001-005-007..010`, `...012..017` — REWORK
- Next review: `DBG-RVW-001-005-019`

## Confirmed closures

Complete artifact/binding validation, addressless variable symbols/nullable LocationRows,
selected-frame/ABI binding, corrected seven-Slice diagram and every earlier finding.

## Findings

1. **High — global VariableExpression could not represent None/None function/scope.** It
   required a non-null lexical scope and would need a sentinel or omitted global Watch support.
2. **High — scalar raw_bytes encoding undefined.** Register/constant numeric values had no
   byte order, fixed-width or non-byte-aligned padding rule.
3. **Medium — SourceResolver outcome precedence incomplete.** Multiple winning-tier paths with
   one matching content candidate could be resolved, ambiguous or mismatch by worker choice.
4. **Medium — IdScheme retained old Slice-005 recipe/location ownership wording.**

No product finding or accepted DBG/HSX design-change request was reported.

## Independent evidence

- exact local/tracking/live remote head, clean worktree and base ancestry: PASS;
- 35 SDP-only paths and `git diff --check`: PASS;
- three YAML files and 134-row append-only Ledger: PASS;
- seven Slice mappings/order, Markdown and authority/gate checks: PASS.

This is not product verification or Master sign-off.

## Master disposition

REWORK accepted. Master makes VariableExpression function/scope nullable with exact symbol
join, freezes ScalarBytes fixed-width/two's-complement/byte-order/padding rules plus byte-order
sources for every expression/location kind, freezes resolver outcome precedence, and corrects
IdScheme Slice-005 ownership. Fresh `DBG-RVW-001-005-019` is required before any product worker.

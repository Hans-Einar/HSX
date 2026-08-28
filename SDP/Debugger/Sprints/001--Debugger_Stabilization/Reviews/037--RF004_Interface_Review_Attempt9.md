# DBG-RVW-001-005-016 — RF-004 Interface Review Attempt 9

- Status: **REWORK**
- Reviewed exact head: `e330a7b344715dfdbae0de46e44f4720b4387d4e`
- Remote branch: `origin/codex/dbg-rf-004`
- Review mode: fresh independent, read-only
- Prior interface reviews: `DBG-RVW-001-005-007..010`, `...012..015` — REWORK
- Next review: `DBG-RVW-001-005-017`

## Confirmed closures

Shared DebugBindingValidator is required by every public entrypoint and exact-context handle
STALE/foreign UNKNOWN classification is coherent. All earlier review findings and mechanical/
authority gates remain closed.

## Finding

1. **High — LocationRow lacked AbiDescriptorRef.** The evaluator required `row.abi == ABI` and
   HSX-D-002 binds location entries to exact ABI, but the closed DTO could not represent it.

No product finding or accepted DBG/HSX design-change request was reported.

## Independent evidence

- exact local/tracking/live remote head, clean worktree and base ancestry: PASS;
- 33 SDP-only paths and `git diff --check`: PASS;
- three YAML files and 130-row append-only Ledger: PASS;
- seven Slice mappings/order, Markdown and authority/gate checks: PASS.

This is not product verification or Master sign-off.

## Master disposition

REWORK accepted. Master adds exact `abi: AbiDescriptorRef` to LocationRow and requires recipe/
artifact row construction, validation and evaluator tests to reject ABI mismatch before reads.
Fresh `DBG-RVW-001-005-017` is required before any product worker.

# DBG-RVW-001-005-012 — RF-004 Interface Review Attempt 5

- Status: **REWORK**
- Reviewed exact head: `573f396e29de728f69abb0961e9b79a2fdb3c29d`
- Remote branch: `origin/codex/dbg-rf-004`
- Review mode: fresh independent, read-only
- Prior interface reviews: `DBG-RVW-001-005-007..010` — REWORK
- Next review: `DBG-RVW-001-005-013`

## Confirmed closures

All review 007..009 findings and review 010's symbol_id/order findings; seven-Slice ownership/
order; exact canonical projections; recipe outcomes; public inspection composition; legacy
separation; StopEpoch matrix; RF-005 dependency and authority fences.

## Findings

1. **High — invalidated epochs could be reopened.** Service stale history did not participate
   in open_epoch after active invalidation/close, close terminality was unspecified, and direct
   handle-store repeated invalidation had no frozen result.
2. **High — DomainHandle could alias across services.** Handle equality contained only opaque
   epoch string/kind/serial rather than exact target/image/stop/snapshot context.
3. **High — service factory did not enforce complete architecture/profile identity.** It
   compared architecture ref but not bundle descriptor digest, ABI ref/digest or accepted
   capability profile, and mismatch status/codes were unspecified.

No product finding or accepted DBG/HSX design-change request was reported.

## Independent evidence

- exact local/tracking/live remote head and clean worktree: PASS;
- ancestry from `69a54aeb3394d3cd4792bce620748e15bab69f1f`: PASS;
- 29 changed paths, all SDP-only; no product/Verification/sign-off scope;
- `git diff --check`: PASS;
- three YAML files and 122-row append-only Ledger: PASS;
- seven Slice IDs/paths/order/review+verification mappings: PASS;
- Markdown fences/local links and RF-004-only authority: PASS.

This is not product verification or Master sign-off.

## Master disposition

REWORK accepted. Master retains service-lifetime stale history and rejects every stale-ID
open, makes close terminal and direct invalidation idempotent, embeds full InspectionContext
in DomainHandle with exact foreign/stale resolution, and freezes first-match architecture/
ABI ref+digest/full-profile/limit factory validation. Fresh `DBG-RVW-001-005-013` is required
before any product worker.

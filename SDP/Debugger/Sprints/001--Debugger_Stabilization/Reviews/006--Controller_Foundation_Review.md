# DBG-RVW-001-004-001 — RF-002 Controller Foundation Review

- Status: **REWORK REQUIRED**
- Slice: `DBG-SL-001-004-001`
- Exact implementation head: `a0e986c46d741ee46ba7f21615811723630414d0`
- Base: `80f6fa095eb749f7ec83674bd7dae7a8e58cefd3`
- Reviewer: fresh independent
- Product changes by reviewer: none

## Findings

1. **High — post-GAP/LOST events remain state-authoritative.** Gap processing advances
   `last_event_sequence` to unapplied observed sequence and later exact-stamp events can restore
   STOPPED/open an epoch while event health is GAP/LOST and recovery REQUIRED.
2. **High — deadline identity is not correlated.** Pending operations store no deadline ID;
   any same-operation/generation expiry can fail a live retry/reservation.
3. **High — subscribe can race close.** A subscriber added between cleanup snapshot and
   `_closed` publication survives with worker alive after controller close completes.
4. **Medium — reconcile retires pending reconcile operation without correlated CommandResult.**

## Positive evidence

- Required suites: `81 passed`.
- v1.1 reserve/promote/burn/parent/namespace probes: PASS.
- Compile/import, six-file scope, shared-interface hash, diff check and clean worktree: PASS.

Fresh rework worker and `DBG-RVW-001-004-005` are required. No verification/sign-off follows.

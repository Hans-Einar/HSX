# HSX-RVW-001-001-004 — Portable Debug Runtime Contract Review Attempt 4

- Status: REWORK REQUIRED
- Exact reviewed head: `cbddfa24d3cbb25bf7a17c63a0146ee8d0600883`
- Issues: #47/#38; comments `5354421778` / `5354421925`

## Findings

### Medium — open address/ABI questions lack decisions or routes

Concrete ABI/profile selection, unwind/location recipe schema boundary, bundle digest
canonicalization, source identity/case contract and raw-register-write semantics from
`HSX-ST-003` were absent from synthesis and not routed to numbered Studies.

### Medium — recursive image/debug-bundle identity

LoadedImageRef included accepted bundle digest while ImageDebugBundle bound exact
LoadedImageRef. Without a canonical non-recursive digest/binding model, identity cannot be
constructed deterministically.

## Required rework

- `HSX-ST-007` owns ABI profile, recipe schema and raw-register semantics.
- `HSX-ST-008` owns bundle/source identity and digest canonicalization.
- Master synthesizes their outputs and removes recursive identity before a fresh review.

## Positive validation

Prior technical closures, 10 mappings, 36/5/5 IDs, provenance, profiles, fixtures, guards,
eight YAML/two NDJSON files, links/fences, diff-check and SDP-only scope passed. Tests: 114;
40/1 skipped; 7 passed.

No implementation or AVR authority follows.

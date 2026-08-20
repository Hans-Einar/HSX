# HSX Core Traceability IDs

Namespace: `HSX`.

The HSX core track uses the shared SDP artifact classes defined in `SDP/Shared/Process.md`, for example `HSX-ST-001`, `HSX-R-001`, `HSX-A-001`, `HSX-DA-001`, `HSX-D-001`, `HSX-CR-001`, `HSX-GAP-001`, `HSX-RF-001`, and corresponding sprint/review/verification IDs.

The existing DR, DG, and DO identifiers remain legacy provenance identifiers until the migration study maps them to stable HSX-track IDs. Historical identifiers must not be deleted or recycled during migration.

## Allocated portable debug-runtime IDs

- `HSX-R-001..HSX-R-036` — proposed portable runtime requirements
- `HSX-A-001..HSX-A-005` — proposed portable architecture boundaries
- `HSX-D-001..HSX-D-005` — proposed portable contract groups
- `HSX-RVW-001-001-001` — independent cross-track contract review
- `HSX-RVW-001-001-002` — fresh exact-head re-review after required corrections
- `HSX-RVW-001-001-003` — fresh exact-head review after stage-coherence correction
- `HSX-RVW-001-001-004` — fresh exact-head review after final current-gate correction
- `HSX-ST-007` — ABI profile/recipe/register semantics follow-up
- `HSX-ST-008` — debug bundle/source identity canonicalization follow-up
- `HSX-RVW-001-001-005` — fresh exact-head review after supplemental Studies
- `HSX-RVW-001-001-006` — final fresh exact-content review after review-005 corrections
- `HSX-VER-001-001-001` — formal verification of exact portable-contract proposal content

These IDs are stable but their artifacts remain target/proposed pending review and Steering
acceptance. Stable numbering is not implementation authority.

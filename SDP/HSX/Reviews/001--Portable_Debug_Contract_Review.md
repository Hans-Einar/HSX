# HSX-RVW-001-001-001 — Portable Debug Runtime Contract Review

- Status: REWORK REQUIRED
- Exact reviewed head: `5fff403f6668f794b760caf64ef34b4d1ecb4ae3`
- Studies: `HSX-ST-001..HSX-ST-006`, `DBG-ST-006`
- Issues: #47/#38; finding comments `5354102185` / `5354102417`

## Findings

### High — loaded-image identity weakened

Synthesis omitted the target-bound opaque `LoadedImageId/LoadedImageRef` required by
`HSX-ST-002`, allowing identical artifacts with equal generation numbers on different targets
to alias. Required correction: separate ArtifactRef from target-scoped never-reused
LoadedImageRef and carry it through requirements/design/debug bundle/resources.

### Medium — exact-step zero-count and precedence conflict

The design omitted pre-dispatch pause/stale/target-loss zero-retirement outcomes and replaced
the Study's phase/linearization contract with a fixed reason order. Required correction:
restore phase-based causality and leave fault/BRK retirement to the accepted ISA profile.

### Medium — capability registry inconsistency

Architecture and Design used conflicting names/composition for event/resource capabilities.
Required correction: one exact canonical registry and full-profile composition.

### Medium — cross-track stage and Handoff stale

HSX/Debugger CurrentIndexes and both Handoffs disagreed about `DBG-ST-006` and proposal/review
stage. Required correction: synchronize current state and next review.

## Validation

- 36 unique requirements, 5 architecture IDs, 5 design IDs;
- all ten `DBG-ST-006` mappings present;
- YAML/NDJSON, Markdown fences, IDs, fixtures and `git diff --check`: PASS;
- SDP-only scope;
- read-only aggregate: `161 passed, 1 skipped` (Windows symlink privilege).

## Next review

Fresh review is `HSX-RVW-001-001-002`. This record grants no contract acceptance,
implementation authority or AVR scope.

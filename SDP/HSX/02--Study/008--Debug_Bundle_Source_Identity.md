# HSX-ST-008 — Debug Bundle and Source Identity Canonicalization

- Status: ACTIVE STUDY
- Spawned from: `HSX-ST-003`, review `HSX-RVW-001-001-004`
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`

## Question and scope

Define a non-recursive canonical digest/binding model for ArtifactRef, LoadedImageRef,
ImageDebugBundle and source identities, including filesystem case and relocation semantics.

## Evidence sources

`HSX-ST-002/003`; HXE/.sym/sources schemas; linker/source-map behavior; current loaders,
symbol consumers and path/case/relocation tests.

## Required decisions

- canonical digest scopes/serialization and excluded self-referential fields;
- reusable bundle identity versus target-specific binding record;
- exact ArtifactRef/LoadedImageRef/bundle/source relationships and mismatch outcomes;
- stable source identity, spelling/checksum/case/collision and local-resolution separation;
- degraded legacy profile and conformance fixtures.

## Findings and uncertainty

To be completed by the assigned worker.

## Traceability and guard

Map to `HSX-R-004`, `HSX-R-015`, `HSX-A-001/002`, `HSX-D-001/002`, `DBG-D-003/004/006`.
No numeric new contract IDs, product changes or AVR decisions.

# HSX-RVW-001-001-005 — Portable Debug Runtime Contract Review Attempt 5

- Status: **REWORK REQUIRED**
- Exact reviewed proposal head: `84df21d763b73209efd0292990799f469283460a`
- Reviewer role: fresh independent cross-track architecture/contract reviewer
- Issues: #47/#38; comments `5354906185` / `5354906338`
- Product/AVR authority: **NONE**

## Findings

### Medium — current f16 upper-bit nonconformance is not declared

`HSX-ST-007` and the synthesized `hsx.abi.llc-r7-word32/1` require one-word f16 values with
zero upper 16 bits. Current `FADD`/`FSUB`/`FMUL`/`FDIV`/`I2F` preserve the destination
register's existing upper 16 bits. A compiled allocator-reuse probe returned `R0=0x12340000`
for a half-zero result. The portable target may retain zero-extension, but the current
compiler/VM path must then be named nonconformant/degraded with a failing/removal fixture.

### Medium — structured digest bytes are not uniquely specified

The proposed digest formula did not enumerate literal domain-tag bytes, assign one lexical
form to every integer/ID field, or choose one JSON escape form. Semantically equal values can
therefore produce different bytes and hashes across implementations. Exact domain tags,
field encodings, one normative serializer and golden bundle/source/component/binding vectors
are required.

### Medium — exact-head gate reconstruction is stale

Both Handoffs still instructed a fresh agent to commit/assign an already committed proposal,
and no SDP current surface anchored this review to the exact SHA above. The review result,
exact SHA, fresh review reservation and current rework gate must be durable before rereview.

## Positive closure

- Review-004 routing to `HSX-ST-007`/`HSX-ST-008`: PASS.
- Acyclic ArtifactRef → independent LoadedImageRef/ImageDebugBundleRef → ImageDebugBinding:
  PASS.
- Exact-case, content-bound source identity: PASS.
- Recipe opcodes, rows, bounds, failure categories and register-write epoch replacement:
  PASS apart from the f16 profile finding.
- Identity/lifecycle/execution/events/snapshots/resources/blocked-state domains: PASS.
- Capability/schema-name separation and synthesized capability registry: PASS.
- 36/5/5 stable IDs, 10/10 DBG mappings and all no-implementation guards: PASS.

## Independent evidence

- ST-006 resource set: `114 passed`.
- ST-003 address/ABI set: `40 passed, 1 skipped, 53 deselected`.
- ST-004 execution sets: `99 passed`; fault set `7 passed`.
- ST-007 ABI sets: `15 passed`; `7 passed, 56 deselected`.
- ST-008 bundle/source set: `18 passed, 1 skipped`.
- Eight YAML files with duplicate-key guard, two NDJSON Ledgers/49 records, append-only
  history, 49 Markdown files/123 tables, fences, links and `git diff --check`: PASS.
- Complete package scope from `c0003d0`: 34 files, all under `SDP/`.

## Required next gate

Master performs documentation-only rework, records an exact proposal-content candidate and
reserves fresh `HSX-RVW-001-001-006`. No prior review context may be reused for that review.
No HSX/Debugger contract is accepted or frozen, and no product, RF or AVR work is authorized.

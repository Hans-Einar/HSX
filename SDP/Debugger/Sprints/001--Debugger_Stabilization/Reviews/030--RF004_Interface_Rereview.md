# DBG-RVW-001-005-008 — RF-004 Interface Re-review

- Status: **REWORK**
- Reviewed exact head: `8d6c0f571f46a10ce6db7331618ef7600d6a8203`
- Remote branch: `origin/codex/dbg-rf-004`
- Review mode: fresh independent, read-only
- Prior review: `DBG-RVW-001-005-007` — REWORK
- Next review: `DBG-RVW-001-005-009`

## Closure confirmed from review 007

- StackService now returns handle-free UnwindFrames and Slice 006 owns wrapping/allocation.
- Portable-address and first-wave live Relations gates now reconstruct accepted/current state.

## Remaining findings

1. **High — identity projections contradicted canonical HSX bundle/ref/binding shapes.** The
   candidate folded component/descriptor data into ImageDebugBundleRef, omitted required
   fields including digest algorithm and capability profile, and lacked an exact normative
   projection mapping.
2. **High — recipe/result/query/page semantics remained incomplete.** Public recipe operands,
   rules, pieces, evaluator method/results, query-ID generation and deterministic ordering/page
   behavior still required worker decisions.
3. **High — variable handles and partial pieces were not representable.** VARIABLE handles
   were allocated but absent from returned variable records, and partial location pieces had
   no structured DTO.
4. **High — legacy adapter could advertise an exact portable binding without canonical
   component/source evidence.** A separate mandatory legacy-unverified index/provenance type
   is required.
5. **Medium — StopEpoch binding status matrix/evidence grade remained incomplete.** Snapshot
   carried no evidence grade and target/image/artifact/token/revision mismatches had no exact
   status/code mapping.

No product finding or existing accepted DBG/HSX design-change request was reported. Rework is
limited to the still-candidate RF-004 interface/Slice/trace documents.

## Independent evidence

- exact local/tracking/live remote head: PASS and clean;
- base ancestry from `69a54aeb3394d3cd4792bce620748e15bab69f1f`: PASS;
- 25 changed paths, all SDP-only; protected product/Executive/VM/AVR/frontend scope clean;
- `git diff --check`: PASS;
- CurrentIndex/Issues/Relations YAML: PASS;
- Ledger: 116 valid rows and base prefix append-only;
- Slice IDs/paths, Markdown fences and active/blocked authority: PASS;
- issue #38 comment `5362514094` and #42 comment `5362515750`: authority matched.

This is not product verification or Master sign-off.

## Master disposition

REWORK accepted. Master replaces the convenience identity shapes with exact canonical HSX
payload/ref/binding projections, freezes full recipe/evaluator/result/order/page semantics,
returns variable IDs/handles and structural pieces, separates LegacyDebugArtifactIndex with
mandatory LEGACY_UNVERIFIED provenance and no binding/SourceRef, freezes the StopEpoch mismatch
matrix/evidence grade, and assigns fresh `DBG-RVW-001-005-009` before any product worker.

# DBG-ST-006 — Portable Debug Runtime Contract Study

- Status: REWORKED COMPLETE / PENDING FRESH CROSS-TRACK REVIEW
- Owning track: Debugger
- Required coordinator: HSX track through `HSX-ST-001`
- Proposed by: `DBG-DA-001`
- Evidence inputs: `DBG-ST-002`, `DBG-ST-003`, `DBG-ST-005`
- Owning issue/gate: #38, Steering activation comment `5348190806`

## Question and scope

Which portable HSX executive/VM/ABI contracts must exist before the proposed Debugger
gateway, stop-epoch inspection, resource reconciliation, lifecycle, and source-step contracts
can be frozen as implementable rather than interface aspirations?

This is a Debugger-owned dependency Study: it defines and validates what the debugger needs,
coordinates evidence/decisions with the HSX track, and records the resulting stable `HSX-*`
inputs. It must not invent portable HSX semantics inside Debugger documents.

## Evidence sources

- `docs/executive_protocol.md`, `docs/hsx_spec-v2.md`, `docs/symbol_format.md`,
  `docs/sources_json.md`, and accepted future HSX SDP contracts;
- debugger-facing `python/execd.py`, `platforms/python/host_vm.py`,
  `python/executive_session.py`, and protocol/VM/executive tests;
- `DBG-ST-002` recovery/causality questions;
- `DBG-ST-003` address/snapshot/ABI/lifecycle/resource questions;
- `DBG-ST-005` evidence gaps and compatibility exit conditions;
- `HSX-ST-001` migration inventory and any spawned stable HSX Studies/designs.

## Current findings and uncertainty

Current documents/code provide useful behaviors, but no accepted portable contract yet proves:

1. stable executive-instance, event-stream, target/PID-generation, and loaded-image identity;
2. named code/data/register address spaces, widths, byte order, alignment, serialization, and
   overflow rules;
3. authoritative ordered run/stop/block/fault/termination evidence with causal stop token or
   state revision;
4. event cursor scope, `since_seq`, `seq_evicted`, drop reporting, ACK semantics, and
   capability negotiation;
5. atomic inspection snapshots or stopped-revision validation across registers, stack,
   memory, disassembly, and resources;
6. portable ABI/unwind/frame and variable-location semantics, including partial data;
7. exact instruction retirement, one-shot breakpoint bypass, source-step prerequisites, and
   independent stop-condition precedence;
8. atomic create/load/start/claim, attach/observer authority, detach/release, kill/terminate,
   and reconnect ownership semantics;
9. stable breakpoint/watch remote IDs, owner/provenance, resource revision, and conditional
   update support;
10. whether mailbox-wait and sleep states are inspection-stable snapshots or runtime-state
    notifications only.

Uncertainty is material: current implementations contain masks, PID-only identity, time-based
fallbacks, address/ID-only resources, live multi-read inspection, and documented event-resume
features not consumed by the client. None may be silently promoted to a portable contract.

## Required conclusions and decisions

The Study must produce or link stable HSX requirement/design IDs for every item above, plus:

- capability names and minimum-version behavior;
- explicit unsupported/degraded outcomes consumed by Debugger contracts;
- conformance fixtures covering target continuity/loss, event gaps, snapshots, resources,
  lifecycle, and exact step semantics;
- a matrix from each accepted HSX contract to `DBG-D-002..DBG-D-006` and affected Refactor
  slices.

## Master-synthesized contract outputs

The coordinated Studies produced stable proposed HSX IDs:

- requirements `HSX-R-001..HSX-R-036`;
- architecture `HSX-A-001..HSX-A-005`;
- design contracts `HSX-D-001..HSX-D-005`;
- conformance fixture matrix in
  `SDP/HSX/06--Design/001--Portable_Debug_Runtime_Contracts.md`.

All remain target/proposed pending independent review and Steering acceptance.

## Dependency closure matrix

| DBG-ST-006 question | HSX Study | Proposed requirements | Architecture/design | Capability/fixture evidence |
|---|---|---|---|---|
| 1. Executive/stream/target/image identity | ST-002, ST-005 | R-001..R-005, R-011 | A-001; D-001/D-004 | restart, PID reuse, stream replacement, opaque target-bound LoadedImageIds for identical artifacts, image digest/load generation |
| 2. Address spaces/width/endian/alignment | ST-003 | R-012..R-015 | A-002; D-002 | multi-space/width/endian/alignment/overflow and image-bundle mismatch |
| 3. Ordered run/stop/fault/terminal evidence | ST-004 | R-019..R-021 | A-003; D-003 | command receipt vs transition, causal precedence, terminal/fault ordering |
| 4. Event cursor/gap/ACK/capabilities | ST-005 | R-028..R-033 | A-004; D-004 | filter-safe cursors, future ACK rejection, seq eviction/gaps/resume/health |
| 5. Inspection snapshot consistency | ST-004, ST-003 | R-022..R-023 | A-003/A-002; D-003/D-002 | immutable/revision snapshots, stale reads, debug-bundle/address fencing |
| 6. ABI/unwind/frame/location semantics | ST-003 | R-016..R-018 | A-002; D-002 | versioned unwind/location complete/partial/unavailable/corrupt fixtures |
| 7. Exact step/bypass/precedence/source prerequisites | ST-004, ST-006 | R-025..R-027, R-035 | A-003/A-005; D-003/D-005 | retired_count 0/1, fenced bypass, shared breakpoint precedence |
| 8. Lifecycle/observer/ownership authority | ST-002 | R-005..R-011 | A-001; D-001 | atomic launch, lease/observer enforcement, policy outcomes, tombstones |
| 9. Resource identity/provenance/revisions | ST-006, ST-005 | R-034..R-036 | A-005/A-004; D-005/D-004 | multi-owner/CAS/tombstone/reconnect/event-gap/degraded no-delete fixtures |
| 10. Blocked-state inspection stability | ST-004, ST-005 | R-022..R-024, R-030..R-033 | A-003/A-004; D-003/D-004 | WAIT_MBX/SLEEPING snapshot capability, wake invalidation and stream gaps |

No dependency question remains without a stable proposed owner and fixture path.

## Proposed compatibility boundary

- Full portable profile: `hsx.portable-debug-runtime/1` with explicit identity, lifecycle,
  architecture/debug bundle, execution/snapshot, event-resume and resource-revision
  capabilities.
- Current Python legacy behavior is admitted only through named degraded profiles
  (`hsx.python-debug-legacy/1`, `hsx.legacy-event-stream/1`,
  `hsx.legacy-debug-resources/1`) with conservative semantics and removal fixtures.
- Extension/runtime package coherence remains exact-manifest matching under the accepted
  Debugger architecture. Runtime/Executive behavior is selected only from negotiated profiles,
  never version guessing.

## Exact gate effect

Until `DBG-ST-006` is complete and its required stable HSX contracts are accepted:

- `DBG-D-002..DBG-D-006` remain proposed and may not be frozen as implementation authority;
- all product implementation in `DBG-RF-003`, `DBG-RF-004`, `DBG-RF-005`, and `DBG-RF-006`
  remains blocked;
- `DBG-RF-002` controller/model work may be authorized later only for `DBG-D-001`-bounded
  slices; target-identity, stop-epoch, snapshot, or handle-lifetime slices remain blocked by
  `DBG-D-003`/this Study;
- `DBG-RF-007..DBG-RF-009` remain blocked by their existing upstream dependencies regardless.

Documentation, test-oracle design, and interface comparison remain allowed within explicit
Steering scope; this Study never grants product implementation authority by itself.

The evidence and contract mapping are now complete, but the gate stays closed until the exact
package passes fresh `HSX-RVW-001-001-004` and Steering accepts the HSX contracts and freezes the
affected `DBG-D-*` contracts in a later decision.

## Affected proposed contracts and requirements

- Proposed design: `DBG-D-002`, `DBG-D-003`, `DBG-D-004`, `DBG-D-005`, `DBG-D-006`
- Requirements: `DBG-R-004..DBG-R-006`, `DBG-R-009..DBG-R-025`, `DBG-R-026`, `DBG-R-034`,
  `DBG-R-036`
- Refactors: bounded portions of `DBG-RF-002` and all product implementation in
  `DBG-RF-003..DBG-RF-006`

## Open questions

1. Which questions can `HSX-ST-001` settle directly, and which require new `HSX-ST-*` Studies?
2. Which capabilities are current implemented behavior versus only legacy documentation?
3. Can protocol version 1 add identity/revision/provenance fields compatibly, or is a new
   capability/version boundary required?
4. Which blocked-state snapshots are stable across every target implementation?
5. What minimum executive version is supported during migration, and which degraded modes
   have explicit removal conditions?

## Traceability relations

- `DBG-ST-002`, `DBG-ST-003`, `DBG-ST-005` inform this Study.
- `DBG-ST-006` coordinates with `HSX-ST-001`.
- A completed Study will provide dependencies to `DBG-D-002..DBG-D-006`.
- The gate effects above block the named Refactor scopes until stable contracts exist.

## Steering routing decision requested

Steering authorized `DBG-ST-006` as the coordinated Debugger Study and `HSX-ST-001`/#47 as the
HSX coordinator. `HSX-ST-002..HSX-ST-006` own the five natural runtime-contract domains. The
Study must return reviewed mappings and contracts to #47/#38; it still cannot freeze
`DBG-D-002..DBG-D-006` or authorize blocked Refactor scopes.

## Conclusion

The dependency questions now map to a complete stable proposed HSX contract set and
conformance plan. `DBG-ST-006` is complete for independent review. Completion is not
acceptance: `DBG-D-001..DBG-D-010`, `DBG-RF-002..DBG-RF-009`, product code and AVR work remain
blocked pending exact-head review and durable Steering decisions in #47/#38.

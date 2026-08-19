# DBG-ST-006 — Portable Debug Runtime Contract Study

- Status: PROPOSED / REQUIRED BEFORE DESIGN FREEZE
- Owning track: Debugger
- Required coordinator: HSX track through `HSX-ST-001`
- Proposed by: `DBG-DA-001`
- Evidence inputs: `DBG-ST-002`, `DBG-ST-003`, `DBG-ST-005`
- Owning issue/gate: #38 pending Steering routing decision

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

Issue #38 should explicitly authorize `DBG-ST-006` as the next coordinated Debugger/HSX Study
or identify an accepted equivalent. The current `DBG-DA-001` decision may accept the overall
architecture direction, but must not freeze `DBG-D-002..DBG-D-006` or authorize the blocked
Refactor scopes until this Study and its HSX inputs are complete.

## Conclusion

The dependency questions are sufficiently concrete to design typed ports, but insufficient to
claim portable implementation semantics. `DBG-ST-006` is therefore mandatory before the
affected design contracts can be accepted as executable and before the affected product work
can start.

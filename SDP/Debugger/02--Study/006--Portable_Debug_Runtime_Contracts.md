# DBG-ST-006 — Portable Debug Runtime Contract Study

- Status: PROPOSED / REQUIRED CROSS-TRACK FOLLOW-UP
- Proposed by: `DBG-DA-001`
- Owning tracks: Debugger evidence with required HSX-track decisions
- Upstream: `DBG-ST-002`, `DBG-ST-003`, `DBG-ST-005`, `HSX-ST-001`

## Question

Which portable HSX executive/VM/ABI contracts must exist before the proposed Debugger
gateway, stop-epoch inspection, resource reconciliation, lifecycle, and source-step designs
can be accepted as implementable rather than interface aspirations?

## Required outputs

1. Stable executive-instance, event-stream, target/PID-generation, and loaded-image identity.
2. Named code/data/register address spaces, widths, byte order, alignment, serialization, and
   overflow rules.
3. Authoritative ordered run/stop/block/fault/termination evidence with causal stop token or
   state revision.
4. Event resume/gap contract: cursor scope, `since_seq`, `seq_evicted`, drop reporting, ACK
   semantics, and capability negotiation.
5. Atomic inspection snapshot or stopped-revision validation across registers, stack, memory,
   disassembly, and resources.
6. Portable ABI/unwind/frame and variable-location semantics, including missing/partial data.
7. Exact instruction retirement, one-shot breakpoint bypass, source-step prerequisites, and
   independent stop-condition precedence.
8. Atomic create/load/start/claim, attach/observer authority, detach/release, kill/terminate,
   and reconnect ownership semantics.
9. Stable breakpoint/watch remote IDs, owner/provenance, resource revision, and conditional
   update support—or an explicit declaration that only conservative compatibility mode is
   possible.
10. Whether mailbox-wait and sleep states are inspection-stable stopped snapshots or only
    runtime-state notifications.

## Guard

This Study is a dependency request, not an HSX design decision. The Debugger track may define
typed ports and degraded behavior, but may not invent the portable semantics above. Proposed
`DBG-D-002..DBG-D-006` remain pending and their owning implementation work stays blocked until
the relevant stable `HSX-*` requirements/design contracts exist.

## Handoff

The Steering package for `DBG-DA-001` should decide whether to open this as a coordinated
Debugger/HSX Study immediately. `HSX-ST-001` remains the current stable cross-track anchor.

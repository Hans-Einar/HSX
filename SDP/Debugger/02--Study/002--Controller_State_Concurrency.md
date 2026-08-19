# DBG-ST-002 — Controller, State, Concurrency, Events, and Recovery

- Status: ACTIVE STUDY
- DesignAnalysis: `DBG-DA-001`
- Iteration: `DBG-IT-001-002`
- Owning issue: #38

## Question and scope

Which frontend-neutral controller, state machine, stop-epoch, concurrency, event-authority,
transport-health, reconnect, and fallback model best satisfies `DBG-R-004`,
`DBG-R-007..DBG-R-013`, `DBG-R-020`, and `DBG-R-026..DBG-R-028`?

## Required evidence

- current `python/hsx_dbg/backend.py`, `python/hsx_dbg/session.py`,
  `python/executive_session.py`, and state/concurrency portions of `python/hsx_dap/__init__.py`;
- relevant tests and executive protocol documentation;
- `DBG-ST-001`, `DBG-CR-001`, and `DBG-GAP-001`.

## Required analysis

- compare serialized synchronous controller, actor/queue controller, and fully async models;
- define candidate states, transitions, authoritative inputs, invariants, and failure modes;
- define stop-epoch/snapshot ownership and reference invalidation;
- define RPC/event-stream health, capability negotiation, reconnect, and bounded fallback;
- state module responsibilities/non-responsibilities and candidate frontend-neutral API;
- identify unresolved questions and proposed architecture/design contracts.

## Non-goals

No product edits, no DAP/VS Code presentation design, no final architecture decision, and no
implementation authorization.

## Findings

To be completed by the assigned Study worker.

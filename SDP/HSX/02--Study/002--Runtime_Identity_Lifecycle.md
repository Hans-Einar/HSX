# HSX-ST-002 — Runtime Identity, Generations, Lifecycle, and Ownership

- Status: ACTIVE STUDY
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`

## Question and scope

Define portable identity/generation and lifecycle/ownership evidence for executive instances,
event streams, targets/PIDs, loaded images, sessions, attach/observer authority,
create/load/start/claim, detach/release, kill/terminate, and reconnect continuity.

## Evidence sources

Legacy DR/DG/DO and architecture/design documents; `docs/executive_protocol.md`;
`python/execd.py`, task/session models, HXE load paths, VM controller behavior, and tests.

## Required analysis

- current implementation versus legacy intent versus portable target contract;
- identity types, generation changes, ordering, authority, failure/degraded behavior;
- protocol-version/capability boundary and conformance fixtures;
- traceability to `DBG-ST-006`, affected `DBG-D-*`, and other HSX Studies.

## Findings and uncertainty

To be completed by the assigned worker.

## Required conclusions

Recommend stable proposed HSX requirement/architecture/design concepts without allocating
numeric IDs; Master assigns final IDs during cross-track synthesis.

## Open questions and traceability

Record unresolved evidence and exact upstream/downstream relations. Do not invent AVR policy
or authorize product work.

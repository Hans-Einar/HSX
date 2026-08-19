# HSX-ST-004 — Run/Stop Evidence, Snapshots, Exact Stepping, and Blocked States

- Status: ACTIVE STUDY
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`

## Question and scope

Define authoritative run/stop/block/fault/termination evidence, causal tokens/revisions,
inspection snapshot consistency, exact instruction retirement/breakpoint precedence, and
whether mailbox-wait/sleep states are inspection-stable.

## Evidence sources

Legacy VM/executive/debug design; `docs/hsx_spec-v2.md`, `docs/executive_protocol.md`;
MiniVM/VMController, executive scheduler/state/event/step paths, mailbox/sleep behavior and tests.

## Required analysis

- state versus cause versus command acknowledgement;
- snapshot token/revision and stale-read behavior;
- exact step and one-shot breakpoint bypass semantics;
- source-step prerequisites without moving debugger algorithms into HSX;
- blocked-state stability matrix, capability/versioning and conformance fixtures.

## Findings and uncertainty

To be completed by the assigned worker.

## Required conclusions

Recommend stable proposed HSX contract concepts without numeric ID allocation. Preserve the
single-instruction oracle while distinguishing current behavior from portable guarantees.

## Open questions and traceability

Map explicitly to `DBG-D-003`, `DBG-D-004`, `DBG-D-006` and sibling event/lifecycle Studies.

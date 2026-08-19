# HSX-ST-005 — Event Stream Cursor, ACK, Gaps, and Capability Profiles

- Status: ACTIVE STUDY
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`

## Question and scope

Define portable event-stream identity, sequence/cursor scope, ordering, ACK-after-apply,
back-pressure, drop/gap/`seq_evicted`, resume/full-reconcile behavior, health evidence, and
negotiated current/degraded capability profiles.

## Evidence sources

Legacy executive/event design; `docs/executive_protocol.md`; executive session/event broker,
client stream/ACK/keepalive/retry behavior and event/session tests.

## Required analysis

- documented versus implemented event semantics;
- stream/executive generation and cursor validity;
- loss, malformed input, half-open health and recovery outcomes;
- capability names, compatibility/removal conditions, and adversarial fixtures.

## Findings and uncertainty

To be completed by the assigned worker.

## Required conclusions

Recommend stable proposed HSX contract concepts without numeric ID allocation and preserve
explicit degraded profiles rather than version guessing.

## Open questions and traceability

Map to `DBG-D-002`, controller reconciliation, runtime identity, and run/stop evidence.

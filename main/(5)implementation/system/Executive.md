# Executive Implementation Plan

## DR/DG Alignment
- DR-5.1–5.3 / DG-5.1–5.4: Scheduler, resource budgets, persistence services implemented per design.
- DR-8.1 / DG-5.2 / DG-8.2: Session/event streaming (session.open, events.subscribe, ACK/back-pressure).
- DR-2.5 / DG-3.4: ABI/version handshake (EXEC_GET_VERSION) sourced from shared header.

## Implementation Notes
- Implement PID lock table + capability negotiation (refactorNotes: "Rework existing executive endpoints" + event stream tasks).
- Add shared syscall header import to Python exec + host VM; ensure module 0x06 is canonical.
- Build EventStreamer with bounded queue + ACK handling per docs/executive_protocol.md; include warning events on drop.
- Integrate resource budget telemetry (RAM/flash counters) for later enforcement.
- Align provisioning/persistence hooks with FRAM layout decisions (DR-5.3) and mailbox stdio policies (DG-6.4).

## Playbook (Implementation)
- [ ] Port PID lock + capability handshake to Python exec (session.open/close).
- [ ] Finalise event streaming pipeline (producer queue, ack, back-pressure logging).
- [ ] Expose EXEC_GET_VERSION SVC + RPC command returning shared header info.
- [ ] Update CLI/tests to consume new APIs; log commits referencing DR IDs.

## Commit Log
- _Pending_: append commit entries (hash, summary, DR/DG references) as work lands.

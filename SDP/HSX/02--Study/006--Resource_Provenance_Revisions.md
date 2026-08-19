# HSX-ST-006 — Breakpoint and Watch Identity, Provenance, and Revisions

- Status: ACTIVE STUDY
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`

## Question and scope

Define portable remote breakpoint/live-watch resource IDs, owner/provenance, target/image
generation, revisions/conditional updates, events, session cleanup, reconnect semantics, and
the exact guarantees or degraded limits for legacy address/ID-only profiles.

## Evidence sources

Legacy breakpoint/watch/session design; executive/VM breakpoint and watch stores, session
locks, events, client behavior and multi-client/reconnect tests.

## Required analysis

- actual current ownership/cleanup behavior and collision risks;
- stable logical versus remote identity and revision semantics;
- owner release, shared resources, external observation and reconnect;
- capability/versioning, conservative degraded behavior and conformance fixtures.

## Findings and uncertainty

To be completed by the assigned worker.

## Required conclusions

Recommend stable proposed HSX contract concepts without numeric ID allocation. Standard
snapshot Watch expressions remain Debugger-owned and outside persistent resource semantics.

## Open questions and traceability

Map to `DBG-D-005`, lifecycle identity, event continuity, and target generations.

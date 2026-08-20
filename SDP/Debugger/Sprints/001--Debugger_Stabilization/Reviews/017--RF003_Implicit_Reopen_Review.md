# DBG-RVW-001-004-009 — RF-003 Implicit-Reopen Review

- Status: **REWORK REQUIRED**
- Exact reviewed head: `f776b1a0ef847227ad94676a0328dc9c78eba507`
- Reviewer changes: none

High: explicit replacement OPEN suppresses physical `None→new` / `None→None` loss evidence
before its outcome is known. When OPEN is REJECTED, prior generation health is restored despite
the old physical continuity already being lost. Both cases reproduced 25/25. Only authoritative
OPEN success may legitimate/clear replacement continuity; failed replacement must retain
degraded/lost/reconcile evidence. Medium: active review assignment was not yet durable.

Positive evidence: combined `208 passed`; RF-003 25x41; focused 30 rounds; legitimate initial
OPEN and non-OPEN/latch behavior PASS; compile/import/trace/scope/shared/RF-002/integration/
protected hashes PASS. Fresh bounded rework and `DBG-RVW-001-004-011` are required.

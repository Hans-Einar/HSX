# DBG-DA-001 — Optimal Debugger Architecture DesignAnalysis

Status: ACTIVE DESIGNANALYSIS — STEERING REVIEW REQUIRED

Former prerequisite: `DBG-RF-001` baseline protocol stabilization, independent review, and
verification. The prerequisite is complete at signed implementation head
`208063e344b767f82790ce579eba6327e2cdd0ce`.

Steering authorized this DesignAnalysis in issue #38 comment `5345600066`. The authorization
is limited to Study, DesignAnalysis, proposed architecture/design-contract preparation, and
independent architecture review. No structural product-code implementation is authorized.

## Objective

Design the debugger from accepted `DBG-R-*` requirements without treating the legacy
monoliths as required structure. Produce an optimal responsibility model and then make an
explicit per-component reuse/adapt/replace decision against the legacy implementation.

## Required outputs

- authoritative debugger state machine and state ownership;
- concurrency/serialization model;
- core/frontend/backend/API boundaries;
- lifecycle semantics;
- stepping semantics;
- stop-epoch/snapshot model;
- event/reconnect/fallback model;
- breakpoint/watch ownership model;
- symbol/source/address model;
- packaging/version model;
- module responsibility/non-responsibility table;
- dependency/contracts diagram;
- migration strategy that keeps the legacy debugger available as a behavioral oracle;
- reuse/adapt/replace matrix with evidence and risk for each major current component;
- proposed `DBG-D-*` detailed design contracts used by structural Refactors.

## Active Study work packages

- `DBG-ST-002` — controller, state machine, stop epochs, concurrency, events, and recovery;
- `DBG-ST-003` — inspection, symbols/source/address, resource ownership, lifecycle, and
  stepping semantics;
- `DBG-ST-004` — DAP/VS Code frontend boundaries, packaging, and production verification;
- `DBG-ST-005` — legacy component reuse/adapt/replace evidence and regression oracle.

The Study documents hold bounded evidence and alternatives. The Master alone synthesizes the
recommended architecture here so domain-local assumptions cannot become competing designs.

## Review and stop gate

- Active iteration: `DBG-IT-001-002`
- Planned independent architecture review: `DBG-RVW-001-002-001`
- Owning issue: #38

Completion for this iteration means one coherent proposed architecture has an independent
exact-head review and a decision package is posted to issue #38. Proposed `DBG-A-*` and
`DBG-D-*` items remain target/proposed state pending Steering acceptance.

## Guard

No structural product-code worker is authorized by this DesignAnalysis. The Master must stop
after the reviewed proposal is posted to issue #38. Only a later, durable Steering acceptance
may promote proposed `DBG-D-*` contracts or authorize `DBG-RF-002..DBG-RF-009` implementation.

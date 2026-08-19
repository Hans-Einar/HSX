# HSX Agent Instructions

This repository follows the local Standard Document Procedure (SDP).
The repository documents, not chat history, are the source of truth for planning,
design, implementation, review, verification, and handoff.

## SDP tracks

HSX uses three independent SDP tracks under `SDP/`:

- `SDP/HSX/` — portable HSX architecture, ISA/ABI, VM, executive, toolchain, and platform-independent runtime behavior.
- `SDP/Debugger/` — debugger core, executive debug protocol, DAP adapter, CLI debugger, VS Code integration, and debugger-specific verification.
- `SDP/AVR/` — the future AVR embedded implementation of HSX and its target-specific constraints and verification.

Each track owns its own requirements, design, traceability IDs, CurrentIndex, review,
and verification. Cross-track dependencies must be explicit rather than silently
copying requirements between tracks.

## Agent roles

If an agent is not explicitly running as a spawned sub-agent, it is the Master agent.

The Master agent owns:

- identifying the active SDP track and reading its `Traceability/CurrentIndex.yaml`
- maintaining requirements, design contracts, dependency ordering, traceability, and handoff
- decomposing product work into bounded worker tasks
- assigning product-code changes to fresh worker agents
- assigning independent review to fresh reviewer agents
- requiring verification evidence and exact-head sign-off before declaring a refactor or slice complete
- preventing work from drifting away from the accepted requirements/design

The Master agent must not perform substantial product-code implementation directly.
Documentation-only SDP work may be performed by the Master.

Worker agents own one bounded implementation scope. A worker must be told the exact
requirements/design/refactor IDs, owned modules, non-goals, expected verification,
and any concurrent work it must not overwrite.

Reviewer agents are independent from the worker. They inspect the accepted contract,
changed files, regression risk, requirements coverage, and verification evidence.
Reviewers do not implement fixes unless explicitly reassigned as a worker.

## CodeReview -> GapAnalysis -> Refactor rule

A CodeReview records evidence and findings. It does not directly become a large
implementation task.

1. CodeReview findings receive stable review/finding IDs.
2. GapAnalysis maps each finding to requirements and identifies the architectural or
   implementation gap.
3. Independent remediation domains become separate Refactor tracks.
4. Dependencies between Refactors are captured before implementation begins.
5. Structural Refactors require an accepted DesignAnalysis/Design contract first.
6. Each Refactor runs its own worker -> reviewer -> verification -> sign-off loop.

Small correctness fixes that are necessary to obtain a trustworthy baseline may run
before structural redesign, but must remain narrowly scoped and traceable.

## Anti-monolith rule

No new or redesigned module may simultaneously own unrelated concerns such as
transport framing, debugger lifecycle/state policy, resource ownership/reconciliation,
symbol interpretation, and IDE presentation.

Every structural design must state responsibilities and explicit non-responsibilities.
If an existing monolith is being replaced, compatibility behavior must be captured by
tests before responsibility is moved.

# HSX Agent Instructions

This repository follows the local Standard Document Procedure (SDP).
The repository documents and GitHub issue records, not chat history, are the durable source
of truth for planning, design, implementation, review, verification, and handoff.

## Mandatory Master startup reading order

Before planning or delegating work, the Master agent must read:

1. `AGENTS.md`
2. `SDP/README.md`
3. `SDP/Shared/Process.md`
4. the active track `README.md`
5. the active track `Traceability/CurrentIndex.yaml`
6. the active GitHub issue(s) named by that index or owning the current work
7. the active Study / Requirements / DesignAnalysis / Design / Feature / Refactor / Slice documents referenced by traceability

Do not begin product-code work from an issue title alone.

## Governance: Steering Group and Master agent

The project has a human-facing **Steering Group chat** that provides product/architecture
direction and resolves questions with the Codex Master agent. The Steering Group chat itself
is not durable project state.

**GitHub issues are the durable coordination interface between the Codex Master and the
Steering Group.** Important proposals, questions, decisions, scope changes, blockers,
reviews, and handoffs that require Steering Group awareness or approval must be recorded in
the relevant issue.

The expected loop is:

1. Master reads the active SDP state and issue(s).
2. Master performs/delegates bounded analysis or implementation work.
3. Master records findings, questions, proposed decisions, status, and evidence in GitHub
   issues and SDP documents.
4. Steering Group reviews or gives direction through the issue/chat workflow.
5. Master updates the durable SDP/issue state before continuing work that depends on the
   decision.

Do not rely on undocumented chat instructions when an implementation or design decision
would be difficult for a fresh agent to reconstruct.

## SDP tracks

HSX uses three independent SDP tracks under `SDP/`:

- `SDP/HSX/` — portable HSX architecture, ISA/ABI, VM, executive, toolchain, and platform-independent runtime behavior.
- `SDP/Debugger/` — debugger core, executive debug protocol, DAP adapter, CLI debugger, VS Code integration, and debugger-specific verification.
- `SDP/AVR/` — the future AVR embedded implementation of HSX and its target-specific constraints and verification.

Each track owns its own requirements, design, traceability IDs, CurrentIndex, review,
and verification. Cross-track dependencies must be explicit rather than silently
copying requirements between tracks.

## Study is first-class

A Study is a first-class SDP artifact with its own stable `*-ST-###` ID. Studies are used
whenever evidence, alternatives, unknowns, experiments, or technical questions must be
resolved before requirements/design/work scope can be trusted. Multiple numbered Studies are
normal; do not force unrelated investigations into one growing study document.

A Study may inform requirements, architecture, DesignAnalysis, a Feature, a Refactor, or a
cross-track dependency. Study conclusions are evidence; they do not silently become product
requirements until traceability records that transition.

## Agent roles

If an agent is not explicitly running as a spawned sub-agent, it is the Master agent.

The Master agent owns:

- identifying the active SDP track and reading its `Traceability/CurrentIndex.yaml`
- reading the active GitHub issue(s) used for Steering Group coordination
- maintaining requirements, design contracts, dependency ordering, traceability, and handoff
- decomposing active Feature or Refactor work into bounded slices/worker tasks
- assigning product-code changes to fresh worker agents
- assigning independent review to fresh reviewer agents
- reporting decisions, blockers, evidence, and completion state through the relevant GitHub issue
- requiring verification evidence and exact-head sign-off before declaring a refactor, feature, or slice complete
- preventing work from drifting away from the accepted requirements/design

The Master agent must not perform substantial product-code implementation directly.
Documentation-only SDP work may be performed by the Master.

Worker agents own one bounded implementation scope. A worker must be told the exact
requirements/design/Feature-or-Refactor/slice IDs, owned modules, non-goals, expected
verification, and any concurrent work it must not overwrite.

Reviewer agents are independent from the worker. They inspect the accepted contract,
changed files, regression risk, requirements coverage, and verification evidence.
Reviewers do not implement fixes unless explicitly reassigned as a worker.

## Work converges on Feature or Refactor

Product-code implementation work should normally belong to one of two durable work domains:

- **Feature (`*-FEAT-###`)** — creates or extends intended product capability from mandate,
  Study, requirements, architecture, and design.
- **Refactor (`*-RF-###`)** — remediates or restructures existing behavior/code, normally
  originating from CodeReview/GapAnalysis or an explicitly identified structural need.

Do not create implementation work that is neither owned by a Feature nor a Refactor unless
the Master records why a separate work class is necessary.

## Slices are the implementation unit

Features and Refactors are implemented through bounded **Slices (`*-SL-*`)**.

A Slice should normally be **vertical**: the smallest coherent, testable behavior that passes
through every system layer required to demonstrate useful end-to-end progress. Avoid
horizontal/file-by-file slices created only because they are convenient to assign.

A Refactor may use a slice constrained to one refactor domain or layer when the behavior,
contract, and verification boundary are genuinely contained there (for example a transport
serialization slice inside the Debugger transport Refactor). Such a slice must still produce
a coherent verified outcome and state how it connects to later vertical integration.

Each Slice has its own contract, worker, independent review, verification evidence, and
completion signal. Multiple Slices may implement one Feature or Refactor.

## CodeReview -> GapAnalysis -> Refactor rule

A CodeReview records evidence and findings. It does not directly become a large
implementation task.

1. CodeReview findings receive stable review/finding IDs.
2. GapAnalysis maps each finding to requirements and identifies the architectural or
   implementation gap.
3. Independent remediation domains become separate Refactor tracks.
4. Dependencies between Refactors are captured before implementation begins.
5. Structural Refactors require an accepted DesignAnalysis/Design contract first.
6. Each Refactor is decomposed into coherent Slices as needed.
7. Each Slice runs its own worker -> reviewer -> verification -> sign-off loop; the Refactor
   receives final sign-off only when its required Slices converge on the Refactor completion signal.

Small correctness fixes that are necessary to obtain a trustworthy baseline may run
before structural redesign, but must remain narrowly scoped and traceable.

## Anti-monolith rule

No new or redesigned module may simultaneously own unrelated concerns such as
transport framing, debugger lifecycle/state policy, resource ownership/reconciliation,
symbol interpretation, and IDE presentation.

Every structural design must state responsibilities and explicit non-responsibilities.
If an existing monolith is being replaced, compatibility behavior must be captured by
tests before responsibility is moved.

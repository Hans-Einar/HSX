# Shared SDP Process

This file defines the common process used by the HSX, Debugger, and AVR SDP tracks.
Track-specific requirements and designs remain in their own directories.

## Governance and durable coordination

The project uses two complementary coordination surfaces:

- **Steering Group chat** — human-facing discussion, direction, prioritization, and rapid
  clarification with the project Steering Group.
- **GitHub issues + SDP documents** — durable project state and the formal coordination
  interface used by the Codex Master agent.

The Steering Group chat is not considered reconstructable project state by itself. When a
question, decision, scope change, blocker, review outcome, or approval affects future work,
the Codex Master records it in the relevant GitHub issue and updates the owning SDP artifacts.

The Master and Steering Group therefore coordinate work through issues even if the discussion
originates in chat. A fresh agent should be able to reconstruct the active decision and next
action from repository documents and issues without needing chat history.

## Stable artifact classes

Each track may use the following ID classes, prefixed by the track namespace:

- `ST-###` — Study or evidence-gathering investigation
- `R-###` — Requirement
- `A-###` — Architecture decision/boundary
- `DA-###` — Design analysis
- `D-###` — Accepted detailed design decision/contract
- `FEAT-###` — Feature work domain for intended/new product capability
- `CR-###` — CodeReview
- `F-###` — CodeReview finding
- `GAP-###` — GapAnalysis
- `RF-###` — Refactor work domain
- `SPR-###` — Sprint
- `IT-###-###` — Iteration
- `SL-###-###-###` — bounded implementation slice
- `RVW-###-###-###` — independent review record
- `VER-###-###-###` — verification record

Examples: `DBG-ST-001`, `DBG-R-004`, `DBG-FEAT-001`, `DBG-F-001-003`,
`DBG-RF-002`, `HSX-R-012`, `AVR-VER-001-001-001`.

IDs are never recycled after they have been referenced by traceability or an issue.

## Study is a first-class artifact

A track may have multiple Studies. Each Study receives its own stable `ST-###` ID and
must state:

- question/scope;
- evidence sources;
- findings and uncertainty;
- conclusions/decisions;
- affected or proposed requirements;
- open questions;
- traceability relations.

Studies are not limited to the beginning of a project. A new Study may be created whenever
new evidence or uncertainty appears during architecture, design, Feature, Refactor, or target
work. This is preferable to hiding investigation inside an implementation issue.

A Study may inform requirements, architecture, design, a Feature, a Refactor, or a cross-track
dependency. A Study conclusion becomes a requirement/design decision only when the relevant
traceability relation and durable document are updated.

## Two normal product-work domains: Feature and Refactor

Substantial product-code work normally converges on one of two durable domains.

### Feature

A `FEAT-###` owns intended capability: new behavior or a deliberate extension of existing
behavior. A Feature usually originates from mandate/use case, Study, requirements,
architecture, and design.

A Feature contract should state:

- user/operator capability;
- requirements and designs implemented;
- system layers/contracts involved;
- dependencies and non-goals;
- Slice plan;
- verification/completion signal.

### Refactor

An `RF-###` owns remediation or structural change to existing code/behavior. A Refactor often
originates from CodeReview -> GapAnalysis, but may also originate from an explicit design or
maintainability requirement.

A Refactor contract should state:

- findings/requirements addressed;
- behavior that must be preserved or intentionally changed;
- responsibility/domain boundary;
- accepted DesignAnalysis/Design inputs for structural work;
- dependencies and non-goals;
- Slice plan;
- verification/completion signal.

Implementation work that belongs to neither a Feature nor a Refactor requires an explicit
Master decision and rationale in traceability.

## Existing-code remediation flow

### 1. CodeReview

A CodeReview is an evidence snapshot of an identified code baseline. It records:

- exact branch/commit or other provenance;
- review scope;
- findings with severity and stable finding IDs;
- observed behavior and evidence;
- suspected ownership/design causes;
- what is explicitly not concluded yet.

The CodeReview must not silently redesign the system.

### 2. GapAnalysis

GapAnalysis compares the reviewed baseline against accepted or proposed requirements.
For each finding it records:

- requirement(s) affected;
- actual behavior/structure;
- required behavior/structure;
- risk;
- whether the gap is correctness, architecture, maintainability, verification,
  traceability, packaging, or UX;
- proposed remediation domain;
- dependencies on other gaps/refactors.

### 3. Refactor fan-out

A GapAnalysis should spawn multiple Refactors when findings have independent ownership
or verification boundaries. Do not create one catch-all refactor merely because the
findings came from one CodeReview.

Each Refactor must have:

- one stable `RF-###` ID;
- requirements and findings addressed;
- dependencies and ordering;
- accepted DesignAnalysis/Design inputs when structure changes;
- explicit owned modules and non-goals;
- compatibility behavior that must be preserved;
- Slice plan;
- verification plan;
- completion signal.

### 4. Design before structural implementation

Small baseline correctness defects may be fixed before redesign if they are isolated
and necessary to make tests/tooling trustworthy.

Structural changes — responsibility movement, module boundaries, state ownership,
protocol/lifecycle redesign, concurrency model, or public interfaces — require a
DesignAnalysis followed by an accepted Design contract before a worker implements them.

## Slices are the execution unit

Features and Refactors are implemented through bounded `SL-*` Slices.

### Default: vertical Slice

A Slice should normally be vertical: the smallest coherent, testable behavior that crosses
every system layer required to demonstrate useful end-to-end progress. The purpose is to
produce a working capability increment rather than complete one horizontal layer in isolation.

Examples:

- Feature slice: request -> backend contract -> processing -> persisted result -> UI evidence.
- Debugger slice: DAP request -> debugger core -> executive fixture -> DAP event/result ->
  black-box verification.

Avoid splitting work into file-by-file or frontend-only/backend-only slices merely because it
is easier to assign agents.

### Domain-scoped Refactor Slice

A Refactor may contain a Slice intentionally constrained to a single responsibility domain
when the refactor contract and its verification boundary are genuinely local. For example,
a transport Refactor may have one Slice that establishes a single serialized outbound DAP
writer before a later integration Slice connects the new transport to the full debugger.

A domain-scoped Slice must still:

- produce a coherent verified outcome;
- state what external behavior is preserved;
- state which later Slice performs vertical integration if this Slice does not;
- avoid leaking temporary architecture into unrelated domains.

Multiple Slices may run in parallel only when dependencies/interfaces are frozen and module
ownership is disjoint or explicitly coordinated.

## Worker / Reviewer / Sign-off

For each product-code Slice:

1. Master freezes the parent Feature/Refactor contract, Slice contract, dependencies, and traceability.
2. Fresh worker implements only the bounded Slice scope.
3. Fresh reviewer independently inspects the exact changed head against the contract.
4. Blocking/High/Medium findings require rework and a new review unless the track
   explicitly defines a stricter rule.
5. Verification records exact evidence (tests/builds/scenarios/artifacts).
6. Master signs off the Slice only when requirements, review, verification, and traceability agree.

A parent Feature or Refactor receives final sign-off only when its required Slices have
converged on the parent completion signal and an integration/final review has verified the
combined exact head where appropriate.

Sign-off is always against an exact commit/head, not merely a PR title or conversation.

## Master / Steering Group issue workflow

For active work, the GitHub issue should normally contain or link:

- owning Study/Requirement/Feature/Refactor/Slice IDs;
- current status and blockers;
- questions requiring Steering Group direction;
- worker handoff/status;
- reviewer findings;
- verification evidence;
- exact-head sign-off or rework decision;
- next allowed work according to dependencies.

When Steering Group direction changes scope, requirements, or design, the Master updates the
SDP documents/traceability first or as part of the same controlled change before dependent
implementation continues.

## Anti-drift rules

- Repository SDP documents and issue decisions are authoritative; chat alone is not.
- A worker may not invent new requirements to justify an implementation choice.
- A design change discovered during implementation returns to Master/DesignAnalysis.
- Review findings are never silently fixed outside their recorded Refactor/Slice.
- Compatibility fallbacks must have an explicit owner and removal/retention decision.
- Polling, retries, caches, fallback timers, and duplicated state are architecture
  mechanisms, not incidental fixes; adding one requires design ownership and tests.
- New work must identify its parent Feature or Refactor before implementation unless an
  explicit exception is recorded by the Master.

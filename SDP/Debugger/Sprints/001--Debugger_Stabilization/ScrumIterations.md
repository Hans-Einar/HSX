# DBG-SPR-001 Scrum Iterations

## DBG-IT-001-001 — DAP Protocol Baseline Stabilization

Status: CLOSED — MASTER SIGN-OFF COMPLETE

### Slice

`DBG-SL-001-001-001` — see
`Slices/001--DAP_Protocol_Baseline.md`.

### Execution order

1. Master recorded Steering acceptance against PR #49 head
   `403d55c621d50212940b4c8668ac20a3cf8519b5` and froze the contract.
2. Fresh worker records `slice_started` and implements only the Slice.
3. Fresh independent reviewer reviews the exact worker head.
4. Blocking/High/Medium findings cause rework and a fresh exact-head review.
5. Verifier runs the required evidence and records `DBG-VER-001-001-001`.
6. Master reconciles sprint notes, CurrentIndex, Relations, Ledger, issue #37, and exact-head
   sign-off.

### Current result

The bounded worker completed `DBG-SL-001-001-001` on `codex/dbg-rf-001` from base
`e5a50ab45acdcb515ccd3602ce99487bd668cdfd`:

- raw adapter/bootstrap diagnostics now use stderr or configured logging;
- initialize response is serialized before the `initialized` event;
- the black-box subprocess test launches `vscode-hsx/debugAdapter/hsx-dap.py`, exercises
  initialize plus launch and attach, rejects unframed preambles, and runs on Windows;
- targeted Windows evidence: `36 passed` across DAP CLI, harness, and backend tests;
- broader `python/tests` evidence: `534 passed, 2 skipped, 2 failed`; the failures are an
  absent generated demo symbol artifact and an unrelated shell pretty-output assertion on
  the untouched optional-`tabulate` rendering path.

Fresh independent review `DBG-RVW-001-001-001` inspected exact implementation head
`208063e344b767f82790ce579eba6327e2cdd0ce` and returned PASS with no
Blocking/High/Medium findings. Reviewer Windows evidence repeated the targeted `36 passed`,
ran the production-wrapper subprocess cases ten times without a cleanup hang, and confirmed
strict rejection of both injected preamble and trailing unframed bytes.

Formal `DBG-VER-001-001-001` passed against repository head
`fefd4b0c427dfa71d637e4f4cce9e4a345912591`, with no product/test diff from independently
reviewed implementation head `208063e344b767f82790ce579eba6327e2cdd0ce`:

- targeted Windows DAP CLI/harness/backend evidence: `36 passed`;
- production wrapper initialize ordering plus launch/attach: `3 passed`;
- raw preamble and trailing-byte negative controls: `2/2 rejected`;
- broader `python/tests`: `534 passed, 2 skipped, 2 failed`, both independently classified
  outside Slice ownership;
- traceability YAML and Ledger NDJSON validation: PASS.

Linux execution is not claimed and remains assigned to `DBG-RF-009`. Master signed off exact
implementation head `208063e344b767f82790ce579eba6327e2cdd0ce` after reconciling
`DBG-RVW-001-001-001`, `DBG-VER-001-001-001`, the Slice contract, traceability, and handoff.

`DBG-IT-001-001` and `DBG-SL-001-001-001` are closed. Issue #38 / `DBG-DA-001` is the next
separate gate and was not started in this iteration.

## DBG-IT-001-002 — Optimal Modular Debugger DesignAnalysis

Status: AWAITING STEERING ACCEPTANCE

### Goal

Produce one requirements-driven modular debugger architecture, reuse/adapt/replace matrix,
migration sequence, and proposed architecture/design-contract set for Steering review.

### Why now

`DBG-RF-001` established a trustworthy production DAP baseline and completed exact-head
sign-off. Steering comment `5345600066` in issue #38 authorizes `DBG-DA-001` analysis, but
explicitly withholds structural product-code implementation authority.

### Expected files

- `SDP/Debugger/02--Study/002--Controller_State_Concurrency.md`
- `SDP/Debugger/02--Study/003--Inspection_Resources_Execution.md`
- `SDP/Debugger/02--Study/004--Frontend_Packaging_Verification.md`
- `SDP/Debugger/02--Study/005--Legacy_Reuse_Audit.md`
- `SDP/Debugger/05--DesignAnalysis/001--Optimal_Debugger_Architecture/README.md`
- proposed documents under `SDP/Debugger/04--Architecture/` and `SDP/Debugger/06--Design/`
- this sprint's `ScrumIterations.md`, `Handoff.md`, and Debugger traceability files
- architecture review records `DBG-RVW-001-002-001..DBG-RVW-001-002-003`

No product, runtime, extension, test, or packaging file may be modified in this iteration.

### Invariants

- optimize from accepted `DBG-R-001..DBG-R-036`, not existing monolith boundaries;
- preserve legacy behavior as an oracle until replacement parity is independently proven;
- one authoritative debugger state owner and one serialized mutation model;
- explicit responsibility and non-responsibility for every proposed module;
- frontend-neutral core reused by CLI and DAP;
- executive-only runtime control;
- proposed `DBG-A-*` / `DBG-D-*` remain target state pending Steering acceptance;
- `DBG-RF-002..DBG-RF-009` product implementation stays blocked.

### Non-goals

- no structural product-code change;
- no final acceptance or freezing of `DBG-D-*` contracts;
- no worker dispatch for any Refactor;
- no silent invention of missing HSX address/execution semantics.

### Bounded Study work packages

1. `DBG-ST-002`: controller/state/concurrency/events/reconnect alternatives.
2. `DBG-ST-003`: inspection/resources/lifecycle/stepping alternatives and HSX dependencies.
3. `DBG-ST-004`: DAP/VS Code/package/verification boundaries.
4. `DBG-ST-005`: legacy reuse/adapt/replace evidence and regression-oracle audit.

Study workers own only their assigned documents. Master owns shared traceability and final
cross-domain synthesis.

### Traceability

- Inputs: `DBG-ST-001`, `DBG-CR-001`, `DBG-GAP-001`, `DBG-R-001..DBG-R-036`
- Active: `DBG-DA-001`, `DBG-ST-002..DBG-ST-005`, `DBG-IT-001-002`
- Completed review attempts: `DBG-RVW-001-002-001`, `DBG-RVW-001-002-002` — REWORK
- Final independent review: `DBG-RVW-001-002-003` — PASS at
  `89d95de2d944179219a93895f1ab956f2786a232`
- Downstream blocked work: `DBG-RF-002..DBG-RF-009`

### Validation and completion signal

- every requirement is mapped to proposed architecture/design responsibility;
- architecture, state, lifecycle, API/boundary, reuse, and migration outputs are complete;
- Markdown links, Mermaid syntax, YAML, and Ledger NDJSON validate;
- a fresh independent architecture reviewer reviews the exact proposed-design head;
- Blocking/High/Medium review findings are corrected and re-reviewed;
- reviewed decision package is posted to issue #38;
- status becomes `awaiting_steering_acceptance`, not accepted/implementation-authorized.

### Study work-package result

All four bounded Studies are complete for Master synthesis:

- `DBG-ST-002` recommends a single actor/command-queue controller, typed executive gateway,
  orthogonal connection/target state, explicit stop epochs, and reconciliation barrier;
- `DBG-ST-003` recommends typed target/image/address boundaries, immutable artifact/source and
  inspection services, owner-scoped resources, explicit lifecycle, and a bounded shared step
  planner while recording eight missing HSX contracts;
- `DBG-ST-004` recommends thin CLI/DAP peers, one DAP outbound serializer, standard-DAP-first
  VS Code presentation, a vendored immutable Python runtime, compatibility registry, and
  extracted-artifact Windows/Linux verification;
- `DBG-ST-005` classifies 34 legacy component/responsibility rows and recommends a strangler
  migration that preserves proven semantics/tests while replacing legacy ownership.

Study-worker evidence included 51 and 118 targeted Python tests, balanced Mermaid/Markdown,
complete `DBG-F-001..026` and `DBG-R-001..036` coverage in the reuse audit, and clean diffs.
No Study granted implementation authority. Master synthesis and exact-head architecture review
are complete; posting the reviewed Steering decision package is now the active action.

### Master synthesis result

Master synthesized one proposal across all four Studies:

- proposed architecture `DBG-A-001..DBG-A-008`;
- proposed detailed contracts `DBG-D-001..DBG-D-010`;
- first-class follow-up `DBG-ST-006` for unresolved portable HSX runtime contracts;
- context, command/event, connection, target lifecycle, and responsibility diagrams/tables;
- complete major-component reuse/adapt/replace matrix with the 34-row `DBG-ST-005` audit as
  detailed evidence;
- strangler migration and proposed RF-004→RF-005→RF-006 dependency refinements;
- explicit Steering choices for controller model, packaging, runtime requirements, lifecycle
  defaults, watch semantics, custom views, and compatibility window.

The initial synthesis status was `proposed_pending_review`. No target-state item was accepted
or implementation-authorized before review attempt `DBG-RVW-001-002-001`.

### Architecture review attempt 1

`DBG-RVW-001-002-001` reviewed exact proposal head
`f8b80977c5a78b81488ffc486a3604be863dfb26` and returned REWORK:

- High: command acceptance incorrectly transitioned the target directly to running;
- Medium: `DBG-ST-006` ownership/structure/gate effects disagreed across documents;
- Medium: `DBG-IT-001-002`, sprint exit, Handoff authority, and review-stage traceability
  were incomplete or stale;
- Low: `DBG-ST-005` contains 34 component rows, not the claimed 36.

Master corrected the target state machine with pending states and authoritative-evidence
transitions, rebuilt the first-class `DBG-ST-006` contract/gates, synchronized iteration and
review traceability, and corrected the row count through an append-only Ledger correction.
Fresh exact-head re-review was reserved as `DBG-RVW-001-002-002`.

### Architecture review attempt 2

`DBG-RVW-001-002-002` reviewed exact rework head
`e1f72a59bed3455a06d4443750ebf2f8c068e409`. It confirmed technical closure of pending
states and `DBG-ST-006`, then returned REWORK for one stale review-stage/iteration status and
one remaining stale 36-row claim. Master corrected those current surfaces. Fresh review
attempt 3 is `DBG-RVW-001-002-003`.

### Architecture review attempt 3

`DBG-RVW-001-002-003` reviewed the complete corrected proposal at exact head
`89d95de2d944179219a93895f1ab956f2786a232` and returned PASS with no
Blocking/High/Medium findings. It confirmed closure of event-authoritative pending states,
the first-class `DBG-ST-006` ownership/gates/Steering route, iteration and handoff status,
and the 34-row append-only correction. It also revalidated full requirements/findings
coverage, anti-monolith responsibilities, proposal-only dependency changes, SDP-only scope,
YAML/NDJSON, 14 Mermaid blocks, and the read-only `118 passed` evidence.

The proposal is reviewed but not accepted. Master posted the issue #38 decision package as
comment `5346421143`; the iteration is waiting at the Steering gate. `DBG-A-*` / `DBG-D-*`
remain target/proposed, `DBG-D-002..DBG-D-006`
remain gated by `DBG-ST-006` and stable HSX inputs, and all `DBG-RF-002..DBG-RF-009` product
implementation remains blocked.

## DBG-IT-001-003 — Portable Debug Runtime Contracts

Status: SUPPLEMENTAL CONTRACT STUDIES ACTIVE

### Goal

Complete `DBG-ST-006` by producing reviewed, stable, traceable HSX contract proposals for the
portable runtime semantics required by `DBG-D-002..DBG-D-006`.

### Authority

- issue #38 Steering comment `5348190806` accepts `DBG-A-001..DBG-A-008` as target direction,
  keeps every `DBG-D-*` proposed, and authorizes `DBG-ST-006`;
- issue #47 Steering comment `5348192567` activates `HSX-ST-001` as HSX coordinator and
  authorizes numbered HSX Studies;
- no structural product implementation and no AVR work are authorized.

### Study decomposition

1. `HSX-ST-001` — legacy provenance/migration coordinator.
2. `HSX-ST-002` — executive/target/image identity, generations, lifecycle and ownership.
3. `HSX-ST-003` — address spaces, ABI, unwind, frame and variable-location semantics.
4. `HSX-ST-004` — run/stop evidence, snapshots, exact stepping and blocked-state inspection.
5. `HSX-ST-005` — event-stream cursor, ACK, gaps, drops, resume and capability profiles.
6. `HSX-ST-006` — breakpoint/watch identity, provenance, revisions and reconciliation evidence.

### Expected files

- `SDP/Debugger/02--Study/006--Portable_Debug_Runtime_Contracts.md`
- `SDP/HSX/02--Study/001--Legacy_Traceability_Migration.md`
- `SDP/HSX/02--Study/002--Runtime_Identity_Lifecycle.md`
- `SDP/HSX/02--Study/003--Address_ABI_Unwind.md`
- `SDP/HSX/02--Study/004--Execution_Snapshot_Blocked_States.md`
- `SDP/HSX/02--Study/005--Event_Stream_Continuity.md`
- `SDP/HSX/02--Study/006--Resource_Provenance_Revisions.md`
- proposed HSX Requirements/Architecture/Design contract documents and both track traceability
- independent review records `HSX-RVW-001-001-001..HSX-RVW-001-001-005`

No product/runtime/extension/test/package/AVR file may be modified.

### Invariants and non-goals

- legacy DR/DG/DO IDs remain provenance, not silently renamed authority;
- current behavior, legacy intent, and proposed portable target semantics remain distinct;
- each contract states identity, type/range, ordering, failure/degraded behavior, capability,
  versioning, and conformance evidence;
- Debugger owns dependency consumption; HSX owns portable runtime semantics;
- no `DBG-D-*` freeze, RF implementation, AVR design, or product change;
- missing evidence becomes an explicit gap/Study route, not an assumed contract.

### Traceability

- Debugger: `DBG-ST-006`, `DBG-D-002..DBG-D-006`, `DBG-IT-001-003`
- HSX: `HSX-ST-001..HSX-ST-006`, proposed stable `HSX-R-*`, `HSX-A-*`, `HSX-D-*`
- Reviews: `HSX-RVW-001-001-001` REWORK, `...002` REWORK, `...003` REWORK, `...004` planned
- Issues: #47 coordination and #38 Steering gate

### Completion signal

- every `DBG-ST-006` question maps to a stable proposed HSX contract and conformance fixture;
- all HSX Studies distinguish evidence, decisions, uncertainty, and cross-track ownership;
- HSX CurrentIndex/Relations/Ledger and Debugger cross-track relations agree;
- fresh independent review passes the exact contract package head;
- reviewed decision packages are posted to #47 and #38;
- status becomes `awaiting_steering_acceptance`, with every `DBG-D-*` and RF product gate still
  closed.

### Study work-package result

`HSX-ST-001..HSX-ST-006` are complete for Master synthesis:

- ST-001 classified the legacy DR/DG/DO catalogue and current Python oracle while routing
  broader HSX migration separately;
- ST-002 defined composite runtime/stream/target/image identity and explicit lifecycle leases;
- ST-003 defined typed address/architecture/ABI/debug-bundle/unwind/location concepts;
- ST-004 defined causal transition evidence, inspection revisions/snapshots, exact stepping,
  breakpoint precedence and blocked-state capability;
- ST-005 defined stream-scoped cursors, ACK-after-apply, typed gaps/resume profiles and event
  health/reconciliation;
- ST-006 defined owner/provenance/revision-aware remote resources and conservative legacy mode.

Read-only evidence totals include 90, 40, 106, 77 and 114 passing targeted tests across the
five technical Studies. All workers changed only their assigned Study. Study and contract
synthesis are complete.

### Master contract synthesis result

Master allocated and synthesized:

- `HSX-R-001..HSX-R-036` portable requirements;
- `HSX-A-001..HSX-A-005` architecture boundaries;
- `HSX-D-001..HSX-D-005` detailed contract groups;
- full `DBG-ST-006` dependency closure matrix;
- named full/degraded capability profiles and reusable conformance fixtures.

At initial synthesis, all artifacts remained target/proposed and the first exact-head review
was `HSX-RVW-001-001-001`; no design freeze or implementation authority resulted.

### Cross-track review attempt 1

`HSX-RVW-001-001-001` reviewed exact proposal head
`5fff403f6668f794b760caf64ef34b4d1ecb4ae3` and returned REWORK:

- High: LoadedImageRef lost opaque target-bound load identity;
- Medium: exact-step zero-retirement/precedence contradicted ST-004;
- Medium: capability names/full-profile composition conflicted across A/D;
- Medium: HSX/Debugger stage and Handoffs were stale.

Master corrected all four documentation/contract findings. Fresh review is
`HSX-RVW-001-001-002`. Every contract remains target/proposed and all implementation gates
remain closed.

### Cross-track review attempt 2

`HSX-RVW-001-001-002` reviewed exact head
`ffd0a4254751dea2692eb8e2f3d66cb6e68f7d5a`. It confirmed LoadedImageRef,
phase-linearized exact-step and capability-registry closure, then returned REWORK for stale
current review-stage references. Master synchronized every next-gate surface. Fresh review is
`HSX-RVW-001-001-003`.

### Cross-track review attempt 3

`HSX-RVW-001-001-003` reviewed exact head
`efd43d2be9e4db1646419fe5036ec1f5b22c8deb`. Technical contracts passed, but it returned
REWORK because HSX README, Debugger CurrentIndex and Debugger Handoff still exposed stale
current-stage claims. Master corrected every current gate to point solely to
`HSX-RVW-001-001-004`; prior review IDs remain history.

### Cross-track review attempt 4

`HSX-RVW-001-001-004` reviewed exact head
`cbddfa24d3cbb25bf7a17c63a0146ee8d0600883`. It confirmed all prior closures but found
unrouted address/ABI decisions and a recursive/underspecified debug-bundle identity. Master
activated first-class `HSX-ST-007` and `HSX-ST-008`. Fresh review after synthesis is
`HSX-RVW-001-001-005`.

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

Status: REWORK COMPLETE — PENDING FRESH REVIEW `DBG-RVW-001-002-003`

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
- Planned fresh review: `DBG-RVW-001-002-003`
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
No Study granted implementation authority. Master synthesis is now the active action.

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

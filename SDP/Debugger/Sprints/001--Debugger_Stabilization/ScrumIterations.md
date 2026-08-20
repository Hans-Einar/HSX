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

Status: CLOSED — ARCHITECTURE DIRECTION ACCEPTED; DESIGN CONTRACTS UNFROZEN

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
are complete. The reviewed package was posted and Steering accepted the architecture direction
in issue #38 comment `5348190806`; detailed design and implementation authority remain closed.

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

Status: COMPLETE / REMOTE VERIFIED / STEERING ACCEPTED AND FROZEN

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
7. `HSX-ST-007` — concrete ABI profile, bounded unwind/location schemas and register mutation.
8. `HSX-ST-008` — non-recursive debug-bundle/source identity and canonicalization.

### Expected files

- `SDP/Debugger/02--Study/006--Portable_Debug_Runtime_Contracts.md`
- `SDP/HSX/02--Study/001--Legacy_Traceability_Migration.md`
- `SDP/HSX/02--Study/002--Runtime_Identity_Lifecycle.md`
- `SDP/HSX/02--Study/003--Address_ABI_Unwind.md`
- `SDP/HSX/02--Study/004--Execution_Snapshot_Blocked_States.md`
- `SDP/HSX/02--Study/005--Event_Stream_Continuity.md`
- `SDP/HSX/02--Study/006--Resource_Provenance_Revisions.md`
- `SDP/HSX/02--Study/007--ABI_Profile_Recipe_Schema.md`
- `SDP/HSX/02--Study/008--Debug_Bundle_Source_Identity.md`
- proposed HSX Requirements/Architecture/Design contract documents, the `HSX-D-002` canonical
  digest-vector appendix, and both track traceability
- independent review records `HSX-RVW-001-001-001..HSX-RVW-001-001-006`

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
- HSX: `HSX-ST-001..HSX-ST-008`, proposed stable `HSX-R-*`, `HSX-A-*`, `HSX-D-*`
- Reviews: `HSX-RVW-001-001-001..005` REWORK; `...006` PASS on exact proposal content
  `b57e368…` plus trace-only assignment `24beb82…`
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

`HSX-ST-001..HSX-ST-008` are complete and synthesized:

- ST-001 classified the legacy DR/DG/DO catalogue and current Python oracle while routing
  broader HSX migration separately;
- ST-002 defined composite runtime/stream/target/image identity and explicit lifecycle leases;
- ST-003 defined typed address/architecture/ABI/debug-bundle/unwind/location concepts;
- ST-004 defined causal transition evidence, inspection revisions/snapshots, exact stepping,
  breakpoint precedence and blocked-state capability;
- ST-005 defined stream-scoped cursors, ACK-after-apply, typed gaps/resume profiles and event
  health/reconciliation;
- ST-006 defined owner/provenance/revision-aware remote resources and conservative legacy mode.
- ST-007 defined `hsx.abi.llc-r7-word32/1`, bounded versioned unwind/location recipes and
  exclusive revision-fenced register mutation.
- ST-008 defined the acyclic ArtifactRef/LoadedImageRef/ImageDebugBundleRef/ImageDebugBinding
  model and exact-case, content-bound source identity.

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

### Supplemental Study and resynthesis result

Both supplemental Studies completed in bounded, disjoint Study files with no product or AVR
changes. Master resynthesized their decisions into `HSX-R-004`, `R-006`, `R-015..R-018`,
`R-023`, `HSX-A-001/002`, `HSX-D-001..003`, `DBG-ST-006`, and proposed
`DBG-D-002..DBG-D-006`. The package now defines exact ABI/frame rows, bounded recipe opcodes
and limits, atomic register-write epoch replacement, canonical non-recursive bundle binding,
and stable content-bound source identity. Review 005 completed REWORK; no contract is accepted
or implementation-authorized.

### Cross-track review attempt 5

`HSX-RVW-001-001-005` reviewed exact head
`84df21d763b73209efd0292990799f469283460a` and returned REWORK for three Medium findings:

- the target f16 zero-upper-bit rule omitted current VM/compiler upper-half preservation as a
  named nonconformance/removal fixture;
- structured digest domain bytes, integer encodings and JSON escaping were not unique and
  lacked golden vectors;
- current Handoffs did not anchor the reviewed SHA or reflect the already-assigned review.

All other technical, traceability, scope and evidence checks passed. Master completed and
validated documentation-only corrections at exact proposal-content head
`b57e368f77bb533b09397d633fc92565655e1668`; fresh `HSX-RVW-001-001-006` is assigned. Every
design/RF/product/AVR gate remains closed.

### Cross-track review attempt 6

`HSX-RVW-001-001-006` reviewed exact proposal-content head
`b57e368f77bb533b09397d633fc92565655e1668` plus trace-only assignment head
`24beb825b40ccafb9391019f7bd7530e388cd675` and returned PASS with no Blocking/High/Medium
findings. It independently reproduced all four canonical hashes in Python and Node, repeated
the current f16 allocator-reuse nonconformance, re-ran the representative oracle suites, and
validated YAML/NDJSON, Markdown, IDs/mappings, guards, SDP-only scope and diff cleanliness.

Verification `HSX-VER-001-001-001`, Master exact-content sign-off and remote fresh-checkout
publication passed. Steering froze the HSX portable target contracts in #47 comment
`5356480919`, accepted `DBG-ST-006` complete and froze `DBG-D-001..010` in #38 comment
`5356484309`. `DBG-IT-001-003` is closed. The freeze grants no HSX runtime/AVR implementation.

## DBG-IT-001-004 — Controller/Gateway First Structural Wave

Status: CLOSED — STEERING ACCEPTED / REMOTE PUBLICATION PASS

### Authority and scope

- Steering: issue #38 comment `5356484309`.
- Authorized: `DBG-RF-002`, `DBG-RF-003`, then `DBG-SL-001-004-003` integration.
- Frozen designs: `DBG-D-001..DBG-D-010`.
- Frozen portable target baseline: `HSX-R-001..036`, `HSX-A-001..005`, `HSX-D-001..005`.
- Runtime boundary: current Executive only through `hsx.python-debug-legacy/1`; no
  `execd.py`/VM/portable-runtime implementation.
- Still blocked: `DBG-RF-004..DBG-RF-009`.

### Frozen execution units

1. `DBG-SL-001-004-001` — RF-002 controller/state/epoch foundation.
2. `DBG-SL-001-004-002` — RF-003 typed legacy gateway/health/recovery foundation.
3. `DBG-SL-001-004-003` — early controller/gateway integration, blocked until both parent
   Slices are independently signed off.

Refrozen `dbg.controller-gateway/1.1` envelopes, generations, health, recovery and public
ports are frozen in `Interfaces/003--Controller_Gateway_Envelope_Set_v1_1.md`; independent
interface review and both foundation Slice re-reviews passed before formal verification.

### Parallel ownership

- RF-002 owns shared contracts plus controller/model/reducer/epoch files and their tests.
- RF-003 owns only gateway/health/legacy adapter files and their tests; shared contracts are
  read-only.
- No existing ExecutiveSession/backend/DAP/CLI/VS Code/runtime/AVR file is worker-owned.
- Discovery requiring an interface or accepted-design change stops both workers and returns to
  Master/Steering.

### Execution loop

1. Fresh bounded RF-002/RF-003 workers may overlap after the contracts module exists; file
   ownership remains disjoint and workers commit only owned files.
2. `DBG-RVW-001-004-001` / `...002` independently review exact Slice heads.
3. Formal verification and Master exact-head sign-off close each foundation Slice.
4. Fresh integration worker implements only Slice 003 on the signed combined foundation.
5. `DBG-RVW-001-004-003`, `DBG-VER-001-004-003` and Master sign-off close integration.
6. Fresh parent final reviewers/verifiers reconcile RF-002/RF-003 after integration PASS.
7. Master posts a concise result package to issue #38 and stops before RF-004..009.

### Exit signal

RF-002 foundation, RF-003 foundation and integration Slice all have independent exact-head
PASS, formal verification and Master sign-off; public interfaces/deviations/evidence/residuals
are durable and the next wave remains Steering-controlled.

### Interface blocker discovered before product commit

The parallel workers stopped on an exact-generation contradiction in
`dbg.controller-gateway/1`: gateway OPEN/SUBSCRIBE must advance local session/stream
generation, while controller exact-fencing rejects the first resulting `N+1` notice and has no
authorized adoption transition. No product file was staged/committed and no Slice review or
verification began.

Steering authorized `dbg.controller-gateway/1.1` with reserve -> authoritative success ->
promote semantics in issue #38 comment `5357146230`. The frozen successor is
`Interfaces/003--Controller_Gateway_Envelope_Set_v1_1.md`. A clean bounded interface
implementation, all nine specified fixtures and fresh `DBG-RVW-001-004-004` are required
before RF-002/RF-003 resume. Partial stash `efc91f2640647402bc92c69bde1c57685cfaa1f1`
remains candidate-only and integration/RF-004..009 remain blocked.

### Final closeout

RF-002, RF-003 and dependent integration passed their complete worker/review/verification/
sign-off chains. The signed ancestry through final publication head
`69a54aeb3394d3cd4792bce620748e15bab69f1f` is remote-resolvable on
`origin/codex/dbg-rf-002-003`; fresh-checkout contracted evidence reported `121 passed`, clean
traceability and no product drift after the combined signed head. Steering accepted iteration
004 and the three first-wave units complete in issue #38 comment `5362514094`.

## DBG-IT-001-005 — Typed Resolver and Inspection

Status: ACTIVE — CONTRACTS FROZEN / PRODUCT NOT STARTED

### Authority and goal

- Steering authority: issue #38 comment `5362514094`.
- Dependency clarification: issue #42 comment `5362515750`.
- Authorized product domain: `DBG-RF-004` only.
- Goal: frontend-neutral artifact/source/address/stack/variables/memory/disassembly services
  under `DBG-D-003`, `DBG-D-004`, `DBG-D-009` and frozen portable HSX contracts.
- Branch/base: `codex/dbg-rf-004` from
  `69a54aeb3394d3cd4792bce620748e15bab69f1f`.
- Still blocked: `DBG-RF-005..DBG-RF-009`, Executive/VM/AVR, DAP/CLI/VS Code migration.

### Frozen public interface

`Interfaces/004--Typed_Resolver_Inspection_Interface_v1.md` freezes
`dbg.resolver-inspection/1`. Every successful/partial inspection result carries the exact
TargetRef, LoadedImageRef, StopEpochId, StopToken and InspectionSnapshotRef. Typed HSX
addresses use descriptor-checked spaces/ranges; best-effort live reads are explicitly degraded
and cannot be coherent. Artifact index, source resolver, recipes/stack, epoch inspection and
frontend mapping remain separate responsibilities.

Interface review `DBG-RVW-001-005-007` returned REWORK at exact remote-published head
`82154c614a31284723bf3e6a337c5bedfb8aba5d`. Master corrected only the candidate interface,
Slice ownership and live traceability. Reviews 008 through 010 also returned REWORK; fresh
`DBG-RVW-001-005-012` must PASS before product
dispatch. A finding requiring an accepted DBG/HSX design change returns to Steering.

### Frozen execution units

1. `DBG-SL-001-005-001` — classified legacy oracle/golden evidence; tests/fixtures only.
2. `DBG-SL-001-005-002` — immutable identities, binding, typed addresses and result algebra.
3. `DBG-SL-001-005-007` — recipe DTO/validator/evaluator foundation.
4. `DBG-SL-001-005-003` — verified immutable artifact index and explicit legacy `.sym` adapter.
5. `DBG-SL-001-005-004` — exact content-verified SourceResolver.
6. `DBG-SL-001-005-005` — snapshot-bound StackService.
7. `DBG-SL-001-005-006` — domain handles and integrated epoch-bound InspectionService.

Slices are sequential because each later worker consumes prior signed interfaces. Each uses a
fresh worker, fresh exact-head reviewer, formal `DBG-VER-001-005-00N` evidence and Master
exact-head sign-off before the next Slice starts.

### Invariants

- no hidden `0xFFFF`/`0xFFFFFFFF`, modulo/truncation or implicit wrap;
- no unconditional lowercase/casefold identity, basename guessing or first-candidate choice;
- no unknown-frame fallback, fixed-R7 guess or invented/padded partial values;
- no independent live reads represented as one coherent stop snapshot;
- legacy algorithms are adapted only after Slice 001 classifies executable evidence;
- no module owns artifact parsing, source resolution, unwind/stack, epoch inspection and
  frontend policy together;
- prior signed controller/gateway modules and `dbg.controller-gateway/1.1` remain unchanged.

### Traceability and dependency graph

- Parent: `DBG-RF-004`; iteration `DBG-IT-001-005`; Slices
  `DBG-SL-001-005-001..007`.
- Requirements: `DBG-R-004`, `DBG-R-021..DBG-R-028`, `DBG-R-034..DBG-R-036`.
- Design: `DBG-D-003`, `DBG-D-004`, `DBG-D-009`; portable `HSX-D-001..003`.
- Slice reviews: `DBG-RVW-001-005-001..006` and `DBG-RVW-001-005-011`; interface
  reviews: `DBG-RVW-001-005-007..010`, then `...012`; verifications
  `DBG-VER-001-005-001..007`.
- Parent final: `DBG-RVW-004-001-001`, `DBG-VER-004-001-001`.
- RF-005 explicitly depends on RF-004's accepted `dbg.resolver-inspection/1`; partial/frozen
  implementation does not satisfy the dependency and no RF-005 worker is authorized.

### Verification and exit signal

Each Slice runs its frozen focused matrix, prior signed RF-004 tests and applicable
RF-002/RF-003 regressions, plus YAML/NDJSON/diff/protected-path checks. Iteration 005 closes
only after all seven exact-head Slice sign-offs, fresh combined parent review/verification,
parent Master sign-off, remote publication/fresh reconstruction and issue #38 decision
package. The package must cover interfaces, address/source/stack/variables/memory/disassembly,
legacy status, degraded behavior, exact heads and RF-005 recommendation. Master then stops for
Steering.

### Interface review attempt 1

Fresh read-only `DBG-RVW-001-005-007` confirmed exact remote head/ancestry, SDP-only scope,
clean worktree, YAML/114-row NDJSON, IDs/paths/fences and one active iteration, but returned
REWORK:

- High: incomplete record/query/pagination/expression schemas plus contradictory wrap API;
- High: Slice 005 required handles owned only by Slice 006;
- Medium: RF-002 StopEpoch consumption seam was unspecified;
- Medium: two live Relations gates remained stale.

Master refroze a complete public schema/result surface, explicit checked/wrap mode,
handle-free Slice 005 output with Slice 006 wrapping, a read-only `ControllerEpochAdapter`, and
corrected live dependency statuses. No product file changed. Fresh exact-head review is
`DBG-RVW-001-005-008`; Slice 001 remained unstarted.

### Interface review attempt 2

Fresh read-only `DBG-RVW-001-005-008` reviewed exact remote head `8d6c0f571…`. It confirmed
the prior stack-handle and live-Relations closures, exact remote/ancestry/clean scope,
YAML/116-row append-only Ledger, paths/fences and RF-004-only authority, then returned REWORK:

- High: convenience bundle/ref/binding schemas contradicted the canonical HSX payloads;
- High: recipe/evaluator/result/order/page semantics remained incomplete;
- High: returned variables could not carry VARIABLE handles or structural partial pieces;
- High: legacy index could advertise an exact binding without canonical evidence;
- Medium: StopEpoch evidence grade and mismatch status/code matrix remained incomplete.

Master replaced the identity types with exact normative payload/ref/binding projections,
froze recipe/op/rule/evaluator/budget and deterministic ordering/page rules, added variable
records/handles/pieces, separated LegacyDebugArtifactIndex with mandatory
LEGACY_UNVERIFIED provenance and no binding/SourceRef, and froze the StopEpoch matrix. No
product file changed. Fresh exact-head review is `DBG-RVW-001-005-009`.

### Interface review attempt 3

Fresh read-only `DBG-RVW-001-005-009` reviewed exact remote head `07f7e1604…`. It confirmed
the earlier handle/Relations/StopEpoch/variable-piece/legacy-type closures and all scope/
trace validations, then returned REWORK:

- High: composite TargetRef lacked exact scalar mapping for canonical LoadedImageRef;
- High: recipe bound exhaustion used a forbidden separate LIMIT_EXCEEDED status;
- High: artifact queries could not enumerate sources/types/scopes/variables, and generic
  expressions incorrectly required variable identity;
- High: artifact Slice 003 preceded the Slice 005-owned recipe validator it required;
- Medium: legacy functions could transitively return portable SourceRef.

Master added the exact opaque TargetRef canonical scalar/emission mapping, restored
`unsupported(limit_exceeded)`, froze source/type/scope/variable queries and separate
ExpressionValue plus scope composition, introduced early recipe foundation Slice 007 before
artifact Slice 003, and added LegacyFunctionRecord. No product file changed. Fresh exact-head
review is `DBG-RVW-001-005-010`.

### Interface review attempt 4

Fresh read-only `DBG-RVW-001-005-010` reviewed exact remote head `72b06ad0…`. It confirmed
all review 007..009 closures plus seven-Slice ownership/order, SDP-only scope and 120-row
append-only trace, then returned REWORK:

- High: InspectionService dependency construction, epoch/session activation/invalidation and
  persistent handle-store lifetime were not public/frozen;
- High: SymbolRecord used symbol_id while LocationRow/results/handles used an undefined second
  variable_id namespace;
- Medium: index order referenced absent address `.value` and no SymbolKind rank.

Master froze explicit service/session/store factory and lifecycle/concurrency semantics,
standardized variables end-to-end on SymbolRecord.symbol_id with referential validation, and
corrected `.unsigned_value` ordering plus SymbolKind rank. Review 011 remains reserved for
Recipe Slice 007; fresh interface review is `DBG-RVW-001-005-012`.

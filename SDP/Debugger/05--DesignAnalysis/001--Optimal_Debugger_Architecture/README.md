# DBG-DA-001 — Optimal Modular Debugger Architecture

- Status: DEBUGGER V1 ARCHITECTURE AND DESIGN BASELINE ACCEPTED
- Started by Steering: issue #38 comment `5345600066`
- Active iteration: `DBG-IT-001-002`
- Evidence head for completed Studies: `a8eae871537cb70ea78502f7d34fbdbe68d837fa`
- Final independent review: `DBG-RVW-001-002-003` — PASS at
  `89d95de2d944179219a93895f1ab956f2786a232`
- Steering architecture acceptance: issue #38 comment `5348190806`
- Implementation authority: first-wave frozen Slices only

## Objective and decision boundary

Design the debugger from accepted `DBG-R-001..DBG-R-036`, without treating the legacy
monoliths as required structure. The output is one recommended architecture, proposed
architecture/design contracts, migration sequencing, and a reuse/adapt/replace matrix.

`DBG-A-001..DBG-A-008` are accepted as target architecture direction. Steering froze
`DBG-D-001..DBG-D-010` in issue #38 comment `5356484309`. Only frozen first-wave Slices under
`DBG-RF-002`, `DBG-RF-003`, and their early integration are implementation-authorized;
`DBG-RF-004..DBG-RF-009` remain blocked.

## Evidence synthesized

- `DBG-ST-001` legacy baseline;
- `DBG-ST-002` controller/state/concurrency/events/recovery alternatives;
- `DBG-ST-003` inspection/resources/lifecycle/execution semantics;
- `DBG-ST-004` DAP/CLI/VS Code/package/verification architecture;
- `DBG-ST-005` 34-row legacy reuse/adapt/replace audit;
- `DBG-CR-001` / `DBG-F-001..DBG-F-026`;
- accepted `DBG-GAP-001` and signed `DBG-RF-001` production-path oracle;
- current product, protocol, test, package, and legacy-document evidence cited by the Studies.

The Study workers edited only their assigned documents. Master owns this cross-domain
synthesis and all stable proposal numbering.

## Recommended architecture in one paragraph

Build one frontend-neutral debugger core around an actor/command-queue controller that is the
only authoritative state writer. Put executive RPC/event mechanics behind a typed gateway with
separate RPC and event health. Bind inspection to immutable target/image-specific stop epochs.
Keep artifact/source interpretation, inspection, resource reconciliation, and lifecycle/step
planning as bounded services coordinated through the controller. Make CLI and DAP thin peer
frontends, give DAP one outbound serializer, keep VS Code standard-DAP-first, and ship the exact
pure-Python runtime inside an immutable VSIX with an explicit compatibility registry and
Windows/Linux artifact oracle. Migrate through a strangler path while the legacy debugger
remains a classified behavioral oracle.

## Master synthesis decisions

### 1. State and concurrency

Recommend the actor/command-queue alternative from `DBG-ST-002`.

- Rejected: one broad lock around a synchronous controller, because blocking I/O and callback
  ordering preserve deadlock/stale-completion risk.
- Rejected as first migration: fully async core, because async tasks still need one reducer and
  would require a larger rewrite of current blocking frontends/transport.
- Selected: one controller actor/reducer, typed commands/effects/completions/events/deadlines,
  blocking I/O outside the actor, and synchronous facade Futures for CLI/DAP callers.

### 2. Runtime authority and recovery

Executive events are authoritative only under a negotiated reliable-event profile. RPC and
event-stream health are independent controller state. Poll-only operation is a named bounded
compatibility mode, never simultaneous competing truth. Reconnect is complete only after
identity, ownership, capabilities, cursor/state, resources, and epoch reconcile.

### 3. Stop epochs and inspection

One authoritative stable stop creates one immutable epoch. Registers, stack, scopes,
variables, memory, disassembly, artifact identity, and handles refer to that epoch or return
explicit partial/unavailable/stale results. Resume or uncertain target identity invalidates it
before effects proceed. DAP IDs map epoch handles; they do not define lifetime.

### 4. Artifacts, source, and addresses

Adapt the current symbol/source algorithms behind image-bound, case-preserving services and an
explicit HSX `ArchitectureDescriptor`. Do not retain scattered masks, global lowercase, or
basename guessing. Missing portable address/ABI/snapshot semantics are recorded in
`DBG-ST-006` and remain cross-track dependencies.

### 5. Breakpoints and watches

One Resource Catalog/Reconciler owns logical desired state, owner/provenance, remote actual
state, and reconnect reconciliation. Standard Watch expressions are snapshot queries;
persistent live watches are a separate optional HSX resource. Legacy address/ID-only
executives use conservative preservation and never claim full ownership.

### 6. Lifecycle and execution

Attach, launch, detach, disconnect, terminate, and kill are distinct core intents. Until HSX
supports atomic true launch, frontends expose attach rather than mislabeled launch. One shared
Execution Planner owns instruction/into/over/out plans, budgets, internal conditions,
preemption, and canonical completion. Timers cannot fabricate stops.
Command acceptance creates a pending operation only; target run/stop state and step completion
advance solely on authoritative response/event/reconciliation evidence.

### 7. Frontends and VS Code

CLI and DAP consume the same typed `DebuggerFrontendPort`. DAP owns only DAP framing, phase,
capabilities, mapping, handles, and one sequence-owning writer. VS Code's normal debugging
path uses standard DAP; optional memory/register/disassembly/trace views are derived,
version-negotiated projections and never state/resource owners.

### 8. Packaging and release

Recommend one pure-Python distribution for CLI and DAP, vendored exactly inside the VSIX,
initially executed by a fail-closed external Python 3.10+ prerequisite. A manifest binds
extension/runtime/source/protocol/schema/Python versions and hashes. Production launch never
imports debugger code from the debuggee workspace. Frozen per-platform executables may later
implement the same launcher contract.

## Proposed artifact registry

Architecture proposals are defined in
`SDP/Debugger/04--Architecture/001--Modular_Debugger_Architecture.md`:

- `DBG-A-001..DBG-A-008` — controller, gateway, epochs, inspection, resources, execution,
  frontends/package, and migration/verification boundaries.

Detailed proposals are defined in
`SDP/Debugger/06--Design/001--Debugger_Design_Contracts.md`:

- `DBG-D-001..DBG-D-010` — controller, gateway, epoch/identity, artifact/inspection,
  resources, lifecycle/execution, frontends/DAP, VS Code/package, compatibility/migration,
  and artifact verification contracts.

Every item is `proposed_pending_steering` and `state: target`.

## Module/API and diagram outputs

The proposed Architecture document contains:

- context/dependency diagram;
- command/event sequence;
- orthogonal connection/recovery and target-lifecycle state diagrams;
- full responsibility/non-responsibility/concurrency-owner table;
- architectural invariants and cross-track boundary.

The proposed Design document contains:

- frontend port and controller envelope/API contracts;
- session/event/reconnect and epoch/reference rules;
- inspection/resource/lifecycle/step/package/compatibility contracts;
- proposed downstream Refactor interfaces and dependency changes;
- verification ladder and negative controls.

## Requirements-to-design coverage

| Requirements | Proposed owner/contracts | Planned Refactor evidence |
|---|---|---|
| R-001..R-003 | A-007; D-007/D-008 | RF-007, RF-008, RF-009 |
| R-004 | A-003; D-003/D-007 | RF-002, RF-004, RF-007 |
| R-005..R-006 | A-006; D-006 | RF-006 |
| R-007..R-008 | A-001/A-002; D-001/D-002/D-007 | RF-002, RF-003, RF-007 |
| R-009..R-013 | A-001/A-002; D-001/D-002/D-009 | RF-002, RF-003, RF-009 |
| R-014..R-015 | A-005; D-005 | RF-005, RF-007, RF-009 |
| R-016..R-020 | A-001/A-006; D-001/D-006 | RF-006, RF-009 plus HSX contracts |
| R-021..R-025 | A-003/A-004; D-003/D-004 | RF-004, RF-009 plus HSX contracts |
| R-026..R-028 | A-001..A-007; D-001..D-008 | RF-002..RF-008 |
| R-029..R-030 | A-007; D-007/D-008 | RF-007, RF-008, RF-009 |
| R-031..R-034 | A-002/A-007/A-008; D-002/D-008..D-010 | RF-003, RF-008, RF-009 |
| R-035..R-036 | A-008; D-009/D-010 | every Refactor, final RF-009 |

No requirement is intentionally left without a proposed owner. Implementation evidence does
not yet exist for target-state items.

## Master reuse/adapt/replace matrix

The authoritative evidence-rich 34-row audit is `DBG-ST-005`. This synthesis sets the
recommended disposition for the major current surfaces required by issue #38.

| Current component/responsibility | Decision | Preserved value | Target owner | Migration/retirement gate |
|---|---|---|---|---|
| `python/hsx_dbg/backend.py` DTOs/conversions/typed operations | Adapt/extract | `RegisterState`, `StackFrame`, `WatchValue`, conversion/test vectors | Executive Gateway and Inspection DTOs | Typed errors/capabilities/epoch/address tests; remove frontend generic `request` |
| `backend.py` session/PID state | Replace | Endpoint/config inputs only | Controller plus Session Gateway | Retire after CLI/DAP read controller snapshot only |
| `python/hsx_dbg/session.py` | Adapt concept, replace state shape | One owned connection, explicit teardown/config | Session Gateway supervised by controller | Reconnect/health/generation tests and no second state owner |
| `python/hsx_dbg/symbols.py` | Adapt/extract | Parsing/index algorithms, locals/globals/lookup semantics | Artifact Index | Image/schema/address/case/ambiguity goldens pass |
| `python/source_map.py` | Reuse/adapt | Prefix/relocation/symlink mapping | Source Resolver | Typed ambiguity and artifact identity added |
| `python/executive_session.py` RPC/session mechanics | Adapt substantially | Negotiation, typed errors, PID locks, keepalive, helpers | Executive Gateway | Fault-injection and explicit health/capability/generation contract passes |
| `ExecutiveSession` event callback worker | Replace | Event envelope/sequence/ACK concepts only | Event Transport feeding controller inbox | EOF/gap/drop/ACK/recovery tests; no swallowed callback or policy mutation |
| Gateway command fallbacks/caches | Adapt/centralize | Versioned disasm/debug-state/sessionless behavior where supported | Compatibility Registry plus Gateway | Per-entry owner/version/removal test; no epochless transport cache |
| CLI parser/REPL/history/completion/output | Reuse/adapt | User and automation ergonomics | Thin CLI | Public-port fake tests and CLI/DAP parity |
| CLI `DebuggerContext` and raw request commands | Replace policy | Command vocabulary only | Controller/frontend port | Remove after vertical CLI migration and no raw RPC imports |
| DAP Content-Length framing | Adapt/extract | Signed RF-001 strict-stdio behavior | `DapReader`/`DapOutbound` | Raced writer/malformed framing exact-wrapper tests |
| DAP reflection/router/capabilities | Adapt router, replace capability policy | DAP envelope/error/ordering behavior | `DapSession` and capability broker | Handler/capability/client-gating matrix passes |
| `HSXDebugAdapter` controller/reconnect/cache/timer state | Replace | Classified user-visible outcomes only | Controller/Gateway/services | Shadow/vertical parity and adversarial state tests pass |
| DAP frame/scope/source handle tables | Replace | DAP response shapes | Epoch-bound DAP handle registry | Repeated/out-of-order/stale reference tests pass |
| DAP breakpoint/watch policy | Replace; adapt mapping | DAP request/result shapes and goldens | Resource Reconciler plus mapper | Multi-owner/external preservation/reconnect tests pass |
| DAP lifecycle/step policy | Replace | Request names and exact instruction-step oracle | Lifecycle Policy/Execution Planner | Accepted semantics and golden traces pass |
| DAP symbol/memory/disassembly formatters | Adapt/extract | Pure DAP encoding/format behavior | Inspection mapper | No raw RPC/masks/path guessing; epoch tests pass |
| Python DAP/backend/symbol/session fixtures/tests | Reuse and extend | Regression evidence and RF-001 product oracle | Contract/artifact test layers | Private monolith tests retired only after public-port/product superset |
| `python/hsx-dap.py` | Retain temporary shim | Developer CLI compatibility | Canonical packaged entrypoint | Remove after declared compatibility window |
| `vscode-hsx/debugAdapter/hsx-dap.py` | Adapt/replace bootstrap | Production script location and stdio contract | Runtime Launcher | Extracted VSIX starts with sanitized env/unrelated workspace |
| `extension.ts` configuration provider | Adapt | Defaults/validation | Configuration module | True attach/launch schema and migration diagnostics |
| `HSXAdapterFactory` | Keep factory, replace internals | VS Code adapter-launch integration | Runtime Launcher | Manifest/hash/Python preflight and no workspace runtime |
| Extension coordinator/status state | Minimize/replace truth | Derived status UX and refresh hints | Session Presentation | Epoch/session-keyed projections; no target transitions/polling |
| Memory/register/stack/disassembly views | Adapt presentation | Useful embedded-target UX | Optional presenters | Standard DAP first, then additive parity and stale/unavailable tests |
| Trace view | Adapt/retain optional | HSX-specific trace UX | Versioned trace presenter | Negotiated `hsx/trace/*`, target/session cache invalidation |
| Disassembly breakpoint manager/pseudo-doc | Replace ownership; conditionally reuse rendering | Visual metadata/toggle affordance | Breakpoint Presenter over Resource Catalog | No duplicate owner/feedback loop; retire if native UX reaches parity |
| `package.json` contributions | Adapt | Stable public view/command/debug IDs where useful | Extension package contract | Manifest/extension-host snapshot tests |
| `bump-version.js` and hand-built tracked VSIX | Replace/retire | None beyond historical artifact evidence | Deterministic release pipeline | One version source, immutable artifact hash, release retention policy |
| `configProvider.test.ts` / current npm test | Reuse seed, replace harness coverage | Existing config cases | Layered unit/extension-host/artifact tests | Script runs a verified superset on Windows/Linux |

### Summary posture

- Reuse behavior/data/tests where ownership already fits.
- Adapt/extract useful typed models, protocol algorithms, symbol/source logic, CLI UX, DAP
  encoding, and optional view presentation.
- Replace controller-like frontend state, silent/hidden transport policy, epochless handles,
  resource ownership, lifecycle/step semantics, and workspace runtime discovery.
- Retire only after explicit oracle, compatibility, review, and artifact exit gates.

## Migration sequence

1. Classify existing scenarios as preserve/change/retire and capture public DAP/executive
   traces before responsibility moves.
2. Freeze proposed controller/gateway/epoch/frontend envelopes after Steering acceptance and
   `DBG-ST-006` dependency routing.
3. Extract DAP output serialization and typed gateway compatibility seams without changing
   product policy.
4. Introduce controller/model/epoch types beside legacy state, initially shadowing and
   comparing classified traces.
5. Introduce artifact/source/inspection services with old/new evidence comparison.
6. Migrate resource and lifecycle/execution vertical scenarios after required HSX contracts.
7. Switch CLI and DAP incrementally to the shared frontend port behind the same product
   entrypoint; keep deliberate rollback/oracle lane.
8. Modularize VS Code presentation and build the version-coherent runtime artifact.
9. Run immutable packaged-artifact Windows/Linux/live-executive convergence, then retire each
   legacy surface only at its row-specific exit condition.

## Proposed Refactor dependency changes

The current DAG remains the baseline until Steering accepts these changes:

- RF-002 and RF-003 may proceed in parallel only after shared envelopes/health/recovery
  ownership are frozen, with an early integration Slice.
- RF-005 gains an explicit dependency on RF-004's typed resolver interface.
- RF-006 gains an explicit dependency on RF-005 because source-step internal conditions must
  use owner-safe resources.
- RF-007 remains one parent Refactor but must have separate CLI migration, DAP module, and
  parity/integration Slices with independent review.
- RF-008 consumes the canonical packaged entrypoint and namespaced presentation contract.
- RF-009 remains final convergence; all earlier Refactors still own their fast portable tests.

Steering subsequently accepted/froze the proposal as recorded in issue #38 comment
`5356484309`; current execution authority remains Slice-bounded.

## Resolved first-class portable follow-up

### `DBG-ST-006` technical dependency

`DBG-ST-006` resolved target/image/stream identity, address/ABI, stop token/snapshot, event
cursor, exact step, lifecycle authority, resource provenance, and stable blocked-state target
contracts through the frozen HSX baseline. The first wave consumes current Executive behavior
only through `hsx.python-debug-legacy/1`; target-runtime implementation remains separate.

### Steering choices requested

1. Approve actor/command-queue controller rather than broad-lock or full-async-first.
2. Approve vendored pure-Python debugger distribution plus external Python 3.10+ preflight as
   the initial VSIX model, while preserving a launcher seam for frozen executables.
3. Approve one distribution/version source for CLI and DAP, and move generated VSIX files to
   controlled release artifacts.
4. Until true launch is available, expose attach only; decide later explicit attach/launch
   disconnect/detach defaults rather than inheriting legacy behavior.
5. Treat standard Watch as snapshot evaluation and live executive watch as optional HSX
   capability.
6. Keep standard DAP as the normal VS Code path and retain only additive versioned custom
   views, especially trace.
7. Decide the supported extension/runtime/executive compatibility window; the proposed
   registry defaults to exact extension/runtime coherence and capability-negotiated executive
   behavior.
8. Authorize `DBG-ST-006` as the next coordinated Debugger/HSX Study, or identify an accepted
   equivalent; do not freeze D-002..D-006 or unblock the affected Refactor scopes beforehand.

## Anti-monolith compliance

The proposed Architecture table gives every boundary responsibilities,
non-responsibilities, consumed/exposed contracts, and concurrency ownership. No proposed
component spans transport framing, debugger lifecycle truth, resource reconciliation,
symbol interpretation, and IDE presentation. Controller coordination does not absorb domain
algorithms or transport mechanics.

## Review and stop gate

Fresh independent review `DBG-RVW-001-002-003` reviewed the exact complete proposal at
`89d95de2d944179219a93895f1ab956f2786a232` and returned PASS with no
Blocking/High/Medium findings. The proposal is reviewed, not accepted.

Master will now:

- use the reviewed CurrentIndex, Relations, Ledger, ScrumIterations, and Handoff state;
- post a short decision package with review result, material tradeoffs, unresolved questions,
  and proposed dependency changes to issue #38;
- set status `awaiting_steering_acceptance`;
- stop.

No structural product worker, accepted `DBG-D-*`, or implementation authorization follows
from this reviewed proposal before the required Steering decisions.

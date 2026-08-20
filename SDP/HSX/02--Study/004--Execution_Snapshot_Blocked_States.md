# HSX-ST-004 — Run/Stop Evidence, Snapshots, Exact Stepping, and Blocked States

- Status: COMPLETE FOR MASTER SYNTHESIS
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`
- Evidence baseline: activation head `d135e542b2a959c2ea67e3a1ea65df7e0bcd6baf`

## Question and scope

What portable runtime contract lets a debugger distinguish command acceptance from actual
run-state change, identify why a transition happened, prove that a non-running target is safe
to inspect, retire exactly one instruction, and inspect mailbox-wait or sleep states without
presenting racing live reads as one coherent stop?

This Study owns the portable execution-evidence, inspection-coherence, exact-step, and
blocked-state recommendations needed by `DBG-ST-006`. It does not design debugger source-step
algorithms, assign numeric HSX Requirement/Architecture/Design IDs, change product code, or
define target-specific AVR realization.

## Ownership and cross-Study boundary

| Concern | Owner used by this Study |
|---|---|
| Executive, target and image identity/generation; lifecycle and mutation authority | `HSX-ST-002` |
| Named address spaces, ABI, unwind and variable locations | `HSX-ST-003` |
| Run/stop/block/fault/termination evidence, snapshots, exact retirement and blocked inspection | this Study |
| Event-stream identity, ordering, cursor, ACK, gaps and reconciliation | `HSX-ST-005` |
| Breakpoint/watch identity, ownership, provenance and resource revision | `HSX-ST-006` |
| Debugger stop epochs, source-step plans and frontend presentation | `DBG-D-003`, `DBG-D-004`, `DBG-D-006` |

The runtime supplies target primitives and evidence. The shared Debugger core remains the
semantic owner of source-into, source-over and source-out planning.

## Evidence sources

### Durable coordination and proposed consumer contracts

- `AGENTS.md`, `SDP/README.md`, `SDP/Shared/Process.md`;
- HSX and Debugger `Traceability/CurrentIndex.yaml`;
- issues #47 and #38;
- `DBG-ST-006`, `DBG-ST-003`, and proposed `DBG-D-003`, `DBG-D-004`, `DBG-D-006`.

### Legacy intent and current documentation

- `main/03--Architecture/03.01--VM.md` and `03.02--Executive.md`;
- `main/04--Design/04.01--VM.md`, `04.02--Executive.md`, `04.03--Mailbox.md`,
  `04.09--Debugger.md`, and the source-step material in `04.10--TUI_Debugger.md`;
- `docs/hsx_spec-v2.md` and `docs/executive_protocol.md`.

Legacy documents are provenance, not accepted portable authority. They consistently intend
single-instruction scheduling, explicit wait/sleep states, and debugger inspection, but they
conflict with current code and with one another on VM-versus-Executive breakpoint ownership,
state names, fault handling, and whether a pause is global or per target.

### Current Python oracle, read only

- `platforms/python/host_vm.py`: `MiniVM.step`, debug-stop machinery,
  `VMController.step`, context storage, register/memory reads, wait/wake/timeout, pause/resume,
  and debug run;
- `python/execd.py`: `TaskState`, transition validation, pending reasons, refresh/inference,
  pre/post breakpoints, sleep and mailbox transitions, inspection calls, exact/manual/source
  stepping, and VM-event processing;
- `python/vmclient.py`: individual register, memory, code and step RPCs;
- targeted debugger, scheduler, mailbox, session, fault, stack-guard and exit tests.

## Verification evidence

The worker ran the current oracle with bytecode and pytest cache disabled:

```text
$env:PYTHONDONTWRITEBYTECODE='1'
& 'c:/Users/hanse/miniconda3/python.exe' -m pytest -p no:cacheprovider python/tests/test_debugger_basic.py python/tests/test_vm_pause.py python/tests/test_scheduler_state_machine.py python/tests/test_mailbox_wait.py python/tests/test_mailbox_svc_runtime.py python/tests/test_executive_sessions.py -q

99 passed in 0.39s
```

```text
$env:PYTHONDONTWRITEBYTECODE='1'
& 'c:/Users/hanse/miniconda3/python.exe' -m pytest -p no:cacheprovider python/tests/test_vm_mem_oob.py python/tests/test_svc_invalid.py python/tests/test_stack_guard.py python/tests/test_vm_exit.py -q

7 passed in 0.11s
```

These suites prove important behavior on ordinary paths: one scheduler call per selected
instruction, round-robin accounting, manual re-pause, breakpoint/BRK/async-break stops,
mailbox wait/wake/timeout register restoration, state-event reason examples, source-only
compiler-instruction skipping, and several fault/exit paths. They do not prove causal command
identity, exact retired count on every exceptional path, snapshot atomicity, stale-read
rejection, or blocked-state inspection stability.

## Current implementation findings

### Strong oracle behavior worth preserving

1. `MiniVM.step()` is an instruction-boundary primitive. Normal instructions increment the
   VM and per-context accounted-step counters once; BRK advances the PC, increments the
   counters, then produces a debug stop.
2. `VMController.step()` selects one runnable PID at a time and calls `MiniVM.step()` once per
   scheduler turn. `test_round_robin_single_instruction` proves two tasks each receive two
   turns for a four-step normal-path budget.
3. A targeted debug step can run one instruction and halt with a `step` event. A breakpoint
   at the origin can be skipped without removing it from the breakpoint set.
4. The Executive validates a useful task-state vocabulary: READY, RUNNING, WAIT_MBX,
   SLEEPING, PAUSED, RETURNED, TERMINATED and KILLED.
5. Mailbox block captures task context and wait metadata; wake/timeout restores completion
   registers and memory before making the task READY. Sleep and mailbox deadlines use
   monotonic time.
6. Stack walking and local inspection already return partial results and diagnostics rather
   than requiring every frame/read to succeed. This is useful compatibility evidence for
   snapshot-bound inspection.

### Behavior that is not a portable contract

| Area | Current evidence | Contract gap |
|---|---|---|
| Command acknowledgement | Pause/resume/kill/step RPCs synchronously mutate and often refresh before returning. | No operation/causality token separates accepted request, completed effect and observed state. A lost response cannot be reconciled by command identity. |
| State and cause | `task_state_pending` stores one overwriteable reason; `_refresh_tasks` consumes it or infers a reason from old/new strings. | No target generation, transition revision or causal identity. The reason can be annotation/inference rather than authoritative transition evidence. |
| Stable stop | `paused`, `waiting_mbx`, `sleeping` and `returned` appear in snapshots/events. | No stop token or proof that every inspection-visible source is frozen. A state label alone is not a stable stop. |
| Inspection | Registers, memory, stack, locals and disassembly are separate RPCs. Current-target reads may be live; inactive-target reads use stored state. | No atomic bundle, immutable snapshot, expected revision, coverage descriptor or stale rejection. Stack/disassembly already compose multiple reads that can cross a mutation. |
| Paused mutation | A paused task is excluded from the runnable set. Other RPCs can still write registers/memory, and session ownership is not an inspection revision. | Even PAUSED needs serialized mutation ownership plus snapshot/revision evidence before multi-read coherence can be claimed. |
| Exact count | `VMController.step()` increments its `executed` result after every call to `MiniVM.step()`. | Pre-instruction async debug stop and several fault returns can report an attempted loop iteration as executed although `MiniVM.steps` did not advance. Current `executed` is not a portable retired-instruction count on all outcomes. |
| Faults | PC out of range emits `vm_error` and `debug_stop`; other memory/stack/divide/SVC/illegal-op paths stop or return using different combinations of register status, events and state. `execd` logs `vm_error`. | There is no normalized fault envelope, fault-versus-terminal state rule, or causal relation to step completion. |
| Breakpoints | Executive pre/post address checks coexist with VM debug breakpoint checks. Debug-state stepping can ignore Executive checks, while VM checks remain. | No single precedence owner. Duplicate stops and divergent PC/phase meaning are possible. |
| One-shot bypass | `debug_skip_bp_once` is an address masked to 16 bits; resume/debug-run derives it from a prior stop PC. | It is not bound to target generation, stop token, operation or resource revision. If the next dispatch is at another PC, the skip value can survive and later match accidentally. |
| Source stepping | `source_only` repeatedly exact-steps while the last instruction metadata says `source_kind=compiler`; DAP into/over/out share the same path. | This is a useful heuristic oracle, not portable source-step semantics. It lacks origin frame/location, distinct step kind, bounded typed outcome and preemption evidence. |
| Mailbox wait | Send, timeout and manager events can call `_complete_mailbox_wait`, write buffer/register results and move the task READY. | A wait label and saved context do not freeze a live view. Wake can happen between any two inspection reads. |
| Sleep | Deadline processing can move SLEEPING to READY independently of debugger reads. | No stable inspection epoch or wake barrier exists. |
| Terminal evidence | RETURNED carries an exit status in some paths; kill removes task state and later produces a synthesized terminated event. | Final context retention, exit/fault/killed distinction and optional final snapshot are not one contract. |

The protocol documentation overstates several current behaviors. It describes precise step
retirement and coherent task snapshots, but current APIs do not expose a revision. It also
describes task-state events as transition truth even though current reasons can be pending
command annotations or inference. Those descriptions remain intent, not proof.

## Recommended portable contract model

### Four records that must remain separate

1. **ExecutionCommandReceipt** — proves only that a command was accepted or rejected. It
   carries the exact `TargetRef`/`AttachmentRef` from `HSX-ST-002`, a caller or runtime
   operation token, command kind,
   origin precondition/revision, and acceptance status. An accepted receipt must not itself
   assert RUNNING, STOPPED or step completion.
2. **ExecutionState** — the current runtime state, independent of why it was entered. At
   minimum it distinguishes runnable/running, blocked with typed block kind, inspection-stable
   stopped, terminal, and unavailable/unknown reconciliation state. Loading/ready and more
   detailed scheduler states may remain profile fields.
3. **ExecutionTransitionEvidence** — an authoritative old-state/new-state transition carrying
   target generation, monotonic transition revision, inspection revision, typed cause,
   optional causal operation/resource token, and structured PC/block/fault/exit details.
4. **StableStopEvidence** — the subset of transition/current-state evidence that proves an
   inspection-stable view. It carries an opaque stop token and either an immutable snapshot
   token or a revision-validation contract with declared coverage.

A synchronous RPC may return a command receipt and completion evidence together, but they
remain separate fields with separate meanings. The identical completion evidence must be
deduplicable against an event copy. Loss of either RPC or event is resolved from target-local
revision/current-state queries and the event-gap rules owned by `HSX-ST-005`, never from time
windows or PC equality.

### Identity and revision dimensions

This Study recommends the following descriptive values for Master synthesis:

| Value | Scope and rule |
|---|---|
| Target/image reference | Exact `TargetRef` and `LoadedImageRef` imported from `HSX-ST-002`; every receipt, transition, stop, snapshot and step result is bound to them as applicable. |
| Operation token | Opaque collision-resistant identity within the relevant runtime-instance/target generation; correlates request acceptance, completion, rejection or unknown outcome and follows the operation-ID serialization rules from `HSX-ST-002`. |
| Transition revision | Monotonic within one target generation; advances for every authoritative execution-state transition, including block, wake, fault and terminal transition. |
| Inspection revision | Monotonic within one target generation; advances for every snapshot-visible mutation: instruction commit, wake completion writes, debugger register/memory writes, restore, or equivalent mutation. It may advance without a state transition. |
| Stop token | Opaque identity for one current inspection-stable non-running state. A different stop receives a different token even if PC and cause repeat. |
| Snapshot token | Opaque identity for one immutable captured view, with coverage and lifetime. It may outlive the current stop only under an explicit retention rule. |

Transition and inspection revisions follow the unsigned monotonic 64-bit and JSON-safe string
serialization rules proposed by `HSX-ST-002`. They must not wrap silently; the producer starts
a new runtime/target generation before exhaustion. Timestamps are diagnostic only and never
establish ordering or duplicate identity.

Every transition/state query returns the current target generation and both relevant
revisions. A mutation command uses compare-and-set preconditions where safety requires it.
An accepted run/step effect invalidates the current live stop token before execution can
mutate the target. An immutable already-captured snapshot may remain readable until its
declared expiry; no new request may silently reinterpret an expired stop as the latest stop.

### Stable-stop invariants

A runtime may label evidence inspection-stable only when all of the following hold:

1. the target is excluded from instruction execution for that stop token;
2. every mutation source covered by the snapshot is either prevented, serialized against the
   stop, or represented by an immutable atomic capture;
3. register, PC, stack/context and declared memory-space coverage are explicit;
4. debugger writes, wake completion, restore, lifecycle change and run/step acceptance
   invalidate or advance the relevant revision atomically;
5. reads require target generation plus stop/snapshot token and never default to “current”;
6. a stale token produces a typed failure rather than cached/latest data;
7. terminal removal and target loss never reuse a prior live stop token.

Immutable code may be read by image identity instead of copied into each snapshot. Resource
lists, mailbox queue contents and other Executive services are outside a task inspection
snapshot unless the snapshot coverage explicitly names them.

## Snapshot alternatives and decision

| Alternative | Semantics | Strengths | Decision |
|---|---|---|---|
| Atomic immutable snapshot token | Runtime atomically captures declared state and serves all reads by token. | Strongest coherence; safe across wake/resume; simple stale semantics. Costs copy/storage or copy-on-write support. | Recommended full-profile contract. |
| Revision-pinned live reads | Each read supplies target generation, stop token and expected inspection revision; runtime rejects if any differ before/during the read. A batch is accepted only when every result reports the same revision. | Avoids full copy while a stop can truly prevent mutation. | Accepted full-profile alternative for genuinely frozen paused/fault stops. Not sufficient for naturally waking states without a transition barrier. |
| Bracketed revision validation | Read revision, perform bounded individual reads, read revision again, accept only if unchanged; otherwise discard and retry within a declared bound. | Migration path when per-read conditional checks are unavailable. | Named degraded mode only. Must return `snapshot_changed` after bounded retry; cannot claim atomic capture. |
| Unversioned sequential reads | Read current registers/memory/stack independently. | Matches current legacy behavior. | Best-effort diagnostic mode only; never satisfies coherent stop-snapshot requirements. |
| Temporarily hold every blocked wake | Freeze timer/mailbox completion during inspection. | Can make live reads stable. | Not the default recommendation because debugger observation changes task timing/IPC behavior. May exist as an explicit intrusive capability/policy. |

The snapshot descriptor must report its coherence grade, target/image generation, stop token,
inspection revision, covered address spaces/ranges and register/context sets, creation point,
retention/expiry, and whether reads remain valid after the target resumes.

Required typed failures include, by descriptive meaning rather than fixed wire spelling:

- stale target generation;
- stale stop token;
- snapshot changed, including expected and observed revision;
- snapshot expired or released;
- requested domain/range not covered;
- inspection unavailable in the current state/profile;
- target unavailable or terminal without retained final snapshot.

No failure may fall back to another target, newer stop, top frame, cached registers or current
memory.

## Blocked-state inspection decision

WAIT_MBX and SLEEPING are **not inherently inspection-stable**. They are scheduler states, not
snapshot guarantees. Current Python wait/sleep paths can wake and mutate state independently
of debugger reads.

| Runtime state | Natural mutation source | Portable live-read stability | Full-profile treatment |
|---|---|---|---|
| Debug pause / breakpoint / completed exact step | Resume/step, debugger writes, lifecycle commands | Stable only with serialized mutation authority and revision/token rules | May establish a stop token and immutable or revision-pinned snapshot. |
| READY but not currently selected | Scheduler selection may occur immediately | Not stable | Pause/capture explicitly; do not treat scheduler inactivity as a stop. |
| WAIT_MBX, infinite timeout | Any successful sender can complete the wait and write result registers/buffer | Not stable by state alone | Optional atomic blocked-transition snapshot capability; otherwise state notification only. |
| WAIT_MBX, finite timeout | Sender or monotonic deadline can complete the wait | Not stable by state alone | Same as above; snapshot records wait metadata and the pre-wake view. |
| SLEEPING | Deadline or external lifecycle/pause action | Not stable by state alone | Optional atomic blocked-transition snapshot; otherwise state notification only. |
| Parked recoverable fault | Runtime policy/debugger write/resume | Potentially stable if explicitly parked and retained | May establish a stop token only when fault evidence declares stable retention. |
| RETURNED pending cleanup | Cleanup/removal | Not a reusable live stop by default | Optional immutable final snapshot with explicit retention; terminal evidence remains authoritative. |
| TERMINATED/KILLED/target lost | No live target state | No live inspection | Terminal evidence plus optional retained final snapshot; never silently use old live data. |

The recommended optional blocked-snapshot primitive atomically captures context after the
blocking instruction commits and before wake completion can mutate the task. It declares
coverage and a transition revision. If the target wakes before the debugger accepts the
blocked stop, the immutable capture may remain historical evidence, but it must not be
presented as the target's current stopped state. A current blocked stop epoch is valid only
while current-state/revision evidence still identifies that blocked transition.

Profiles that cannot capture this boundary expose WAIT_MBX/SLEEPING as runtime-state events
with wait kind/deadline metadata only. The Debugger may display them but must not create frame,
scope, variable or memory handles claiming coherent blocked inspection.

## Exact one-instruction contract

### Request and outcome

An exact-step request is valid only for the current target generation, mutation owner, and
inspection-stable origin stop token. It requests **at most one architecturally committed guest
instruction** for one target/PID.

The authoritative outcome reports:

- operation token and origin stop token;
- target/image generation and before/after transition and inspection revisions;
- before PC and after PC in the typed code address space from `HSX-ST-003`;
- `retired_count`, restricted to `0` or `1`;
- final execution state and primary transition/stop cause;
- fault/trap/block/exit details and any independently effective breakpoint/resource evidence;
- a new stop/snapshot token when the final state is inspection-stable;
- explicit target-lost/unknown completion when continuity cannot be proven.

Normal exact-step completion requires `retired_count = 1`. A pre-dispatch pause, stale
precondition, non-bypassed origin breakpoint, target loss or other stop before commit reports
zero. Faulting-instruction retirement is defined by the accepted ISA/fault contract and must
be reported, not guessed from loop attempts. BRK is currently a useful oracle for a retired
guest trap instruction; portable fault/trap fixtures must freeze each class explicitly.

An SVC that commits and then blocks may complete the exact step with `retired_count = 1` and
final state WAIT_MBX or SLEEPING. That is plan preemption by the real block cause, not normal
step-completion relabeling.

### Origin-breakpoint bypass

The recommended bypass is an opaque, one-use run-control authorization bound to:

- target generation and exact origin stop token;
- origin typed PC;
- the effective breakpoint/resource revision that produced the stop;
- the exact-step or continue operation token.

It bypasses the already-observed Executive breakpoint gate at that origin boundary once. It
does not remove, disable or change ownership of any breakpoint; does not suppress a BRK guest
instruction at the same PC; does not suppress a breakpoint at the destination; and cannot
survive a PC, target-generation, stop-token or resource-revision mismatch. It is consumed on
the first dispatch attempt whether or not the instruction commits, preventing a stale skip
from matching a later loop back to the same address.

Where multiple logical breakpoints share the origin, the stop token/resource revision binds
the effective set. A new or changed breakpoint makes the request stale and requires
reconciliation through `HSX-ST-006`; the runtime must not guess which owner may be bypassed.

### Stop-condition classification and precedence

The runtime linearizes control requests and instruction boundaries, reports one primary cause,
and may report secondary contributing conditions. The primary classification follows these
phases:

1. reject stale identity/stop/authority/resource preconditions without execution;
2. before dispatch, report an already-linearized target terminal/loss, user pause/async break,
   or non-bypassed origin breakpoint with `retired_count = 0`;
3. if an instruction is attempted, its architectural outcome wins: fault/exception, guest
   BRK/trap, return/termination, mailbox wait or sleep are never relabeled as step completion;
4. after an otherwise normal commit, an independently owned breakpoint/watchpoint at the new
   boundary wins over requested step completion; a user pause linearized at that boundary is
   retained as its real cause and order;
5. only when no independent condition preempts does the primary cause become exact-step
   completion.

Target loss discovered by reconciliation yields unavailable/unknown outcome unless terminal
evidence is independently proven. Timing proximity is never precedence. The same target
generation plus operation/transition/stop identities deduplicate response and event copies.

## Source-step prerequisites, with Debugger ownership preserved

HSX must provide only the primitives/evidence needed by the shared Debugger planner:

- exact one-instruction request/outcome above;
- continue/pause and cancellation with operation correlation;
- stable target/image/address identity (`HSX-ST-002`/`HSX-ST-003`);
- coherent snapshot/stop evidence and explicit stale/unavailable outcomes;
- accepted ABI/unwind/location semantics and partial diagnostics (`HSX-ST-003`);
- owner/provenance/revision-safe temporary conditions and user resources (`HSX-ST-006`);
- ordered/gap-aware events and state reconciliation (`HSX-ST-005`);
- typed fault, block, terminal and independent breakpoint causes with deterministic precedence.

HSX does not define “next source line”, frame equivalence, recursion handling, into/over/out
completion, compiler-generated instruction policy, or step-plan budgets. Those remain one
frontend-neutral Debugger-core algorithm. An optional optimized runtime step-plan primitive is
conforming only if it returns the same exact evidence/preemption contract and is capability
negotiated; it cannot replace the semantic owner.

## Capability and degraded-profile proposal

The following names are synthesis candidates, not already implemented protocol claims:

| Capability/profile | Minimum semantics |
|---|---|
| `exec.evidence/1` | Separate receipts/state/transition causes; target generation; operation token; monotonic transition and inspection revisions; normalized fault/terminal evidence. |
| `exec.exact-step/1` | At-most-one committed instruction; authoritative `retired_count` 0/1; before/after PC/revisions; real preemption cause. |
| `exec.origin-breakpoint-bypass/1` | Stop-token/resource-revision-bound one-use origin gate bypass with no resource mutation. |
| `inspect.snapshot/1` | Atomic immutable snapshot token, explicit coverage/coherence/lifetime, token-bound reads and stale/expired errors. |
| `inspect.revision-pinned/1` | Frozen-stop conditional reads using expected stop token and inspection revision; same-revision batch validation. |
| `inspect.blocked-snapshot/1` | Atomic after-block/before-wake capture for declared WAIT_MBX/SLEEPING states and coverage. |
| `inspect.final-snapshot/1` | Optional immutable retained snapshot attached to terminal/fault evidence with explicit retention. |
| `portable-debug/full-v1` | Named profile containing `exec.evidence/1`, `exec.exact-step/1`, origin bypass and at least one full coherent inspection mechanism; blocked/final snapshots remain explicitly advertised options. |
| `python-legacy-debug/v1` | Named migration profile: no target-local revisions/snapshot tokens; sequential inspection is `best_effort`; blocked states are notification-only; exceptional `executed` is not accepted as exact retired count without counter comparison; address-only bypass is not full conformance. |

Capability selection must be explicit through the negotiation contract coordinated by
`HSX-ST-005`; absence means unsupported, not a guessed older version. A degraded adapter must
label every result with its coherence grade, bound retries, surface unavailable exact-step
outcomes when retirement cannot be proven, and carry tracked removal criteria. It must not
open a full Debugger stop epoch from unversioned blocked-state reads.

## Conformance fixtures required by Master synthesis

### Receipts, transitions and recovery

1. Accepted pause/continue/step receipt arrives before, after, or together with transition
   evidence; state changes only from evidence/reconciliation.
2. Rejected command has no transition; duplicated operation token is idempotently classified.
3. RPC response or event copy is lost; current-state query and event cursor recover the same
   target generation/revision/cause without duplicate stop.
4. Repeated same-PC/same-reason stops receive different stop tokens and revisions.
5. Exit, explicit kill, recoverable fault, fatal fault and target loss remain distinct.

### Snapshot consistency and stale behavior

1. Registers, stack, locals, memory and disassembly all report one snapshot/revision.
2. Inject mutation between reads; immutable snapshot remains unchanged, revision-pinned mode
   rejects, bracketed mode discards/retries, and legacy mode reports `best_effort`.
3. Resume, debugger write, image/target-generation change and uncertain recovery invalidate the
   live stop; old handles never bind to the new stop.
4. Paged/repeated reads within one immutable snapshot remain stable until explicit expiry.
5. Partial memory/unwind coverage returns data plus typed diagnostics rather than fabricated
   values or a fallback current frame.

### Exact step and precedence

1. Normal ALU, branch, call and return instruction outcomes prove `retired_count = 1` and
   exact before/after PC.
2. Origin breakpoint is bypassed once without resource mutation; loop-back hits it again.
3. BRK at the origin executes despite origin-gate bypass and reports BRK, not normal step.
4. Destination user breakpoint preempts step completion and retains all matching resource
   provenance.
5. Pre-dispatch async pause retires zero; pause after commit is ordered at the boundary.
6. Memory/stack/divide/illegal-op faults and PC out of range report defined retirement,
   structured fault evidence and stopped-versus-terminal state.
7. SVC wait, sleep, return and explicit termination retain their real cause and count.
8. Target/resource generation change between stop and step rejects stale preconditions.

### Blocked states

1. WAIT_MBX wake by sender races capture/read; only the atomic blocked snapshot is accepted.
2. WAIT_MBX timeout races sender delivery; one ordered transition wins and the other cannot
   mutate the accepted snapshot.
3. SLEEPING deadline passes during inspection; immutable mode remains historical, live
   revision mode rejects, and notification-only mode opens no coherent epoch.
4. Infinite wait is still shown to be externally wakeable and not assumed stable.
5. A blocked target already READY/RUNNING when its event is consumed is not presented as a
   current blocked stop.

### Debugger-owned source plan prerequisites

Fixtures must combine exact step, mapped/unmapped instructions, partial unwind, recursive
frames, user breakpoint collision, block/fault/termination preemption, event gap and bounded
plan exhaustion. The expected source-plan result belongs to Debugger verification; HSX
fixtures prove only the primitive evidence delivered to that planner.

## Traceability to Debugger contracts

| Consumer | Portable input supplied by this Study | Remaining dependency |
|---|---|---|
| `DBG-ST-006` questions 3, 5, 7 and 10 | Authoritative causal execution evidence, coherent snapshots/stale behavior, exact step/bypass/precedence, blocked-state stability decision | Master allocates stable HSX Requirement/Architecture/Design IDs and cross-track relations after synthesis/review. |
| `DBG-D-003` | Target-generation-bound transition/inspection revisions, stop token, snapshot token/coherence/lifetime and invalidation rules | Identity from `HSX-ST-002`; addresses from `HSX-ST-003`; event recovery from `HSX-ST-005`. |
| `DBG-D-004` | Same-snapshot register/memory/stack/local/disassembly reads, coverage, partial/unavailable and stale outcomes | ABI/unwind/location semantics from `HSX-ST-003`; artifact/image binding from sibling synthesis. |
| `DBG-D-006` | Separate command receipt and authoritative completion, exact retired count, real state/cause, one-shot bypass, deterministic preemption | Lifecycle authority from `HSX-ST-002`; event ordering from `HSX-ST-005`; resource ownership/revision from `HSX-ST-006`. |
| `DBG-D-005` interaction | Step conditions and origin bypass consume resource revision/provenance without mutating breakpoint ownership | Full remote resource contract remains `HSX-ST-006`. |
| `DBG-D-002` interaction | Gateway must preserve receipt/evidence identity and expose degraded coherence, not flatten them into one response flag | Stream continuity, gap and negotiated-profile transport remain `HSX-ST-005`. |

## Conclusions and recommendations for Master synthesis

1. Preserve the current normal-path single-instruction oracle, but do not equate controller
   loop attempts or the current `executed` field with portable retired count on exceptional
   paths.
2. Freeze a four-part execution model: command receipt, orthogonal state, causal transition
   evidence, and stable-stop evidence.
3. Use target-local transition and inspection revisions plus opaque operation/stop/snapshot
   tokens. Time and `(reason, pc)` are never identity.
4. Prefer atomic immutable snapshots. Allow revision-pinned frozen-stop reads as a full
   alternative and bracketed revision validation only as named degraded migration behavior.
5. Treat WAIT_MBX and SLEEPING as notification-only unless an explicit atomic blocked-snapshot
   capability is negotiated. Infinite mailbox wait is still externally mutable.
6. Define exact step as at most one architecturally committed instruction with `retired_count`
   0/1, typed outcome, and a stop-token/resource-revision-bound origin breakpoint bypass.
7. Architectural fault/trap/block/terminal outcomes and independently owned stop conditions
   retain their real causes; step completion is the fallback only when nothing preempts it.
8. Keep source into/over/out algorithms in the shared Debugger core. HSX supplies exact
   primitives, snapshots, unwind/address inputs, resources and ordered evidence.
9. Require named negotiated capability profiles. Current Python behavior is a degraded oracle,
   not silent full conformance.

## Open synthesis questions

1. The accepted ISA/fault work must specify retirement for each synchronous fault/trap class;
   this Study requires the exact result but does not silently settle every opcode case.
2. Master/Steering must decide whether blocked snapshots are mandatory in the initial full
   portable profile or an optional capability. This Study recommends optional capability with
   notification-only fallback.
3. Snapshot retention limits and whether already-issued reads may finish after resume require
   an implementation-independent lifetime policy and resource-budget review.
4. Master should preserve `HSX-ST-002`'s proposed opaque-ID and unsigned 64-bit revision
   widths; the exact field/capability spelling belongs in the synthesized portable Design after
   `HSX-ST-003` and `HSX-ST-005` align their serialization and continuity conclusions.
5. A future optimized runtime source-step primitive may be studied separately only after the
   Debugger semantic contract is frozen; it is not needed to complete this dependency.

## Completion limit

This Study is **COMPLETE FOR MASTER SYNTHESIS**. It provides evidence and descriptive contract
recommendations, not accepted portable requirements/designs. No numeric HSX
Requirement/Architecture/Design IDs were allocated. No `DBG-D-*` is frozen, and no Debugger,
runtime, native/AVR or product implementation is authorized.

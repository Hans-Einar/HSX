# HSX-ST-005 — Event Stream Cursor, ACK, Gaps, and Capability Profiles

- Status: **COMPLETE FOR MASTER SYNTHESIS**
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`
- Evidence baseline: `d135e542b2a959c2ea67e3a1ea65df7e0bcd6baf`
- Scope guard: Study/contract proposal only; no product, Debugger Refactor, or AVR authority

## Question and bounded scope

What portable HSX contract lets a debugger consume one ordered executive event history,
prove whether a cursor still belongs to that history, acknowledge only evidence it has
successfully applied, detect loss and half-open streams, and recover either by contiguous
resume or an explicit full-reconciliation barrier?

This Study covers:

- event-stream identity and generation as consumed from `HSX-ST-002`;
- canonical event sequence, subscription delivery cursor, filters, ordering and duplicates;
- cumulative ACK-after-apply, bounded queues, back-pressure, drops, gaps and `seq_evicted`;
- resume versus full reconciliation and the required cross-domain baseline cursor;
- stream liveness/health evidence and malformed, half-open or uncertain-delivery outcomes;
- explicit current/degraded capability profiles, capability versioning and removal criteria;
- portable conformance fixtures required by `DBG-ST-006` and proposed `DBG-D-002`.

It does not define target/run-stop causes or snapshot contents (`HSX-ST-004`), target and
session ownership (`HSX-ST-002`), breakpoint/watch resource meaning (`HSX-ST-006`), Debugger
reducer policy, an AVR buffer size, or a transport-specific binary representation. Sequence
and cursor mechanics carry those domains' evidence; they do not create it.

## Authority and method

The evidence classes remain separate:

1. **Current implementation** is observable Python behavior at the evidence baseline. It is
   a regression oracle, not portable authority.
2. **Documented intent** is the protocol and legacy architecture/design text. It is useful
   provenance, but several promises are not implemented or are internally inconsistent.
3. **Recommended target contract** is this Study's input to Master synthesis. Numeric
   `HSX-R-*`, `HSX-A-*`, and `HSX-D-*` IDs are intentionally not allocated here.

Where current behavior and text conflict, this Study does not choose either implicitly. It
recommends typed, capability-negotiated semantics that can be implemented by the Python
reference and other targets and verified by the same fixtures.

## Evidence sources

### SDP and Steering inputs

- `AGENTS.md`, `SDP/README.md`, and `SDP/Shared/Process.md`;
- both active `Traceability/CurrentIndex.yaml` files and the active Handoff;
- `HSX-ST-001`, `HSX-ST-002`, `DBG-ST-002`, and `DBG-ST-006`;
- proposed `DBG-D-001..DBG-D-006` and the accepted target architecture direction;
- issues #47 and #38, including Steering comments `5348192567` and `5348190806`.

### Legacy intent and current protocol

- `main/02--Study/02.01--Requirements.md` (`DR-8.1`, `DG-5.2`, `DG-8.2`);
- `main/03--Architecture/03.02--Executive.md`;
- `main/04--Design/04.02--Executive.md`, `04.09--Debugger.md`, and
  `_archive_old/04.02--Executive_old.md`;
- `main/05--Implementation/shared/executive_protocol.md` and the Executive/Toolkit
  implementation and test notes;
- `docs/executive_protocol.md`, especially Debugger Sessions & Event Streaming and
  Back-pressure & errors;
- `docs/resource_budgets.md` as target-budget provenance only.

### Current code and tests

- `python/execd.py`: `SessionRecord`, `EventSubscription`, event history/broadcast,
  subscribe/ACK/metrics, session pruning and stream handler;
- `python/executive_session.py`: negotiation, RPC retry, keepalive, stream handshake,
  background read/callback/ACK and cleanup;
- `python/hsx_dbg/backend.py`, `python/hsx_dbg/context.py`, `python/blinkenlights.py`, and
  `python/hsx_dap/__init__.py` as current consumers;
- `python/tests/test_executive_sessions.py` and
  `python/tests/test_executive_session_helpers.py`.

Focused read-only evidence:

```text
c:/Users/hanse/miniconda3/python.exe -m pytest \
  python/tests/test_executive_sessions.py \
  python/tests/test_executive_session_helpers.py -q

77 passed in 0.79s
```

The run proves the existing session/basic event, queue-warning, metrics, stream-establishment
and RPC-retry oracles still pass. It does not cover safe resume, eviction, filtered cursor
continuity, concurrent publish ordering, ACK-after-apply, malformed/EOF/half-open health, or
full reconciliation.

## Terminology and ownership boundaries

| Term | Meaning | Explicit non-meaning |
|---|---|---|
| Executive incarnation | Identity domain supplied by `HSX-ST-002` | Endpoint, process name or protocol version |
| Event stream | One canonical sequence/history namespace within an exact executive incarnation | One TCP connection, session or subscription |
| Stream generation | Fence for reset/replacement of sequence or retained-history semantics | A reconnect attempt counter |
| Canonical event sequence | Total commit order within one stream generation | Wall-clock order, delivery count or target state revision |
| Subscription | One session-scoped delivery selection and queue | The canonical history itself |
| Delivery cursor | Scoped proof of how far one selection has been processed | A bare integer safe across restart or filter changes |
| Applied cursor | Highest contiguous delivery cursor the consumer successfully reduced or deliberately classified | Highest parsed, buffered, callback-attempted or merely received sequence |
| ACK cursor | Cumulative applied cursor reported to the producer | Permission to hide a gap or claim controller application |
| Gap | Explicit proof that part of the required cursor chain is unavailable | Every numeric skip caused by a subscriber filter |
| Checkpoint | A no-target-mutation stream frame that advances/proves cursor chain and liveness | A `ps` poll or fabricated run-state event |

Event sequence, run/stop state revision and resource revision are separate monotonic domains.
An event may carry the latter revisions and a causal transition/operation reference; equality
of event sequence alone never proves two stop/resource events are duplicates.

## Findings — documented intent

The legacy/current documents intend a useful system:

- events have monotonically increasing `seq`, timestamp, category, PID and data;
- sessions negotiate event features and a bounded `max_events` queue;
- `events.ack` advances a processed cursor and enables reclamation;
- `since_seq` resumes after transient disconnect;
- retention/back-pressure produces warning/drop evidence;
- an evicted resume request returns `seq_evicted` so the client performs a full refresh;
- owner and observer subscribers coexist, with slow observers not harming owners;
- invalid categories are rejected and unknown future event fields are tolerated.

But the text is not one coherent contract:

- `docs/executive_protocol.md` names both 256 and 512 as the default event depth;
- one section says overflow drops oldest immediately, another says delivery first stalls;
- warnings use `reason: backpressure` in one place and `event_dropped`, `slow_consumer` or
  `slow_consumer_drop` elsewhere;
- the documented drop field is alternately `data.seq`, first missing sequence, or unspecified;
- some examples ACK `seq`, others use `subscription_id` plus `last_seq`;
- filters share a global event sequence, but no document says whether numeric skips from
  filtered-out events are gaps;
- retention is described as time-based and ACK-based without a precise earliest-retained
  boundary or capacity result;
- session keepalive is described, but no same-stream idle checkpoint/read deadline proves the
  receive path is alive;
- `since_seq` lacks executive/stream identity, so the same integer after restart is ambiguous.

These contradictions make protocol-version or simple feature-string inference unsafe.

## Findings — current Python implementation

### Documented versus implemented matrix

| Concern | Documented intent | Current evidence | Classification |
|---|---|---|---|
| Stream identity | Resume in one monotonic history | `event_seq` begins at 1 in each `ExecutiveState`; envelopes carry no executive/stream identity | Missing; repeated sequence after restart is ambiguous |
| Publish order | Monotonic sequence is event order | `_next_event_seq`, history append and broadcast are separate critical sections; concurrent emitters can allocate A before B but store/deliver B before A | Total order not proven |
| Sequence width | `uint64` | Python integer grows without wire bound/exhaustion rule | Observable but not a portable width contract |
| History model | Stored once, reclaimed after subscribers ACK or retention expires | Global `deque(maxlen=4096)` plus per-subscription queues; ACK does not reclaim global history | Different model |
| Retention | Default 5 s | `event_retention_ms=5000` is advertised, but no time eviction uses it | Advertised-only value |
| Resume | `since_seq` replays retained events | Server accepts a non-negative integer and replays whatever remains with `seq > since_seq` | Partial implementation without continuity proof |
| Evicted resume | Error `seq_evicted` | No comparison with earliest retained sequence; subscribe succeeds with a truncated/empty replay | Not implemented |
| Future cursor | Reject invalid/ahead request | Any non-negative `since_seq`, including beyond current sequence, is accepted | Not implemented |
| Filters | Unsupported categories error; filtered subscription | Category strings are accepted without validation; matching events only are enqueued | Validation missing; numeric skips are ambiguous |
| ACK meaning | Highest processed sequence | Server accepts any non-negative sequence, including beyond delivered, and takes `max(last_ack, seq)` | ACK can falsely cross undelivered/unapplied evidence |
| Queue overflow | Explicit drop/gap evidence | Oldest queue item is popped and `last_ack` is advanced automatically; a session warning is enqueued | Loss is mislabeled as acknowledgement |
| Drop warning | First missing range/cursor | Warning carries one `dropped_seq`; warning insertion can displace another queue item without recording that second interval | Incomplete/non-contiguous loss evidence |
| Pending metric | Delivered but unacknowledged event count | `delivered_seq - last_ack` uses global sequence distance, so filters and session-only warning sequences inflate it; delivered queue items are already popped | Metric is not an event count |
| Back-pressure | Bounded backlog, explicit owner/observer policy | Thresholds use the sequence-distance metric; all subscriptions follow the same logic; no owner preference | Intent not implemented as documented |
| Client resume | Reconnect from last processed sequence | `ExecutiveSession.start_event_stream` passes caller filters only; it stores no applied cursor and automatically supplies no `since_seq` | Not consumed |
| ACK-after-apply | ACK after client processing | Event is buffered, callback is attempted, exceptions are swallowed, then the sequence contributes to ACK | Callback failure can still be ACKed |
| ACK failure | Observable/recoverable | ACK exceptions are swallowed and pending count is reset in `finally` | Health/cursor uncertainty hidden |
| Malformed frame | Protocol/health failure | Event JSON decode error is silently skipped | A possible gap is hidden |
| EOF/socket loss | Stream health transition | Worker clears its internal stream reference; adapter `_event_stream_active` can remain true | Health not propagated |
| Half-open idle stream | Liveness evidence/read deadline | Socket is switched to blocking mode; session keepalive uses separate RPC sockets | Receive direction can remain silently half-open |
| Keepalive failure | Session-health evidence | Keepalive worker swallows failure and retries later | Ownership/session uncertainty hidden |
| Reconnect policy | Explicit recovery/reconcile | RPC helper can discard/reopen sessions and retry; DAP adds its own reconnect/reapply policy; event stream is not resumed | Competing hidden recovery |

### Additional correctness observations

1. Subscriber queues are popped by `events_next` when the socket writer takes an event, before
   any client ACK. ACK therefore does not free that queue entry; it only changes logical
   counters and removes any entries still waiting whose sequence is low enough.
2. Session-specific warning events allocate from the global `event_seq` but are not stored in
   global history. Other subscribers will observe a numeric skip that is neither a filtered
   canonical event nor replayable history.
3. A filtered subscription can receive event sequence 10 then 100 with perfect delivery. A
   client cannot infer whether 11..99 were filtered or lost. Conversely the current `pending`
   metric treats them as 90 pending events.
4. The TCP stream is ordered while connected, but clean EOF, reset, silent server handler
   exception and JSON corruption all converge on no typed health evidence for the consumer.
5. Tests cover basic queue/drop warnings and ACK metrics, but no test asserts `since_seq`,
   `seq_evicted`, invalid categories, retention expiry, ACK-ahead rejection, filter-correct
   metrics, concurrent publish order, malformed input, callback failure or half-open detection.
6. The current DAP translates warning text but does not stop applying later state events or
   enter a reconciliation barrier after `event_dropped`/slow-consumer evidence.

The broad `events` feature is therefore evidence of a useful best-effort live stream, not a
safe resumable or state-authoritative portable profile.

## Alternatives compared

### Sequence and cursor model

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| Bare global `seq` as both event ID and subscriber cursor | Small; resembles current JSON | Restart aliasing, filters make skips ambiguous, no selection/generation scope | Reject as full contract; legacy-only observation |
| Per-subscription contiguous sequence only | Easy loss detection while connected | Cannot resume through a new subscription or correlate global causal order | Reject as sole model |
| Canonical stream sequence plus scoped delivery cursor chain | Stable total order, filter-safe continuity, resumable across subscription sockets, explicit checkpoints/gaps | More envelope metadata and producer bookkeeping | **Recommend** |

### Back-pressure behavior

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| Silently drop telemetry/oldest and keep session healthy | Maximum throughput | State/resource truth can be permanently wrong | Reject |
| Block canonical producer on slow subscriber | No subscriber loss | One observer can stall runtime/control; deadlock/resource risk | Reject |
| Isolated bounded delivery queue; explicit gap and degrade/unsubscribe | Protects producer and other subscribers; loss is mechanically visible | Client must reconcile and some telemetry is lost | **Recommend** |

### Recovery

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| Always full poll after any reconnect | Simple | Expensive; cannot preserve epoch; races unless baseline is cursor/revision-bound | Degraded fallback only |
| Resume by unscoped `since_seq` | Current server shape | Can replay wrong incarnation or a truncated interval as success | Reject as portable behavior |
| Same-generation contiguous resume, otherwise typed full-reconcile barrier | Efficient normal recovery and fail-closed discontinuity | Requires stream identity, retention evidence and cross-domain baseline | **Recommend** |

### Idle health

| Alternative | Advantages | Risks | Decision |
|---|---|---|---|
| Assume blocking socket is healthy until data appears | No traffic | Half-open can remain falsely healthy indefinitely | Reject |
| Periodic `ps`/resource polling | Detects some failure | Competes with event authority and violates healthy-idle no-poll rule | Reject as full profile |
| Same-stream cursor checkpoint with negotiated maximum interval | Proves receive path and cursor watermark without target polling | Small bounded control traffic | **Recommend** |

## Recommended portable target contract

### Identity and wire-safety inputs

This Study consumes the `HSX-ST-002` identity domains:

```text
EventStreamRef {
  executive: ExecutiveRef
  stream_id: OpaqueId128
  stream_generation: UInt64
}
```

An executive restart changes `ExecutiveRef`. A reset/replacement of sequence or retained
history semantics changes `stream_id` or increments `stream_generation`, even if the
executive incarnation remains. A subscription socket does not create a new stream generation.

All sequences/cursor positions are unsigned monotonic 64-bit values, never wrap within one
stream generation, and follow `HSX-ST-002`'s JavaScript-safe string serialization. Before
exhaustion the producer starts a new stream generation. A timestamp is diagnostic only and
never orders events, proves liveness, or resolves a cursor conflict.

### Proposed descriptive DTOs

```text
EventCursor {
  stream: EventStreamRef
  position: UInt64
  selection_digest: Digest
}

SubscriptionRef {
  session: SessionRef
  subscription_id: OpaqueId128
  subscription_generation: UInt64
  selection_digest: Digest
}

CanonicalEvent {
  stream: EventStreamRef
  event_seq: UInt64
  event_type: StableName
  target: TargetRef?
  causal_ref: OpaqueRef?
  state_revision: UInt64?
  resource_revision: UInt64?
  ts_diagnostic: Timestamp?
  data: TypedPayload
}

EventEnvelope {
  subscription: SubscriptionRef
  cursor_before: EventCursor
  cursor_after: EventCursor
  event: CanonicalEvent
}

CheckpointEnvelope {
  stream: EventStreamRef
  subscription: SubscriptionRef
  cursor_before: EventCursor
  cursor_after: EventCursor
  latest_committed_seq: UInt64
  earliest_retained_seq: UInt64
  health: StreamHealthEvidence
}

GapEnvelope {
  stream: EventStreamRef
  subscription: SubscriptionRef
  cursor_before: EventCursor
  first_unavailable: UInt64
  last_unavailable: UInt64
  earliest_retained_seq: UInt64
  latest_committed_seq: UInt64
  cause: GapCause
  recovery: "resume_from" | "full_reconcile"
}
```

Names and exact field encoding remain for Master design allocation, but these semantic fields
are required. The normalized PID/category/authority selection is hashed into
`selection_digest`; changing it invalidates cursor continuity unless the server explicitly
proves a compatible narrowing. Expanding a selection always requires a baseline for the newly
included state/resource domains.

### Canonical publish and delivery ordering

1. The executive assigns `event_seq` at the same atomic commit that places the immutable
   `CanonicalEvent` in the stream log. Sequence order is canonical commit order; the
   subscription-specific `EventEnvelope` wraps that event without changing it.
2. Every publisher uses that sequencer. Allocate-then-later-append/broadcast is forbidden.
3. Subscribers observe matching canonical events in ascending order. Related run-state or
   resource events also carry the owning domain's causal reference/revision.
4. A filter may legitimately skip canonical event sequences. Numeric `event_seq + 1` is not
   the subscriber's gap rule. `cursor_before == previously_applied_cursor` is the continuity
   rule; checkpoints advance across filtered regions and prove idle liveness.
5. A repeated identical envelope/cursor after uncertain ACK is a duplicate and is classified
   without a second domain transition. The same stream/sequence with different immutable
   content is corruption and fails stream health.
6. Out-of-order cursor chains are not applied optimistically. A bounded transport reorder may
   be buffered only if the negotiated transport profile explicitly permits it; the current
   newline/TCP profile permits none.
7. Unknown additive payload fields are ignored. An unknown event type is explicitly
   classified and may advance ACK only if its advertised authority class is non-critical. An
   unknown state/resource-authoritative type forces capability failure or reconciliation.

### Subscription and resume handshake

A full-profile subscription request carries `SessionRef`, exact `EventStreamRef` when
resuming, normalized selection, and optional `resume_cursor`. The reply includes:

- exact `SubscriptionRef` and `EventStreamRef`;
- whether delivery is `live`, `replay`, or `reconcile_required`;
- accepted/base cursor and replay-through cursor;
- earliest retained and latest committed sequence;
- retention floors/limits, queue limit and checkpoint maximum interval;
- immutable negotiated capability profile and generation.

Resume succeeds only when executive/stream identity, generation and selection digest are
compatible and every required cursor interval remains available. Boundary rules are exact:

- cursor at latest committed: success, no replay;
- cursor immediately before earliest retained: success replaying from earliest retained;
- older same-generation cursor: typed `seq_evicted`;
- cursor ahead of latest committed: `cursor_ahead`;
- different executive/stream generation: `stream_replaced`, not `seq_evicted`;
- different/expanded selection: `selection_changed` and baseline/full reconcile.

`seq_evicted` includes requested cursor, exact stream identity, earliest retained, latest
committed and `recovery: full_reconcile`. A successful reply may never silently truncate the
requested interval. Legacy `since_seq` may be retained only inside a named degraded adapter;
in a full profile it is the `position` portion of an identity-scoped `resume_cursor`, never a
standalone authority.

### ACK-after-apply contract

1. Receipt, JSON parse, enqueue and callback invocation are not application.
2. The consumer advances its applied cursor only after its single state owner has successfully
   reduced the envelope or deliberately classified it under the negotiated forward-
   compatibility policy.
3. ACK is cumulative and may batch, but it carries exact subscription/stream generation and
   the highest contiguous applied cursor. It never crosses an unresolved gap or reducer error.
4. Equality with the last accepted ACK is idempotent. A lower cursor returns `ack_regression`;
   a cursor past the highest delivered chain returns `ack_ahead`; wrong selection,
   subscription, session or stream generation returns the corresponding stale-reference error.
5. An uncertain ACK response is safe: retain the applied cursor and resend the same ACK or
   resume from it. Duplicate replay is expected and must not duplicate state transitions.
6. Producer queue eviction never advances a client's ACK. Loss produces a gap/health failure.
7. ACK frees only producer retention/backlog state described by the negotiated profile. It
   does not imply a target state change and cannot be used as a lifecycle lease heartbeat.

For the Debugger, “successfully applied” means accepted by its serialized controller reducer,
not delivered to a gateway callback. Gateway and controller cursors are therefore separate
evidence fields; proposed `DBG-D-002` must expose the ACK effect rather than send it hidden
inside the stream-reader thread.

### Retention, back-pressure, drops and gaps

- Canonical retention and each delivery queue are bounded, with limits/guaranteed floors
  returned by negotiation. `retention_ms` without enforcement is not a capability.
- A slow subscription cannot block the canonical producer or another subscription. Priority
  reservations for owners versus observers are optional target parameters, not implied
  semantics; either way every affected subscription receives its own exact outcome.
- Before ordinary delivery reaches a soft limit the server may emit health metrics/checkpoints.
  No warning by itself authorizes cursor advancement.
- When required delivery is no longer available, the subscription becomes discontinuous. The
  server emits `GapEnvelope` if possible and then suspends authoritative delivery or closes the
  subscription. If the socket dies before that control frame, EOF/read deadline produces the
  same degraded client outcome.
- Gap evidence reports an inclusive unavailable interval, cause (`retention_evicted`,
  `subscriber_overflow`, `producer_overflow`, `transport_corrupt`, `administrative_reset` or
  unknown future cause), retained/committed watermarks and recovery disposition.
- Telemetry shedding is allowed only when the capability profile classifies the category as
  non-authoritative and still preserves a verifiable cursor chain/checkpoint. Loss of any
  state/resource-authoritative category requires resume or full reconciliation.
- Counters are event counts, not arithmetic sequence distance. Required metrics include queued,
  delivered, applied/ACKed as reported, high-water, dropped intervals/count, earliest retained,
  latest committed and subscription active/closing state.

### Stream and session health evidence

RPC transport, session lease, stream transport, cursor continuity, consumer application and
ACK health are separate dimensions. “TCP connected” or “session keepalive succeeded” is not
enough to call the event stream healthy.

The full profile negotiates a maximum checkpoint interval. When no matching event is emitted,
the executive sends a same-stream `CheckpointEnvelope` within that interval. The client uses a
local monotonic read deadline derived from the negotiated value. This proves the receive path
and cursor watermark without polling target/resource state.

Typed health notices carry available stream/subscription references, last received/applied/
ACKed cursor, retained/committed watermarks, queue metrics, failure stage, last protocol error
and retry disposition. Required outcomes include:

| Evidence | Required outcome |
|---|---|
| Clean EOF or reset | `stream_eof`; stop healthy claim and ACK progress; bounded recovery |
| Checkpoint deadline missed | `stream_silent`; treat half-open as degraded; close/reopen transport |
| Invalid JSON/framing/encoding/oversize | `stream_malformed`; preserve frame context safely, do not skip or ACK |
| Missing identity/cursor/required field | `stream_contract_violation`; incompatible/degraded recovery |
| Cursor regression/conflicting duplicate | `stream_order_violation`; close and reconcile |
| Explicit gap/drop | `stream_gap`; suspend authoritative application at prior cursor |
| Controller/reducer failure | `event_apply_failed`; retain prior applied cursor and diagnostic cause |
| ACK rejected/timeout/connection loss | `ack_uncertain` or typed rejection; do not forget applied cursor |
| Keepalive/session lease failure | `session_suspect`/`session_lost`; ownership is separately reconciled |
| Capability/profile changes | `capability_changed`; new session/profile generation and reconcile |

Checkpoint traffic is transport health, not target polling. A healthy event-authoritative idle
session therefore performs zero periodic `ps`, breakpoint or resource-list polls.

### Contiguous resume and full reconciliation

Contiguous resume is allowed only when all of these are proven:

1. same `ExecutiveRef` and `EventStreamRef` generation;
2. same compatible selection and capability profile generation;
3. requested applied cursor is retained and replay begins at its exact successor chain;
4. same target/attachment continuity where the selected events carry target authority;
5. replayed events reduce through one contiguous cursor to the live checkpoint.

Otherwise the connection remains degraded and executes a full reconciliation. A safe full
reconciliation requires a **reconcile baseline** jointly owned by this Study and sibling
state/resource Studies: exact identities plus authoritative run-state/snapshot and resource
revisions are paired with an event baseline cursor. The implementation may provide an atomic
bundle or a subscribe-first/revision-fenced protocol, but it must prove that events concurrent
with the refresh are neither lost nor applied older-than-snapshot.

The recovery barrier is:

1. negotiate executive/session/capability identities;
2. establish the new stream/subscription and obtain the reconcile baseline mechanism;
3. obtain exact target/ownership, run-state/snapshot and resource evidence from their owning
   contracts;
4. apply/classify queued events strictly after the baseline revisions/cursor;
5. ACK through the final contiguous applied cursor;
6. publish healthy only after identity, ownership, state/epoch, resources and cursor agree.

`seq_evicted`, stream replacement, selection expansion, authoritative gap, malformed frame,
unrecoverable apply failure or missing reconcile-baseline capability invalidates preservation
of an old stop epoch. `HSX-ST-004` decides whether the refreshed state opens a new epoch.

## Capability names, versioning, and profiles

### Recommended stable capability names

The session handshake should negotiate named capability objects, not infer semantics from
protocol version or the broad string `events`:

| Capability name | Major 1 guarantee | Main consumer/owner |
|---|---|---|
| `hsx.event-stream.core` | Exact stream/subscription identity, canonical ordered envelopes, filter-safe cursor chain, cumulative ACK-after-apply, explicit gaps and typed failures | This Study / `DBG-D-002` |
| `hsx.event-stream.resume` | Retention watermarks, exact cursor resume, `seq_evicted`, `stream_replaced` and no silent truncation | This Study / `DBG-D-002` |
| `hsx.event-stream.health` | Same-stream checkpoints, negotiated read deadline and typed EOF/malformed/silent/ACK health evidence | This Study / `DBG-D-002` |
| `hsx.runtime-state.events` | State-authoritative event types, causal/state revisions and authority classification | `HSX-ST-004` |
| `hsx.debug-resource.events` | Resource identities/revisions/provenance events and authority classification | `HSX-ST-006` |
| `hsx.reconcile-baseline` | Event cursor paired with authoritative state/snapshot/resource baseline or equivalent revision-fenced proof | `HSX-ST-004..006` synthesis |

Capability objects carry `major`, `minor`, required/optional feature flags, category schema
versions and limits (retention, queue, checkpoint interval, envelope size). Major mismatch is
incompatible. A higher minor may add optional fields/categories only when the negotiated
unknown-field/authority-class rule makes them safe. Changing a required guarantee, cursor
comparison, ACK meaning, gap meaning or identity scope requires a new major. The negotiated
set is immutable within one session generation; any change creates a new capability profile
generation and reconciliation barrier.

### Explicit profiles

| Profile | Required capabilities/evidence | Authority and recovery | Status/use |
|---|---|---|---|
| `portable-debug-event-resumable/1` | All six capabilities for used state/resource domains | Contiguous applied events are authority; exact resume; full baseline only on typed discontinuity; no healthy polling | **Recommended current portable event subprofile** |
| `portable-debug-event-live/1` | Core, health, state authority and reconcile baseline; resume absent | Events authoritative only while continuous; any EOF/gap starts full reconcile; old epoch not retained | Optional constrained/transitional degraded profile |
| `legacy-python-events/1` | Explicit compatibility mapping from the current `events` feature and tested current shapes | Live events are hints, not resumable authority; every loss/malformed/callback/ACK uncertainty requires bounded full refresh; no cursor/epoch continuity | Named degraded migration oracle only |
| `legacy-poll/1` | Event capability explicitly absent; declared snapshot commands available | One controller-owned bounded poller is state authority; visible degraded status; no synthetic time-based stops | Last-resort named degraded profile |

The current Python implementation does **not** satisfy
`portable-debug-event-resumable/1` merely because protocol version is 1 or `events` was
negotiated. It maps only to `legacy-python-events/1` until the full conformance fixtures pass.
The Debugger gateway reports the negotiated facts; the controller chooses only among profiles
explicitly accepted by its compatibility registry.

### Degraded-profile removal conditions

No degraded path is permanent by default or removed by date/version guessing.

- `legacy-python-events/1` may be removed when every supported Executive artifact negotiates
  the full current profile, passes restart/resume/gap/ACK/health/reconcile fixtures, the
  compatibility inventory names no supported deployment that still requires it, and Steering
  accepts the removal package.
- `legacy-poll/1` has the same artifact/inventory/Steering gate plus proven no-poll healthy
  operation on all supported event-capable deployments.
- `portable-debug-event-live/1` remains only for a specifically supported target class whose
  bounded retention cannot provide resume but whose reconcile-baseline fixtures pass. Remove
  it when that target class is no longer supported or supplies safe resume.
- Every degraded entry records owner, exact capability trigger, allowed commands/polls,
  cadence/backoff/budgets, user-visible diagnostic, fixtures and removal evidence. A missing
  entry is `incompatible_capability_profile`, not an invitation to guess.

## Failure vocabulary

Full-profile errors are typed and include exact available references/cursors, health stage and
retry disposition. Required vocabulary includes:

- `incompatible_capability_profile`, `unsupported_category`, `selection_changed`;
- `stale_executive`, `stale_session`, `stale_subscription`, `stream_replaced`;
- `invalid_cursor`, `cursor_ahead`, `seq_evicted`, `stream_gap`;
- `ack_regression`, `ack_ahead`, `ack_uncertain`;
- `stream_eof`, `stream_silent`, `stream_malformed`, `stream_order_violation`,
  `stream_contract_violation`;
- `event_apply_failed`, `subscriber_overflow`, `producer_overflow`;
- `session_suspect`, `session_lost`, `reconcile_required`, `reconcile_failed`.

Diagnostic strings and timestamps are supplementary. Unknown diagnostic fields are tolerated;
unknown authority outcomes or missing required identity/cursor fields are not.

## Conformance fixture plan

The target contract needs portable golden envelopes/handshakes plus a deterministic in-memory
producer/subscriber model. The same fixtures should run against Python first and later every
supported implementation.

### Identity, order, cursor and filter fixtures

1. **Stream restart:** emit sequences in stream A, restart/reset with the same initial numeric
   sequence in stream B, and reject A's cursor as `stream_replaced`.
2. **Concurrent publishers:** force allocate/commit races across scheduler, mailbox and debug
   producers; all history and subscribers observe one identical ascending commit order.
3. **No wrap/serialization:** round-trip maximum sequence/generation as JavaScript-safe strings
   and rotate generation before exhaustion.
4. **Filtered continuity:** deliver events 10 and 100 to a filter while other categories fill
   the interval; checkpoints/cursor chain prove no loss and pending metrics count two events,
   not 90.
5. **Filter change:** same/narrowed compatible selection follows declared rule; expanded or
   category-version-changed selection returns `selection_changed` and reconcile.
6. **Unknown category:** unsupported requested category fails negotiation; an additive
   non-authoritative event type is classified once; unknown authoritative type fails profile.
7. **Duplicate/conflict:** replay an identical cursor/event and reduce once; same stream/seq
   with different content produces `stream_order_violation`.
8. **Out of order:** deliver N+1 before N on a no-reorder profile; neither is applied past the
   prior cursor and the stream degrades.

### Resume, retention, drop and ACK fixtures

9. **Resume boundaries:** latest cursor and earliest-retained-minus-one succeed; older returns
   `seq_evicted`; ahead returns `cursor_ahead`; response includes exact watermarks.
10. **No silent truncation:** request an evicted interval and prove no success/partial replay is
    possible.
11. **ACK-after-apply:** block controller application after receipt; producer sees no ACK past
    the prior cursor. Complete application and observe one cumulative ACK.
12. **Reducer/callback failure:** inject exception; retain prior applied cursor, report context,
    replay safely, and never acknowledge failed evidence.
13. **ACK rejection/uncertain response:** regression, future, wrong stream/subscription and lost
    reply yield typed outcomes; retry equality is idempotent and duplicates reduce once.
14. **Subscription overflow:** slow one subscriber to capacity; fast subscriber remains
    contiguous; slow subscriber receives exact gap or EOF and must reconcile. No ACK is
    fabricated.
15. **Producer overflow:** overflow canonical retention before a required cursor; every affected
    resume gets the same exact unavailable interval/watermarks.
16. **Warning/control pressure:** fill a queue when a warning/checkpoint is due; control delivery
    cannot silently evict an additional unreported interval.
17. **Retention time/capacity:** use a fake monotonic clock and exact capacity boundary; prove
    negotiated floors and earliest-retained watermark rather than merely advertising them.
18. **Owner/observer isolation:** slow observers cannot block or corrupt owner delivery; any
    reserved priority is reported as a limit, and each gap is subscription-specific.

### Framing, health and session fixtures

19. **Malformed stream:** invalid JSON, UTF-8, missing newline/fields, oversized frame and wrong
    identity each cause typed health failure, no skip and no ACK.
20. **EOF/reset:** clean EOF and connection reset immediately clear active health and notify the
    controller; no stale frontend “connected/healthy” flag remains.
21. **Half-open:** black-hole one direction while RPC keepalive still succeeds; missed
    checkpoint deadline produces `stream_silent` without target polling.
22. **Idle healthy:** checkpoints arrive at the negotiated bound for a fully idle target and
    healthy mode generates zero periodic task/resource/breakpoint list calls.
23. **Keepalive failure:** stream checkpoints may remain while session lease fails; health
    dimensions diverge and ownership is reconciled rather than assumed.
24. **Server handler failure:** abort the stream before an intended gap warning; EOF still
    forces the same conservative reconcile outcome.
25. **Shutdown/cancellation:** blocked read, pending ACK and recovery terminate within bounded
    shutdown without self-join or hidden exception.

### Cross-domain reconciliation fixtures

26. **Contiguous state resume:** same executive/stream/target/attachment and retained cursor;
    replay run/stop events once and preserve the epoch only with `HSX-ST-004` continuity proof.
27. **Evicted state history:** `seq_evicted` starts the baseline barrier; state/snapshot revision,
    resource revision and event cursor agree before healthy publication.
28. **Snapshot/event race:** inject run-state transition while baseline snapshot is read; the
    atomic or revision-fenced mechanism loses and regresses no transition.
29. **Resource/event race:** mutate breakpoint/watch resources during baseline; apply exact
    later revisions without adopting or deleting unowned resources.
30. **Target/PID replacement:** same numeric PID with changed `TargetRef` cannot resume an old
    cursor/epoch/resource set.
31. **Capability regression:** reconnect without resume/state/resource/baseline capability;
    choose only an explicitly registered degraded profile or fail incompatible.
32. **Full recovery matrix:** retained, evicted, stream replaced, target lost, ownership lost,
    resource conflict, reconcile failure and exhausted recovery each produce one typed result.

### Existing oracles to retain

- session open/feature/max-event/lock/keepalive/timeout/close tests;
- basic subscribe/filter/delivery and stream establishment-once tests;
- current ACK/metrics and queue/back-pressure warning tests;
- RPC connection-loss/session-reopen tests;
- debugger/DAP event translation fixtures.

They remain useful compatibility evidence, but none substitutes for exact stream identity,
cursor-chain, health and reconciliation assertions above.

## Cross-study and Debugger mapping

### `DBG-ST-006` question coverage

| Portable question | Contribution from this Study | Remaining owner |
|---|---|---|
| Executive/event-stream identity | Consumes `ExecutiveRef`/`EventStreamRef`; freezes sequence namespace and generation/cursor validity rules | `HSX-ST-002` owns identity construction and lifecycle |
| Ordered run/stop/block/fault/termination evidence | Canonical delivery order, cursor chain, causal/state-revision carrier and no ACK past unapplied evidence | `HSX-ST-004` owns authoritative states/causes/revisions |
| Cursor, `since_seq`, `seq_evicted`, drop and ACK | Full proposed semantics, failure boundaries, back-pressure and fixtures | Master allocates stable contracts |
| Snapshot consistency | Requires event-cursor/revision-fenced reconcile baseline and race fixtures | `HSX-ST-004` owns snapshot token/content |
| Lifecycle/ownership recovery | Session/attachment continuity gates resume; session health remains separate | `HSX-ST-002` |
| Resource provenance/revisions | Carries resource revision/events and requires event/resource baseline consistency | `HSX-ST-006` |
| Blocked-state inspection | Delivers blocked-state evidence without deciding inspection stability | `HSX-ST-004` |

### Proposed Debugger contract dependencies

| Debugger contract | Required output from this Study |
|---|---|
| `DBG-D-001` | Applied-cursor input ordering, queue saturation as health failure, no timer-fabricated state, duplicate/gap reducer rules |
| `DBG-D-002` | Typed gateway envelope, stream/subscription identity, immutable profile generation, explicit health dimensions, resume/gap/ACK effects, no hidden reconnect |
| `DBG-D-003` | Event cursor and exact target/state revision binding for epoch retention/invalidation |
| `DBG-D-005` | Resource-event revision continuity and nondestructive reconcile after gaps |
| `DBG-D-006` | Lifecycle operation/state evidence delivered in canonical order, but acceptance is not completion |

`DBG-D-002` should expose `last_received_cursor`, `last_applied_cursor` and
`last_acknowledged_cursor` separately. The gateway may parse/transport but cannot decide that
an event changed debugger truth; only the controller reducer advances applied/ACK authority.

### Sibling HSX Study boundaries

- `HSX-ST-002` owns `ExecutiveRef`, `EventStreamRef`, session/attachment/target generations
  and continuity. This Study owns cursor validity inside that exact stream generation.
- `HSX-ST-004` owns state revision, stop/blocked/fault/termination causality, snapshot token and
  epoch stability. This Study guarantees ordered/loss-aware delivery and baseline coupling.
- `HSX-ST-006` owns resource identity, provenance, desired/observed revision and owner-safe
  reconciliation. This Study carries its events/revisions and makes resource loss visible.
- `HSX-ST-001` owns final legacy mapping, stable HSX ID allocation, capability field registry,
  cross-track Relations/Ledger and any further Study routing.

## Uncertainty and open questions

1. **Reconcile baseline mechanism:** an atomic snapshot+resource+cursor bundle is simplest;
   subscribe-first plus revision-fenced snapshots can also work. Master synthesis with
   `HSX-ST-004/006` must choose one portable minimum and prove the race fixtures.
2. **Retention guarantees:** exact duration/capacity are target-profile parameters. The safe
   semantic requirement is enforceable advertised floors and explicit watermarks/outcomes,
   not one desktop value imposed on AVR.
3. **Category authority registry:** Master design must assign each event schema version as
   state-authoritative, resource-authoritative, telemetry or control. Unknown authoritative
   categories cannot be safely ignored.
4. **Filter narrowing:** a server may prove normalized narrowing cursor-compatible; otherwise
   treating all filter changes as reconcile-required is conservative and acceptable.
5. **Cross-incarnation durable replay:** minimum profile rejects it. A future persisted event
   log needs separate durability/authenticity/boot recovery contracts.
6. **Security/authenticity:** identity and cursor fencing here do not authenticate a remote
   executive or event. Transport/authentication remains separate future work.
7. **Owner priority:** legacy text prefers dropping inactive observers first. Portable
   semantics require isolation and explicit loss; exact scheduling/quotas remain a target
   parameter and must not make owner continuity depend on silently losing observer evidence.
8. **Legacy warning mapping:** `event_dropped`, `slow_consumer` and
   `slow_consumer_drop` can remain diagnostics in the degraded adapter, but cannot be promoted
   to full-profile gap evidence without exact interval/cursor fields.

None of these questions prevents Master synthesis of the core requirements/architecture
boundary. The reconcile-baseline choice must be settled before the affected detailed design
can freeze.

## Proposed descriptive contract concepts for Master

Without allocating numeric HSX requirement/architecture/design IDs, this Study recommends
stable proposed contracts for:

- executive-scoped event-stream identity and no-wrap sequence generation;
- canonical atomic publish order and filter-safe subscription cursor chains;
- typed event/checkpoint/gap envelopes and exact resume/eviction boundary results;
- cumulative ACK only after serialized consumer application/classification;
- isolated bounded delivery, explicit gap/back-pressure and truthful metrics;
- same-stream checkpoint health, half-open detection and typed failure propagation;
- contiguous resume versus exact state/resource/event reconcile baseline;
- named/versioned event, state, resource and reconcile capabilities;
- the current portable and explicitly degraded profiles/removal gates above;
- portable adversarial fixtures covering every claimed guarantee.

## Conclusions

1. The current Python event system is a valuable best-effort live-stream oracle, but the broad
   `events` feature is not proof of safe resume, state authority or healthy continuity.
2. A bare `seq` cannot survive executive restart, stream reset or filter ambiguity. The minimum
   safe cursor includes exact `EventStreamRef`, generation and normalized selection.
3. Canonical event order must be assigned at one atomic log commit. Subscriber continuity is a
   cursor chain, not arithmetic `seq + 1` across filtered events.
4. ACK means highest contiguous event successfully applied/classified by the authoritative
   consumer. Parsing, buffering, callback attempt, drop or timer expiry cannot advance it.
5. `seq_evicted` is a precise same-generation retention outcome with watermarks. Stream
   replacement, cursor-ahead and selection change are distinct failures. Silent truncated
   replay is forbidden.
6. Queue/producer loss is an observable health failure. It never becomes acknowledgement;
   affected state/resource domains resume contiguously or pass a full reconcile barrier.
7. Same-stream checkpoints provide idle liveness without competing target polling. RPC,
   session, stream, continuity, application and ACK health remain separate evidence.
8. `portable-debug-event-resumable/1` is the recommended current portable event subprofile
   for composition into the synthesized full portable-debug profile.
   `legacy-python-events/1` and `legacy-poll/1` are named/tested degraded migration profiles
   with explicit removal evidence, never behavior inferred from protocol version.
9. Event recovery becomes healthy only when exact identity, ownership, state/epoch, resources,
   capability generation and applied cursor agree. Reopening a socket is insufficient.
10. These conclusions provide the stream contract needed by `DBG-ST-006` and proposed
    `DBG-D-002`, while leaving state, lifecycle and resource meaning to their owning Studies.

## Completion and handoff

Status is **COMPLETE FOR MASTER SYNTHESIS**. Master owns stable HSX requirement/architecture/
design ID allocation, final DTO/capability registry, reconcile-baseline synthesis with sibling
Studies, traceability updates, independent exact-head review and Steering routing through
issues #47/#38. This Study grants no product, Debugger Refactor or AVR implementation
authority.

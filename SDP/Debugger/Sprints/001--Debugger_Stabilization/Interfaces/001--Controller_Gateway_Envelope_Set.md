# DBG-D-001 / DBG-D-002 v1 — Frozen Controller/Gateway Envelope Set

- Status: **FROZEN BUT BLOCKED — GENERATION HANDSHAKE REFREEZE REQUIRED**
- Interface version: `dbg.controller-gateway/1`
- Steering authority: issue #38 comment `5356484309`
- Design inputs: `DBG-D-001`, `DBG-D-002`, `DBG-D-003`, `DBG-D-009`
- Portable inputs: frozen `HSX-R-001..036`, `HSX-A-001..005`, `HSX-D-001..005`
- Implementation module owner: `DBG-SL-001-004-001` / `DBG-RF-002`
- Read-only consumer: `DBG-SL-001-004-002` / `DBG-RF-003`
- Integration consumer: `DBG-SL-001-004-003`

This is the shared public interface freeze required before RF-002/RF-003 worker dispatch. The
Python implementation lives at `python/hsx_debugger/contracts.py`. RF-003 and the integration
Slice may import it but may not edit it. Any incompatible field, enum, generation or authority
change stops both workers and returns to Master/Design; no worker may improvise a parallel DTO.

Worker implementation exposed a generation-handshake contradiction before any product commit.
See `002--Generation_Handshake_Refreeze_Proposal.md`; no implementation may resume until
Steering authorizes/refuses the proposed `dbg.controller-gateway/1.1` correction.

## Identity and generation rules

`CommandId`, `OperationId`, `DeadlineId`, `StreamId` and `StopEpochId` are non-empty opaque
strings. They are never inferred from PID, socket endpoint, timer time or list position.

```text
GenerationStamp {
  executive_instance_id: str | None
  session_generation: non-negative int
  target_id: str | None
  target_generation: non-negative int
  capability_generation: non-negative int
  stream_generation: non-negative int
  display_pid: int | None
  evidence_grade: portable | legacy_degraded
}
```

Portable identities are consumed when the negotiated Executive provides them. In this wave the
existing Executive is accessed only through `hsx.python-debug-legacy/1`; the gateway therefore
sets unavailable portable IDs to `None`, increments debugger-local session/stream generations,
keeps PID display-only and marks every envelope `legacy_degraded`. It must not fabricate
continuity or advertise portable identity/event-resume/resource capabilities.

## Frozen enums

| Enum | Frozen values |
|---|---|
| `EvidenceGrade` | `PORTABLE`, `LEGACY_DEGRADED` |
| `RpcHealth` | `CLOSED`, `CONNECTING`, `HEALTHY`, `DEGRADED`, `LOST` |
| `EventHealth` | `DISABLED`, `CONNECTING`, `HEALTHY`, `GAP`, `LOST` |
| `RecoveryStatus` | `IDLE`, `REQUIRED`, `IN_PROGRESS`, `RETAINED`, `TARGET_LOST`, `OWNERSHIP_LOST`, `INCOMPATIBLE`, `EXHAUSTED` |
| `TargetRunState` | `NONE`, `UNKNOWN`, `STOPPED`, `RUN_PENDING`, `RUNNING`, `STOP_PENDING`, `STEP_PENDING`, `TERMINATED`, `LOST` |
| `EffectKind` | `OPEN_SESSION`, `CLOSE_SESSION`, `REQUEST`, `SUBSCRIBE_EVENTS`, `UNSUBSCRIBE_EVENTS`, `RECONCILE` |
| `CompletionStatus` | `OK`, `REJECTED`, `TRANSPORT_ERROR`, `PROTOCOL_ERROR`, `STALE`, `CANCELLED`, `UNSUPPORTED` |
| `ReconcileStatus` | `RETAINED`, `TARGET_LOST`, `OWNERSHIP_LOST`, `INCOMPATIBLE`, `EXHAUSTED`, `LEGACY_UNPROVEN` |
| `CommandStatus` | `ACCEPTED`, `COMPLETED`, `REJECTED`, `FAILED`, `CANCELLED` |

## Frozen immutable records

All records are frozen dataclasses. Mapping/list inputs are defensively copied into immutable
mapping/tuple values at construction; callers cannot mutate an envelope after enqueue.

| Record | Required fields and authority |
|---|---|
| `CapabilityProfile` | `profile_id`, `generation`, frozen capability set, `degraded`, diagnostics. Legacy gateway uses `hsx.python-debug-legacy/1` and named legacy event/resource capabilities only. |
| `ControllerCommand` | `command_id`, typed command kind, optional expected controller revision, frozen payload. No raw Executive request dict is accepted as a public frontend command. |
| `GatewayEffect` | `operation_id`, originating `command_id`, `EffectKind`, exact `GenerationStamp`, frozen payload, explicit `idempotent`. Only the gateway may translate payload to legacy JSON/RPC. |
| `GatewayFailure` | stable code, message, retryable flag, diagnostic cause; raw exception text is diagnostic only. |
| `GatewayCompletion` | operation ID, exact generation, `CompletionStatus`, frozen response payload, optional failure and evidence grade. RPC acceptance alone is not target run/stop truth. |
| `EventGap` | expected sequence, observed sequence, reason and reconciliation requirement. |
| `GatewayEvent` | exact generation, stream ID, optional positive sequence, category, frozen payload, optional gap, evidence grade. |
| `HealthNotice` | exact generation, independent RPC health, event health and reason. It never silently advances target state. |
| `ReconcileResult` | exact generation, `ReconcileStatus`, frozen baseline/diagnostics and evidence grade. `LEGACY_UNPROVEN` cannot retain a stop epoch. |
| `DeadlineExpired` | deadline ID, operation ID and exact generation. It is an input only and never fabricates completion/state. |
| `StopEpoch` | epoch ID, exact generation, stop token or explicit legacy local token, optional snapshot ref, evidence grade. |
| `ControllerSnapshot` | controller revision, generation, health, recovery, target state, capability profile, optional active epoch and pending operation IDs. |
| `CommandResult` | command ID, status, controller revision, optional operation ID, optional stable error and diagnostics. |
| `ControllerEvent` | controller revision, stable event kind, exact generation and frozen payload. |

## Frozen ports

```text
DebuggerController.start() -> None
DebuggerController.submit(command: ControllerCommand) -> Future[CommandResult]
DebuggerController.accept_gateway_notice(notice: GatewayCompletion | GatewayEvent |
                                         HealthNotice | ReconcileResult) -> None
DebuggerController.accept_deadline(expired: DeadlineExpired) -> None
DebuggerController.snapshot() -> Future[ControllerSnapshot]
DebuggerController.subscribe(callback: Callable[[ControllerEvent], None]) -> Subscription
DebuggerController.close() -> Future[CommandResult]

ExecutiveGatewayPort.start(notice_sink: Callable[[GatewayNotice], None]) -> None
ExecutiveGatewayPort.submit(effect: GatewayEffect) -> None
ExecutiveGatewayPort.close() -> None
```

The controller actor is the only debugger-state writer. Gateway sockets, event readers,
keepalive, callbacks and future integration adapters never mutate controller state directly.

## Ordering and state-authority rules

1. Controller acceptance allocates one operation and may enter a pending state only.
2. A gateway completion is correlated by operation ID and exact generation. Stale completions
   are ignored for mutation and recorded diagnostically.
3. `RUNNING`/`STOPPED`/terminal state requires authoritative event/reconcile evidence. Under the
   legacy profile, an RPC `OK` never proves that state.
4. A valid stop invalidates the previous epoch and opens exactly one new epoch. Legacy stop
   tokens are debugger-local `(session_generation, stream_generation, sequence-or-counter)`
   identities and are explicitly not portable continuity evidence.
5. RPC health and event health are independent. EOF/parser/callback/gap failures make event
   health non-healthy immediately.
6. `DeadlineExpired` may fail/degrade an operation or require reconcile; it cannot synthesize
   a stop, resume or completion.
7. Portable ACK-after-controller-apply is not claimed in this wave. Existing
   `ExecutiveSession` callback/ACK behavior is wrapped only by the named legacy event profile.
8. Recovery becomes healthy only on a `ReconcileResult`. `LEGACY_UNPROVEN` invalidates epochs
   and cannot silently adopt a PID/lock/resource.

## Explicit wave exclusions

- no `execd.py`, VM, ISA, scheduler, event-server or portable HSX runtime implementation;
- no symbol/source/inspection/resource/lifecycle/source-step implementation (`DBG-RF-004..006`);
- no DAP/CLI/VS Code production-path migration (`DBG-RF-007..008`);
- no polling/timer truth, hidden reconnect, raw frontend RPC escape hatch or fabricated target
  identity;
- no incompatible interface change without Master contract re-freeze and Steering routing.

## Interface acceptance fixtures

- every record is immutable under nested payload mutation attempts;
- wrong/negative generation and empty IDs reject at construction;
- stale generation completion/event does not mutate controller state;
- RPC and event health vary independently;
- legacy capability profile never advertises portable identity/resume/resource guarantees;
- response acceptance does not create `RUNNING` or `STOPPED`;
- event/reconcile stop opens one epoch; health loss/gap invalidates it;
- deadline expiry produces no synthetic state;
- gateway/controller imports share the one `contracts.py` definitions with no duplicate DTO.

Status is blocked for refreeze; the workers stopped exactly as this contract required.

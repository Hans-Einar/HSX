# DBG-D-001 / DBG-D-002 — Frozen Controller/Gateway Envelope Set v1.1

- Status: **REFROZEN / IMPLEMENTED / INDEPENDENT REVIEW PASS**
- Interface version: `dbg.controller-gateway/1.1`
- Supersedes: `dbg.controller-gateway/1` for implementation
- Steering authority: issue #38 comment `5357146230`
- Blocker evidence: `002--Generation_Handshake_Refreeze_Proposal.md`
- Designs: `DBG-D-001`, `DBG-D-002`, `DBG-D-003`, `DBG-D-009`
- Interface implementation owner: bounded pre-resume interface worker
- Product files: `python/hsx_debugger/__init__.py`, `python/hsx_debugger/contracts.py`
- Contract tests: `python/tests/test_hsx_debugger_contracts.py`
- Independent interface review: `DBG-RVW-001-004-004`

No RF-002/RF-003 partial WIP may be restored and no foundation implementation may resume until
the exact refreeze head passes the independent interface review.

## Unchanged v1 surface

All v1 opaque IDs, `GenerationStamp`, health/recovery/target/effect/completion/command enums,
immutable DTOs, public Controller/Gateway ports, legacy/degraded capability rules, ACK limits,
state-authority rules and wave exclusions remain unless explicitly refined below. There is one
shared `contracts.py`; RF-003 defines no parallel DTO.

## New/refined frozen records

| Record/value | Frozen v1.1 fields/rules |
|---|---|
| `CompletionAuthority` | `ACK_ONLY`, `AUTHORITATIVE_RESOURCE_ESTABLISHED`. OPEN/SUBSCRIBE promotion requires `OK` + `AUTHORITATIVE_RESOURCE_ESTABLISHED`; numeric stamp alone is never authority. |
| `GenerationWatermarks` | immutable non-negative `session`, `stream`; each is monotonic allocation watermark and may be greater than active generation after failure/cancellation. |
| `GenerationReservation` | non-empty operation ID, effect kind limited to OPEN_SESSION/SUBSCRIBE_EVENTS, exact reserved stamp, exact active-parent stamp, and consumed namespace. SUBSCRIBE parent includes exact active session generation. |
| `GatewayCompletion.authority` | defaults `ACK_ONLY`; gateway uses authoritative value only after the named session/subscription resource is actually established. |

`GatewayEffect.generation` is the exact controller-reserved stamp. Gateway validates it against
its known active/pending transport state and echoes it unchanged; it never increments,
substitutes or causes controller adoption of a generation.

## Controller-owned two-phase algorithm

### 1. Reserve

On accepted OPEN_SESSION or SUBSCRIBE_EVENTS intent, inside the controller actor:

1. validate command expected revision and current active parent continuity;
2. increment only the applicable allocation watermark and consume that number permanently;
3. create `GenerationReservation(operation_id, kind, reserved_stamp, active_parent_stamp)`;
4. store the reservation on the pending operation before effect dispatch;
5. emit `GatewayEffect` with the same operation ID and reserved stamp.

Reservation does **not** make the stamp active. It does not retire, invalidate or reinterpret a
still-valid old session/stream/epoch by itself.

For OPEN_SESSION, the reserved stamp increments session generation, resets its candidate stream
generation to zero and uses a capability generation allocated for that candidate session.
For SUBSCRIBE_EVENTS, only stream watermark/generation advances and the reservation is fenced by
the exact active session generation/identity.

### 2. Pending evidence fences

- Active session/stream health/events continue to exact-match the old active stamp while a
  replacement reservation is pending.
- A completion stamped with reserved N+1 is eligible only when operation ID, effect kind,
  pending reservation and full reserved stamp all match.
- A numerically higher stamp, wrong operation ID, cancelled/retired reservation, wrong session
  parent or unsolicited health/event never triggers adoption.
- Gateway must emit authoritative success completion before new-generation health/events.
  Pre-promotion N+1 event/health is rejected for mutation and cannot advance ACK/application.

### 3. Promote

Only matching `CompletionStatus.OK` plus
`CompletionAuthority.AUTHORITATIVE_RESOURCE_ESTABLISHED` promotes:

1. atomically set the reserved session/stream stamp active in controller state;
2. retire/invalidate the superseded continuity domain and affected stop epoch/handles;
3. remove the pending reservation and resolve the operation once;
4. accept later health/events only against the new active stamp.

If operation semantics explicitly tear down old continuity before success, that teardown is a
separate authoritative transition; reservation alone never implies teardown.

### 4. Failure, cancellation, retry, and burn

- REJECTED/TRANSPORT_ERROR/PROTOCOL_ERROR/STALE/CANCELLED/UNSUPPORTED consumes the reserved
  generation but does not promote it and does not roll the watermark back.
- Old active continuity remains active unless separately torn down.
- Same-operation idempotent retry reuses the same reservation/stamp.
- A new operation ID creates a new reservation from watermark+1, thereby visibly burning every
  failed/cancelled reservation.
- Late completion for an old/cancelled/replaced reservation is rejected even if its number is
  greater than active.

## Separate namespaces

Session and event-stream allocation watermarks/reservations are independent. A failed stream
reservation does not burn a session generation; a new session promotion retires prior stream
continuity and starts a separate stream namespace for the new active session. SUBSCRIBE always
names/fences its exact active session parent.

Capability/profile content is gateway evidence. Capability generation identity/allocation and
promotion remain controller state and follow the same session reservation.

## Required contract fixtures before interface review

1. successful OPEN reservation does not change active session; authoritative matching success
   promotes exactly once and retires old continuity;
2. failed OPEN consumes watermark, does not promote and leaves legal old active continuity;
3. failed SUBSCRIBE consumes stream watermark only, does not promote and leaves old stream;
4. same-operation idempotent retry reuses reservation/stamp;
5. new operation after failure receives the next watermark (generation burn);
6. old-active-stream events remain accepted while replacement SUBSCRIBE is pending;
7. after promotion, old-stream events are rejected and new exact-stamp events are accepted;
8. late N+1 completion with wrong operation ID or retired reservation is rejected;
9. session/stream namespaces and SUBSCRIBE parent-session fence are independent/negative-tested.

Additional retained v1 fixtures cover nested immutability, ID/generation validation, legacy
capability negatives, response-not-state-authority, epoch invalidation, deadline behavior,
health independence and single DTO imports.

## Explicit non-changes

- no portable HSX target-contract change;
- no Executive protocol, `execd.py`, VM/event server or AVR change;
- no product frontend/resource/inspection/lifecycle/step behavior;
- no RF-004..RF-009 authorization;
- no review/verification/sign-off credit for pre-refreeze stash WIP.

Status becomes implementation-resumable only after `DBG-RVW-001-004-004` PASS at exact
refreeze/interface-test head.

That prerequisite passed at `0cf52fcf69d11f254b957cfc52605a8be3114955`; the interface is
frozen and unchanged through the first structural wave.

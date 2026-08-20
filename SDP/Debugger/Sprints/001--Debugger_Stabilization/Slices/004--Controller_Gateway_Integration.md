# DBG-SL-001-004-003 — Early Controller/Gateway Integration

- Status: **BLOCKED — v1.1 REVIEW AND BOTH PARENT SIGN-OFFS REQUIRED**
- Parents: `DBG-RF-002`, `DBG-RF-003`
- Iteration: `DBG-IT-001-004`
- Steering: issue #38 comment `5356484309`
- Interface: refrozen `dbg.controller-gateway/1.1`
- Review: `DBG-RVW-001-004-003`
- Verification: `DBG-VER-001-004-003`
- Contract base: `97d8c5b8d62d56dcfcab59c97c516d83f68c7075`

## Bounded vertical outcome

Wire the signed controller and gateway foundations through one small runtime coordinator and
prove a legacy-profile command/effect/completion/event/health path. This Slice validates public
interfaces; it does not migrate DAP/CLI production ownership.

## Required scenarios

1. Start gateway and controller with deterministic ownership and idempotent shutdown.
2. Connect/open effect yields typed legacy capability and separate health evidence.
3. Pause or step command becomes pending; legacy RPC acceptance does not create `STOPPED`.
4. Matching legacy task-state event creates exactly one degraded stop epoch and completes the
   correlated command only through reducer rules.
5. Stale generation completion/event is ignored for mutation.
6. Event loss/gap invalidates epoch, marks event health non-healthy and requires reconcile.
7. `LEGACY_UNPROVEN` reconcile cannot retain epoch/target continuity.
8. Deadline expiry produces failure/recovery input without synthetic target state.
9. OPEN/SUBSCRIBE reserve -> pending old continuity -> authoritative success -> promote is
   proven across the real controller/gateway ports, including failure burn and stale late
   completion rejection.

## Owned files

- `python/hsx_debugger/runtime.py`
- `python/tests/test_hsx_debugger_controller_gateway.py`

The Slice may import signed RF-002/RF-003 modules but may not edit them. No existing
Executive/backend/DAP/CLI/VS Code/runtime/AVR file may change.

## Required evidence

- integration scenarios above pass with deterministic fake/legacy-session fixtures;
- every RF-002 and RF-003 Slice test remains green;
- unchanged ExecutiveSession/backend/DAP regression sets remain green;
- product diff from both signed parent heads contains only the two owned integration files;
- fresh independent integration review, formal `DBG-VER-001-004-003`, and Master exact-head
  sign-off pass.

## Completion signal

The integration head proves the frozen public interface without design deviation, records any
explicit residual/degraded behavior, and is ready for the issue #38 first-wave decision package.

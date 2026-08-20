# DBG-SL-001-004-002 — Typed Legacy Executive Gateway / Health Foundation

- Status: **RE-REVIEW PASS — FORMAL VERIFICATION PENDING**
- Parent: `DBG-RF-003`
- Iteration: `DBG-IT-001-004`
- Steering: issue #38 comment `5356484309`
- Frozen interface: `dbg.controller-gateway/1.1` (read-only implementation dependency)
- Review: `DBG-RVW-001-004-002`
- Re-review: `DBG-RVW-001-004-006`
- Exact reviewed head: `cf4d8a6665e9a6ebf35d425b227bc7a5c7bd3fa9`
- Verification: `DBG-VER-001-004-002`
- Implementation base: `97d8c5b8d62d56dcfcab59c97c516d83f68c7075`

## Bounded outcome

Implement a typed worker-thread gateway, independent health tracker and conservative adapter
around the unchanged current `ExecutiveSession`. It is a side-by-side foundation and does not
replace existing backend/DAP/CLI paths.

## Required behavior

1. Import the frozen records from `python/hsx_debugger/contracts.py`; define no duplicate DTO.
2. Typed gateway owns bounded effect queue, worker lifetime and one notice sink; callback/sink
   failures become observable event-health degradation.
3. RPC and event health are independent and every notice carries exact debugger-local
   generations.
4. Translate only gateway effects to legacy request/session/event calls. Retry is enabled only
   for explicitly idempotent effects.
5. Capability profile is `hsx.python-debug-legacy/1`; portable identity, ACK-after-apply,
   resume and resource guarantees are absent/negative-tested.
6. EOF, malformed input, protocol/transport errors and event gaps surface typed notices; no
   silent healthy state or policy reconnect.
7. Reconcile returns conservative typed outcomes. Reopened legacy session/PID is
   `LEGACY_UNPROVEN`, never retained portable continuity.
8. Close is idempotent, bounded and does not leak/join the current worker thread.
9. Gateway never allocates a generation: it validates/echoes the controller-reserved stamp,
   emits authoritative resource-established completion before new-generation notices, and
   preserves old active continuity while replacement is pending.

## Owned files

- `python/hsx_debugger/health.py`
- `python/hsx_debugger/gateway.py`
- `python/hsx_debugger/legacy_gateway.py`
- `python/tests/test_hsx_debugger_gateway.py`
- `python/tests/test_hsx_debugger_legacy_gateway.py`

Read-only: RF-002 modules, `python/executive_session.py`, existing backend/DAP tests. No other
product/test file may be edited.

## Required evidence

- new gateway/legacy tests cover queue, health, generations, capability negatives, retry,
  EOF/error/gap, conservative reconcile and shutdown;
- `test_executive_session_helpers.py`, `test_executive_sessions.py`,
  `test_hsx_dbg_backend.py`, and `test_hsx_dap_reconnect.py` pass unchanged;
- import/compile sanity for all new modules;
- no `execd.py`, VM, ExecutiveSession, backend, DAP/CLI/VS Code/AVR diff;
- worker commits exact owned-file head and returns clean status.

The pre-refreeze stash is candidate WIP only. Fresh worker must selectively apply/rework it
against reviewed v1.1 and rerun all evidence; no old test result carries sign-off credit.

## Completion signal

Fresh independent review has no Blocking/High/Medium finding, formal verification passes exact
implementation head, and Master signs both Slice and RF-003 foundation without widening scope.

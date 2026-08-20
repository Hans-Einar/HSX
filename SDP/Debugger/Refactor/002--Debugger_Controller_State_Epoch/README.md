# DBG-RF-002 — Debugger Controller, State Machine, and Stop-Epoch Foundation

- Status: **CONTRACT FROZEN / FIRST-WAVE IMPLEMENTATION AUTHORIZED**
- Steering authority: issue #38 comment `5356484309`
- Iteration: `DBG-IT-001-004`
- Owning Slice: `DBG-SL-001-004-001`
- Integration Slice: `DBG-SL-001-004-003`
- Requirements: `DBG-R-004`, `DBG-R-007..010`, `DBG-R-020`, `DBG-R-027..028`
- Findings: `DBG-F-007..009`, `DBG-F-013`, `DBG-F-025`, core part of `DBG-F-026`
- Architecture/design: `DBG-A-001`, `DBG-A-003`, `DBG-D-001`, `DBG-D-003`, `DBG-D-009`
- Shared interface: `dbg.controller-gateway/1` (frozen)
- Product baseline: `bf92c9be6cf81a7cb704778dafe88e55fee2e235`

## Refactor objective

Create a side-by-side frontend-neutral debugger-core foundation with one actor/reducer as the
only lifecycle/health/target/operation/stop-epoch state writer. Establish immutable state,
typed command/effect/notice flow, generation fencing, pending-operation semantics and stable
epoch lifetime without migrating DAP/CLI production behavior in this wave.

## Preserved behavior and deliberate change

- Preserve existing DAP/CLI/backend behavior and regression tests; no current production
  entrypoint is switched to the new controller yet.
- Deliberately replace multi-writer/timer/cache concepts inside the new foundation with one
  serialized actor and pure reducer.
- A command response may establish acceptance/pending state but not authoritative run/stop.
- Stop epochs are immutable and invalidated on resume, loss, gap, generation change or
  unproven legacy recovery.

## Owned implementation modules

Only Slice 001 may edit:

- `python/hsx_debugger/__init__.py`
- `python/hsx_debugger/contracts.py` — implementation owner of the frozen shared interface
- `python/hsx_debugger/model.py`
- `python/hsx_debugger/epochs.py`
- `python/hsx_debugger/reducer.py`
- `python/hsx_debugger/controller.py`
- `python/tests/test_hsx_debugger_contracts.py`
- `python/tests/test_hsx_debugger_controller.py`
- `python/tests/test_hsx_debugger_epochs.py`

RF-003 may import `contracts.py` but may not edit any file above. The integration Slice may
import these modules but owns separate files.

## Explicit non-goals

- no sockets, JSON/RPC, `ExecutiveSession`, keepalive, event ACK or reconnect implementation;
- no `execd.py`, VM, portable HSX runtime contract implementation or AVR work;
- no artifact/inspection/resource/lifecycle/source-step/DAP/CLI/VS Code migration;
- no final detach/disconnect/terminate product default;
- no product-path claim that the new controller is yet the sole owner outside its own tests.

## Slice plan

1. `DBG-SL-001-004-001` implements and independently signs the controller/model/epoch
   foundation plus frozen shared envelopes.
2. `DBG-SL-001-004-003` later proves the public controller port against RF-003 through one
   early legacy-profile integration flow.

## Verification plan

- frozen-envelope validation/immutability/generation tests;
- pure reducer transition-table and stale-message tests;
- actor single-writer, bounded inbox/subscriber, shutdown and concurrency tests;
- epoch allocation/validation/invalidation/legacy-grade tests;
- existing `test_hsx_dbg_backend.py`, `test_hsx_dap_harness.py`, and reconnect tests remain
  green as regression oracle;
- independent Slice review, formal `DBG-VER-001-004-001`, exact-head Slice sign-off, then
  separate parent Refactor reconciliation/sign-off.

## Foundation completion signal

RF-002 foundation is complete when Slice 001 is exact-head signed, its public interface remains
identical to the frozen envelope document, and later integration Slice 003 passes without
moving frontend or runtime ownership. This sign-off does not claim DAP/CLI adoption; that is
owned by later authorized Refactors.

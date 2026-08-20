# DBG-SL-001-004-001 — Controller / State / Stop-Epoch Foundation

- Status: **FROZEN / READY FOR FRESH WORKER**
- Parent: `DBG-RF-002`
- Iteration: `DBG-IT-001-004`
- Steering: issue #38 comment `5356484309`
- Frozen interface: `dbg.controller-gateway/1`
- Review: `DBG-RVW-001-004-001`
- Verification: `DBG-VER-001-004-001`
- Implementation base: `97d8c5bda717ce285b5c01c94c2fe19a714121ac`

## Bounded outcome

Implement the new side-by-side `python/hsx_debugger` typed contract, immutable model, pure
reducer, stop-epoch store and single-writer actor. No existing production frontend is migrated.

## Required behavior

1. Implement every frozen record/enum/port in the shared interface document with defensive
   nested immutability and construction validation.
2. Pure reducer validates expected revision/generation and returns immutable transition,
   effects, controller events and result intents without I/O or sleeps.
3. Command acceptance allocates a pending operation. `RUNNING`, `STOPPED` and terminal state
   require matching gateway event/reconcile evidence; RPC `OK` alone is insufficient.
4. Stale completion/event/deadline cannot mutate state. A deadline never fabricates state.
5. One stop opens one immutable epoch; run/loss/gap/generation/unproven recovery invalidates it.
6. Actor queue is bounded, is the sole state writer, executes effect sink outside state
   mutation, isolates subscriber exceptions and closes idempotently without self-join.
7. Legacy epoch evidence is explicitly graded and never promoted to portable continuity.

## Owned files

- `python/hsx_debugger/__init__.py`
- `python/hsx_debugger/contracts.py`
- `python/hsx_debugger/model.py`
- `python/hsx_debugger/epochs.py`
- `python/hsx_debugger/reducer.py`
- `python/hsx_debugger/controller.py`
- `python/tests/test_hsx_debugger_contracts.py`
- `python/tests/test_hsx_debugger_controller.py`
- `python/tests/test_hsx_debugger_epochs.py`

No other product/test file may be edited. Concurrent RF-003 files are read-only/nonexistent
from this worker's perspective.

## Required evidence

- new Slice tests pass and include stale/adversarial/concurrency/immutability negative controls;
- `python/tests/test_hsx_dbg_backend.py`, `test_hsx_dap_harness.py`, and
  `test_hsx_dap_reconnect.py` pass unchanged;
- import/compile sanity for all new modules;
- no `execd.py`, VM, ExecutiveSession, DAP/CLI/VS Code/AVR diff;
- worker commits exact owned-file head and returns clean status.

## Completion signal

Fresh independent review has no Blocking/High/Medium finding, formal verification passes exact
implementation head, and Master signs both Slice and RF-002 foundation without widening scope.

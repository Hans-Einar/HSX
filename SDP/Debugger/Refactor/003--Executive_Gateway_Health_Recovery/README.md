# DBG-RF-003 — Typed Executive Gateway, Health, and Recovery Foundation

- Status: **SLICE SIGNED — INTEGRATION ELIGIBLE AFTER RF-002 RE-SIGN-OFF**
- Steering authority: issue #38 comment `5356484309`
- Iteration: `DBG-IT-001-004`
- Owning Slice: `DBG-SL-001-004-002`
- Integration Slice: `DBG-SL-001-004-003`
- Requirements: `DBG-R-009..013`, `DBG-R-026..027`, `DBG-R-034`
- Findings: `DBG-F-010..011`, `DBG-F-013`, `DBG-F-017`, transport part of `DBG-F-026`
- Architecture/design: `DBG-A-002`, `DBG-D-002`, `DBG-D-009`
- Shared interface: `dbg.controller-gateway/1.1` (refrozen, read-only consumer;
  `DBG-RVW-001-004-004` PASS)
- Product baseline: `bf92c9be6cf81a7cb704778dafe88e55fee2e235`

## Refactor objective

Create a side-by-side typed Executive Gateway foundation that owns worker-thread transport
effects, independent RPC/event health, capability decoding, typed failures and conservative
reconciliation. Adapt the existing `ExecutiveSession` only through a wrapper and expose its
current behavior under named legacy/degraded profiles.

## Legacy Executive boundary for this wave

- Current Executive behavior is `hsx.python-debug-legacy/1`; optional current events/resources
  remain named legacy profiles.
- The gateway never fabricates ExecutiveInstanceRef, TargetId, image generation, stop token,
  resumable cursor or ownership evidence absent from the server.
- Existing callback/ACK semantics do not satisfy portable ACK-after-apply; the portable event
  resume capability is not advertised.
- Recovery may prove only local transport/session reopening. PID/lock/target continuity is
  `LEGACY_UNPROVEN` unless exact evidence exists, which invalidates controller epochs.

## Owned implementation modules

Only Slice 002 may edit:

- `python/hsx_debugger/health.py`
- `python/hsx_debugger/gateway.py`
- `python/hsx_debugger/legacy_gateway.py`
- `python/tests/test_hsx_debugger_gateway.py`
- `python/tests/test_hsx_debugger_legacy_gateway.py`

It may read/import `python/hsx_debugger/contracts.py` but may not edit RF-002 files. It may read
`python/executive_session.py` and legacy debugger tests but must not edit them.

## Explicit non-goals

- no `execd.py`, VM, event-server, scheduler or portable HSX runtime implementation;
- no changes to `python/executive_session.py`, `python/hsx_dbg/backend.py`, `python/hsx_dap`,
  `vscode-hsx`, CLI commands or product entrypoints;
- no policy-level target adoption, resource reconciliation, lifecycle defaults or source step;
- no claim of portable identity/event-resume/resource capability for the legacy Executive;
- no hidden retries of non-idempotent requests and no swallowed transport/callback failure.

## Slice plan

1. `DBG-SL-001-004-002` implements and independently signs the gateway/health/legacy adapter
   foundation against the frozen envelope set.
2. `DBG-SL-001-004-003` later proves controller effect -> gateway completion/event/health ->
   controller transition under the named degraded profile.

## Verification plan

- typed completion/error and exact generation tests;
- independent RPC/event health transition tests;
- bounded worker queue/shutdown and non-idempotent retry rejection;
- legacy capability profile/negative portable-capability tests;
- event EOF/malformed/gap/callback and conservative reconcile outcomes using stub sessions;
- existing ExecutiveSession/backend/DAP reconnect oracles remain green;
- independent Slice review, formal `DBG-VER-001-004-002`, exact-head Slice sign-off, then
  separate parent Refactor reconciliation/sign-off.

## Foundation completion signal

RF-003 foundation is complete when Slice 002 is exact-head signed, the shared envelope module
is consumed without duplicate DTOs, the current Executive is truthfully degraded, and
integration Slice 003 passes without Executive/runtime or frontend mutation.

Parent review `DBG-RVW-003-001-001` found no product defect but correctly rejected the
circular gate that attempted parent final sign-off before integration. Fresh parent final
review/verification/sign-off follows the separately signed integration Slice.

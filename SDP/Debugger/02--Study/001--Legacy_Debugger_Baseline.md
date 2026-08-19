# DBG-ST-001 — Legacy Debugger Baseline Study

Status: COMPLETE ENOUGH FOR DBG-GAP-001  
Date: 2026-08-19

## Question

What debugger system actually exists on `Implementation/vscode`, how trustworthy are its
current documents/tests as a source of truth, and what evidence must be preserved before a
redesign or structural refactor?

## Baseline

- Repository: `Hans-Einar/HSX`
- Product baseline branch: `Implementation/vscode`
- Reviewed product commit: `a1daa1c62605c44ac67e58e2b71320006f73cdd9`
- Relation to `main`: 84 commits ahead, 0 behind at study time.
- Historical debugger design/implementation material lives under legacy
  `main/04--Design` and `main/05--Implementation/01--GapAnalysis`.
- The current debugger stack includes:
  - `python/hsx_dap/`
  - `python/hsx_dbg/`
  - `python/executive_session.py`
  - debugger-facing portions of `python/execd.py`
  - `vscode-hsx/`
  - debugger tests under `python/tests/` and `vscode-hsx/src/test/`.

## Evidence reviewed

Primary reviewed artifacts include:

- `main/04--Design/04.09--Debugger.md`
- `main/04--Design/04.11--vscode_debugger.md`
- `main/05--Implementation/01--GapAnalysis/11--vscode_debugger/ImplementationPlan.md`
- legacy `main/05--Implementation/01--GapAnalysis/codeReview.md`
- `python/hsx_dap/__init__.py`
- `python/hsx_dbg/backend.py`
- `python/hsx_dbg/session.py`
- `python/hsx_dbg/symbols.py`
- `python/executive_session.py`
- `python/tests/test_hsx_dap_harness.py`
- `python/tests/test_hsx_dap_cli.py`
- `python/tests/test_hsx_dbg_backend.py`
- `vscode-hsx/debugAdapter/hsx-dap.py`
- `vscode-hsx/src/extension.ts`
- `vscode-hsx/src/test/configProvider.test.ts`
- `vscode-hsx/package.json`

## Findings

### ST-F1 — The implementation is function-rich, not an empty prototype

Useful foundations already exist: a shared `DebuggerBackend`, `DebuggerSession`,
`SymbolIndex`, event/session transport, breakpoint/watch/stack/memory/disassembly helpers,
DAP harness tests, and substantial VS Code views.

Conclusion: a complete rewrite without first capturing regression behavior would discard
valuable working semantics and evidence.

### ST-F2 — The architectural center of gravity is unclear

The later `hsx_dbg` shared backend refactor was directionally correct, but policy remained
spread across `HSXDebugAdapter`, `ExecutiveSession`, executive events, timers/polling, and
VS Code coordinator state.

Conclusion: the next design must choose one authoritative debugger controller/state owner.

### ST-F3 — Legacy design and plan documents have drifted

Legacy design files still describe older direct-RPC adapter shapes while the implementation
later moved toward shared debugger backends. The implementation plan mixes old unchecked
items with later prose that says related work was completed.

Conclusion: legacy documents are evidence/provenance, not current normative contracts.

### ST-F4 — Existing tests are useful but do not fully test the product path

Python handler/harness tests cover a significant amount of behavior. However, the subprocess
DAP test starts `python/hsx-dap.py`, while VS Code launches
`vscode-hsx/debugAdapter/hsx-dap.py`. The VS Code test suite mainly tests configuration
provider defaults rather than the complete extension/debug-adapter lifecycle.

Conclusion: preserve existing tests, then build a production-entrypoint black-box oracle.

### ST-F5 — The debugger accumulated compensating mechanisms

The adapter contains event handling plus state polling, pause/step fallback timers, duplicate
stop suppression, reconnect/reapply logic, backoff, local/remote breakpoint bookkeeping,
and multiple caches. These mechanisms appear to have been added incrementally to repair
symptoms rather than derived from one state/lifecycle model.

Conclusion: do not add more local fallbacks before DesignAnalysis.

### ST-F6 — Monolith growth is a primary maintainability risk

`python/hsx_dap/__init__.py` owns DAP transport, request dispatch, lifecycle, reconnect,
stepping, breakpoint/watch reconciliation, source/symbol interpretation, frame/scope
references, state synchronization, and DAP event translation. `vscode-hsx/src/extension.ts`
likewise owns activation, configuration, adapter spawning, status, coordinator state, and
multiple custom views.

Conclusion: modular responsibility redesign is a first-class requirement, not cosmetic
cleanup.

## Study conclusion

The legacy debugger should be treated as a **behavioral reference implementation with known
faults**, not as the architecture to preserve wholesale. The safe path is:

1. establish SDP/traceability and freeze this evidence baseline;
2. fix only small P0 defects needed to make the real DAP path trustworthy;
3. create `DBG-DA-001` to design the debugger optimally from requirements;
4. decide component-by-component what is reused, adapted, or replaced;
5. fan structural remediation into separate `DBG-RF-*` tracks with independent review and
   verification;
6. retain legacy implementation until replacement behavior is proven.

## Open questions forwarded to DBG-DA-001

- What is the exact state machine and state owner?
- Should the core be synchronous-with-serialized-controller or fully async?
- What is the public frontend API used by both CLI and DAP?
- Which executive events are authoritative and which fallback capabilities remain necessary?
- What ownership model is used for breakpoints/watches created by multiple clients?
- What is the stop-epoch/snapshot model for frames/scopes/variables?
- Which existing `hsx_dbg`, `ExecutiveSession`, symbol, DAP, and extension components are
  reused vs replaced?
- How is the Python debugger runtime packaged/versioned with the VS Code extension?

# Gap Analysis v2: VS Code Debugger

## 1. Scope Recap

**Design References**
- [04.11--vscode_debugger.md](../../../04--Design/04.11--vscode_debugger.md)
- [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md)
- Implementation plan refresh: [ImplementationPlan.md](./ImplementationPlan.md)

**Summary**
The design targets a VS Code extension + Debug Adapter Protocol (DAP) bridge that exposes the same debugger behavior delivered in the CLI (`hsx-dbg`). The adapter must translate DAP requests/events to the HSX executive RPC protocol via the shared debugger backend, provide source-level breakpoints/stepping, and surface stack/variable/memory/disassembly data inside VS Code.

## 2. Current Implementation (Nov 2025)

**Extension scaffolding**
- `vscode-hsx/src/extension.ts` registers a debug configuration provider and starts the Python adapter (`debugAdapter/hsx-dap.py`).
- `debugAdapter/hsx-dap.py` merely inserts the repo root on `sys.path` and calls `python/hsx_dap/main`. This is effectively the “old” adapter.

**Adapter internals**
- `python/hsx_dap/__init__.py` implements a bespoke DAP server with its own transport, session manager (`python/hsxdbg/*`), symbol mapper, and event bus. It predates the new CLI debugger context and therefore duplicates (and diverges from) its logic.
- Error handling lacks the Phase 5.4 improvements: connection loss causes hangs, events unsubscribe when the backlog grows, and breakpoints remain in decimal.
- Tests for the legacy adapter (`python/tests/test_hsx_dap_*.py` and `python/tests/test_hsxdbg_*.py`) have been deleted because they exercise the wrong stack and routinely hang inside the old transport/event bus.

**CLI debugger overlap**
- The CLI (`python/hsx_dbg/*`) now provides rich features: session management, breakpoint/watches, stack/disassembly, observer mode, reconnection, history/completion, etc. None of this is reused by the adapter yet; instead, two divergent implementations exist.

**Net result**
- There *is* a working extension/adapter, but it is tightly coupled to the legacy hsxdbg transport and violates the “single source of truth” goal. Refactoring is required before we can trust it for VS Code users.

## 3. Gaps vs. Design & CLI

| Area | Gap |
| --- | --- |
| Shared backend | Adapter does not reuse `hsx_dbg.context`, symbol index, or breakpoint/watch helpers. Two separate session managers exist. |
| Transport resilience | No auto-reconnect/backoff, event subscriptions get dropped (“events unsubscribed session_id=None”), and connection-loss handling predates Phase 5.4. |
| Breakpoint parity | VS Code uses decimal addresses, lacks CLI disabled-breakpoint tracking, and does not piggyback on symbol/file:line helpers. |
| Stack/variables/watch | Adapter-specific implementations drift from CLI caches; no guarantee that stack frames or watch expressions match CLI output. |
| DAP event flow | `stopped`, `continued`, and output events are wired manually and can deadlock when the event loop and synchronous RPC share the socket. |
| Testing | All legacy hsx_dap/hsxdbg tests were removed due to divergence; no new adapter tests exist yet. |
| Documentation | README references outdated features; no user guide describing the new backend or CLI parity. |

## 4. Study Findings

1. **Adapter should not be rewritten from scratch.** The existing VS Code extension scaffolding (TypeScript factory, debug configuration) works and should be retained. The Python adapter, however, must be refactored to import the same backend as the CLI.
2. **Legacy hsxdbg modules (`python/hsxdbg/*`) are largely redundant.** They implement their own transport/session/event/cache layers. We should harvest the small bits still useful (e.g., transport helpers if needed) or retire them in favor of `hsx_dbg` context + `executive_session`.
3. **Symbol mapper overlaps with CLI `SymbolIndex`.** The adapter should directly import `hsx_dbg.symbols.SymbolIndex` to avoid inconsistent source mappings.
4. **DAP tests need a fresh harness.** Rather than resurrect the old blocking tests, we should leverage a lightweight DAP client harness (Node or Python) that talks to the refactored adapter via stdio and asserts CLI parity.
5. **Documentation must reflect the shared architecture.** Users expect the same behavior whether they run `hsx-dbg` or use VS Code; docs must explain the backend reuse, reconnection behavior, and configuration knobs.

## 5. Next Actions (Phase 0 → Phase 1 of ImplementationPlan)

1. **Inventory & Notes**
   - Update `03--ImplementationNotes.md` in both 09--Debugger and 11--vscode_debugger with the findings above (legacy modules, missing reuse, test deletions).
2. **Shared Backend Extraction**
   - Define a `DebuggerBackend` module (likely in `python/hsx_dbg/backend.py`) that exposes async-friendly wrappers for attach/detach, breakpoints, stack, watches, memory, disassembly, and events. CLI commands and the adapter will import this module.
3. **Adapter Refactor Strategy**
   - Replace `python/hsx_dap`’s reliance on `python/hsxdbg/*` with `hsx_dbg` backend + `executive_session` + `SymbolIndex`.
   - Remove the legacy transport/session/event cache modules once the adapter switches to the new backend.
4. **Test Plan v2**
  - Draft new adapter test strategy (DAP client harness, golden JSON fixtures) and capture it in `ImplementationPlan.md` Phase 5.
5. **Documentation**
   - Schedule doc updates (README, docs/vscode_adapter.md) to coincide with the refactor.

Completing the steps above unblocks Phase 1 of ImplementationPlan‑v2, ensuring the VS Code adapter evolves in lock-step with the CLI debugger rather than maintaining two divergent code paths.

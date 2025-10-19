# HSX Debugger — Implementation Gaps (Code vs. Requirements)

Derived from the documentation in `functionality/#1_TUI_DEBUGGER/HSX_(3)_requirements_structured.md` and a review of the current Python implementation (`python/execd.py`, `python/vmclient.py`, `platforms/python/host_vm.py`).

---

## 1. Session & Capability Layer (`EXEC.Session`)
- **Expectation (doc refs):** Exclusive PID lock per debugger, capability handshake, persistent session state, and clean detachment (`EXEC_CTRL`, `SESSION_FEED`, `CFG_STORE`, `LOG_BUS`).
- **Current code:** `ExecutiveState` (`python/execd.py:31-200`) attaches globally to the VM and forwards commands without PID-level locks or capability exchange. The only mutex is a coarse `threading.Lock` around `step()`.
- **Impact:** Multiple front-ends can issue conflicting commands; requirements that depend on session metadata (breakpoint persistence, capability negotiation) are unmet.
- **Suggested follow-up:** Implement PID-scoped sessions in `execd.py` (attach/detach bookkeeping, lock table), extend protocol responses with advertised capabilities, and wire session state into config/logging once available.

## 2. Breakpoint Management Bridge (`EXEC_BP`, `BREAK_NOTIFY`)
- **Expectation:** Debugger issues breakpoint add/remove via execd; execd mirrors VM breakpoint state and forwards break notifications back to the control loop.
- **Current code:** Breakpoints live solely inside the VM RPC (`platforms/python/host_vm.py:2888-2956`). `VMClient` lacks `dbg_*` helpers, and `ExecutiveServer.exec_state_handle` never exposes `dbg` operations (`python/execd.py:800-1008`).
- **Impact:** TUI/CLI cannot manage breakpoints through the documented interface; no break-hit notifications reach the UI.
- **Suggested follow-up:** Add `dbg` wrappers to `VMClient`, surface corresponding commands in `execd`, and translate VM `debug_stop` events into an outbound queue (which also feeds the session/update stream).

## 3. Event & Trace Streaming (`EXEC.Events`, `EXEC_TRACE_FEED`, `STATE_FEED`)
- **Expectation:** Persistent subscription endpoint for trace/scheduler/mailbox events with back-pressure and reconnection semantics.
- **Current code:** `VMController.step` aggregates events per call (`platforms/python/host_vm.py:2600-2675`). Execd simply reads them synchronously and logs mailbox transitions (`python/execd.py:505-547`) before discarding the payload.
- **Impact:** No API exists for clients to subscribe to live traces; requirements around event-driven UI refresh and backlog control remain unsatisfied.
- **Suggested follow-up:** Introduce an event queue in execd, expose `events.subscribe/poll` commands, and retain trace buffers (`DATA_TRACE`) per the structured requirements.

## 4. Symbol/Trace/Data Stores (`DATA_*`, `SVC.Config/Logging`)
- **Expectation:** Shared data stores for symbols, trace history, and breakpoint archives, plus integration with config/logging services.
- **Current code:** Execd keeps only transient data—a log `deque` and stdio helpers (`python/execd.py:87-402`). No persistence or symbol cache is maintained.
- **Impact:** Documentation references (`DATA_SYM`, `DATA_TRACE`, `DATA_BP`, `CFG_STORE`) have no concrete backing; tracer/breakpoint persistence is missing.
- **Suggested follow-up:** Define storage strategy (in-memory caches with serialization, or reuse existing tooling) and connect to planned config/logging modules when they materialize.

## 5. Toolchain Integration Surface (`SVC_IPC` parity)
- **Expectation:** Execd should expose the rich RPC surface described in `docs/executive_protocol.md`, including breakpoint, stack, and event commands used by new front-ends.
- **Current code:** Many documented commands exist only on the VM server (e.g. `dbg` ops) and are not proxied through execd. The `ExecutiveState` façade covers core VM control but stops short of the debugger-facing surface.
- **Impact:** CLI/TUI cannot rely on execd alone; they would need to talk to the VM RPC directly, diverging from the layered architecture.
- **Suggested follow-up:** Expand execd’s command set to mirror the VM controller features required for the debugger (stack info, watchpoints, advanced clock control) or adjust the spec to clarify current limitations.

---

### Recommended Next Steps
1. Prioritize implementing PID-scoped sessions and breakpoint bridging in `execd.py`/`VMClient`, since downstream UI work depends on them.
2. Design an event streaming mechanism (even if initially polling-based) so the TUI can subscribe to trace/break updates without blocking on `step`.
3. Align the requirements document with interim capabilities if implementation will stage progressively; otherwise, file work items to cover the missing APIs before the TUI effort proceeds.


# Grand Implementation Plan (Python-First Focus)

> Strategy: Execute all **Python** implementations for each module before tackling the corresponding **C ports**. The C milestones remain documented inside each module's plan but are deferred until the Python feature set is verified end-to-end.

## Legend
- `[done]` Completed
- `[wip]` In progress
- `[todo]` Not started / upcoming
- `C (deferred)` Explicitly postponed to the post-Python phase.

---

## 01 - VM
| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Python reference implementation (shifts, PSW, DIV, ADC/SBC, trace, streaming loader) | [done] | Completed 2025-11-01 (Sessions 1-7). |
| 2 | C port | C (deferred) | Execute after Python stack stabilizes. |
| 3 | Advanced features (heap, paging, value/command services) | [todo] | Dependent on downstream requirements. |
| 4 | Documentation & validation pass | [todo] | Run once all features are in place. |

Dependencies: shared ABI header (Phase 1.8) still outstanding; coordinate once header spec exists.

Next Python milestone: ensure trace docs/executive consumption are synced (see 02 - Executive).

---

## 02 - Executive
| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Core debugger infrastructure (sessions, locks) | [done] | Sessions, PID locks, keepalive, and capability negotiation delivered. |
| 2 | Event streaming + scheduler integration | [done] | Event bus, task state broadcasts, and scheduler hooks implemented. |
| 3 | RPC/controller extensions for streaming loader | [done] | HXE v2 loader, symbol metadata plumbing, and provisioning hooks landed. |
| 4 | Clock & task orchestration polish | [done] | Breakpoint handling, pause semantics, and register delta tracking shipped. |
| 5 | Python TUI integration hooks | [done] | Watch expressions, trace polling, and client wiring complete (consumer UIs pending). |
| 6 | C port | C (deferred) | After Python milestones. |
| 7 | Docs & validation pass | [todo] | Final documentation sweep once downstream consumers settle. |

Immediate action: Transition focus to Mailbox Phase 1 now that Python executive phases 1-5 are complete.

---

## 03 - Mailbox
| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Python mailbox manager parity (current) | [todo] | Ready to start; executive event APIs now available. |
| 2 | Wait/timeout, fan-out, tracing | [todo] | Builds on Phase 1 implementation. |
| 3 | Provisioning hooks (streaming coordination) | [todo] | Depends on streaming loader support from Executive Phase 3. |
| 4 | Stability & stress tests | [todo] | After feature completion. |
| 5 | C port | C (deferred) | Post-Python stage. |
| 6 | Documentation & examples | [todo] | Final step. |

---

## 04 - ValCmd
All phases are **Python-first** and currently `[todo]`. Coordinate after mailbox and executive streaming are stable.

- Phase 1: Value service scaffolding (Python)
- Phase 2: Command service core flows (Python)
- Phase 3: Telemetry and mailbox bindings (Python)
- Phase 4: Shell adapters and interactive workflows (Python)
- Phase 5: Extended scenarios and regression coverage (Python)
- Phase 6: Documentation and examples refresh
- Phase 7: C port (deferred until Python validation completes)

---

## 05 - Toolchain
| Phase | Description | Status |
|-------|-------------|--------|
| 1 | ISA updates (Python) | [todo] — coordinate with VM features (already available). |
| 2 | Debug metadata | [todo] |
| 3 | Trace integration (match VM events) | [todo] |
| 4 | Streaming loader support in assembler/linker | [todo] — update CLI to chunk uploads. |
| 5 | Test matrix expansion | [todo] |
| 6 | Packaging | [todo] |
| 7 | C toolchain components | C (deferred) |

---

## 06 - Toolkit
Python phases (CLI/monitor tools) remain `[todo]`; plan mirrors executive/mailbox availability.  
Deferred: binary packaging and TUI deliverables depend on Phase 2 work.

---

## 07 - Provisioning
| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Monolithic HXE loader integration | [todo] | Already possible via VM controller; needs polish. |
| 2 | Streaming loader RPC/workflows | [todo] | Requires Executive Phase 3 outputs and VM streaming (ready). |
| 3 | Progress and event streaming | [todo] | Dependent on executive event pipeline (now available). |
| 4-9 | Transport adapters, persistence, recovery | [todo] | Sequence once streaming pipeline is proven. |

C port tasks (embedded provisioning) remain deferred.

---

## 08 - HAL
All HAL phases (drivers, mock transports, C port) remain `[todo]` with explicit C-port deferral. Begin Python mocks only when provisioning/executive combinations require them.

---

## 09 - Debugger (CLI)
Phases 1-4 (Python) depend on VM trace and executive event APIs; all are `[todo]`.  
Phases 5-6 (C integration and packaging) are deferred.

---

## 10 - TUI Debugger
Entirely Python; start after the CLI debugger stabilizes. Current status `[todo]`.

---

## 11 - VSCode Debugger
Python DAP adapter can leverage CLI/TUI work; all items currently `[todo]`. C/native extensions remain deferred.

---

## Summary Timeline (Python-first)
1. Execute Mailbox Phase 1 to establish parity with legacy manager.
2. Follow with Mailbox Phases 2-3 (wait/wake, fan-out, provisioning hooks).
3. Roll Provisioning Phase 2 (streaming loader usage) and associated toolkit updates.
4. With pipeline stable, proceed to CLI/TUI debugger work.
5. After all Python deliverables complete, revisit C-port phases (VM Phase 2, Executive Phase 6, Mailbox Phase 5, etc.).

Grand plan will be revisited whenever module plans change or once Python milestones reach completion.

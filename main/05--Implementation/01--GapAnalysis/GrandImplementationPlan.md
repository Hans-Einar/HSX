# Grand Implementation Plan (Python-First Focus)

> Strategy: Execute all **Python** implementations for each module before tackling the corresponding **C ports**. The C milestones remain documented inside each module’s plan but are deferred until the Python feature set is verified end-to-end.

## Legend
- **✓** Complete
- **▶** In progress
- **○** Not started / upcoming
- **C (deferred)** – Items explicitly postponed to the post-Python phase.

---

## 01 – VM
| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Python reference implementation (shifts, PSW, DIV, ADC/SBC, trace, streaming loader) | ✓ | Completed 2025-11-01 (Sessions 1–7). |
| 2 | C port | C (deferred) | Execute after Python stack stabilizes. |
| 3 | Advanced features (heap, paging, value/command services) | ○ | Dependent on downstream requirements. |
| 4 | Documentation & validation pass | ○ | Run once all features are in place. |

Dependencies: shared ABI header (Phase 1.8) still outstanding; coordinate once header spec exists.

Next Python milestone: ensure trace docs/executive consumption are synced (see 02–Executive).

---

## 02 – Executive
| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Core debugger infrastructure (sessions, locks) | ○ | Requires VM Phase 1 trace APIs (done). |
| 2 | Event streaming + scheduler | ○ | Blocks mailbox wait/timeout & provisioning. |
| 3 | RPC / controller extensions for streaming loader | ○ | Consume new VM streaming APIs. |
| 4 | Clock & task orchestration polish | ○ | Follows event streaming. |
| 5 | Python TUI integration hooks | ○ | Dependent on phases 1–4. |
| 6 | C port | C (deferred) | After Python milestones. |
| 7 | Docs & validation | ○ | Final pass. |

Immediate action: Phase 2 (event/scheduler) to unblock mailbox + provisioning, then Phase 3 for streaming RPC hooks.

---

## 03 – Mailbox
| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Python mailbox manager parity (current) | ▶ | In progress (sessions support, send/recv). |
| 2 | Wait/timeout, fan-out, tracing | ○ | Requires Executive event APIs (Phase 2). |
| 3 | Provisioning hooks (streaming coordination) | ○ | Dependent on VM streaming & exec RPC. |
| 4 | Stability & stress tests | ○ | After feature completion. |
| 5 | C port | C (deferred) | Post-Python stage. |
| 6 | Docs & examples | ○ | Final step. |

---

## 04 – ValCmd
All phases are **Python-first** and currently ○. Coordinate after mailbox & executive streaming are stable.
- Phase 1: Value service scaffolding (Python)
- Phase 2–7: Command service, telemetry, shell
- Phases requiring C port → mark deferred
- Documentation/regression at end.

---

## 05 – Toolchain
| Phase | Description | Status |
|-------|-------------|--------|
| 1 | ISA updates (Python) | ○ – coordinate with VM features (already available). |
| 2 | Debug metadata | ○ |
| 3 | Trace integration (match VM events) | ○ |
| 4 | Streaming loader support in asm/link | ○ (update CLI to chunk). |
| 5 | Test matrix expansion | ○ |
| 6 | Packaging | ○ |
| 7 | C toolchain pieces | C (deferred) |

---

## 06 – Toolkit
Python phases (CLI/monitor tools) all ○; plan mirrors executive/mailer availability.
Deferred: binary packaging/TUI, etc., depending on Phase 2 work.

---

## 07 – Provisioning
| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Monolithic HXE loader integration | ○ | Already possible via VM controller. |
| 2 | Streaming loader RPC/workflows | ○ | Needs exec Phase 3 & VM streaming (done). |
| 3 | Progress & event streaming | ○ | Dependent on exec event pipeline. |
| 4–9 | Transport adapters, persistence | ○ | Sequence after streaming pipeline works. |

C port tasks (embedded provisioning) deferred.

---

## 08 – HAL
All HAL phases (drivers, mock transports, C port) remain ○ with explicit C-port deferral. Begin Python mocks only when provisioning/executive combos require them.

---

## 09 – Debugger (CLI)
Phases 1–4 (Python) depend on VM trace + executive event API. All ○.
Phases 5–6 (C, packaging) → deferred.

---

## 10 – TUI Debugger
Entirely Python; start after CLI debugger stabilizes.

---

## 11 – VSCode Debugger
Python DAP adapter can leverage CLI/TUI work; all C tasks deferred.

---

## Summary Timeline (Python-first)
1. Finalize **Executive Phase 2 & 3** (event + streaming RPCs).
2. Unlock **Mailbox Phase 2/3** (wait/wake, streaming integration).
3. Roll provisioning Phase 2 (streaming loader usage) and associated toolkit updates.
4. With pipeline stable, proceed to CLI/TUI debugger work.
5. After all Python deliverables complete, revisit C-port phases (VM Phase 2, Executive Phase 6, Mailbox Phase 5, etc.).

Grand plan will be revisited whenever module plans change or once Python milestones reach completion.

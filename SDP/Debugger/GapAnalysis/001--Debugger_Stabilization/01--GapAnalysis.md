# DBG-GAP-001 — Debugger Stabilization Gap Analysis

Status: ACCEPTED / DEBUGGER STABILIZATION ACTIVE
Date: 2026-08-19  
Inputs: `DBG-ST-001`, `DBG-CR-001`, `DBG-R-001..DBG-R-036`

## Purpose

Convert the legacy debugger CodeReview into a controlled remediation program without
continuing the historic pattern of fixing symptoms inside monolithic modules.

This GapAnalysis deliberately separates:

1. **baseline correctness repairs** needed before architecture work;
2. **DesignAnalysis** that defines the optimal debugger structure from requirements;
3. **independent Refactor workstreams** spawned from coherent responsibility domains;
4. **final cross-platform verification/sign-off**.

No structural Refactor below is authorization to implement before `DBG-DA-001` has accepted
the owning boundaries/contracts.

## Gap classes

- **Protocol baseline:** product path cannot be trusted until corrected.
- **State/lifecycle architecture:** multiple competing state owners and ambiguous target semantics.
- **Concurrency/transport:** multiple threads, sequence/output ownership, stream health/recovery.
- **Resource ownership:** breakpoint/watch state is not modeled as multi-client desired/actual state.
- **Execution semantics:** source-step operations and stop reasons are not formally distinct.
- **Inspection/symbol model:** stop epochs, addresses, source identity, stack/variables need explicit contracts.
- **Frontend boundaries:** DAP and VS Code layers own too much debugger policy.
- **Packaging/verification:** extension/runtime versioning and real product-path tests are insufficient.
- **Traceability:** legacy docs cannot safely drive future implementation.

## Finding-to-gap-to-refactor mapping

| Finding | Primary requirements | Gap class | Planned remediation |
|---|---|---|---|
| DBG-F-001 raw stdout | DBG-R-001,032 | Protocol baseline | **DBG-RF-001** |
| DBG-F-002 init ordering | DBG-R-002 | Protocol baseline | **DBG-RF-001** |
| DBG-F-003 wrong E2E entrypoint | DBG-R-032,033,036 | Protocol baseline / verification | **DBG-RF-001**, then DBG-RF-009 |
| DBG-F-004 identical source steps | DBG-R-017..020 | Execution semantics | **DBG-RF-006** |
| DBG-F-005 launch==attach | DBG-R-005,006 | Lifecycle | **DBG-RF-006** |
| DBG-F-006 terminate only pauses | DBG-R-006 | Lifecycle | **DBG-RF-006** |
| DBG-F-007 unstable frame/scope refs | DBG-R-004,021,022 | State/inspection | **DBG-RF-002**, DBG-RF-004 |
| DBG-F-008 multi-writer state | DBG-R-007,008 | State/concurrency | **DBG-RF-002** |
| DBG-F-009 DAP seq race | DBG-R-008 | Concurrency/transport | **DBG-RF-002**, DBG-RF-007 |
| DBG-F-010 silent stream loss | DBG-R-009,011,012 | Transport/recovery | **DBG-RF-003** |
| DBG-F-011 swallowed callback error | DBG-R-011,012 | Transport/recovery | **DBG-RF-003** |
| DBG-F-012 external watch adopted/deleted | DBG-R-015 | Resource ownership | **DBG-RF-005** |
| DBG-F-013 competing event/poll/cache/timer truth | DBG-R-007,009,010,013,020 | State architecture | **DBG-RF-002**, DBG-RF-003 |
| DBG-F-014 BP policy remains in DAP | DBG-R-014,027,028 | Resource/frontend boundary | **DBG-RF-005**, DBG-RF-007 |
| DBG-F-015 Python DAP monolith | DBG-R-027,028 | Frontend boundary | **DBG-RF-007** |
| DBG-F-016 TypeScript extension monolith | DBG-R-028..030 | Frontend boundary | **DBG-RF-008** |
| DBG-F-017 raw RPC leaks through DAP | DBG-R-026,027,034 | Core/transport boundary | **DBG-RF-003**, DBG-RF-007 |
| DBG-F-018 capability drift | DBG-R-003 | DAP contract | **DBG-RF-007** |
| DBG-F-019 hard-coded 16-bit mask | DBG-R-023 | Symbol/address contract | **DBG-RF-004** + HSX dependency |
| DBG-F-020 lowercase source identity | DBG-R-024 | Source mapping | **DBG-RF-004** |
| DBG-F-021 workspace-dependent runtime | DBG-R-031,032 | Packaging | **DBG-RF-008** |
| DBG-F-022 Windows E2E missing | DBG-R-033 | Verification | **DBG-RF-009** |
| DBG-F-023 shallow extension tests | DBG-R-029,030,032,036 | Verification/frontend | **DBG-RF-008**, DBG-RF-009 |
| DBG-F-024 legacy docs inconsistent | DBG-R-035,036 | Traceability | current SDP migration + **DBG-DA-001** |
| DBG-F-025 backend/client duplicate identity | DBG-R-007,027 | State boundary | **DBG-RF-002** |
| DBG-F-026 core is not sole frontend API | DBG-R-027,036 | Architecture | **DBG-RF-002..DBG-RF-007** |

All CodeReview findings are assigned; none remain as an unowned catch-all.

# Phase 0 — SDP and evidence activation

This documentation branch establishes:

- independent `SDP/Debugger`, `SDP/HSX`, and `SDP/AVR` tracks;
- debugger requirements with stable `DBG-R-*` IDs;
- `DBG-ST-001`, `DBG-CR-001`, and this `DBG-GAP-001`;
- Refactor IDs and dependency plan;
- a future `DBG-DA-001` design-analysis gate.

Product-code change: **not authorized in this phase**.

# Phase 1 — DBG-RF-001: DAP Protocol Baseline Stabilization

Type: narrow correctness Refactor; permitted before structural DesignAnalysis.  
Addresses: DBG-F-001, DBG-F-002, DBG-F-003.  
Requirements: DBG-R-001, DBG-R-002, DBG-R-032, initial DBG-R-033/036 evidence.

Scope:

- remove/redirect all raw stdout diagnostics in production DAP entrypoints;
- correct initialize/initialized ordering;
- make the black-box subprocess test start the exact wrapper/path the extension launches;
- add framing assertions that fail on any preamble/non-DAP stdout bytes;
- preserve all unrelated legacy behavior.

Non-goals:

- no state-machine redesign;
- no stepping/lifecycle redesign;
- no breakpoint/watch rewrite;
- no module decomposition beyond what is strictly necessary for the three defects.

Completion signal:

- product wrapper passes black-box initialize + attach/launch handshake fixture;
- no raw stdout outside DAP framing;
- independent review PASS on exact head.

# Phase 2 — DBG-DA-001: Optimal Debugger Architecture DesignAnalysis

Type: documentation/design gate, not product implementation.  
Depends on: DBG-RF-001 complete and reviewed.

The analysis designs from requirements rather than from the current monolith. It must decide:

- authoritative debugger state machine/controller and ownership;
- threading/serialization model;
- frontend/core/backend contracts;
- event-stream and reconnect model;
- stop-epoch/snapshot/reference model;
- breakpoint/watch multi-client ownership model;
- lifecycle semantics for attach/launch/disconnect/terminate;
- execution/stepping semantics;
- symbol/source/address model and HSX dependencies;
- packaging/versioning boundary;
- module boundaries with responsibilities and explicit non-responsibilities;
- migration strategy and component-by-component reuse/adapt/replace decision;
- compatibility strategy for legacy RPC/executive versions.

The analysis must include an explicit **reuse matrix** for at least:

- `python/hsx_dbg/backend.py`
- `python/hsx_dbg/session.py`
- `python/hsx_dbg/symbols.py`
- `python/executive_session.py`
- `python/hsx_dap/__init__.py`
- current DAP tests/fixtures
- `vscode-hsx/src/extension.ts`
- custom VS Code view behavior.

No structural worker may begin before the relevant `DBG-D-*` contracts are accepted.

# Structural Refactor fan-out

## DBG-RF-002 — Debugger Controller, State Machine, and Stop Epochs

Addresses: DBG-F-007,008,009,013,025 and core part of 026.  
Requirements: DBG-R-004,007,008,009,010,020,027,028.

Goal: establish one authoritative debugger-controller owner for lifecycle/run/stop state and
stable stop-epoch handles; serialize all state transitions and outbound protocol intent.

Expected design ownership:

- controller state machine;
- stop epoch / snapshot lifetime;
- input event/command queue or equivalent serialization;
- current target/session identity;
- no DAP/VS Code presentation knowledge beyond frontend-neutral events.

Dependencies: DBG-DA-001 accepted.  
Blocks: DBG-RF-005, DBG-RF-006, DBG-RF-007.

## DBG-RF-003 — Session, Executive Transport, Event Health, and Recovery

Addresses: DBG-F-010,011,013,017 and transport part of 026.  
Requirements: DBG-R-009..013,026,027,034.

Goal: provide one typed debugger-facing transport/session boundary with explicit connection
and event-stream health, bounded recovery, capability negotiation, and observable failure.

Dependencies: DBG-DA-001; must integrate with DBG-RF-002 controller contract.  
Can proceed in parallel with DBG-RF-004 after interfaces are frozen.  
Blocks: DBG-RF-005, DBG-RF-007.

## DBG-RF-004 — Symbol, Source Mapping, Address, and Inspection Model

Addresses: DBG-F-007 (inspection side),019,020.  
Requirements: DBG-R-021..025,036.

Goal: formalize source identity, address widths, PC/source mapping, stack/symbol metadata,
frame-relative variable resolution, and snapshot-safe inspection APIs.

Cross-track dependency: HSX must expose/accept a portable address-space contract rather than
forcing the debugger to invent one.

Dependencies: DBG-DA-001; coordinate stop-epoch interface with DBG-RF-002.  
Blocks: DBG-RF-006 and source-aware portions of DBG-RF-007.

## DBG-RF-005 — Breakpoint and Watch Ownership/Reconciliation

Addresses: DBG-F-012,014 and resource part of 026.  
Requirements: DBG-R-014,015,027,036.

Goal: one frontend-neutral resource model for desired vs remote breakpoints/watches with
explicit owner/provenance, reconnect reconciliation, external-resource preservation, and
stable identity.

Dependencies: DBG-RF-002 + DBG-RF-003 contracts available.  
Blocks: DBG-RF-007.

## DBG-RF-006 — Lifecycle and Execution/Stepping Semantics

Addresses: DBG-F-004,005,006 and execution/state part of 013/026.  
Requirements: DBG-R-005,006,016..020,030,036.

Goal: define and implement distinct instruction/into/over/out behavior plus explicit attach,
launch, disconnect, terminate, and stop-reason semantics in the shared core.

Dependencies: DBG-RF-002 controller + DBG-RF-004 source/stack contract; transport contract
from DBG-RF-003.  
Blocks: final DAP parity in DBG-RF-007.

## DBG-RF-007 — Thin, Modular DAP Adapter

Addresses: DBG-F-009,014,015,017,018,026.  
Requirements: DBG-R-001..004,026..030,034,036.

Goal: replace the current policy-heavy DAP monolith with bounded modules whose primary job is
DAP framing/lifecycle translation to the shared debugger core.

Expected boundaries (final names decided by DBG-DA-001):

- DAP transport/framing + single outbound serializer;
- request router/validation;
- lifecycle translation;
- breakpoint/inspection/execution request mapping that delegates policy to core;
- frontend event mapper;
- capability negotiation.

Dependencies: DBG-RF-002..006 sufficiently complete/frozen.  
Blocks: DBG-RF-008 and final verification.

## DBG-RF-008 — Modular VS Code Extension and Version-Coherent Packaging

Addresses: DBG-F-016,021,023.  
Requirements: DBG-R-028..032,036.

Goal: split extension responsibilities, keep custom views presentation-only, provide a
version-coherent debugger runtime package, and ensure standard DAP UI remains sufficient for
normal debugging.

Expected decomposition domains:

- configuration;
- adapter/runtime launcher;
- debug-session/status coordination;
- memory/register/stack views;
- disassembly;
- trace;
- breakpoint-specific UI;
- shared presentation utilities.

Dependencies: DBG-RF-007 frontend contract stable.  
Blocks: DBG-RF-009.

## DBG-RF-009 — Product-Path Cross-Platform Verification and Debugger 1.0 Sign-off

Addresses: DBG-F-003,022,023 and verification obligations across all findings.  
Requirements: DBG-R-032..036 plus acceptance evidence for all active DBG-R requirements.

Goal: make the real packaged debugger path the release oracle.

Minimum evidence:

- Windows + Linux production-entrypoint DAP framing/lifecycle tests;
- standard VS Code-equivalent scenarios for breakpoints, pause/continue, instruction step,
  source into/over/out, stack/locals/globals/watches, memory/registers/disassembly;
- reconnect with target retained and target lost;
- simultaneous external CLI breakpoint/watch ownership scenarios;
- event-stream loss/recovery;
- no-poll healthy idle evidence if events are supported;
- package/runtime version mismatch behavior;
- exact-head independent review and final requirement matrix.

Dependencies: DBG-RF-002..008 complete.  
Completion signal: Debugger 1.0 sign-off.

# Dependency graph

```text
SDP activation / DBG-GAP-001
          |
          v
DBG-RF-001  P0 protocol baseline
          |
          v
DBG-DA-001  optimal architecture + reuse matrix
          |
          +--------------------+---------------------+
          v                    v                     v
DBG-RF-002 Controller     DBG-RF-003 Transport  DBG-RF-004 Symbols/Inspect
          |                    |                     |
          +----------+---------+---------+-----------+
                     |                   |
                     v                   v
              DBG-RF-005 Resources  DBG-RF-006 Lifecycle/Step
                     \                   /
                      \                 /
                       v               v
                       DBG-RF-007 Thin DAP
                              |
                              v
                       DBG-RF-008 VS Code/package
                              |
                              v
                       DBG-RF-009 Verification
                              |
                              v
                        Debugger 1.0 sign-off
```

Parallelism is allowed only after the owning contracts from `DBG-DA-001` are frozen. Workers
on parallel Refactors must receive disjoint module ownership or an explicit shared-interface
coordination rule.

# Preliminary reuse posture — not a design decision

The CodeReview suggests the following should be evaluated for reuse rather than discarded by
default:

- typed data classes and typed RPC helpers in `DebuggerBackend`;
- `DebuggerSession` connection ownership concept;
- substantial session/event/keepalive behavior in `ExecutiveSession`;
- `SymbolIndex` parsing/lookup behavior after address/path assumptions are formalized;
- existing DAP fixtures/harness tests as regression evidence;
- useful VS Code memory/register/stack/disassembly/trace UX behavior.

The following should **not** be treated as architecture constraints merely because they exist:

- the single-file `HSXDebugAdapter` responsibility layout;
- the single-file `extension.ts` responsibility layout;
- dual `backend/client` state;
- periodic breakpoint/task polling under healthy event support;
- pause/step fallback timers as currently arranged;
- synthetic-stop/duplicate-suppression state model;
- workspace-dependent Python package bootstrap.

`DBG-DA-001` makes the actual reuse/adapt/replace decisions.

# Exit criteria for DBG-GAP-001

- every `DBG-F-001..026` finding is mapped to at least one requirement and remediation owner;
- all structural remediation is blocked behind DesignAnalysis;
- the only pre-design product-code scope is `DBG-RF-001`;
- dependency order is explicit enough for a Master agent to spawn bounded workers/reviewers;
- GitHub issues exist for the Refactors/DesignAnalysis and link back to these IDs;
- `Traceability/CurrentIndex.yaml` points to this active gap analysis.

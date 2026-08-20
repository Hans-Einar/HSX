# DBG-RF-004 — Typed Artifact, Source, Address, Stack, and Inspection

- Status: **ACTIVE — CONTRACTS FROZEN / PRODUCT NOT STARTED**
- Steering authority: issue #38 comment `5362514094`
- Dependency clarification: issue #42 comment `5362515750`
- Sprint/iteration: `DBG-SPR-001` / `DBG-IT-001-005`
- Slices: `DBG-SL-001-005-001..DBG-SL-001-005-006`
- Requirements: `DBG-R-004`, `DBG-R-021..DBG-R-028`, `DBG-R-034..DBG-R-036`
- Findings: `DBG-F-007`, `DBG-F-015`, `DBG-F-017`, `DBG-F-019`, `DBG-F-020`,
  inspection portion of `DBG-F-026`
- Architecture/design: `DBG-A-003`, `DBG-A-004`, `DBG-A-008`, `DBG-D-003`,
  `DBG-D-004`, `DBG-D-009`
- Portable inputs: `HSX-D-001..HSX-D-003`, especially `HSX-D-002`
- Frozen interface: `dbg.resolver-inspection/1`
- Product base: `69a54aeb3394d3cd4792bce620748e15bab69f1f`

## Objective

Implement the side-by-side frontend-neutral services required to bind artifact/source/address/
stack/variables/snapshot-expression/memory/disassembly results to one exact TargetRef, LoadedImageRef, StopEpoch,
StopToken and InspectionSnapshotRef. The result is a typed public interface consumed by later
Refactors, not a DAP/CLI/VS Code migration.

## Frozen contracts and dependency direction

The implementation contract is
`Sprints/001--Debugger_Stabilization/Interfaces/004--Typed_Resolver_Inspection_Interface_v1.md`.
Dependency direction is:

```text
portable identities/descriptors
  -> typed identities/addresses/results
  -> verified artifact index
  -> source resolver
  -> bounded recipes/location/stack
  -> epoch inspection composition
  -> later RF-005/RF-006/RF-007 consumers (still blocked)
```

`DBG-RF-005` explicitly depends on RF-004's **accepted** `dbg.resolver-inspection/1` interface.
Frozen-for-implementation or partially signed Slice state does not satisfy that dependency.

## Anti-monolith and file ownership

RF-004 adds bounded modules under `python/hsx_debugger/`; it does not extend one existing file
into a resolver/inspection monolith.

| Slice | Owned product/test files | Read-only dependencies |
|---|---|---|
| 001 legacy oracle | `python/tests/fixtures/rf004/`, `python/tests/test_hsx_debugger_rf004_legacy_oracles.py` | legacy SymbolIndex/SourceMap/stack behavior |
| 002 identity/address | `identity.py`, `addresses.py`, `results.py`, `test_hsx_debugger_identity.py`, `test_hsx_debugger_addresses.py` | frozen HSX/Debugger contracts; existing `contracts.py` |
| 003 artifact/index | `artifacts.py`, `legacy_symbols.py`, `test_hsx_debugger_artifacts.py` | signed Slices 001-002; legacy SymbolIndex read-only |
| 004 source resolver | `sources.py`, `test_hsx_debugger_sources.py` | signed Slices 001-003; legacy SourceMap read-only |
| 005 recipes/stack | `recipes.py`, `stack.py`, `test_hsx_debugger_recipes.py`, `test_hsx_debugger_stack.py` | signed Slices 001-004; snapshot test doubles only |
| 006 inspection | `handles.py`, `inspection.py`, `test_hsx_debugger_inspection.py` | signed Slices 001-005; existing epoch/controller contracts read-only |

`python/hsx_debugger/__init__.py` may receive public exports only in the Slice that owns the
exported implementation, with no import-time behavior. Shared product files from earlier
Slices become read-only to later workers unless a recorded corrective Slice explicitly owns a
change. The Master coordinates any cross-Slice correction and requires fresh review of all
affected heads.

## Preserved and intentionally changed legacy behavior

Preserve only after Slice 001 classifies and captures executable evidence:

- valid `.sym` v1 parser/index content, instruction-to-source metadata, duplicate-preserving
  lookup order, locals/globals and memory-region concepts;
- SourceMap prefix-map, relocated-root and symlink candidate discovery;
- partial stack/location diagnostics as evidence, not as a fixed ABI implementation.

Change intentionally or retire in the new interface:

- fixed masks/wrap, global lowercase identity, basename aliases/guessing and first-candidate
  selection;
- mutable/recycled frame/scope references and unknown-frame fallback;
- fixed-R7 stack walking without exact ABI/recipe rows;
- independent live reads or current-frame reads represented as one coherent snapshot.

Legacy production files stay unchanged and runnable in this Refactor. RF-004 may add explicit
adapters but may not silently redirect current DAP/CLI product paths.

## Explicit non-goals

- no `python/execd.py`, `platforms/python/host_vm.py`, ExecutiveSession, VM, scheduler, AVR or
  portable-runtime implementation;
- no existing `python/hsx_dap`, `python/hsx_dbg` CLI/backend/session, VS Code, DAP handle or
  frontend policy migration;
- no breakpoint/watch ownership or reconciliation (`DBG-RF-005`);
- no lifecycle/source-step policy (`DBG-RF-006`);
- no raw RPC adapter to SnapshotReadPort and no best-effort live read promoted to coherent;
- no change to frozen `dbg.controller-gateway/1.1`, `DBG-D-*` or `HSX-D-*` contracts.

## Slice plan and gates

1. Slice 001 freezes classified regression/golden evidence before legacy algorithms move.
2. Slice 002 implements the public exact identity/address/result foundation.
3. Slice 003 implements binding-verified immutable artifact/index behavior.
4. Slice 004 implements exact case/content source resolution.
5. Slice 005 implements bounded recipes, locations and stack reconstruction.
6. Slice 006 integrates epoch handles and all inspection surfaces through an immutable
   SnapshotReadPort fixture.

Each Slice is sequential because the next consumes the prior signed public surface. Every
Slice executes:

`fresh worker -> independent exact-head reviewer -> formal verification -> Master sign-off`.

Blocking/High/Medium findings require bounded rework and a fresh review. A frozen-interface or
design contradiction stops product work and returns to Steering; it is not fixed by widening a
Slice or editing frozen contracts during implementation.

## Verification plan

At minimum, evidence across the six Slices covers:

- immutable type/equality validation and mismatch rejection across target/image/binding/epoch/
  snapshot refs;
- multiple address widths/spaces, checked overflow/alignment/range and no hidden mask;
- canonical valid/mismatch/malformed/unsupported bundle and legacy `.sym` cases, duplicate
  symbols/basenames and multiple line addresses;
- NFC/case collisions, content digest/length, prefix/relocation/symlink/override, missing and
  ambiguous source candidates;
- frozen recipe opcodes/limits, corrupt/unsupported/stale/partial outcomes, entry/body/epilogue
  unwind rows, top-level termination and selected non-top-frame locations;
- repeated/paged handle stability, stale/unknown rejection, registers/stack/scopes/variables/snapshot expressions/
  memory/disassembly, exact context matching and cross-service snapshot consistency;
- existing RF-002/RF-003/controller/gateway regression suites remain green;
- YAML/NDJSON/Markdown/diff validation and protected-path diff guards.

Formal verification records are `DBG-VER-001-005-001..006`. Planned Slice reviews are
`DBG-RVW-001-005-001..006`; interface review is `DBG-RVW-001-005-007`. Parent final review and
verification are `DBG-RVW-004-001-001` and `DBG-VER-004-001-001`.

## Retirement gates

RF-004 parent sign-off must state, for each legacy seed, one of:

- **adapted and retained as explicit degraded adapter** with profile, diagnostics and removal
  condition;
- **oracle only** with the new implementation owning behavior;
- **retired from the new interface** while legacy product paths remain for later migration.

No legacy file is deleted in this Refactor. `SymbolIndex` or SourceMap compatibility can be
called accepted only if every classified preserved golden case passes through the typed
adapter and all intentional-change cases produce the frozen typed result.

## Parent completion signal

RF-004 completes only when all six Slices are exact-head signed; the combined head passes
fresh independent parent review and formal verification; `dbg.resolver-inspection/1` coverage
for address/source/stack/variables/snapshot expressions/memory/disassembly is durable; remaining degraded behavior
is explicit; traceability and Handoff agree; and the full signed chain is published remotely.

The Master then posts the Steering decision package to issue #38 and stops. RF-005..009 remain
blocked until a later Steering instruction.

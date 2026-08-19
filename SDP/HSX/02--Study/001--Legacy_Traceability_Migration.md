# HSX-ST-001 — Legacy HSX Traceability Migration Study

- Status: ACTIVE COORDINATING STUDY
- Owner: HSX SDP Master
- Active issue: #47
- Steering activation: comment `5348192567`
- Coordinated Debugger dependency: `DBG-ST-006`, issue #38
- Iteration: `DBG-IT-001-003`

## Purpose

Migrate the useful legacy HSX study/requirements/architecture/design material into the new
HSX SDP track without losing provenance or letting old implementation notes become accidental
requirements.

## Required inventory

- legacy `DR-*` non-negotiable requirements;
- legacy `DG-*` design goals;
- legacy optional `DO-*` items;
- ISA/workspace/ABI decisions;
- HXO/HXE and toolchain contracts;
- VM/executive/scheduler/mailbox/value-command contracts;
- Python reference implementation behavior and test evidence;
- known design gaps and unresolved questions;
- debugger dependencies that should become cross-track relations rather than HSX debugger
  requirements;
- stable HSX IDs/contracts for the portable address model and debugger execution semantics
  currently required by `DBG-R-023` and `DBG-R-016..DBG-R-020`;
- future embedded-port constraints that belong in AVR rather than HSX core.

## Output

- stable `HSX-R-*`, `HSX-A-*`, `HSX-DA-*`, and `HSX-D-*` mappings;
- explicit legacy-ID provenance table;
- CurrentIndex/Relations/Ledger baseline;
- identification of any required new Studies before portable HSX design is considered frozen.

## Active priority phase — portable debug runtime contracts

The broad migration inventory remains the coordinator, but the current bounded priority is to
establish provenance and stable contract proposals for the portable runtime behavior required
by `DBG-ST-006`. Unrelated HSX domains remain inventoried/routed rather than redesigned here.

Five first-class Studies own the natural contract domains:

- `HSX-ST-002` — runtime identity, generations, lifecycle and ownership;
- `HSX-ST-003` — address spaces, ABI, unwind and variable locations;
- `HSX-ST-004` — run/stop evidence, snapshots, exact stepping and blocked-state inspection;
- `HSX-ST-005` — event stream cursor, ACK, gaps, drops and capability profiles;
- `HSX-ST-006` — breakpoint/watch identity, provenance, revisions and reconciliation.

## Current phase outputs

- explicit DR/DG/DO and legacy design/code/test provenance for each portable contract;
- stable proposed `HSX-R-*`, `HSX-A-*`, and `HSX-D-*` IDs allocated by Master synthesis;
- conformance-fixture plans and current/degraded/target behavior labels;
- complete mapping back to all ten `DBG-ST-006` questions and `DBG-D-002..DBG-D-006`;
- HSX CurrentIndex/Relations/Ledger and independent review `HSX-RVW-001-001-001`.

## Current phase guard

No product, debugger Refactor, or AVR implementation is authorized. Study workers own only
their assigned documents. Master owns stable ID allocation, shared traceability, contract
synthesis, and issue coordination.

This study does not redesign HSX and does not authorize implementation changes.

# HSX-ST-001 — Legacy HSX Traceability Migration Study

Status: PLANNED  
Owner: HSX SDP Master

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
- future embedded-port constraints that belong in AVR rather than HSX core.

## Output

- stable `HSX-R-*`, `HSX-A-*`, `HSX-DA-*`, and `HSX-D-*` mappings;
- explicit legacy-ID provenance table;
- CurrentIndex/Relations/Ledger baseline;
- identification of any required new Studies before portable HSX design is considered frozen.

This study does not redesign HSX and does not authorize implementation changes.

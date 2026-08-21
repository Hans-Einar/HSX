# DBG-SL-001-005-003 — RF-004 Verified Debug Artifact Index

- Status: **FROZEN / PLANNED**
- Parent: `DBG-RF-004`
- Iteration: `DBG-IT-001-005`
- Depends on signed: `DBG-SL-001-005-001..002`, `DBG-SL-001-005-007`
- Review: `DBG-RVW-001-005-003`
- Verification: `DBG-VER-001-005-003`

## Goal and why now

Implement an immutable binding-verified artifact/index service, separate from local source
resolution and live target inspection, plus an explicitly degraded adapter for classified
legacy `.sym` evidence.

## Owned files

- `python/hsx_debugger/artifacts.py`
- `python/hsx_debugger/legacy_symbols.py`
- relevant additive exports in `python/hsx_debugger/__init__.py`
- `python/tests/test_hsx_debugger_artifacts.py`

Legacy `python/hsx_dbg/symbols.py`, source mapping, runtime and frontend files are read-only.

## Required behavior

- construct only from exact ImageDebugBinding and verified component/schema refs;
- require exact ArchitectureDescriptor/AbiDescriptorRef and pass shared DebugBindingValidator
  before validating typed address/range/recipe rows or publishing an index;
- parse recipe-bearing rows only through Slice 007's signed pure DTO/validator surface;
- require every UnwindRow/LocationRow ABI to equal the validated accepted ABI;
- reject artifact, bundle, binding, architecture, ABI, recipe or component mismatch without
  publishing an index;
- preserve all duplicate symbol/name/line candidates and exact source identity/spelling;
- keep FUNCTION/LABEL addresses separate from addressless LOCAL/GLOBAL/CONSTANT variable
  identities; represent every variable location only through exact nullable-scope LocationRow;
- expose typed functions, symbols, instructions, SourceRefs, memory regions, unwind rows and
  location rows using typed addresses/ranges, plus type records, lexical scopes and exact
  scope/global variable enumeration;
- reject malformed/overlapping/unsupported metadata with frozen result categories;
- legacy adapter validates `.sym` v1 plus supplied HXE CRC evidence, uses explicit descriptor
  conversion, preserves candidates and returns only separate LegacyDebugArtifactIndex /
  LEGACY_UNVERIFIED provenance with no ImageDebugBinding, SourceRef or portable recipe rows;
- no basename alias, lowercase identity, hidden mask or first-candidate preference.

## Invariants and non-goals

- no local filesystem candidate choice, source content reads, stack walking or inspection;
- no mutation/cache refresh after index construction;
- no claim that `.sym` is `hsx.debug.image-bundle/1` conformant;
- no legacy production path switch or RF-005..009/runtime/frontend work.

## Traceability

`DBG-R-021`, `DBG-R-023..DBG-R-025`, `DBG-R-028`, `DBG-R-034..DBG-R-036`;
`DBG-F-015`, `DBG-F-019`, `DBG-F-020`; `DBG-D-003`, `DBG-D-004`, `DBG-D-009`;
`HSX-D-002`; interface `dbg.resolver-inspection/1.1`.

## Verification and completion signal

Test canonical binding/component success and every mismatch, malformed/unsupported schemas,
multiple spaces/widths, duplicate symbols/basenames, multiple line addresses, memory regions,
row overlaps and exact legacy-golden preservation/change cases. Run legacy SymbolIndex tests
unchanged. Close only after exact-head review, formal verification and Master sign-off.

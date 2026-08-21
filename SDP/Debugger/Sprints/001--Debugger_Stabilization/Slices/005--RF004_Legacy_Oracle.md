# DBG-SL-001-005-001 — RF-004 Legacy Oracle Classification

- Status: **ACTIVE / FRESH WORKER DISPATCH**
- Parent: `DBG-RF-004`
- Iteration: `DBG-IT-001-005`
- Review: `DBG-RVW-001-005-001`
- Verification: `DBG-VER-001-005-001`

## Goal and why now

Create executable, classified regression/golden evidence before adapting legacy SymbolIndex,
SourceMap or stack/location behavior. This Slice changes tests/fixtures only and gives later
workers a precise preserve/change/retire oracle.

## Owned files

- `python/tests/fixtures/rf004/`
- `python/tests/test_hsx_debugger_rf004_legacy_oracles.py`

Legacy product modules and every existing test are read-only.

## Required cases

- preserve: `.sym` v1 instruction/source metadata, duplicate-preserving symbol/line order,
  functions, labels, locals, globals and memory regions where present;
- preserve: SourceMap explicit prefix map, relocated root, symlink and exact requested path;
- preserve as diagnostic evidence: partial stack/location outputs already asserted by legacy
  executive tests;
- intentional change: addresses above 16 bits, case-colliding logical paths, duplicate
  basenames, multiple line candidates, malformed/version/image mismatch, unknown frame and
  mixed-read snapshot behavior;
- retire: hidden masks, unconditional lowercase identity, basename/first-candidate guessing,
  unknown-frame fallback and fixed live-current-state assumptions.

Each golden entry records `preserve`, `change_intentionally`, or `retire`, source provenance,
exact current output where useful, and the frozen target expectation/category. Known-bad
behavior is confined to the named legacy oracle and is never imported as target conformance.

## Invariants and non-goals

- no product/runtime/extension/SDP-shared-trace edits by the worker;
- no new resolver/index implementation;
- fixtures contain no host-specific absolute locator as stable identity;
- no broad rewrite of legacy tests;
- no RF-005..009, Executive, VM, AVR, DAP or VS Code work.

## Traceability

`DBG-R-024`, `DBG-R-034`, `DBG-R-036`; `DBG-F-007`, `DBG-F-019`, `DBG-F-020`;
`DBG-D-004`, `DBG-D-009`; interface `dbg.resolver-inspection/1`.

## Verification and completion signal

Run the new oracle test plus existing symbol/source/stack-oracle tests, validate fixture
determinism and ensure the diff is test/fixture-only. The Slice completes only after fresh
exact-head review, formal verification and Master sign-off.

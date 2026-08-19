# DBG-RF-001 — DAP Protocol Baseline Stabilization

- Status: IMPLEMENTATION COMPLETE — AWAITING INDEPENDENT REVIEW
- Owning issue: #37
- Steering gate: #36 — accepted against PR #49 head
  `403d55c621d50212940b4c8668ac20a3cf8519b5`
- Parent: `DBG-GAP-001`
Reviewed product baseline: `Implementation/vscode` at
`a1daa1c62605c44ac67e58e2b71320006f73cdd9`

## Goal

Repair only the P0 DAP protocol and product-entrypoint defects required to make the real
VS Code adapter path a trustworthy regression baseline before architecture work.

## Traceability

- Findings: `DBG-F-001`, `DBG-F-002`, `DBG-F-003`
- Requirements: `DBG-R-001`, `DBG-R-002`, `DBG-R-032`
- Initial evidence obligations: `DBG-R-033`, `DBG-R-036`
- Sprint: `DBG-SPR-001`
- Iteration: `DBG-IT-001-001`
- Slice: `DBG-SL-001-001-001`
- Independent review: `DBG-RVW-001-001-001`
- Verification: `DBG-VER-001-001-001`

## Scope and owned modules

- `vscode-hsx/debugAdapter/hsx-dap.py`
- `python/hsx_dap/__init__.py`
- `python/tests/test_hsx_dap_cli.py`
- existing DAP harness/backend tests only where assertions or fixtures must be adjusted for
  the corrected protocol order/product entrypoint
- owning Debugger SDP sprint, traceability, verification, and handoff records

## Required behavior

- stdout from the production adapter path contains only correctly framed DAP messages;
- diagnostics use stderr or the configured log file;
- the initialize response is written before the `initialized` event;
- black-box subprocess coverage launches the exact wrapper used by VS Code;
- the test fails on a non-DAP preamble or any other unframed stdout bytes;
- the existing attach/launch handshake fixture remains functional through that wrapper.

## Invariants

- preserve all unrelated legacy debugger behavior;
- preserve existing CLI flags, imports, executive/RPC behavior, DAP handlers, and extension
  launch arguments unless the three owned defects require a narrowly documented adjustment;
- do not change HSXE/ISA/VM/executive semantics;
- do not make the current monolith shape an accepted architecture.

## Non-goals

- no debugger-controller/state-machine redesign;
- no stepping, lifecycle-ownership, breakpoint/watch, reconnect, symbol, source, address, or
  packaging redesign;
- no module decomposition except the minimum needed for the three defects;
- no structural work from `DBG-RF-002..DBG-RF-009`;
- no work from `DBG-DA-001`.

## Slice plan

This Refactor has one domain-contained Slice: `DBG-SL-001-001-001`. It is allowed to remain
within the DAP protocol/product-entrypoint domain because its external behavior and
verification boundary are complete and coherent. Its later vertical integration point is
`DBG-DA-001` and the structural Refactors; no temporary architecture introduced here may
constrain those designs.

## Completion signal

- product wrapper passes black-box initialize plus launch/attach handshake evidence;
- stdout purity is asserted at the byte/framing boundary;
- required regression tests pass on the exact implementation head;
- independent reviewer records PASS with no Blocking/High/Medium findings;
- `DBG-VER-001-001-001` records exact commands/platform/results;
- Master signs off the exact commit in issue #37 and traceability;
- only then may `DBG-DA-001` move from blocked to its Steering/design gate.

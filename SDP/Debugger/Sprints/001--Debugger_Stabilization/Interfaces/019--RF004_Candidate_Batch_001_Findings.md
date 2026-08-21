# RF-004 candidate batch 001 — findings and classification

Status: **CANDIDATE EVIDENCE / NOT SIGN-OFF**

Tester authority: issue #38 `HSX | TESTER -> MASTER | RF-004 candidate batch 001 result`, comment `5375376247`.
Exact tested candidate: `6bd0095c607f2517d6d3a70e8d58c783b1bb2d79`.
Authoritative PR #50 head remains `46169516058aadf0e691a5981e29da4954b7444f`.

## Confirmed good evidence

- candidate AST/import phase passed;
- `dbg.resolver-inspection/1.3` focused tests: 6 PASS;
- unchanged signed RF-004 regression surface: 159 PASS / 3 existing skips;
- broad Python aggregate reached 532 PASS / 3 skips with one unrelated shell-client baseline failure;
- no tracked mutation was caused by read-only execution.

## Product findings

### C001 — contract Enum bootstrap depends on import order

Isolated Stack/Handle/Inspection tests failed while the broad aggregate mostly passed because
`EvidenceGrade.PORTABLE`, nested inside `GenerationStamp`/`InspectionContext`, was not
deterministically admitted to the RF-004 contract-safe Enum registry. Earlier test imports could
accidentally register it and hide the failure.

Disposition: **FIX IN CANDIDATE**. Package bootstrap must register the exact closed
`hsx_debugger.contracts.EvidenceGrade` independently of test/import order.

### C002 — StackService touches register port before read-set fence

`StackService._read_top_seed()` called `SnapshotReadPort.read_registers()` without first proving
that the exact snapshot advertises `registers` coverage.

Disposition: **FIX IN CANDIDATE**. Require the exact read-set before any port I/O.

### C003 — Inspection register selection validated after port I/O

An unknown register selection reached `read_registers()` and was classified as a port contract
failure instead of deterministic `register_selection_invalid` before I/O.

Disposition: **FIX IN CANDIDATE**. Validate selection against `ArchitectureDescriptor` after the
session stale gate but before read-set/port I/O.

## Test findings

### T001 — closed-service expectation was wrong

The candidate test expected STALE after `InspectionService.close()`. The frozen lifecycle
contract states that a closed service rejects every later `open_epoch()` as
`UNAVAILABLE/inspection_service_closed`.

Disposition: **FIX TEST**; product behavior was correct for the tested valid-context case.

### T002 — missing instruction metadata must not fabricate call-site

A candidate guard expected `resume_pc-4` to be published even when no instruction metadata
proved the candidate address. `HSX-D-002` requires aligned/same-image evidence that the address
names a CALL. Missing semantic evidence therefore cannot produce `call_site_pc`.

Disposition: **FIX TEST**. Preserve exact `resume_pc`; `call_site_pc=None` without proof.

## Promotion-only gaps

### P001 — exact symbol-ID query

`dbg.resolver-inspection/1.5` requires real `DebugArtifactIndex.symbol_by_id(symbol_id)`.
Inspection test doubles expose the seam, but the signed Slice003 class does not yet.

Disposition: **PROMOTION BLOCKER**, not permission for private `_symbols` access or broad rewrite.

### P002 — LocationRow TypeError spelling

`RecipeComponentValidator.validate_location_row(object(), ...)` currently says
`row must be UnwindRow`; the exact public error should name `LocationRow`.

Disposition: **PROMOTION CLEANUP**; functional behavior is otherwise unaffected.

## Unrelated baseline

`python/tests/test_shell_client.py::test_pretty_dmesg_assigns_session_numbers` remained the only
broad Python failure. It is outside RF-004 scope and is not to be repaired from this candidate.

## Gate

None of these candidate results constitute Slice005/006 review, verification, sign-off, or PR
promotion. Fresh independent review remains required before authoritative history moves.

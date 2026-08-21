# DBG-SPR-001 Implementation Notes

Record verified work only.

## DBG-VER-001-001-001

`DBG-SL-001-001-001` is verified on Windows and has Master exact-head sign-off.

- exact reviewed implementation head:
  `208063e344b767f82790ce579eba6327e2cdd0ce`;
- exact repository head tested:
  `fefd4b0c427dfa71d637e4f4cce9e4a345912591`;
- no product/test diff exists between those heads;
- targeted DAP CLI/harness/backend tests: `36 passed`;
- production-wrapper initialize ordering plus launch/attach: `3 passed`;
- raw preamble and trailing-byte negative controls: `2/2 rejected`;
- broad suite: `534 passed, 2 skipped, 2 failed`, with both failures classified outside the
  Slice;
- Debugger traceability YAML and Ledger NDJSON validation: PASS;
- independent review `DBG-RVW-001-001-001`: PASS with no findings.

Linux product-wrapper evidence remains assigned to `DBG-RF-009`; no Linux PASS is claimed.

## Master sign-off

Master exact-head reconciliation accepted implementation head
`208063e344b767f82790ce579eba6327e2cdd0ce` after PASS records
`DBG-RVW-001-001-001` and `DBG-VER-001-001-001`. `DBG-RF-001` and
`DBG-SL-001-001-001` are complete. Issue #38 / `DBG-DA-001` is the next gate and has not
started; structural product-code work remains blocked pending accepted design contracts.

## DBG-IT-001-004 verified and signed state

- Frozen `dbg.controller-gateway/1.1` interface review PASS at `0cf52fcf…`.
- Corrected RF-002 Slice review/verification/sign-off PASS at `a064020…`.
- Corrected RF-003 Slice review/verification/sign-off PASS at `1e47953…`.
- Unchanged integration code at `860a98a…` passed dependent review/verification/re-sign-off
  against combined head `1e47953…`.
- Parent final reviews and formal verifications PASS; RF-002 and RF-003 parent exact-head
  sign-offs complete.

## DBG-IT-001-004 final accepted state

- RF-002 signed product `a0640203a1a87c7acb080c75286ef09808e5195c`, RF-003/combined
  product `1e479536ce5e746e1b06a53b1039b1af84adaed6`, integration code
  `860a98a68440b8e22b67f03fbdbb93d2dd33ab7a`, parent sign-off
  `f52447ab7dcf6b1ddcca5934be0c8516d5255a14` and final publication head
  `69a54aeb3394d3cd4792bce620748e15bab69f1f` are remote-resolvable.
- Fresh-checkout publication evidence: `121 passed`, traceability/clean-tree/object checks PASS,
  and no non-SDP product diff after the combined signed head.
- Steering accepted RF-002, RF-003 and dependent integration complete for this stabilization
  stage in issue #38 comment `5362514094`.
- The frozen `dbg.controller-gateway/1.1` interface remains authoritative.

RF-004 activation/contracts themselves are planning state; verified RF-004 execution begins
with the Slice 001 record below.

## DBG-SL-001-005-001 verified legacy oracle

- exact signed head: `8e5669940dd5c23df532577c39dc10bd84692ad2`;
- interface review `DBG-RVW-001-005-019`: PASS;
- Slice review `DBG-RVW-001-005-020`: PASS;
- formal verification `DBG-VER-001-005-009`: PASS after trace-only attempts 001/008;
- 29 classified cases: 13 preserve, 8 intentional-change, 8 retire; all legacy outputs are
  explicitly non-target-conformant;
- oracle 16 passed/1 explicit WinError 1314 skip; symbols 2 passed; source map 4 passed/1 same
  skip; focused 14 passed; hashseed 0/1 repeats PASS;
- exact owned/protected scope, trace, hashes, ancestry, objects/connectivity and remote/clean
  evidence: PASS.

Windows symlink behavior remains degraded/unverified on this host; no symlink PASS is claimed.

## DBG-SL-001-005-002 verified identity/address/result foundation

- exact signed product head: `c7bc39057469f1aa62a78f409753ec0213631214`;
- Steering-refrozen `dbg.resolver-inspection/1.1` review `DBG-RVW-001-005-030`: PASS;
- post-refreeze product review `DBG-RVW-001-005-027`: PASS;
- formal verification `DBG-VER-001-005-002`: PASS;
- exact public schemas/classes/fields/Enum members/aliases and 129 exports preserved;
- exact private 19-type Enum catalog and supported recursive contract-safe payload boundary;
- focused 47, debugger 184+1, mandated 39+1, oracle 16+1, canonical 2, hashseed 0/1 PASS;
- exact five-file correction scope, trace, ancestry, objects/connectivity and remote/clean PASS.

Windows symlink behavior remains the sole degraded skip. Slice 002 has Master exact-head
sign-off and authorizes only Slice 007 recipe foundation next.

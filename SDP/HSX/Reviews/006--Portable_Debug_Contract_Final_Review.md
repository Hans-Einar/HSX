# HSX-RVW-001-001-006 — Portable Debug Contract Final Review

- Status: **PASS**
- Exact proposal-content head reviewed: `b57e368f77bb533b09397d633fc92565655e1668`
- Trace-only assignment head inspected: `24beb825b40ccafb9391019f7bd7530e388cd675`
- Reviewer role: fresh independent cross-track architecture/contract reviewer
- Issues: #47 / #38; assignment comments `5355069576` / `5355069733`
- Product/AVR authority: **NONE**

## Result

PASS with no Blocking, High, or Medium findings. The reviewed package is ready for Master
verification and issue decision packages. This review does not accept or freeze any HSX or
Debugger contract and grants no product, Refactor, native, or AVR implementation authority.

## Exact-content and scope result

- HEAD was clean at the assigned trace commit before review.
- `b57e368f77bb533b09397d633fc92565655e1668..24beb825b40ccafb9391019f7bd7530e388cd675`
  changes exactly eleven HSX/Debugger CurrentIndex, Issues, Ledger, Handoff, README, and Scrum
  files. No Study, Requirement, Architecture, Design, appendix, review-history, product, test,
  package, or AVR file changed after the proposal-content anchor.
- The complete proposal package from `c0003d070c6840f0d55487d73b227880cfd27494`
  through the assignment head is SDP-only. `git diff --check` passed.

## Review-005 finding closure

### f16 target versus current nonconformance — PASS

`hsx.abi.llc-r7-word32/1` consistently keeps the portable rule that an f16 word has zero upper
16 bits. `HSX-ST-007`, `HSX-R-016`, `HSX-D-002`, and `DBG-ST-006` all classify current Python
`FADD`/`FSUB`/`FMUL`/`FDIV`/`I2F` destination-upper-half preservation as
`hsx.python-debug-legacy/1` nonconformance and require the allocator-reuse upper-zero fixture
as its removal gate.

Independent code inspection confirmed all five VM paths preserve the destination upper half.
An independently compiled allocator-reuse probe poisoned `R4` with `0x12340000`, reused it as
the FADD result register, and returned half-zero as `R0=0x12340000`, rather than the portable
target `0x00000000`. The documented failing/removal fixture is therefore precise and truthful.

### canonical structured-digest interoperability — PASS

The normative appendix and `HSX-ST-008` agree on:

- the six literal, case-sensitive UTF-8 domain tags and the required `0x00` separator;
- schema-typed integer fields as minimal signed/unsigned decimal JSON strings, exact lowercase
  Hex64 digests, and opaque NFC IDs that are never numerically reformatted;
- duplicate raw/NFC-key rejection, NFC normalization, Unicode-scalar key ordering,
  schema-defined array ordering, source/set UTF-8 ordering, direct UTF-8 output, exact quote
  and backslash escapes, no slash/`\u` canonical escapes, and C0/DEL/lone-surrogate rejection;
- JSON number, float, null, alternate integer, malformed digest, and unknown-mandatory-field
  rejection, with only schema-declared booleans admitted;
- exact self-field/signature/timestamp/local-locator exclusions by identity payload schema;
- the nonrecursive construction graph: exact bytes -> ArtifactRef; independent
  LoadedImageRef and reusable bundle ref; target-specific binding last.

Independent Python and Node/JavaScript implementations reproduced the exact canonical bytes
and all four SHA-256 values:

1. `6caa23594d6f57fb795a2e73648f5c8ed9928a5e25798d3bb48545412ca164a0`
2. `767ad5f9e1ae49abdc33dfd990e81fc3a5a6b064e23d2e44992dfe20f0d94a73`
3. `61bc53ef9bf46d87dd6f434ddb43e9307921751faa37471323ea734f87105007`
4. `b84f9e6618dea2f8c688bc4930a9915c80c1eea1be22b4233375616d272472f2`

Both implementations also passed representative lexical, NFC, direct-UTF-8 escaping,
control/surrogate, digest-case, domain-tag and separator negative checks. The appendix's
negative forms are coherent with `HSX-ST-008`; serializer conformance does not make the zero
fixture values trusted artifact/component evidence.

### exact-head and next-gate reconstruction — PASS

Review 005 and exact SHA `84df21d763b73209efd0292990799f469283460a` are durable in its
review record, both Issues/CurrentIndexes/Ledgers, both Handoffs, Scrum, and issue comments.
Proposal-content SHA `b57e368f77bb533b09397d633fc92565655e1668` and the trace assignment
head are durably separated. Before this PASS record, `HSX-RVW-001-001-006` was the sole active
review gate across the current HSX/Debugger status surfaces.

## Prior-review and ten-domain regression result

All earlier closures remain consistent:

- opaque target-bound never-reused LoadedImageRef is distinct from ArtifactRef and reusable
  bundle identity;
- lifecycle, generations, ownership leases, observer enforcement, exact mutation fencing,
  atomic launch and tombstones fail closed;
- typed code/data/register address domains, checked ranges, exact ABI/frame rules, bounded
  unwind/location recipes and revision-fenced register mutation remain explicit;
- receipts, state, transition evidence and stable stops remain separate; exact step reports
  zero/one retirement and phase-linearized causes; WAIT_MBX/SLEEPING are not inherently stable;
- filter-safe stream cursors, atomic publish order, ACK-after-apply, typed gaps/resume/health
  and reconcile baselines remain coherent;
- remote resource IDs, provenance, owner/effective/inventory revisions, sharing, tombstones,
  adoption, live-watch separation and conservative legacy cleanup remain owner-safe;
- the synthesized capability registry is consistent between HSX Architecture/Design and the
  Debugger dependency boundary; current/degraded/unsupported behavior is explicit;
- all ten `DBG-ST-006` questions map to stable proposed HSX contracts and fixtures;
- `HSX-R-001..036`, `HSX-A-001..005`, and `HSX-D-001..005` are complete and unique;
- Relations/Ledgers preserve history and all product, Debugger design-freeze, RF, native and
  AVR guards remain closed.

## Independent evidence

- resource/session/debugger oracle set: `114 passed`;
- address/ABI/artifact oracle set: `40 passed, 1 skipped, 53 deselected`;
- execution/snapshot/mailbox set: `99 passed`; fault/terminal set: `7 passed`;
- supplemental ABI sets: `15 passed`; `7 passed, 56 deselected`;
- bundle/source set: `18 passed, 1 skipped`;
- eight traceability YAML files parsed with duplicate/NFC-key guard;
- two Ledgers parsed as 55 NDJSON records before this review record; review-005 rework added
  two append-only records per track and assignment added one per track;
- 51 SDP Markdown files, 124 tables, fences and local links passed structural validation;
- stable definitions: 36 requirements, 5 architecture IDs, 5 design IDs; ten DBG mappings;
- complete proposal and assignment scope are SDP-only; `git diff --check` passed.

The two skips are the already documented environment-dependent Windows source-map symlink
cases. No Linux product-runtime PASS is claimed by this contract review.

## Next gate and guards

The next status is
`reviewed_package_pending_master_verification_and_issue_decision_packages`. Master must verify
this review record and exact review-record commit, then prepare the durable issue #47/#38
decision packages. This reviewer does not claim Master verification, Steering acceptance,
design freeze, implementation authority, or exact-head sign-off.

All `HSX-R-*`, `HSX-A-*`, `HSX-D-*`, `DBG-D-001..DBG-D-010`, and the digest appendix remain
target/proposed. `DBG-RF-002..DBG-RF-009`, product code, native implementation and AVR work
remain blocked.

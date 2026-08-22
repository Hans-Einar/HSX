# SDP Process Proposal 001 — Review-Triggered Nested Remediation

Status: **PROPOSAL / NOT NORMATIVE**

Coordination issue: #57.
Evidence case: Debugger `DBG-RF-004`, issue #38, independent review `DBG-RVW-001-005-037`.

## Problem

The normal SDP product loop is intentionally strict:

`Feature/Refactor -> Slice -> Worker -> independent Review -> Verification -> exact-head Sign-off`.

A late independent review can nevertheless find a material defect whose ownership is narrower
than the parent Refactor but larger than an ordinary local review correction. If that finding is
silently fixed inside the parent, durable ownership and verification boundaries are lost. If the
parent is abandoned in favor of a new unrelated Refactor, the original dependency chain is also
lost.

The process needs an explicit way to suspend the parent, remediate the discovered boundary, and
return to the parent gate without confusing the remediation with the main roadmap.

## Proposed model

### 1. Review remains an evidence snapshot

A formal `RVW-*` is read-only against an exact head. The reviewer publishes findings before any
role switch or mutation.

A reviewer that later becomes a WORKER is no longer independent for any head it changes. A fresh
reviewer is required for that changed head.

### 2. Route findings by ownership, not merely severity

Local Low/Note findings normally stay as bounded rework in the existing Slice/Feature/Refactor
when all of the following are true:

- no accepted public contract changes;
- no responsibility/state/concurrency ownership moves;
- no cross-Slice dependency is introduced;
- verification remains local and obvious.

A Medium/High/Blocking finding, or any finding that crosses a public contract, state/concurrency
boundary, module responsibility or independently verifiable ownership domain, is routed through:

`new CodeReview snapshot -> new GapAnalysis -> corrective child Refactor(s)`.

Severity is evidence for routing, not the sole criterion. A structurally important Low may still
require the child flow; a purely local Medium may be kept local only with an explicit Master/
Steering rationale.

### 3. Parent authority is suspended, not replaced

The parent Feature/Refactor remains the owning product objective and enters a status such as:

`SUSPENDED_AT_REVIEW_GATE / CORRECTIVE_CHILD_ACTIVE`.

The corrective child declares:

`corrective_child_of: <parent ID>`.

It must state the exact parent reviewed head, origin review/finding, owned modules/contracts,
non-goals, verification signal and return gate.

Planned roadmap IDs are never renumbered. Corrective children use the next unallocated IDs.

### 4. Fan out by responsibility

A CodeReview/GapAnalysis may produce more than one corrective child when findings have distinct
module ownership or verification boundaries. Do not create one catch-all remediation Refactor
merely because the findings came from one review.

Each child retains the normal SDP discipline:

`contract -> bounded implementation -> fresh review -> verification -> exact-head sign-off`.

### 5. Return to the parent

Corrective children do not become a replacement mainline. Once their exact corrections are
accepted, reconstruct or integrate them in the original dependency/Slice order and return to the
parent's review gate.

The parent then receives a fresh exact-head review that proves:

- the original review findings are closed;
- corrective children did not broaden scope;
- parent invariants/contracts still hold together;
- traceability identifies the child round trip;
- later roadmap work remains blocked until the parent completes.

### 6. Staging branches are allowed but are not authority

For execution efficiency, multiple disjoint corrective implementations may be developed and
tested on one staging branch. This does not erase dependency order.

Before sign-off/promotion, the work must be reconstructed so each independently owned child/Slice
has a reviewable exact head and the original parent DAG is restored.

### 7. Nesting bound

One corrective nesting level is the normal maximum.

If a corrective child itself discovers a new structural/public-contract issue that appears to
need another child Refactor, stop and return to Steering. This avoids unbounded recursive
Refactor trees and forces reconsideration of whether the parent design/gap decomposition is still
valid.

## Suggested durable relations

Possible traceability relation names:

- `review_of`
- `finding_from`
- `gap_from_review`
- `corrective_child_of`
- `addresses_finding`
- `blocks_parent_review`
- `returns_to_parent_gate`
- `superseded_by_correction_head`

These names are illustrative until the normal traceability schema is reviewed.

## Role discipline

### REVIEWER

- reads/reviews exact head;
- does not mutate reviewed head;
- publishes stable finding IDs, severity, evidence and required boundary;
- may recommend routing but does not self-authorize product changes.

### MASTER

- classifies routing against accepted process/Steering policy;
- creates CodeReview/Gap/child Refactor records when required;
- freezes owned scope and dependency order;
- may implement only when the project explicitly permits a Master corrective-work exception;
- never counts its own implementation analysis as independent review.

### WORKER

- may implement a bounded local correction after review publication;
- if the same agent previously reviewed the parent, its role switch is recorded and its
  independence is considered spent for the changed head.

### TESTER / VERIFIER

- TESTER may provide read-only execution evidence without becoming a reviewer;
- formal VERIFICATION occurs only after the applicable independent review gate passes unless a
  track contract explicitly defines another sequence.

## Example — DBG-RF-004

```text
DBG-RF-004 frozen candidate
        |
        v
DBG-RVW-001-005-037 (read-only)
        |
        +-- DBG-F-027 Medium --> DBG-CR-002 / DBG-GAP-002 --> DBG-RF-010
        |
        +-- DBG-F-028 Medium --> DBG-CR-002 / DBG-GAP-002 --> DBG-RF-011
        |
        +-- DBG-F-029 Low -------------------------------> bounded parent rework

DBG-RF-010 review/verify/sign --+
                               |
DBG-RF-011 review/verify/sign --+--> reconstruct RF-004 DAG --> fresh RF-004 review
                               |
bounded Low correction --------+
```

The frozen candidate remains durable evidence and is not rewritten. The remediation staging
branch is not promoted wholesale.

## Questions before making this normative

1. Should the `corrective_child_of` relation become mandatory schema or remain a documented
   relation convention?
2. Should every Medium finding require `CR -> GAP -> RF`, or should tracks be allowed to keep a
   demonstrably local Medium in the parent with explicit Steering rationale?
3. Should corrective child Refactors receive their own Slice IDs, or may a child whose boundary
   is exactly one existing parent Slice reuse that parent Slice identity while adding a child-RF
   relation?
4. Which traceability surfaces must be synchronized at child activation versus child sign-off?
5. Should one-level nesting be a hard global rule or a Steering-default rule that tracks may
   override?

## Adoption gate

Do not copy this proposal into normative `SDP/Shared/Process.md` until:

- the DBG-RF-004 Routing-C cycle has completed;
- the resulting review/verification history has been assessed for clarity and overhead;
- Steering accepts or amends the proposal;
- traceability schema implications are resolved.

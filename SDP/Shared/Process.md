# Shared SDP Process

This file defines the common process used by the HSX, Debugger, and AVR SDP tracks.
Track-specific requirements and designs remain in their own directories.

## Stable artifact classes

Each track may use the following ID classes, prefixed by the track namespace:

- `ST-###` — Study or evidence-gathering investigation
- `R-###` — Requirement
- `A-###` — Architecture decision/boundary
- `DA-###` — Design analysis
- `D-###` — Accepted detailed design decision/contract
- `CR-###` — CodeReview
- `F-###` — CodeReview finding
- `GAP-###` — GapAnalysis
- `RF-###` — Refactor workstream
- `SPR-###` — Sprint
- `IT-###-###` — Iteration
- `SL-###-###-###` — bounded implementation slice
- `RVW-###-###-###` — independent review record
- `VER-###-###-###` — verification record

Examples: `DBG-ST-001`, `DBG-R-004`, `DBG-F-001-003`, `DBG-RF-002`,
`HSX-R-012`, `AVR-VER-001-001-001`.

IDs are never recycled after they have been referenced by traceability or an issue.

## Numbered Studies

A track may have multiple Studies. Each Study receives its own stable `ST-###` ID and
must state:

- question/scope;
- evidence sources;
- findings and uncertainty;
- conclusions/decisions;
- affected or proposed requirements;
- open questions;
- traceability relations.

This allows later Studies to extend or supersede narrow conclusions without rewriting
older evidence history.

## Existing-code remediation flow

### 1. CodeReview

A CodeReview is an evidence snapshot of an identified code baseline. It records:

- exact branch/commit or other provenance;
- review scope;
- findings with severity and stable finding IDs;
- observed behavior and evidence;
- suspected ownership/design causes;
- what is explicitly not concluded yet.

The CodeReview must not silently redesign the system.

### 2. GapAnalysis

GapAnalysis compares the reviewed baseline against accepted or proposed requirements.
For each finding it records:

- requirement(s) affected;
- actual behavior/structure;
- required behavior/structure;
- risk;
- whether the gap is correctness, architecture, maintainability, verification,
  traceability, packaging, or UX;
- proposed remediation domain;
- dependencies on other gaps/refactors.

### 3. Refactor fan-out

A GapAnalysis should spawn multiple Refactors when findings have independent ownership
or verification boundaries. Do not create one catch-all refactor merely because the
findings came from one CodeReview.

Each Refactor must have:

- one stable `RF-###` ID;
- requirements and findings addressed;
- dependencies and ordering;
- accepted DesignAnalysis/Design inputs when structure changes;
- explicit owned modules and non-goals;
- compatibility behavior that must be preserved;
- verification plan;
- completion signal.

### 4. Design before structural implementation

Small baseline correctness defects may be fixed before redesign if they are isolated
and necessary to make tests/tooling trustworthy.

Structural changes — responsibility movement, module boundaries, state ownership,
protocol/lifecycle redesign, concurrency model, or public interfaces — require a
DesignAnalysis followed by an accepted Design contract before a worker implements them.

### 5. Worker / Reviewer / Sign-off

For each product-code Refactor or Slice:

1. Master freezes the contract and traceability.
2. Fresh worker implements only the bounded scope.
3. Fresh reviewer independently inspects the exact changed head against the contract.
4. Blocking/High/Medium findings require rework and a new review unless the track
   explicitly defines a stricter rule.
5. Verification records exact evidence (tests/builds/scenarios/artifacts).
6. Master signs off only when requirements, review, verification, and traceability agree.

Sign-off is always against an exact commit/head, not merely a PR title or conversation.

## Anti-drift rules

- Repository SDP documents are authoritative; chat is not.
- A worker may not invent new requirements to justify an implementation choice.
- A design change discovered during implementation returns to Master/DesignAnalysis.
- Review findings are never silently fixed outside their recorded Refactor/Slice.
- Compatibility fallbacks must have an explicit owner and removal/retention decision.
- Polling, retries, caches, fallback timers, and duplicated state are architecture
  mechanisms, not incidental fixes; adding one requires design ownership and tests.

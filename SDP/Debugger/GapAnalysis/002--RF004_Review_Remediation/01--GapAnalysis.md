# DBG-GAP-002 — RF-004 Review-Triggered Remediation Gap Analysis

- Status: **ACTIVE / FAN-OUT FROZEN**
- Parent: `DBG-RF-004`
- Origin CodeReview: `DBG-CR-002`
- Independent review: `DBG-RVW-001-005-037`
- Exact reviewed baseline: `514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`
- Coordination issue: #54

## Purpose

Compare the frozen RF-004 candidate against already accepted/frozen requirements and interfaces. No new product requirement is introduced here.

## Gap map

| Finding | Actual behavior | Required behavior | Gap class | Remediation |
|---|---|---|---|---|
| `DBG-F-027` Medium | CALL semantic proof trusts a resolved record whose own address may differ from the checked call-site candidate | exact record identity must include `record.address == candidate`; mismatch is typed CORRUPT before further caller-state reconstruction | correctness / exact-evidence fencing | `DBG-RF-010` |
| `DBG-F-028` Medium | `InspectionService.create` supplies ambient Stack/Location defaults | composition dependencies are explicit required arguments and stored unchanged | public contract / composition ownership | `DBG-RF-011` |
| `DBG-F-029` Low | Location-row type diagnostic names `UnwindRow` | deterministic diagnostic names `LocationRow` | local correctness / diagnostics | bounded RF-004 Low rework |

## Requirement/design mapping

### DBG-F-027

Affected authority:
- `dbg.resolver-inspection/1.9` exact CALL semantic proof;
- accepted `HSX-D-002` resume-vs-call-site semantics;
- `HSX-ST-007` unwind/call-site evidence;
- `DBG-SL-001-005-005` StackService exact-evidence/no-fallback rules.

No contract refreeze is required. The implementation deviates from the existing contract.

### DBG-F-028

Affected authority:
- accepted `dbg.resolver-inspection/1.2` section 9 factory signature and explicit dependency ownership;
- `dbg.resolver-inspection/1.4` changes result-envelope shape only;
- `DBG-SL-001-005-006` explicit composition requirements.

No contract refreeze is required. Remove implementation-only defaults.

### DBG-F-029

Affected authority:
- accepted recipe/location foundation and deterministic validation behavior.

No structural or public behavior change.

## Fan-out decision

The Medium findings have independent responsibility and verification boundaries and therefore must not be collapsed into one corrective Refactor.

1. `DBG-RF-010` — Slice005 exact CALL-site evidence fence.
2. `DBG-RF-011` — Slice006 explicit factory dependency contract.

Both are `corrective_child_of: DBG-RF-004`.

The Low diagnostic correction remains parent-local because giving it a child Refactor would add governance weight without an independent ownership boundary. It still requires test evidence and must be visible to the fresh RF-004 re-review.

## Ordering

`DBG-RF-010` and `DBG-RF-011` may be implemented in parallel/candidate order because ownership is disjoint, but promotion reconstructs the original RF-004 DAG:

`Slice005 corrected -> review/verification/signoff -> Slice006 corrected on accepted Slice005 -> review/verification/signoff -> RF-004 fresh review`.

No whole-branch promotion is allowed.

## Completion signal

GapAnalysis is satisfied only when:
- F-027 and F-028 each have corrective product evidence, independent review and verification;
- F-029 is corrected with focused evidence;
- a fresh independent exact-head RF-004 review confirms all three findings closed and no regression of `1.3..1.9` contracts;
- RF-005..009 remain blocked until RF-004 parent completion.

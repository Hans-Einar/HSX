# MiniVM Test Plan

## DR Coverage
- DR-2.1 / DR-2.1a: Workspace-pointer O(1) context switching (microbench harness, histogram).
- DR-2.3: ABI conformance tests (argument registers, spill, BRK/SVC semantics).
- DR-8.1: Event emission tests (	race_step, debug_break).

## Test Matrix
| Area | Test | Notes |
|------|------|-------|
| Workspace pointer | Measure register swap latency vs threshold | Use synthetic workloads; fail if above budget. |
| ABI compliance | Invoke sample functions compiled via hsx-llc (var args) | Validate register/stack usage. |
| Debug events | Trigger BRK, mailbox wait, step trace | Ensure event payload matches schema. |

## Tooling
- Python pytest suites (python/tests/test_vm_*).
- Future C harness reusing same vectors (DG-1.4).

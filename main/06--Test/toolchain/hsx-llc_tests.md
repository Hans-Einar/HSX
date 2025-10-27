# hsx-llc Test Plan

## DR Coverage
- DR-2.1a / DR-2.2: Register allocation & ABI compliance.
- DR-3.1: Lowering determinism.

## Test Matrix
| Area | Test | Notes |
|------|------|-------|
| ABI | Compile sample C functions, inspect emitted MVASM | Validate register usage + stack spills. |
| Metrics | Capture register pressure/spill data | Fail if thresholds exceed spec. |

## Tooling
- pytest harness running hsx-llc.py on IR fixtures.


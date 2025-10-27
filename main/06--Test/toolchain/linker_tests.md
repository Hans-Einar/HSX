# Linker Test Plan

## DR Coverage
- DR-3.1: .hxe header, CRC, compat rules.
- DR-5.3: FRAM manifest / persistence metadata.
- DR-2.5: Version stamping.

## Test Matrix
| Area | Test | Notes |
|------|------|-------|
| Header validation | Link sample, inspect header fields | Compare against docs/hxe_format.md. |
| Manifest | Include FRAM keys, simulate missing entries | Ensure linker fails with diagnostics. |
| Version stamp | Validate data consumed by EXEC_GET_VERSION | Round-trip with executive integration test. |

## Tooling
- Python tests invoking hld.py and verifying output via helper script.


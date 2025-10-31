# MVASM Test Plan

## DR Coverage
- DR-3.1: .hxo structure + relocation integrity.
- DR-2.5: Shared syscall header import validation.

## Test Matrix
| Area | Test | Notes |
|------|------|-------|
| Relocations | Assemble sample with reloc variants | Compare against golden .hxo. |
| Header sync | Ensure assembler emits error if header drift detected | Scrape shared header + fingerprint. |

## Tooling
- Python unit tests invoking sm.py --dump-json and verifying output.


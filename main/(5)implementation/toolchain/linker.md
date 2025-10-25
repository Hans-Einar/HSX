# Linker Implementation Plan

## DR/DG Alignment
- DR-3.1 / DG-3.1 & DG-3.5: .hxe header contract, listing/debug artefacts.
- DR-5.3 / DG-7.3: FRAM manifest + persistence metadata bundling.
- DR-2.5: Embed ABI/version stamps for EXEC_GET_VERSION verification.

## Implementation Notes
- Solidify hxe_format.md fields (magic, version, entry, code/ro/bss, CRC) and add compatibility checks.
- Bundle provisioning manifest + FRAM key descriptors; fail link if references missing (refactorNotes, DR-5.3).
- Emit version sidecar consumed by EXEC_GET_VERSION + tooling.

## Playbook
- [ ] Implement schema validation vs new docs/hxe_format.md.
- [ ] Add manifest dedupe + FRAM key allocation logic.
- [ ] Hook CRC + compatibility warnings into CI.

## Commit Log
- _Pending_.

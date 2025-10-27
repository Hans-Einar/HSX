# MVASM Implementation Plan

## DR/DG Alignment
- DR-3.1 / DG-3.1: .hxo object format, relocations, directives.
- DR-2.5 / DG-3.4: Consume shared syscall header for module/function IDs automatically.
- DR-2.3 / DG-2.3: Preserve ABI semantics in emitted opcodes.

## Implementation Notes
- Integrate generated header (module/function IDs) so SVC macros stay in sync (refactorNotes: shared syscall header).
- Emit listing/JSON sidecars with symbol + value metadata for debugger (ties to DG-3.3, DG-3.5).
- Harden directive parsing for provisioning manifest fields (FRAM keys, capability bits).

## Playbook
- [ ] Hook header parser into assembler build step.
- [ ] Extend listing output to include OID descriptors for value/command exports.
- [ ] Add regression tests for relocation/section size limits.

## Commit Log
- _Pending_.

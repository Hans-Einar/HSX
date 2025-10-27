# hsx-llc Implementation Plan

## DR/DG Alignment
- DR-2.1a / DG-2.1–2.2: Lowering + register allocation respect workspace-pointer constraints.
- DR-2.2 / DR-2.3: ABI-compliant argument passing + spill logic.
- DR-3.1 / DG-3.2: Deterministic lowering pipeline feeding assembler.

## Implementation Notes
- Capture register pressure metrics per function; feed workspace-pointer acceptance tests.
- Expose instrumentation for spill counts to ensure CI enforces DR-2.1a.
- Generate metadata (value/command descriptors) for downstream tooling.

## Playbook
- [ ] Implement acceptance microbench (Lr/Lw histogram) hook in lowering tests.
- [ ] Wire pass to emit debug sidecar info (symbols, line map).
- [ ] Validate new opcodes introduced by DO-2.a when backlog prioritises them.

## Commit Log
- _Pending_.

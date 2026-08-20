# HSX-ST-007 — ABI Profile, Unwind/Location Recipe Schema, and Register Mutation

- Status: ACTIVE STUDY
- Spawned from: `HSX-ST-003`, review `HSX-RVW-001-001-004`
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`

## Question and scope

Resolve the concrete current portable ABI profile, versioned unwind/location recipe opcode and
schema boundary, and raw register-write authority/coherence semantics needed by `HSX-D-002`.

## Evidence sources

`HSX-ST-003`; compiler/assembler/linker outputs; current CALL/RET/PUSH/POP/frame code;
stack/local inspection; ABI/spec docs and targeted tests.

## Required decisions

- exact current profile register roles, arguments/return, saved sets, stack alignment/growth,
  frame layout and call-site PC rule;
- recipe schema/version/opcode/value model, bounds and unknown-op behavior;
- whether/how register writes update stopped snapshot/transition revisions and authority checks;
- degraded legacy profile and conformance fixtures.

## Findings and uncertainty

To be completed by the assigned worker.

## Traceability and guard

Map to `HSX-R-016..HSX-R-018`, `HSX-A-002`, `HSX-D-002`, `DBG-D-003/004/006`. No numeric new
contract IDs, product changes or AVR decisions.

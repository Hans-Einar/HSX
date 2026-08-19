# HSX Standard Document Procedure

`SDP/` is the authoritative development-process surface for this repository.
The legacy `main/02--Study`, `main/03--Architecture`, `main/04--Design`, and
`main/05--Implementation` trees remain historical source material until their
accepted content has been migrated or explicitly superseded.

## Independent SDP tracks

| Track | Purpose | ID namespace |
|---|---|---|
| `HSX/` | Portable HSX system: ISA/ABI, VM, executive, mailbox, value/command, toolchain | `HSX-*` |
| `Debugger/` | Debugger architecture, protocol, CLI, DAP, VS Code, trace/debug UX | `DBG-*` |
| `AVR/` | AVR implementation and target-specific resource/timing/HAL constraints | `AVR-*` |

Each track has an independent requirements/design/verification lifecycle. A target
implementation must reference portable HSX requirements rather than duplicating them.
A debugger requirement may depend on an HSX runtime capability, but the dependency must
be recorded as a cross-track relation.

## Common lifecycle

The preferred evidence flow is:

`Study -> Requirements -> Architecture -> DesignAnalysis -> Design -> Implementation`

For existing code, the remediation flow is:

`CodeReview -> GapAnalysis -> one or more Refactors -> independent reviews -> verification -> sign-off`

A CodeReview is an evidence source, not a substitute for requirements or design.
A Refactor is a bounded execution track spawned from one coherent remediation domain.
Structural Refactors must have a DesignAnalysis/Design contract before product-code
implementation.

## Agent workflow

See `AGENTS.md` and `SDP/Shared/Process.md`.

A fresh agent should:

1. identify which SDP track it is working in;
2. read that track's `README.md` and `Traceability/CurrentIndex.yaml`;
3. follow only the active contract and its explicit dependencies;
4. update traceability and verification evidence as work progresses.

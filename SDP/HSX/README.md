# HSX Core SDP

This track owns the portable HSX system independent of a specific MCU target:

- mandate/use cases for dynamically loadable embedded logic;
- ISA and architectural register/workspace model;
- ABI and SVC contracts;
- HXO/HXE/toolchain contracts;
- MiniVM behavior;
- executive/scheduler behavior;
- mailbox behavior;
- value/command behavior;
- platform-independent resource/behavior requirements;
- Python reference implementation as a conformance oracle;
- cross-implementation conformance requirements.

The existing legacy `main/02--Study`, `main/03--Architecture`, `main/04--Design`, and
`main/05--Implementation` content is historical source material and must not be bulk-renamed
or silently discarded. Migration starts with `HSX-ST-001`, which will inventory legacy
`DR-*`, `DG-*`, design decisions, and current implementation evidence before establishing
stable `HSX-*` IDs.

## Current phase

Steering activated `HSX-ST-001` in issue #47 as the coordinator for portable runtime
contracts required by Debugger `DBG-ST-006`. Five numbered Studies (`HSX-ST-002..006`) own
identity/lifecycle, address/ABI/unwind, execution/snapshot/blocked states, event continuity,
and resource provenance. This phase produces reviewed proposed contracts only; it authorizes
no product or AVR work.

`HSX-ST-001..HSX-ST-006` are complete for this portable debugger-contract scope. Master has
synthesized stable proposed `HSX-R-001..036`, `HSX-A-001..005`, and `HSX-D-001..005`; the
four independent reviews required rework. The active gate is supplemental
`HSX-ST-007`/`HSX-ST-008`, followed by fresh `HSX-RVW-001-001-005` and issues #47/#38.

Target-specific implementations such as AVR belong in `SDP/AVR` and reference HSX core
requirements rather than duplicating them.

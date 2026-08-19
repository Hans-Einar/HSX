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

Target-specific implementations such as AVR belong in `SDP/AVR` and reference HSX core
requirements rather than duplicating them.

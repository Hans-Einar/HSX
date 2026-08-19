# HSX-ST-003 — Address Spaces, ABI, Unwind, and Variable Locations

- Status: ACTIVE STUDY
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`

## Question and scope

Define portable code/data/register address spaces, widths, endian/alignment/serialization and
overflow rules, plus ABI frame/unwind/call-return and variable-location semantics consumed by
debug artifacts and inspection.

## Evidence sources

Legacy ISA/ABI/toolchain documents; `docs/hsx_spec-v2.md`, `docs/symbol_format.md`, HXE/HXO
contracts; compiler/linker/assembler, VM/executive stack behavior, symbol/source code and tests.

## Required analysis

- current masks/types/layouts versus documented intent;
- typed architecture descriptor and image-bound debug metadata inputs;
- unwind/location partial/unavailable behavior;
- capability/versioning and multi-width/case/relocation conformance fixtures.

## Findings and uncertainty

To be completed by the assigned worker.

## Required conclusions

Recommend stable proposed HSX contract concepts without numeric ID allocation. Separate
portable HSX semantics from Python-oracle details and AVR constraints.

## Open questions and traceability

Record unresolved evidence and mappings to `DBG-ST-006`, `DBG-D-003`, `DBG-D-004`, and
related Studies.

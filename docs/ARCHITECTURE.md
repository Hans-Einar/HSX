# HSX Architecture Overview

This document acts as the landing page for the HSX documentation set. It links to the detailed specifications and guides relocated from the repository root.

## Core References
- [ISA and system overview](hsx_spec.md)
- [Value/command interface](hsx_value_interface.md)
- [System call reference](SYSCALLS.md)
- [Float16 programming guide](HSX_F16_GUIDE.md)
- [Floating-point architecture notes](HSX_FLOAT_ARCHITECTURE.md)
- [Optimisation strategies](HSX_OPTIMIZATION_NOTES.md)
- [Assembler and linker specification](MVASM_SPEC.md)

## Toolchain
- [Python toolset primer](python_toolset.md)
- [Python prototype documentation](python_version.md)
- [Refactor roadmap](REFACTOR_PLAN.md)
- [Backlog and future work](BACKLOG.md)

## How to Navigate
The documentation tree is designed for future Doxygen generation. Markdown files can be browsed directly, or you can run `make docs` at the repository root (after configuring Doxygen) to build the HTML site under `docs/html/`.

## Examples
- Auto-generated C samples live under `examples/tests/test_*`. Run `make examples-tests` to build them, or `make run-<name>` to execute via the host VM.

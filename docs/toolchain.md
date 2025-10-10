# HSX Toolchain

## Version
v0.1.1 (2025-10-10)

## Capabilities in v0.1
- Python-based assembler (`python/asm.py`) with support for `.extern`, `.import`, `.text`, `.data`, stable 16-bit addressing, and `.hxo` emission.
- High-level linker (`python/hld.py`) producing HSXE binaries with `_start` entry resolution and preserved header format (magic `HSXE`, version `0x0001`, 8-byte CRC).
- LLVM IR lowering pipeline (`python/hsx-llc.py`) covering control flow (br/call/phi), integer and half-precision arithmetic, loads/stores, comparisons, and external symbol imports.
- MiniVM host runtime (`platforms/python/host_vm.py`) with CLI flags for entry selection, step limiting, instruction tracing, stdio mailboxes, and SVC EXIT handling.
- Python executive and TCP shell orchestration supporting task lifecycle management, JSON protocol, ps/exec/kill commands, and `.hxe` payload loading.
- Mailbox (SVC 0x05) and stdio bindings with shell listen/send, fan-out policies, and sample producer/consumer programs in both Python and C.
- Continuous integration targets via `make`: virtualenv/bootstrap helpers, packaging/release scripts, and auto-discovered examples/tests pipelines.
- Pytest coverage for IR->ASM translation, VM execution (exit codes, mailboxes, stdio), and mailbox manager behaviors.

## Known Limitations
- Register allocation remains linear-scan-less; complex SSA fragments can exhaust the temporary pool and require manual structuring.
- GEP lowering lacks dynamic index support; union allocas and advanced pointer arithmetic are deferred.
- Scheduler and mailbox wait/wake behavior in the native executive are pending parity with the Python prototype.
- Documentation hosting and long-term artifact cleanup policies are undecided.

## Upcoming Work
- Extend IR lowering for remaining complex pointer forms (nested structs/unions beyond scalar fields) and additional memory ops once allocator coverage is verified.
- Wire spill/reload scenarios into `python/tests/test_host_vm_cli.py` and `python/tests/test_mailbox_manager.py`, adding example inputs under `examples/tests/`.
- After each capability lands, rerun `make -C python test` plus targeted integration tests to ensure mailbox and half-precision demos remain healthy.

## Version Log

### v0.1.2 (2025-10-10)
- Adjusted call lowering so return values land in `R4`, keeping `R7` free for long-lived counters in the MiniVM integration tests.
- Rebuilt the stdio/mailbox samples with the linker fix so hsx_stdio/hsx_mailbox stay at predictable addresses after relinking.

### v0.1.1 (2025-10-10)
- Added SSA liveness tracking with automatic register recycling and spill slots managed via the assembler/linker pipeline.
- Implemented a spill-capable register allocator with compiler-owned `.data` storage and reload support for integer and half/float values.
- Expanded `getelementptr` lowering for scalar element types and union pointers, and taught loads/stores to recreate float aliases; new regression test (`test_spill_data_emitted_for_many_temps`) verifies spill emission.

### v0.1 (2025-10-10)
- Captured current Python toolchain state, including assembler/linker/VM stack, mailbox integrations, and shell orchestration.
- Documented known gaps to guide upcoming allocator and lowering work.

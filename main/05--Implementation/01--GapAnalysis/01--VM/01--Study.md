# Gap Analysis: VM

## 1. Scope Recap

_Brief synopsis of the design document and links back to the design specification._

**Design Reference:** [04.01--VM.md](../../../04--Design/04.01--VM.md)

**Summary:**  
The MiniVM design specifies a "dumb machine" that implements the HSX instruction-set architecture (ISA) for single-task execution on both Python reference and embedded C targets. The VM is always executive-driven in production—it performs no autonomous scheduling, context switching, or HAL work. Key design tenets include:

- **Deterministic execution** with workspace-pointer-based O(1) context switching
- **Complete ISA implementation** covering data movement, integer ALU, control flow, floating-point helpers (f16), and system services (SVC)
- **Executive-driven control plane** with narrow API for orchestration (load, step, clock, register/memory access)
- **Trap interface** for syscalls (SVC), breakpoints (BRK), and faults
- **HXE format support** with both monolithic and streaming loaders
- **Debug infrastructure** including trace records and register inspection
- **ABI compliance** with standard calling conventions and stack management

---

## 2. Current Implementation

_What already exists today that satisfies the design intent._

**Code Paths:**
- **Python reference VM:** `platforms/python/host_vm.py` (3,363 lines, fully functional)
  - `MiniVM` class with complete ISA implementation
  - `TaskContext` dataclass for per-task state management
  - `RegisterFile` class implementing workspace-pointer-based register windows
  - Full opcode dispatch covering all specified instructions (LDI, LD, ST, MOV, LDB, LDH, STB, STH, ADD, SUB, MUL, AND, OR, XOR, NOT, CMP, JMP, JZ, JNZ, CALL, RET, SVC, PUSH, POP, FADD, FSUB, FMUL, FDIV, I2F, F2I, LDI32, BRK)
  - HXE loader with header validation and CRC checking
  - Syscall dispatch for modules 0x00-0x08, 0x0E
  - Debug support with breakpoints, single-step, and trace records
  - Mailbox integration via `MailboxManager`
- **Executive implementation:** `python/executive.py`, `python/execd.py` (45,100 lines)
  - JSON-RPC protocol over TCP for remote control
  - Multi-task scheduling with priority and quantum support
  - Clock control (start, stop, step, rate adjustment)
  - Task lifecycle management (load, pause, resume, kill)
  - Memory inspection (peek/poke)
- **Supporting modules:**
  - `python/vmclient.py` - Client library for executive protocol
  - `python/mailbox.py` - Mailbox subsystem implementation
  - `python/hsx_manager.py` - High-level VM management

**Tests:**
- `python/tests/test_vm_callret.py` - CALL/RET instruction validation
- `python/tests/test_vm_callret_edges.py` - Edge cases for call/return sequences
- `python/tests/test_vm_exit.py` - TASK_EXIT syscall behavior
- `python/tests/test_vm_jump_immediates.py` - Jump instruction operand handling
- `python/tests/test_vm_mem_oob.py` - Out-of-bounds memory access detection
- `python/tests/test_vm_pause.py` - Task pause/resume and state management
- Test plan documented in `main/06--Test/system/MiniVM_tests.md`

**Tools:**
- `python/asm.py` - HSX assembler (MVASM)
- `python/disassemble.py` - Disassembler for HSX bytecode
- `python/build_hxe.py` - HXE binary builder
- `python/hsx-llc.py` - LLVM backend compiler
- `python/shell_client.py` - Interactive executive shell
- `python/blinkenlights.py` - Visual debugger/monitor

**Documentation:**
- `docs/abi_syscalls.md` - Syscall table and calling conventions
- `docs/MVASM_SPEC.md` - Assembly language specification
- `docs/hxe_format.md` - Executable format specification
- `docs/executive_protocol.md` - Executive JSON-RPC protocol
- `docs/resource_budgets.md` - Memory and performance targets
- `docs/hsx_spec-v2.md` - Overall HSX specification

---

## 3. Missing or Partial Coverage

_Gaps that block full compliance with the design._

**Open Items:**
- **C embedded port (DR-1.3, DG-1.4):** Design specifies Python reference **and** C port for embedded targets. No C implementation exists yet in `platforms/`. This is critical for deployment on MCU targets (STM32, etc.)
- **Shift operations (LSL, LSR, ASR):** Study document (`main/02--Study/02--Study.md`) identifies shift operations as part of "minimal instruction set" needed for LLVM lowering and C compilation. Essential for bit manipulation, efficient multiply/divide by powers of 2, and C bitfield operations. Currently missing from ISA.
- **Carry-aware arithmetic (ADC, SBC):** Study document identifies add-with-carry and subtract-with-borrow as part of minimal instruction set. Required for multi-precision arithmetic (e.g., 64-bit operations on 32-bit architecture). Current ISA has ADD/SUB but no carry variants.
- **PSW flag implementation (C, N, V):** Design spec (section 4.3) defines processor status word with Z (zero), C (carry), N (negative), and V (overflow) flags. Current implementation only sets Z flag (line 770 in `host_vm.py`). C, N, V flags are not computed or maintained by any arithmetic/logic operations.
- **DIV opcode (0x13):** Design spec includes DIV in opcode table, but implementation in `host_vm.py` currently skips from MUL (0x12) to AND (0x14). Integer division is missing.
- **Streaming HXE loader (6.1.2):** Design specifies `vm_load_{begin,write,end,abort}` for byte-granularity ingestion. Current implementation only supports monolithic loading via full HXE buffer. Streaming is essential for CAN/UART provisioning on low-RAM targets.
- **Optional code/data paging (4.4, 6.1.4):** Design includes code cache lines (256-512B) and data TLB (2-4 entries) for memory-constrained targets. Not implemented; all code/data must fit in RAM.
- **SETPSW/GETPSW opcodes:** Design section 4.1 mentions "future SETPSW/GETPSW" for system helpers but these are not defined in opcode table or implemented
- **Heap support (6.1.5):** HXE header includes optional `heap_size_bytes` field, but VM does not allocate or manage heap regions. Dynamic allocation support is incomplete.
- **Performance targets (4.9):** Design goal of 2-4M instructions/second on M4 @ 48MHz cannot be validated without C port
- **Trace APIs (6.1, 7.1):** Design specifies `vm_get_last_pc()`, `vm_get_last_opcode()`, and `vm_get_last_regs()` for executive-side trace capture. Python VM stores some trace state but APIs are not formally exposed per design spec.
- **`vm_reg_get_for` and `vm_reg_set_for` (6.1.1):** Optional APIs for reading/writing registers of non-active PIDs are not implemented

**Deferred Features:**
- **Value service (module 0x07):** Specified in `docs/hsx_value_interface.md` but marked "Planned" in `docs/abi_syscalls.md`. Not exposed by Python VM yet.
- **Command service (module 0x08):** Also marked "Planned" in syscall table. Design references but not implemented.
- **Advanced paging modes:** Code prefetch, double-buffering, and data paging with TLB management are optional design features deferred until C port and embedded deployment
- **Policy flags in mem_cfg (6.1.4):** Design includes policy bitset for controlling `mem_write` in RUN state, `reg_set(PC)` in STOPPED state, etc. Current implementation has no policy enforcement framework.

**Documentation Gaps:**
- Missing formal API documentation for Python VM's public interface (method signatures, return types, error codes)
- No migration guide for applications moving between Python and future C implementations
- Performance benchmarking methodology not documented (how to validate 2-4M instr/s target)
- Missing examples of `mem_cfg` usage with different resource budgets

---

## 4. Next Actions

_Ordered steps to close the gaps._

**Priority Actions:**

**Phase 1: Complete Python Reference Implementation**
1. **Add shift operations (LSL, LSR, ASR)** - Implement logical shift left, logical shift right, and arithmetic shift right opcodes. Required by study document for LLVM lowering and C compilation needs.
2. **Add carry-aware arithmetic (ADC, SBC)** - Implement add-with-carry and subtract-with-borrow opcodes for multi-precision arithmetic support.
3. **Complete PSW flag implementation** - Implement C (carry), N (negative), and V (overflow) flag computation in arithmetic and logic operations. Currently only Z (zero) flag is set.
4. **Add DIV opcode (0x13)** - Implement integer division in `host_vm.py` step function to match design spec opcode table
5. **Formalize trace APIs** - Expose `vm_get_last_pc()`, `vm_get_last_opcode()`, `vm_get_last_regs()` as specified in sections 6.1 and 7.1
6. **Implement streaming loader** - Add `vm_load_{begin,write,end,abort}` methods per section 6.1.2 for byte-wise HXE ingestion
7. **Add optional register access APIs** - Implement `vm_reg_get_for(pid, reg_id)` and `vm_reg_set_for(pid, reg_id, value)` per section 6.1.1

**Phase 2: C Embedded Port (Critical for DR-1.3, DG-1.4)**
8. **Create C port structure** - Set up `platforms/c/` with build system (Makefile, CMake)
9. **Port core VM** - Translate MiniVM class to C with opcode dispatch (prefer jump table or computed goto per section 4.1)
10. **Port context management** - Implement TaskContext and workspace pointer swapping in C
11. **Port HXE loader** - Implement monolithic and streaming loaders in C
12. **Port syscall handlers** - Implement module 0x00, 0x01, 0x02, 0x04, 0x05, 0x06 in C
13. **Cross-platform test suite** - Create shared test vectors that run on both Python and C implementations (per DG-1.4)

**Phase 3: Advanced Features**
14. **Heap support** - Implement heap region allocation and management per HXE `heap_size_bytes` field
15. **Memory paging** - Implement optional code cache and data TLB per sections 4.4 and 6.1.4 (deferred until C port deployed on constrained MCU)
16. **Value/Command services** - Complete module 0x07 and 0x08 implementations per `docs/hsx_value_interface.md`
17. **Policy framework** - Add policy flags to `mem_cfg` for fine-grained access control

**Phase 4: Documentation & Validation**
18. **API documentation** - Document all public VM APIs with signatures, return types, error codes
19. **Performance benchmarking** - Establish methodology and measure C port against 2-4M instr/s target on M4@48MHz
20. **Migration guide** - Document behavioral equivalence and any platform-specific considerations
21. **Expand test coverage** - Add tests for workspace swap timing, ABI compliance (DR-2.3), paging edge cases, shift operations, and carry flag behavior

**Cross-References:**
- Design Requirements: DR-1.3, DR-2.1, DR-2.1a, DR-2.3, DR-3.1, DR-5.1, DR-6.1, DR-8.1
- Design Goals: DG-1.3, DG-1.4, DG-2.1-2.4, DG-3.1-3.3, DG-4.1-4.3, DG-5.1-5.4, DG-6.1, DG-7.2
- Related milestones: Check `MILESTONES.md` for C port target dates
- Test specification: `main/06--Test/system/MiniVM_tests.md`

---

**Last Updated:** 2025-10-31  
**Status:** In Progress (Python implementation substantial, C port not started)

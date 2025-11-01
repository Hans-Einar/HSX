# VM Implementation Plan

## Planned Implementation Order (Grand Plan)

1. Phase 1 - Python reference implementation (shifts, PSW, DIV, ADC/SBC, trace, streaming loader).
2. Phase 2 - C port (deferred until the Python stack stabilizes).
3. Phase 3 - Advanced features (heap, paging, value/command services).
4. Phase 4 - Documentation and validation pass.

## Sprint Scope

Focus on the Python milestones and follow-up feature work before touching the Phase 2 C port. Capture C-related notes as future TODOs so the current sprint remains Python-only.

## Overview

This implementation plan addresses the gaps identified in the VM Study document ([01--Study.md](./01--Study.md)) and aligns with the implementation notes in the System document ([../../system/MiniVM.md](../../system/MiniVM.md)). The plan is organized chronologically with clear dependencies tracked in [DependencyTree.md](../DependencyTree.md).

**Design Reference:** [04.01--VM.md](../../../04--Design/04.01--VM.md)

---

## Phase 1: Complete Python Reference Implementation

### 1.1 Shift Operations (LSL, LSR, ASR)

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Study document identifies shift operations as part of "minimal instruction set" needed for LLVM lowering and C compilation. Essential for bit manipulation, efficient multiply/divide by powers of 2, and C bitfield operations.

**Todo:**
- [ ] Define opcodes for LSL (logical shift left), LSR (logical shift right), ASR (arithmetic shift right)
- [ ] Implement shift operations in `platforms/python/host_vm.py` MiniVM.step() dispatcher
- [ ] Update PSW flags (N, Z) after shift operations
- [ ] Add shift instruction tests to test suite (edge cases: shift by 0, shift by 32, shift amounts > 32)
- [ ] Update `docs/abi_syscalls.md` with new opcode definitions
- [ ] Update `python/asm.py` (MVASM) to support shift mnemonics
- [ ] Update `python/disassemble.py` to decode shift instructions

---

### 1.2 Carry-Aware Arithmetic (ADC, SBC)

**Priority:** HIGH  
**Dependencies:** 1.3 (PSW flag implementation - C flag must be functional)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Required for multi-precision arithmetic (e.g., 64-bit operations on 32-bit architecture). Essential for LLVM lowering of 64-bit types.

**Todo:**
- [ ] Define opcodes for ADC (add with carry) and SBC (subtract with borrow)
- [ ] Implement ADC/SBC in `platforms/python/host_vm.py` with proper carry flag usage
- [ ] Update PSW flags (C, N, Z, V) after ADC/SBC operations
- [ ] Add multi-precision arithmetic tests (64-bit add/subtract examples)
- [ ] Update `docs/abi_syscalls.md` with ADC/SBC opcode definitions
- [ ] Update MVASM and disassembler to support ADC/SBC mnemonics
- [ ] Document multi-precision arithmetic patterns in ABI documentation

---

### 1.3 Complete PSW Flag Implementation

**Priority:** HIGH  
**Dependencies:** None (blocks 1.2)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design spec (section 4.3) defines processor status word with Z (zero), C (carry), N (negative), and V (overflow) flags. Current implementation only sets Z flag. Full PSW support is essential for conditional branches and multi-precision arithmetic.

**Todo:**
- [ ] Implement C (carry) flag computation in ADD, SUB operations
- [ ] Implement N (negative) flag computation in all arithmetic/logic operations
- [ ] Implement V (overflow) flag computation in ADD, SUB (signed overflow detection)
- [ ] Update CMP instruction to set all four flags appropriately
- [ ] Add conditional branch instructions that test C, N, V flags (if not already present)
- [ ] Add comprehensive flag behavior tests (boundary conditions, signed/unsigned overflow)
- [ ] Update `docs/abi_syscalls.md` with complete PSW flag behavior documentation
- [ ] Verify all existing tests still pass with full flag implementation

---

### 1.4 DIV Opcode Implementation

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design spec includes DIV in opcode table, but implementation currently skips from MUL (0x12) to AND (0x14). Integer division is essential for complete ISA coverage.

**Todo:**
- [ ] Implement DIV opcode (0x13) in `platforms/python/host_vm.py`
- [ ] Handle division by zero (should trigger fault/trap)
- [ ] Update PSW flags after division (N, Z based on quotient)
- [ ] Add division tests (positive/negative operands, divide by zero, min/max values)
- [ ] Update `docs/abi_syscalls.md` with DIV behavior and error conditions
- [ ] Update MVASM and disassembler for DIV instruction
- [ ] Document division semantics (truncation, remainder handling)

---

### 1.5 Formalize Trace APIs

**Priority:** MEDIUM  
**Dependencies:** 1.8 (Shared syscall header integration)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies `vm_get_last_pc()`, `vm_get_last_opcode()`, and `vm_get_last_regs()` for executive-side trace capture. System/MiniVM.md notes requirement to emit structured events (trace_step, debug_break) for executive stream.

**Todo:**
- [ ] Expose `vm_get_last_pc()` API in MiniVM class
- [ ] Expose `vm_get_last_opcode()` API in MiniVM class
- [ ] Expose `vm_get_last_regs()` API in MiniVM class (return register snapshot)
- [ ] Integrate with executive event stream (emit_event for trace_step, debug_break)
- [ ] Align event payloads with `docs/executive_protocol.md` schema (seq, ts, pid, type, data)
- [ ] Add trace API tests (verify correct PC/opcode/register capture)
- [ ] Document trace API usage in VM API documentation
- [ ] Ensure trace APIs work for both active and paused tasks

---

### 1.6 Streaming HXE Loader

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies `vm_load_{begin,write,end,abort}` for byte-granularity ingestion. Essential for CAN/UART provisioning on low-RAM targets.

**Todo:**
- [ ] Implement `vm_load_begin(mem_cfg, expected_size)` API
- [ ] Implement `vm_load_write(chunk)` API with incremental parsing
- [ ] Implement `vm_load_end()` API with CRC validation
- [ ] Implement `vm_load_abort()` API for cleanup on failure
- [ ] Maintain state machine for streaming load (BEGIN -> WRITING -> END/ABORT)
- [ ] Add streaming loader tests (chunk sizes: 1 byte, 16 bytes, 256 bytes, full buffer)
- [ ] Test error conditions (CRC mismatch, oversized payload, duplicate begin)
- [ ] Document streaming loader usage patterns and state transitions
- [ ] Verify streaming and monolithic loaders produce identical results

---

### 1.7 Optional Register Access APIs

**Priority:** LOW  
**Dependencies:** None  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design section 6.1.1 specifies optional APIs for reading/writing registers of non-active PIDs. Useful for debugger and monitoring tools.

**Todo:**
- [ ] Implement `vm_reg_get_for(pid, reg_id)` API
- [ ] Implement `vm_reg_set_for(pid, reg_id, value)` API
- [ ] Validate PID exists and is in valid state for register access
- [ ] Add register access tests for active and paused tasks
- [ ] Document register access API limitations and security considerations
- [ ] Integrate with debugger tooling requirements (see TUI_DEBUGGER)

---

### 1.8 Integrate Shared Syscall Header

**Priority:** HIGH  
**Dependencies:** Shared ABI header generation (external dependency)  
**Estimated Effort:** 1-2 days

**Rationale:**  
System/MiniVM.md notes: "Ensure SVC table pulls module/function IDs from forthcoming shared header (ties into DR-2.5 once header lands)."

**Todo:**
- [ ] Wait for shared syscall header to be generated (track in DependencyTree.md)
- [ ] Integrate shared header into Python VM SVC dispatcher
- [ ] Replace hardcoded module/function IDs with header constants
- [ ] Verify all existing SVC tests still pass
- [ ] Update documentation to reference shared header
- [ ] Coordinate with other modules (Executive, Mailbox) using same header

---

### 1.9 Microbench Harness for Workspace Swaps

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
System/MiniVM.md notes: "Finalise microbench harness proving constant-time workspace swaps (tie into DR-2.1a acceptance)." Required to validate O(1) context switch guarantee.

**Todo:**
- [ ] Create microbenchmark harness in `python/tests/bench_workspace_swap.py`
- [ ] Measure workspace pointer swap time with varying task counts (1, 10, 50, 100 tasks)
- [ ] Verify O(1) behavior (time should not scale with task count)
- [ ] Document acceptance criteria from DR-2.1a
- [ ] Generate benchmark report with timing data and graphs
- [ ] Add CI integration to detect performance regressions

---

## Phase 2: C Embedded Port

### 2.1 C Port Structure Setup

**Priority:** HIGH  
**Dependencies:** Phase 1 complete (reference implementation stable)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies Python reference **and** C port for embedded targets (DR-1.3, DG-1.4). Critical for deployment on MCU targets (STM32, etc.).

**Todo:**
- [ ] Create `platforms/c/` directory structure
- [ ] Set up build system (Makefile and/or CMake)
- [ ] Define platform abstraction layer (memory allocation, I/O)
- [ ] Create C header files for VM data structures
- [ ] Set up cross-compilation toolchain configuration
- [ ] Document build prerequisites and toolchain setup
- [ ] Create initial README in `platforms/c/`

---

### 2.2 Port Core VM

**Priority:** HIGH  
**Dependencies:** 2.1 (C port structure)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Core VM functionality must be ported with identical semantics to Python reference. Design suggests jump table or computed goto for opcode dispatch (section 4.1).

**Todo:**
- [ ] Translate MiniVM class to C struct and functions
- [ ] Implement opcode dispatch (jump table or computed goto)
- [ ] Port all instruction implementations (data movement, ALU, control flow)
- [ ] Port PSW flag computation
- [ ] Port shift operations (LSL, LSR, ASR)
- [ ] Port carry-aware arithmetic (ADC, SBC)
- [ ] Port DIV opcode
- [ ] Port floating-point helpers (f16)
- [ ] Implement memory access functions with bounds checking
- [ ] Add performance optimization flags (inline, register allocation hints)
- [ ] Document any C-specific implementation details

---

### 2.3 Port Context Management

**Priority:** HIGH  
**Dependencies:** 2.2 (Core VM)  
**Estimated Effort:** 3-5 days

**Rationale:**  
Workspace-pointer-based O(1) context switching is a core design requirement (DR-2.1, DG-2.1-2.2).

**Todo:**
- [ ] Implement TaskContext struct in C
- [ ] Implement RegisterFile with workspace pointer support
- [ ] Port workspace pointer swapping logic
- [ ] Ensure O(1) context switch property maintained
- [ ] Add context switch microbenchmarks for C port
- [ ] Verify ABI compliance (DR-2.3) in C implementation
- [ ] Test multi-task scenarios with context switching

---

### 2.4 Port HXE Loader

**Priority:** HIGH  
**Dependencies:** 2.2 (Core VM)  
**Estimated Effort:** 3-5 days

**Rationale:**  
Both monolithic and streaming loaders must be available in C port for embedded deployment scenarios.

**Todo:**
- [ ] Port HXE header parsing and validation
- [ ] Port CRC checking logic
- [ ] Implement monolithic loader in C
- [ ] Implement streaming loader in C (vm_load_begin/write/end/abort)
- [ ] Add memory constraints for embedded targets (progressive validation)
- [ ] Test with various HXE files (valid, corrupt CRC, oversized)
- [ ] Document memory requirements for loader operation

---

### 2.5 Port Syscall Handlers

**Priority:** HIGH  
**Dependencies:** 2.2 (Core VM), 1.8 (Shared syscall header)  
**Estimated Effort:** 1 week

**Rationale:**  
Essential syscall modules must be available in C port for basic task functionality.

**Todo:**
- [ ] Port module 0x00 (Task/System services)
- [ ] Port module 0x01 (Memory services)
- [ ] Port module 0x02 (String services)
- [ ] Port module 0x04 (Timer services)
- [ ] Port module 0x05 (Mailbox services - coordinate with Mailbox implementation)
- [ ] Port module 0x06 (Math services)
- [ ] Implement SVC trap handler and dispatch table
- [ ] Add syscall tests for C port
- [ ] Document any platform-specific syscall behavior differences

---

### 2.6 Cross-Platform Test Suite

**Priority:** HIGH  
**Dependencies:** 2.5 (C port functional)  
**Estimated Effort:** 1 week

**Rationale:**  
Design goal DG-1.4 requires shared test vectors that run on both Python and C implementations.

**Todo:**
- [ ] Create shared test vector format (HXE binaries + expected results)
- [ ] Port existing Python tests to shared vector format
- [ ] Create test harness for C port
- [ ] Implement test result comparison (Python vs C outputs)
- [ ] Add CI pipeline for cross-platform testing
- [ ] Document test coverage metrics
- [ ] Add regression tests for all opcodes and edge cases

---

## Phase 3: Advanced Features

### 3.1 Heap Support

**Priority:** LOW  
**Dependencies:** 2.5 (C port syscalls)  
**Estimated Effort:** 1 week

**Rationale:**  
HXE header includes optional `heap_size_bytes` field, but VM does not currently allocate or manage heap regions.

**Todo:**
- [ ] Parse `heap_size_bytes` from HXE header
- [ ] Allocate heap region during task initialization
- [ ] Implement heap allocator (simple bump allocator or TLSF)
- [ ] Add heap syscalls (malloc, free equivalents)
- [ ] Track heap usage and enforce limits
- [ ] Add heap exhaustion handling
- [ ] Add heap corruption detection (guard pages, canaries)
- [ ] Test heap operations and edge cases

---

### 3.2 Memory Paging (Optional)

**Priority:** DEFERRED  
**Dependencies:** 2.6 (C port deployed on embedded target)  
**Estimated Effort:** 2-3 weeks

**Rationale:**  
Design includes optional code cache and data TLB per sections 4.4 and 6.1.4. Deferred until C port is deployed on constrained MCU.

**Todo:**
- [ ] Design code cache architecture (256-512B line size)
- [ ] Design data TLB (2-4 entries)
- [ ] Implement code prefetch and cache management
- [ ] Implement data TLB with LRU replacement
- [ ] Add cache miss/hit instrumentation
- [ ] Implement page fault handling
- [ ] Add paging tests (cache thrashing, TLB thrashing)
- [ ] Benchmark performance impact
- [ ] Document paging configuration and tuning

---

### 3.3 Value/Command Services

**Priority:** LOW  
**Dependencies:** 2.5 (C port syscalls)  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Module 0x07 (Value service) and module 0x08 (Command service) are specified but marked "Planned" in syscall table.

**Todo:**
- [ ] Review `docs/hsx_value_interface.md` specification
- [ ] Design Value service implementation
- [ ] Design Command service implementation
- [ ] Implement module 0x07 handlers
- [ ] Implement module 0x08 handlers
- [ ] Add Value/Command service tests
- [ ] Update `docs/abi_syscalls.md` with implementation status
- [ ] Document usage examples

---

### 3.4 Policy Framework

**Priority:** LOW  
**Dependencies:** 2.2 (Core VM), 2.3 (Context management)  
**Estimated Effort:** 1 week

**Rationale:**  
Design includes policy bitset for controlling `mem_write` in RUN state, `reg_set(PC)` in STOPPED state, etc. No policy enforcement framework exists.

**Todo:**
- [ ] Design policy flag bitset structure
- [ ] Implement policy enforcement in mem_cfg
- [ ] Add policy checks in memory access functions
- [ ] Add policy checks in register access functions
- [ ] Add policy violation handling (trap or error return)
- [ ] Add policy configuration tests
- [ ] Document policy flags and their effects
- [ ] Document security implications

---

## Phase 4: Documentation & Validation

### 4.1 API Documentation

**Priority:** MEDIUM  
**Dependencies:** Phases 1-2 complete  
**Estimated Effort:** 1 week

**Rationale:**  
Missing formal API documentation for VM's public interface (method signatures, return types, error codes).

**Todo:**
- [ ] Document all public VM APIs with signatures
- [ ] Document return types and error codes
- [ ] Document API usage patterns and examples
- [ ] Generate API reference documentation (Sphinx/Doxygen)
- [ ] Document thread-safety and concurrency considerations
- [ ] Document resource limits and constraints
- [ ] Add API usage examples and tutorials

---

### 4.2 Performance Benchmarking

**Priority:** HIGH  
**Dependencies:** 2.6 (C port with tests)  
**Estimated Effort:** 1 week

**Rationale:**  
Design goal of 2-4M instructions/second on M4 @ 48MHz cannot be validated without C port and benchmarking methodology.

**Todo:**
- [ ] Create benchmark suite (instruction mix, memory patterns)
- [ ] Establish benchmarking methodology
- [ ] Measure C port on M4@48MHz target
- [ ] Compare against 2-4M instr/s target
- [ ] Identify performance bottlenecks
- [ ] Optimize critical paths if needed
- [ ] Document benchmark results and methodology
- [ ] Add performance regression tests to CI

---

### 4.3 Migration Guide

**Priority:** MEDIUM  
**Dependencies:** 2.6 (C port complete)  
**Estimated Effort:** 3-5 days

**Rationale:**  
Applications need guidance when moving between Python and C implementations.

**Todo:**
- [ ] Document behavioral equivalence between ports
- [ ] Document platform-specific considerations
- [ ] Document ABI compatibility requirements
- [ ] Provide migration checklist
- [ ] Add migration examples
- [ ] Document common pitfalls and solutions

---

### 4.4 Expand Test Coverage

**Priority:** MEDIUM  
**Dependencies:** Phases 1-2 complete  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Additional test coverage needed for workspace swaps, ABI compliance, paging, shift operations, and carry flag behavior.

**Todo:**
- [ ] Add workspace swap timing tests
- [ ] Add ABI compliance tests (DR-2.3)
- [ ] Add paging edge case tests (if paging implemented)
- [ ] Add shift operation edge case tests
- [ ] Add carry flag behavior tests
- [ ] Add fault injection tests
- [ ] Add stress tests (long-running tasks, many tasks)
- [ ] Measure and document test coverage metrics
- [ ] Add tests to CI pipeline

---

## Definition of Done (DoD)

This implementation is considered complete when all of the following criteria are met:

### Phase 1 Completion
- [ ] All Python reference implementation gaps are closed (shifts, ADC/SBC, PSW flags, DIV, trace APIs, streaming loader)
- [ ] All Phase 1 tests pass with 100% success rate
- [ ] Microbench harness confirms O(1) workspace swap behavior
- [ ] All Phase 1 documentation is updated and reviewed
- [ ] Code review completed by at least one team member
- [ ] No regression in existing functionality

### Phase 2 Completion
- [ ] C port implements all functionality of Python reference
- [ ] Cross-platform test suite passes on both Python and C implementations
- [ ] Performance benchmarks meet 2-4M instr/s target on M4@48MHz
- [ ] Memory footprint meets resource budget constraints
- [ ] C port builds successfully with no warnings on target toolchain
- [ ] C port deploys and runs on at least one embedded target (STM32)

### Phase 3 Completion
- [ ] Heap support implemented and tested
- [ ] Value/Command services implemented and tested
- [ ] Policy framework implemented and tested
- [ ] All Phase 3 features documented

### Phase 4 Completion
- [ ] Complete API documentation published
- [ ] Migration guide reviewed and validated with sample application
- [ ] Test coverage >= 80% for core VM functionality
- [ ] Performance benchmarks documented and reproducible
- [ ] All documentation reviewed and approved

### Overall Quality Criteria
- [ ] Zero known security vulnerabilities in VM implementation
- [ ] Zero known data corruption bugs
- [ ] All design requirements (DR-*) satisfied
- [ ] All design goals (DG-*) achieved or explicitly deferred with rationale
- [ ] CI pipeline green on all supported platforms
- [ ] Code follows project style guidelines and passes linting
- [ ] All changes committed with clear, descriptive commit messages
- [ ] Implementation notes updated in System/MiniVM.md

### Traceability
- [ ] All design requirements tracked to implementation
- [ ] All test cases traced to requirements
- [ ] All gaps from Study document addressed or explicitly deferred
- [ ] DependencyTree.md updated with completion status

---

## Cross-References

**Design Documents:**
- [04.01--VM.md](../../../04--Design/04.01--VM.md) - VM Design Specification
- [System/MiniVM.md](../../system/MiniVM.md) - Implementation Notes

**Gap Analysis:**
- [01--Study.md](./01--Study.md) - Gap Analysis Study

**Dependencies:**
- [DependencyTree.md](../DependencyTree.md) - Cross-module dependency tracking

**Related Components:**
- Executive (scheduler integration, event stream)
- Mailbox (SVC module 0x05)
- HAL (future embedded port integration)
- Toolchain (assembler, disassembler, compiler)

**Test Specifications:**
- `main/06--Test/system/MiniVM_tests.md` - VM test plan

**ABI Documentation:**
- `docs/abi_syscalls.md` - Syscall definitions
- `docs/MVASM_SPEC.md` - Assembly language specification
- `docs/hxe_format.md` - Executable format
- `docs/executive_protocol.md` - Executive JSON-RPC protocol

---

**Last Updated:** 2025-10-31  
**Status:** Initial Plan  
**Owner:** VM Implementation Team

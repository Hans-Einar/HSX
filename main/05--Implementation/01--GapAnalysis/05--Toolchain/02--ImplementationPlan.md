# Toolchain Implementation Plan

## Overview

This implementation plan addresses the gaps identified in the Toolchain Study document ([01--Study.md](./01--Study.md)). The plan is organized chronologically with clear dependencies tracked in [DependencyTree.md](../DependencyTree.md).

**Design Reference:** [04.05--Toolchain.md](../../../04--Design/04.05--Toolchain.md)

**Note:** Core pipeline is functional (assembler, LLVM lowering, linker, unified build script). This plan focuses on HXE v2 format support, debug metadata, and ISA completion.

---

## Phase 1: HXE v2 Format Support

### 1.1 Update HXE Header Format

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies HXE version 0x0002 with metadata sections (sections 4.2.2, 4.2.3). Foundation for declarative value/command/mailbox registration. Blocks ValCmd and Mailbox metadata support.

**Todo:**
- [ ] Add version field support to HXE header (0x0001 vs 0x0002)
- [ ] Add app_name field (32 bytes at offset 0x20)
- [ ] Add allow_multiple_instances flag
- [ ] Add meta_offset field (pointer to section table)
- [ ] Add meta_count field (number of metadata sections)
- [ ] Update HXE header structure in `python/build_hxe.py`
- [ ] Maintain backward compatibility with v0.0001
- [ ] Add HXE v2 header tests
- [ ] Update `docs/hxe_format.md` with v2 specification

---

### 1.2 Define Metadata Section Table Format

**Priority:** HIGH  
**Dependencies:** 1.1 (HXE v2 header)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Section table specifies location and size of .value, .cmd, .mailbox sections. Required for metadata preprocessing.

**Todo:**
- [ ] Design section table entry format (section_type, offset, size)
- [ ] Define section types: VALUE (0x01), COMMAND (0x02), MAILBOX (0x03)
- [ ] Specify table layout (array of entries following header)
- [ ] Document table format in `docs/hxe_format.md`
- [ ] Add section table encoding/decoding functions
- [ ] Add section table tests
- [ ] Validate table integrity (no overlaps, within bounds)

---

### 1.3 Update Linker for v2

**Priority:** HIGH  
**Dependencies:** 1.1 (HXE v2 header), 1.2 (Section table format)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Linker must generate HXE v2 executables with metadata sections. Design specifies --app-name and --allow-multiple-instances parameters (section 4.2.3).

**Todo:**
- [ ] Add `--app-name` parameter to `python/hld.py` (required)
- [ ] Add `--allow-multiple-instances` flag to `python/hld.py`
- [ ] Add `--hxe-version` parameter (default v2, allow v1 for compatibility)
- [ ] Implement section table generation
- [ ] Write metadata sections to HXE file
- [ ] Update CRC calculation to include metadata
- [ ] Add v2 linker tests (with/without metadata)
- [ ] Update linker documentation

---

### 1.4 Update Loader

**Priority:** HIGH  
**Dependencies:** 1.3 (Linker v2 support), Executive Phase 3.1 (HXE v2 preprocessing)  
**Estimated Effort:** 2-3 days

**Rationale:**  
VM/executive must parse HXE v2 headers and section tables. Enables metadata preprocessing before VM execution.

**Todo:**
- [ ] Update HXE loader to detect version field
- [ ] Parse v2 header fields (app_name, meta_offset, meta_count)
- [ ] Parse section table and extract metadata sections
- [ ] Maintain v1 compatibility (fallback for old HXE files)
- [ ] Add loader tests for v1 and v2 formats
- [ ] Document loader behavior for both versions
- [ ] Coordinate with Executive HXE v2 support

---

## Phase 2: Metadata Section Pipeline

### 2.1 Document Pragma Syntax

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design specifies C preprocessor directives for value/command/mailbox declarations (sections 4.2.1, 4.2.2). Developers need syntax documentation.

**Todo:**
- [ ] Define `#pragma hsx_value(group, id, name, unit, ...)` syntax
- [ ] Define `#pragma hsx_command(group, id, name, help, ...)` syntax
- [ ] Define `#pragma hsx_mailbox(name, capacity, mode)` syntax
- [ ] Document pragma parameters and options
- [ ] Provide C code examples using pragmas
- [ ] Document how pragmas map to LLVM IR metadata
- [ ] Create pragma reference documentation

---

### 2.2 Pragma Extraction in hsx-llc

**Priority:** HIGH  
**Dependencies:** 2.1 (Pragma syntax documentation)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies parsing pragma directives from LLVM IR metadata (section 4.2.1). Extracts value/command/mailbox declarations from C source.

**Todo:**
- [ ] Parse LLVM IR metadata nodes (look for pragma annotations)
- [ ] Extract value declarations from metadata
- [ ] Extract command declarations from metadata
- [ ] Extract mailbox declarations from metadata
- [ ] Store extracted metadata in intermediate structure
- [ ] Add pragma extraction tests
- [ ] Document extraction process

---

### 2.3 Metadata Directive Emission

**Priority:** HIGH  
**Dependencies:** 2.2 (Pragma extraction)  
**Estimated Effort:** 2-3 days

**Rationale:**  
hsx-llc must emit .value, .cmd, .mailbox MVASM directives from pragma data (section 4.2.2).

**Todo:**
- [ ] Design MVASM directive syntax (.value group=X id=Y name="..." ...)
- [ ] Implement .value directive emission
- [ ] Implement .cmd directive emission
- [ ] Implement .mailbox directive emission
- [ ] Format metadata as MVASM directives in output
- [ ] Add directive emission tests
- [ ] Document MVASM directive syntax in `docs/MVASM_SPEC.md`

---

### 2.4 Assembler Metadata Parsing

**Priority:** HIGH  
**Dependencies:** 2.3 (Directive syntax)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Assembler must parse metadata directives from MVASM source (section 4.2.2).

**Todo:**
- [ ] Implement .value directive parser in `python/asm.py`
- [ ] Implement .cmd directive parser
- [ ] Implement .mailbox directive parser
- [ ] Validate directive parameters
- [ ] Store metadata in intermediate structures
- [ ] Add assembler metadata parsing tests
- [ ] Update assembler documentation

---

### 2.5 Metadata Section Encoding

**Priority:** HIGH  
**Dependencies:** 2.4 (Assembler parsing), 1.2 (Section format)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Assembler must encode metadata sections per HXE format spec in HXO objects (section 4.2.2).

**Todo:**
- [ ] Design HXO metadata section format
- [ ] Implement .value section encoding
- [ ] Implement .cmd section encoding
- [ ] Implement .mailbox section encoding
- [ ] Include metadata sections in HXO output
- [ ] Add section encoding tests
- [ ] Document HXO metadata format

---

### 2.6 Linker Metadata Merging

**Priority:** HIGH  
**Dependencies:** 2.5 (Section encoding)  
**Estimated Effort:** 4-5 days

**Rationale:**  
Linker must merge metadata sections from multiple HXO inputs, deduplicate strings, build section table (section 4.2.3).

**Todo:**
- [ ] Implement metadata section extraction from HXO inputs
- [ ] Merge .value sections from multiple objects
- [ ] Merge .cmd sections from multiple objects
- [ ] Merge .mailbox sections from multiple objects
- [ ] Deduplicate strings (names, units, help text)
- [ ] Build unified section table
- [ ] Write merged sections to HXE output
- [ ] Add linker metadata merging tests
- [ ] Document merging behavior

---

## Phase 3: Debug Metadata Infrastructure

### 3.1 LLVM Debug Metadata Extraction (Phase 1)

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies 3-phase plan for debug metadata extraction (section 4.2.1). Phase 1 focuses on function-level metadata.

**Todo:**
- [ ] Parse `!DISubprogram` nodes from LLVM IR
- [ ] Extract function names from debug metadata
- [ ] Extract source file names from `!DIFile` nodes
- [ ] Extract function start lines
- [ ] Build function metadata structure
- [ ] Add debug extraction tests
- [ ] Document debug metadata structures

---

### 3.2 Implement --emit-debug Flag

**Priority:** MEDIUM  
**Dependencies:** 3.1 (Debug extraction Phase 1)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies --emit-debug flag to generate .dbg JSON files (section 4.2.1).

**Todo:**
- [ ] Add `--emit-debug` flag to `python/hsx-llc.py`
- [ ] Design .dbg JSON schema (functions, files, line mappings)
- [ ] Implement .dbg file generation
- [ ] Write function metadata to .dbg file
- [ ] Add --emit-debug tests
- [ ] Document .dbg file format
- [ ] Integrate with unified build script

---

### 3.3 Track Instruction Mappings (Phase 2)

**Priority:** MEDIUM  
**Dependencies:** 3.1 (Debug extraction), 3.2 (--emit-debug)  
**Estimated Effort:** 1 week

**Rationale:**  
Phase 2 requires mapping LLVM instructions to MVASM line numbers (section 4.2.1). Enables source-level debugging.

**Todo:**
- [ ] Parse `!DILocation` metadata for each LLVM instruction
- [ ] Track source line numbers during lowering
- [ ] Map LLVM instruction to MVASM line
- [ ] Store instruction mappings in .dbg file
- [ ] Add instruction mapping tests
- [ ] Document mapping format
- [ ] Verify mapping accuracy

---

### 3.4 Implement --emit-sym Flag

**Priority:** MEDIUM  
**Dependencies:** 3.2 (--emit-debug), 1.3 (Linker v2)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Design specifies --emit-sym flag to generate debugger symbol files (section 4.2.3). Linker combines .dbg files with final addresses.

**Todo:**
- [ ] Add `--emit-sym` flag to `python/hld.py`
- [ ] Parse .dbg files from object inputs
- [ ] Resolve addresses after linking
- [ ] Generate .sym JSON file with final addresses
- [ ] Include function boundaries
- [ ] Include memory region information
- [ ] Add --emit-sym tests
- [ ] Integrate with unified build script

---

### 3.5 Symbol File Schema Finalization

**Priority:** LOW  
**Dependencies:** 3.4 (--emit-sym)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Complete JSON schema for functions, variables, labels, instructions, memory regions (section 4.2.3). Ensures debugger compatibility.

**Todo:**
- [ ] Finalize .sym JSON schema
- [ ] Add functions section (name, addr, size, file, line)
- [ ] Add variables section (name, addr, type, scope)
- [ ] Add labels section (name, addr)
- [ ] Add instructions section (addr, source_line, source_file)
- [ ] Add memory_regions section (type, start, end)
- [ ] Document complete schema in `docs/symbol_format.md`
- [ ] Add schema validation tests

---

## Phase 4: Source Path Handling

### 4.1 Integrate -fdebug-prefix-map

**Priority:** MEDIUM  
**Dependencies:** 3.2 (--emit-debug)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design specifies using Clang -fdebug-prefix-map for relative paths (section 4.2.4). Enables portable debug builds.

**Todo:**
- [ ] Ensure build scripts use `-fdebug-prefix-map` flag
- [ ] Test path remapping in debug metadata
- [ ] Verify relative paths in .dbg files
- [ ] Document -fdebug-prefix-map usage
- [ ] Add path remapping tests
- [ ] Provide build script examples

---

### 4.2 Generate sources.json

**Priority:** LOW  
**Dependencies:** 4.1 (-fdebug-prefix-map)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Design specifies sources.json for source list mapping (section 4.2.4). Helps debuggers resolve source files.

**Todo:**
- [ ] Design sources.json format (relative path → absolute path)
- [ ] Generate sources.json during build
- [ ] Include all source files compiled
- [ ] Store build-time absolute paths
- [ ] Add sources.json generation tests
- [ ] Document sources.json format

---

### 4.3 Test Path Resolution

**Priority:** LOW  
**Dependencies:** 4.2 (sources.json)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Validate debugger can resolve source files across different build environments (section 4.2.4).

**Todo:**
- [ ] Create test builds in different directories
- [ ] Verify path resolution with sources.json
- [ ] Test debugger source file loading
- [ ] Test missing source file handling
- [ ] Document resolution algorithm
- [ ] Add edge case tests (symlinks, network paths)

---

### 4.4 Document Workflow

**Priority:** LOW  
**Dependencies:** 4.1, 4.2, 4.3  
**Estimated Effort:** 1 day

**Rationale:**  
Provide examples and guidelines for portable debug builds (section 4.2.4).

**Todo:**
- [ ] Document recommended build workflow
- [ ] Provide Makefile examples
- [ ] Provide build script examples
- [ ] Document common pitfalls
- [ ] Add troubleshooting guide
- [ ] Create tutorial for portable builds

---

## Phase 5: ISA Completion

### 5.1 Add Shift Opcodes

**Priority:** HIGH  
**Dependencies:** VM Phase 1.1 (Shift operations)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design references shift operations (LSL, LSR, ASR). Coordinates with VM ISA completion. Essential for LLVM lowering and C compilation.

**Todo:**
- [ ] Define LSL, LSR, ASR opcodes (coordinate with VM)
- [ ] Implement opcode encoding in `python/asm.py`
- [ ] Update OPC dictionary with shift opcodes
- [ ] Add shift instruction parsing
- [ ] Add shift instruction tests
- [ ] Update `docs/MVASM_SPEC.md` with shift syntax
- [ ] Update disassembler for shift opcodes

---

### 5.2 Add Carry Arithmetic

**Priority:** HIGH  
**Dependencies:** VM Phase 1.2 (Carry-aware arithmetic)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design references ADC, SBC for multi-precision arithmetic. Coordinates with VM ISA completion.

**Todo:**
- [ ] Define ADC, SBC opcodes (coordinate with VM)
- [ ] Implement opcode encoding in `python/asm.py`
- [ ] Update OPC dictionary with ADC, SBC
- [ ] Add carry arithmetic parsing
- [ ] Add carry arithmetic tests
- [ ] Update `docs/MVASM_SPEC.md` with ADC/SBC syntax
- [ ] Update disassembler for ADC/SBC

---

### 5.3 Update Opcode Table

**Priority:** HIGH  
**Dependencies:** 5.1 (Shifts), 5.2 (Carry), VM Phase 1.4 (DIV)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Synchronize OPC dictionary with VM design spec including DIV. Ensures toolchain and VM agree on encoding.

**Todo:**
- [ ] Review VM design spec opcode table
- [ ] Update OPC dictionary in `python/asm.py`
- [ ] Add DIV opcode (0x13)
- [ ] Verify all opcodes match VM implementation
- [ ] Add opcode validation tests
- [ ] Document complete opcode table
- [ ] Update MVASM spec with all opcodes

---

### 5.4 Test New Opcodes

**Priority:** HIGH  
**Dependencies:** 5.3 (Opcode table update)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Comprehensive testing for all new instructions ensures correctness.

**Todo:**
- [ ] Add assembler tests for shift opcodes
- [ ] Add assembler tests for ADC/SBC
- [ ] Add assembler tests for DIV
- [ ] Add disassembler tests for new opcodes
- [ ] Add integration tests (assemble → disassemble)
- [ ] Test edge cases (invalid operands, etc.)
- [ ] Verify opcode encoding matches VM

---

## Phase 6: Toolchain Quality

### 6.1 Deterministic Build Validation

**Priority:** MEDIUM  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design requires bit-identical output for same inputs (section 4.1). Critical for reproducible builds and verification.

**Todo:**
- [ ] Identify sources of non-determinism (timestamps, ordering)
- [ ] Remove or fix non-deterministic behavior
- [ ] Add deterministic build tests (build twice, compare outputs)
- [ ] Test with different build environments
- [ ] Document determinism guarantees
- [ ] Add CI tests for deterministic builds

---

### 6.2 Register Allocation Improvements

**Priority:** LOW  
**Dependencies:** None  
**Estimated Effort:** 1-2 weeks

**Rationale:**  
Current linear scan algorithm is basic. Better allocation reduces spills and improves code quality.

**Todo:**
- [ ] Profile current register allocation
- [ ] Identify common spill scenarios
- [ ] Implement better spill cost heuristics
- [ ] Add register coalescing
- [ ] Add live range splitting
- [ ] Benchmark improvements
- [ ] Add register allocation tests
- [ ] Document allocation algorithm

---

### 6.3 Expand Test Coverage

**Priority:** MEDIUM  
**Dependencies:** Phases 1-5 complete  
**Estimated Effort:** 1 week

**Rationale:**  
Complete build pipeline with debug metadata needs comprehensive testing.

**Todo:**
- [ ] Add end-to-end tests with metadata
- [ ] Add multi-file compilation tests
- [ ] Add debug metadata validation tests
- [ ] Add error handling tests
- [ ] Add performance regression tests
- [ ] Measure test coverage metrics (>80% target)
- [ ] Add tests to CI pipeline
- [ ] Document test architecture

---

### 6.4 Performance Profiling

**Priority:** LOW  
**Dependencies:** None  
**Estimated Effort:** 1 week

**Rationale:**  
Identify and optimize bottlenecks in LLVM lowering and linking. Improves developer experience.

**Todo:**
- [ ] Profile hsx-llc with large inputs
- [ ] Profile linker with many objects
- [ ] Identify bottlenecks (parsing, allocation, encoding)
- [ ] Optimize hot paths
- [ ] Benchmark before/after optimizations
- [ ] Document performance characteristics
- [ ] Add performance benchmarks to CI

---

## Phase 7: Advanced Features

### 7.1 Variable Tracking (Phase 3)

**Priority:** LOW  
**Dependencies:** 3.3 (Instruction mappings Phase 2)  
**Estimated Effort:** 2-3 weeks

**Rationale:**  
Extract `!DILocalVariable` metadata for watch expressions (section 4.2.1 Phase 3). Enables variable inspection in debugger.

**Todo:**
- [ ] Parse `!DILocalVariable` nodes from LLVM IR
- [ ] Track variable locations (registers, stack offsets)
- [ ] Handle variable liveness ranges
- [ ] Store variable metadata in .dbg files
- [ ] Update .sym files with variable information
- [ ] Add variable tracking tests
- [ ] Document variable metadata format
- [ ] Integrate with debugger watch expressions

---

### 7.2 Instruction-Level Line Tracking (Phase 2)

**Priority:** LOW  
**Dependencies:** 3.3 (Instruction mappings)  
**Estimated Effort:** 1 week

**Rationale:**  
Map every MVASM instruction to source line (Phase 2 completion). Enables precise source-level stepping.

**Todo:**
- [ ] Ensure every MVASM instruction has source line mapping
- [ ] Handle instructions generated without source (prologue, epilogue)
- [ ] Add line mapping completeness tests
- [ ] Verify debugger stepping behavior
- [ ] Document line mapping guarantees

---

### 7.3 Library Support

**Priority:** LOW  
**Dependencies:** Phase 2 complete (Metadata pipeline)  
**Estimated Effort:** 3-4 weeks

**Rationale:**  
Design mentions standard library with values/commands/mailboxes. Enables code reuse and standard interfaces.

**Todo:**
- [ ] Design standard library structure
- [ ] Create common value definitions (version, uptime, etc.)
- [ ] Create common command definitions (reset, status, etc.)
- [ ] Create common mailbox definitions (stdio, log, etc.)
- [ ] Package library as linkable objects
- [ ] Add library usage examples
- [ ] Document library API
- [ ] Create library distribution package

---

### 7.4 Native Toolchain Port

**Priority:** LOW (Deferred)  
**Dependencies:** All phases complete  
**Estimated Effort:** 3-6 months

**Rationale:**  
Current Python implementation is reference. C/C++ port for performance. Not critical but improves large project build times.

**Todo:**
- [ ] Benchmark Python toolchain performance
- [ ] Identify performance-critical components
- [ ] Design C/C++ port architecture
- [ ] Port assembler to C/C++
- [ ] Port LLVM lowering to C++ (use LLVM C++ API)
- [ ] Port linker to C/C++
- [ ] Create cross-platform build system
- [ ] Add native toolchain tests
- [ ] Benchmark native vs Python performance
- [ ] Maintain Python reference for comparison

---

## Definition of Done (DoD)

This implementation is considered complete when all of the following criteria are met:

### Phase 1 Completion
- [ ] HXE v2 header format implemented with app_name and metadata fields
- [ ] Metadata section table format defined and documented
- [ ] Linker generates HXE v2 executables with metadata sections
- [ ] Loader parses HXE v2 headers and section tables
- [ ] Backward compatibility with HXE v1 maintained
- [ ] All Phase 1 tests pass with 100% success rate
- [ ] `docs/hxe_format.md` updated with v2 specification

### Phase 2 Completion
- [ ] Pragma syntax documented for value/command/mailbox
- [ ] hsx-llc extracts pragmas from LLVM IR metadata
- [ ] hsx-llc emits .value/.cmd/.mailbox MVASM directives
- [ ] Assembler parses metadata directives
- [ ] Assembler encodes metadata sections in HXO
- [ ] Linker merges metadata sections with string deduplication
- [ ] All Phase 2 tests pass
- [ ] Complete metadata pipeline functional (C source → HXE v2)
- [ ] `docs/MVASM_SPEC.md` updated with directive syntax

### Phase 3 Completion
- [ ] LLVM debug metadata extraction (Phase 1: functions)
- [ ] --emit-debug flag generates .dbg JSON files
- [ ] Instruction mappings track LLVM → MVASM (Phase 2)
- [ ] --emit-sym flag generates .sym files with addresses
- [ ] Symbol file schema finalized and documented
- [ ] All Phase 3 tests pass
- [ ] Debugger integration verified with symbol files

### Phase 4 Completion
- [ ] -fdebug-prefix-map integration working
- [ ] sources.json generation functional
- [ ] Path resolution tested across environments
- [ ] Workflow documented with examples
- [ ] All Phase 4 tests pass
- [ ] Portable debug builds achievable

### Phase 5 Completion
- [ ] Shift opcodes (LSL, LSR, ASR) implemented in assembler
- [ ] Carry arithmetic (ADC, SBC) implemented in assembler
- [ ] Opcode table synchronized with VM design
- [ ] All new opcodes tested (assemble/disassemble)
- [ ] All Phase 5 tests pass
- [ ] MVASM spec updated with all instructions

### Phase 6 Completion
- [ ] Deterministic builds validated (bit-identical outputs)
- [ ] Register allocation improvements implemented
- [ ] Test coverage expanded (>80% for toolchain)
- [ ] Performance profiling completed and optimizations applied
- [ ] All Phase 6 tests pass
- [ ] Build performance acceptable (<5s for small projects)

### Phase 7 Completion
- [ ] Variable tracking (Phase 3) implemented
- [ ] Instruction-level line tracking complete (Phase 2)
- [ ] Standard library designed and implemented
- [ ] Native toolchain port (deferred - not required for DoD)
- [ ] All Phase 7 tests pass
- [ ] Advanced debug features functional

### Overall Quality Criteria
- [ ] Zero known toolchain bugs causing incorrect code generation
- [ ] All design requirements (DR-*) satisfied
- [ ] All design goals (DG-*) achieved or explicitly deferred with rationale
- [ ] CI pipeline green on all supported platforms
- [ ] Code follows project style guidelines and passes linting
- [ ] All changes committed with clear, descriptive commit messages
- [ ] Complete toolchain documentation (assembler, linker, build scripts)
- [ ] Integration with VM verified (ISA opcodes match)
- [ ] Integration with Executive verified (HXE v2 preprocessing)
- [ ] Integration with ValCmd/Mailbox verified (metadata sections)

### Traceability
- [ ] All design requirements tracked to implementation
- [ ] All test cases traced to requirements
- [ ] All gaps from Study document addressed or explicitly deferred
- [ ] DependencyTree.md updated with completion status
- [ ] Test specification documented in `main/06--Test/system/Toolchain_tests.md`

---

## Cross-References

**Design Documents:**
- [04.05--Toolchain.md](../../../04--Design/04.05--Toolchain.md) - Toolchain Design Specification

**Gap Analysis:**
- [01--Study.md](./01--Study.md) - Gap Analysis Study

**Dependencies:**
- [DependencyTree.md](../DependencyTree.md) - Cross-module dependency tracking

**Related Components:**
- VM (ISA opcodes: LSL, LSR, ASR, ADC, SBC, DIV)
- Executive (HXE v2 preprocessing, debugger APIs)
- ValCmd (metadata sections for values/commands)
- Mailbox (metadata sections for mailboxes)
- Debugger (symbol files, source resolution)

**Test Specifications:**
- Test plans to be documented in `main/06--Test/system/Toolchain_tests.md`

**Documentation:**
- `docs/MVASM_SPEC.md` - MVASM assembly language specification
- `docs/hxe_format.md` - HXE executable format specification
- `docs/hsx_llc.md` - LLVM lowering documentation
- `docs/symbol_format.md` - Symbol file format (to be created)

**Tools:**
- `python/asm.py` - MVASM assembler
- `python/hsx-llc.py` - LLVM to MVASM lowering
- `python/hld.py` - HXE linker
- `python/hsx-cc-build.py` - Unified build script
- `python/build_hxe.py` - HXE builder utility
- `python/disasm_util.py` - Disassembler utility

---

**Last Updated:** 2025-10-31  
**Status:** Initial Plan  
**Owner:** Toolchain Implementation Team

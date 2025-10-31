# Gap Analysis: Toolchain

## 1. Scope Recap

_Brief synopsis of the design document and links back to the design specification._

**Design Reference:** [04.05--Toolchain.md](../../../04--Design/04.05--Toolchain.md)

**Summary:**  
The Toolchain design specifies a build-time transformation pipeline producing deterministic HXE executables. It comprises:

- **LLVM lowering pipeline** (`hsx-llc.py`) converting IR to MVASM with register allocation and ABI compliance
- **Assembler** (`asm.py`) producing HXO object files with relocation and debug metadata
- **Linker** (`hld.py`) merging HXO files into HXE executables with section merging and symbol resolution
- **Unified build script** (`hsx-cc-build.py`) orchestrating the complete pipeline from C source to debuggable executable
- **Debug metadata generation** - symbols, line info, value/command descriptors for tooling
- **HXE v2 format support** - metadata sections (`.value`, `.cmd`, `.mailbox`) for declarative registration
- **Standard toolchain architecture** - assembler always emits objects (.hxo), linker creates executables (.hxe)

---

## 2. Current Implementation

_What already exists today that satisfies the design intent._

**Code Paths:**
- **Assembler:** `python/asm.py` (825 lines)
  - Full MVASM parser and opcode encoder
  - HXO object file emission (JSON format)
  - Relocation and symbol table generation
  - Section handling (.text, .data, .bss)
  - `--emit-hxe` convenience wrapper (calls linker internally)
- **LLVM Lowering:** `python/hsx-llc.py` (1,755 lines)
  - LLVM IR parser and basic block extraction
  - Register allocation (linear scan algorithm)
  - Instruction lowering to MVASM
  - ABI compliance (calling convention, stack frame)
  - SVC encoding for syscalls
- **Linker:** `python/hld.py` (208 lines)
  - Multi-object HXO linking
  - Symbol resolution and relocation application
  - Section merging (.text, .data, .bss)
  - HXE executable generation with CRC
  - Entry point calculation
- **Unified Build Script:** `python/hsx-cc-build.py` (473 lines)
  - Complete pipeline orchestration (C → IR → MVASM → HXO → HXE)
  - Makefile integration and direct source mode
  - Debug metadata generation
  - Source path handling with `-fdebug-prefix-map`
- **HXE Builder:** `python/build_hxe.py` (67 lines) - Utility for HXE construction
- **Disassembler:** `python/disasm_util.py` - Opcode decoding utility

**Tests:**
- `python/tests/test_asm_local_relocs.py` - Assembler relocation tests
- `python/tests/test_asm_sections.py` - Section handling tests
- `python/tests/test_hsx_cc_build_integration.py` - End-to-end build integration
- `python/tests/test_asm_brk.py` - BRK opcode tests
- `python/tests/test_hsx_cc_build.py` - Build script tests
- `python/tests/test_asm_emit_hxo.py` - HXO emission tests
- `python/tests/test_asm_duplicate_label.py` - Label conflict tests
- **Total test coverage:** 1,063 lines across 7 test files

**Tools:**
- `python/asm.py` - Standalone assembler CLI
- `python/hsx-llc.py` - Standalone LLVM lowering CLI
- `python/hld.py` - Standalone linker CLI
- `python/hsx-cc-build.py` - Unified build command
- Sample MVASM programs: `python/sampleprog.mvasm`, `python/sample2.mvasm`

**Documentation:**
- `docs/MVASM_SPEC.md` - MVASM assembly language specification (4,498 bytes)
- `docs/hxe_format.md` - HXE executable format specification (9,961 bytes)
- `docs/hsx_llc.md` - LLVM lowering documentation (4,015 bytes)
- Design documents: `main/04--Design/04.05--Toolchain.md` (513 lines)
- Architecture: `main/03--Architecture/03.05--Toolkit.md` (focuses on shell/debugger, not toolchain)

---

## 3. Missing or Partial Coverage

_Gaps that block full compliance with the design._

**Open Items:**
- **HXE v2 format support (4.2.2, 4.2.3):** Design specifies HXE version 0x0002 with metadata sections (`.value`, `.cmd`, `.mailbox`). Current implementation only supports v0.0001 - no metadata section table or app_name field in header.
- **Pragma directive processing (4.2.1, 4.2.2):** Design specifies parsing `#pragma hsx_value`, `#pragma hsx_command`, `#pragma hsx_mailbox` from LLVM IR and emitting metadata section directives. Not implemented - no pragma extraction.
- **Metadata section assembly (4.2.2):** Design specifies assembler should parse `.value`, `.cmd`, `.mailbox` directives and encode per HXE format spec. Not implemented - assembler only handles .text/.data/.bss.
- **Metadata section linking (4.2.3):** Design specifies linker should merge metadata sections, build section table, deduplicate strings. Not implemented - linker has no metadata handling.
- **Debug metadata generation (4.2.1, 4.2.3):** Design specifies `--emit-debug` flag to generate `.dbg` JSON files with function names, line mappings, LLVM→MVASM correlations. Not implemented.
- **Symbol file (.sym) generation (4.2.3):** Design specifies `--emit-sym` flag to generate debugger symbol files with line mappings, function boundaries, memory regions. Not implemented.
- **Source path handling (4.2.4):** Design specifies `-fdebug-prefix-map` integration and `sources.json` generation for debugger path resolution. Partially implemented in build script but not tested.
- **App name handling (4.2.3, 4.3):** Design specifies `--app-name` required parameter and `--allow-multiple-instances` flag for HXE v2 header. Not implemented - linker doesn't accept these parameters.
- **Missing ISA opcodes:** Design references shift operations (LSL, LSR, ASR), carry arithmetic (ADC, SBC), and PSW flags. Assembler has placeholders but no encoding for these opcodes.
- **Deterministic builds (4.1):** Design requires bit-identical output for same inputs. Not formally validated or tested.
- **Register allocation improvements:** Current linear scan algorithm is basic. Design hints at more sophisticated allocation with spill optimization.

**Deferred Features:**
- **LLVM debug metadata extraction (4.2.1):** Design has 3-phase plan - Phase 1 (function-level), Phase 2 (instruction-level), Phase 3 (variable tracking). None implemented.
- **Library support:** Design mentions future library linking with standard values/commands. Not scoped.
- **LTO and whole-program optimization:** Design mentions as future enhancement. Not scoped.
- **CMake support (5.2):** Design mentions future CMake integration. Not implemented - only Makefile supported.
- **Native toolchain port:** Current Python implementation is reference. C/C++ port for performance not started.

**Documentation Gaps:**
- HXE v2 format specification incomplete - metadata section table format not fully documented
- Pragma directive syntax not documented - no examples of how to use in C code
- Symbol file (.sym) format incomplete - JSON schema partially defined but not finalized
- Missing examples of metadata section directives in MVASM
- No architecture document specifically for toolchain (03.05 is Toolkit/debugger focused)

---

## 4. Next Actions

_Ordered steps to close the gaps._

**Priority Actions:**

**Phase 1: HXE v2 Format Support**
1. **Update HXE header format** - Add version 0x0002 support with app_name field (32 bytes at offset 0x20), allow_multiple_instances flag, meta_offset, meta_count fields
2. **Define metadata section table format** - Specify binary layout for section table entries pointing to `.value`, `.cmd`, `.mailbox` sections
3. **Update linker for v2** - Implement `--app-name` and `--allow-multiple-instances` parameters, emit v0.0002 headers with section table
4. **Update loader** - Modify VM/executive to parse HXE v2 headers and section tables

**Phase 2: Metadata Section Pipeline**
5. **Document pragma syntax** - Define C preprocessor directive syntax for `#pragma hsx_value`, `#pragma hsx_command`, `#pragma hsx_mailbox`
6. **Pragma extraction in hsx-llc** - Parse pragma directives from LLVM IR metadata and extract value/command/mailbox declarations
7. **Metadata directive emission** - Generate `.value`, `.cmd`, `.mailbox` MVASM directives from pragma data
8. **Assembler metadata parsing** - Implement parsing of metadata directives in asm.py
9. **Metadata section encoding** - Encode metadata sections per HXE format spec in HXO objects
10. **Linker metadata merging** - Merge metadata sections from multiple HXO inputs, deduplicate strings, build section table

**Phase 3: Debug Metadata Infrastructure**
11. **LLVM debug metadata extraction** - Parse `!DISubprogram`, `!DILocation`, `!DIFile` nodes from LLVM IR (Phase 1: function-level)
12. **Implement `--emit-debug` flag** - Generate `.dbg` JSON files with function names, start lines, and source file mappings
13. **Track instruction mappings** - Map LLVM instructions to MVASM line numbers for Phase 2 line info
14. **Implement `--emit-sym` flag** - Generate `.sym` JSON files from `.dbg` inputs with final addresses after linking
15. **Symbol file schema finalization** - Complete JSON schema for functions, variables, labels, instructions, memory regions

**Phase 4: Source Path Handling**
16. **Integrate `-fdebug-prefix-map`** - Ensure build scripts use Clang flag for relative paths
17. **Generate `sources.json`** - Create source list mapping relative to absolute paths per section 4.2.4
18. **Test path resolution** - Validate debugger can resolve source files across different build environments
19. **Document workflow** - Provide examples and guidelines for portable debug builds

**Phase 5: ISA Completion**
20. **Add shift opcodes** - Implement LSL, LSR, ASR encoding in assembler (coordinates with VM gap Phase 1)
21. **Add carry arithmetic** - Implement ADC, SBC encoding (coordinates with VM gap Phase 1)
22. **Update opcode table** - Synchronize OPC dictionary with VM design spec including DIV
23. **Test new opcodes** - Add assembler/disassembler tests for all new instructions

**Phase 6: Toolchain Quality**
24. **Deterministic build validation** - Add tests verifying bit-identical output for same inputs
25. **Register allocation improvements** - Enhance linear scan with better spill cost heuristics
26. **Expand test coverage** - Add integration tests for complete build pipeline with debug metadata
27. **Performance profiling** - Identify and optimize bottlenecks in LLVM lowering and linking

**Phase 7: Advanced Features**
28. **Variable tracking (Phase 3)** - Extract `!DILocalVariable` metadata for watch expressions
29. **Instruction-level line tracking (Phase 2)** - Map every MVASM instruction to source line
30. **Library support** - Design and implement standard library with values/commands/mailboxes
31. **Native toolchain port** - Implement performance-critical components (lowering, linking) in C/C++

**Cross-References:**
- Design Requirements: DR-1.2, DR-1.3, DR-2.1a, DR-2.2, DR-2.3, DR-2.5, DR-3.1
- Design Goals: DG-1.3, DG-1.4, DG-2.1, DG-2.2, DG-2.3, DG-3.1, DG-3.2, DG-3.3, DG-3.4, DG-3.5
- Related: VM ISA completion (shifts, ADC/SBC, DIV), Executive debugger APIs (symbol loading, disassembly), HXE v2 format (shared with ValCmd, Mailbox metadata)
- Dependencies: HXE v2 format blocks ValCmd/Mailbox declarative registration

---

**Last Updated:** 2025-10-31  
**Status:** In Progress (Core pipeline functional, HXE v2 and debug metadata not implemented)

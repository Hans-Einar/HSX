# Project Study — HSX Runtime & Tooling

> Foundational research and architectural explorations that guided the HSX platform design.

## Study Participants
- Runtime/Tooling engineering (core VM and executive team)
- Firmware/Platform engineers familiar with AVR128DA28 and ARM Cortex‑M deployments
- Tooling leads focused on shell/debugger requirements

## Problem Frame
- Deploy domain-specific logic to CAN/J1939 nodes without recompiling host firmware.
- Provide deterministic, low-latency execution suitable for resource-constrained MCUs.
- Accommodate the fact that many microcontrollers (e.g., AVR) execute from flash and cannot safely load/execute new code in RAM at runtime; an executive must therefore broker HSX applications and provide services such as provisioning and IPC. (MCUs with RAM execute support, like ARM Cortex-M4 with CCM RAM, still benefit from the executive for lifecycle and isolation.)
- Keep the developer workflow productive (Python-first) while preserving a clear migration path to native C implementations.

## Inspirations & Prior Art
### Processor Architecture
- **TMS9900**: uses a workspace pointer so register files live in RAM. Inspired the decision to store HSX architectural registers in memory and switch contexts by updating a base pointer rather than copying register banks.
- **Harvard microcontrollers (AVR/ARM)**: highlight the need for tight control over memory use and deterministic interrupt latency, favouring a small interpreter core over a full OS.

### Messaging & Concurrency
- **VMS / RSX-11 mailboxes**: multi-subscriber mailboxes with configurable delivery semantics (first-reader clears, all-readers clears, taps). Informs HSX mailbox design for inter-task communication and HAL bridging.
- **Embedded control loops**: demonstrate value of lightweight cooperative scheduling managed by a host executive rather than an OS inside the VM.

### Tooling & Provisioning
- **PLC/industrial controllers**: separate host runtime from downloadable “logic apps,” motivating HSX app packaging (`.hxe`) and remote provisioning over CAN or local media.
- **Modern embedded debuggers**: event-driven designs that keep the runtime simple while allowing rich host-side tooling.

## Architectural Hypotheses
1. **Host-controlled MiniVM**  
   - Keep the VM single-task and driven externally. Tasks are swapped by repointing the register base (TMS9900-style) and updating stack pointers.  
   - Avoid running a shell or OS inside the VM; the host executive provides scheduling, I/O, and lifecycle control.

2. **Mailbox-centric Communication**  
   - Provide named mailboxes with configurable retention policies so multiple HSX apps and HAL endpoints can exchange data without shared-state complexities.  
   - Extend mailbox semantics to support stdio, CAN frames, UART traffic, and future services.

3. **Python-first, C-friendly Tooling**  
   - Prototype VM, executive, and tooling in Python for rapid iteration.  
   - Define interfaces (RPC commands, HAL shims) that map cleanly onto a future native executive running on AVR/Cortex-M hardware.  
   - Plan an intermediate phase where the Python implementation mirrors C-style structure (explicit data structs, minimal dynamic features) to ease the port without sacrificing iteration speed.

4. **Provisioning & Deployment**  
   - Treat HSX apps as standalone payloads loaded at node startup (via CAN master broadcast, SD card, or direct host provisioning).  
   - Ensure the executive can validate and manage multiple apps without recompiling host firmware.

## Instruction Set & Toolchain Studies
### ISA Foundations
- **Definition:** Instruction Set Architecture (ISA) describes the programmer-visible interface of the processor (registers, instructions, encoding, memory model). HSX adopts a load/store ISA tailored for compact microcontroller deployments.
- **Register file sizing:** Surveyed 8 vs. 16 vs. 32 general-purpose register windows. Chose **16 32-bit registers (`R0`–`R15`)** to balance:
  - Efficient C code generation (matches ARM calling conventions with four argument registers).
  - Manageable memory footprint per task when registers live in RAM (16 × 4 B = 64 B workspace).
  - Compatibility with the TMS9900-inspired register-base approach (pointer into RAM workspace).
- **Workspace pointer rationale:** Context switching becomes a constant-time operation—just update `reg_base` (and metadata such as `pc`, `sp`, `psw`) rather than copying an entire register bank. The CPU executes the same `reg_base + offset` address arithmetic for register loads regardless of the active task, so there is no per-instruction penalty relative to a copied array. This keeps latency predictable, enforces stack guards via per-task arenas, and aligns with the architecture/toolchain expectations for both the Python prototype and the future C implementation.

### Workspace Pointer — Study Notes
| Aspect | Workspace pointer model | Full-copy model | Notes |
| --- | --- | --- | --- |
| Context switch cost | O(1): update `reg_base`, stack metadata, `pc`, `psw`. | O(N): copy 16×32-bit registers (and potentially stack segments) per swap. | Per-task allocations reside in VM memory, so switching is just pointer retargeting. |
| Instruction cost | Each register access loads from `reg_base + offset`; CPU handles addition inline. | Direct array indexing after copy; no offset arithmetic during execution. | Addition is required in both designs once values reside in memory; modern MCUs perform it in the same load instruction. |
| Memory isolation | Natural isolation: each task owns a register bank and stack arena; stack guards operate on true base addresses. | Requires careful clone-and-restore to maintain guards; easy to leak shared state via copy mistakes. | Our mailbox/scheduling design depends on per-task arenas for safety diagnostics. |
| Determinism | Constant-time switch, predictable latency; instrumentation (step counters) straightforward. | Latency proportional to register/stack size; jitter increases with larger contexts or memcpy overhead. | Real-time goals favour bounded switching time. |
| Toolchain alignment | Matches ABI expectations (register window defined in spec); debugger can map registers by offset. | Debugger/toolchain must understand copy semantics; harder to reconcile with documented ABI. | Keeping architecture and implementation consistent reduces maintenance. |
| Portability | Clear path to C implementation: reuse same `reg_base`/stack metadata, just adjust linker script. | Requires duplicating copy logic in C, increasing flash footprint and verification burden. | Our goal is a Python prototype that mirrors the C architecture; pointer model keeps parity. |
| Drawbacks | Slightly more complex VM memory allocator; must ensure allocations don’t overlap. | Simpler to reason about in toy prototypes; avoids pointer arithmetic mistakes. | We accept allocator complexity in exchange for the advantages above; allocator already exists. |

**Conclusion:** While the copy approach simplifies tiny prototypes, it scales poorly (O(N) per switch), undermines stack-guard enforcement, and diverges from our documented ABI. The workspace pointer model offers bounded switch time, aligns with both Python and future C implementations, and provides built-in memory isolation. We therefore keep the workspace pointer architecture and will finish refactoring the Python VM to honour it.

**Further analysis:** Detailed modelling (see `main/hsx_vm_register_model_analysis.md`) confirms the break-even point between pure workspace-pointer and copy-on-attach strategies is only favourable to copying when a task executes long timeslices without register spills—rare on MCUs with limited host registers. We will implement the simple pointer-swapping approach first, using the Python prototype as an intermediate C-style stepping stone. If profiling ever shows the pointer model is a bottleneck, we can consider mitigations from the analysis (e.g., hot-set mirrors with dirty masks or adaptive promotion) without changing the architecture contract.
- **Specialisation:** `R0` used as return value/temporary, `R1–R3` caller-saved argument registers, `R4–R7` callee-saved, rest scratch/watch registers as captured in `docs/hsx_spec-v2.md`.

### Opcode Encoding & Minimal Instruction Set
- Target platform RAM/flash constraints prompted a **16-bit primary opcode format** with extension words for immediates or wide operands. This mirrors classic microcontrollers and keeps code density high.
- Minimal instruction set identified through LLVM lowering exercises (`hsx-llc.py`):
  - Arithmetic/logic: `ADD`, `SUB`, `ADC`, `SBC`, `AND`, `OR`, `XOR`, `NOT`.
  - Shifts/rotates: `LSL`, `LSR`, `ASR`.
  - Data movement: `MOV`, `LD`, `ST`, register-immediate moves.
  - Control flow: `CMP`, `BR`, `BRZ`, `BRNZ`, `CALL`, `RET`, `BRK`, `SVC`.
  - Floating-point core: `FADD`, `FSUB`, `FMUL`, `FDIV`, `FPEXT`, `FPTRUNC` targeting half precision.
- Study confirmed this set covers C front-end needs (integer arithmetic, pointer ops, comparisons, branching) while deferring specialized DSP/vector instructions.

### Floating-Point Precision
- Evaluated **f16 (IEEE half)** vs. **f32**:
  - f16 halves storage and bandwidth requirements—important for mailbox payloads and per-node data tables.
  - Target applications (sensor scaling, control loops) tolerate ~3 significant digits; operations requiring higher precision can run on host or use software libraries.
  - Decision: core ISA implements f16 natively; f32 support provided via helper routines when needed.

### Toolchain & C Compilation
- Goal: compile HSX apps from standard C sources.
- Selected **Clang/LLVM** toolchain:
  - Mature optimisation pipeline and modular backend (facilitated `hsx-llc` prototype).
  - Easy to target custom ISAs via TableGen/MC layer; reuse large portions of IR legalisation.
  - Rich ecosystem (clang driver, lld, sanitizers) for future diagnostics.
- Study outcome: build LLVM IR lowering (`hsx-llc.py`) translating `hsx`-specific IR to MVASM assembled by `asm.py`. Ensures front-end compatibility while matching our minimal instruction set.

### Calling Convention & ABI Considerations
- **ABI:** Application Binary Interface—defines function calling conventions, register usage, stack layout, and binary object formats.
- Chosen calling convention:
  - First three word arguments in `R1–R3` (with `R0` reserved for return).
  - Additional arguments spill to stack in 4-byte slots; half-precision arguments occupy low 16 bits.
  - `R4–R7` callee-saved; higher registers caller-saved for scratch use.
  - Stack grows downward; `SP` aligned to 4 bytes; optional frame pointer for debugging.
- ABI study ensured alignment with Clang expectations so the compiler can emit conformant prologues/epilogues without bespoke passes.

## Toolchain & Artefact Studies
### Assembler & Object Model
- Decided to implement a **custom assembler (`asm.py`)** rather than reuse GNU assemblers:
  - Instruction encoding is lightweight; bespoke assembler simplifies pipeline and allows domain-specific directives (`.extern`, `.import`, `.text`, `.data`).
  - Integrates with Python toolchain and supports stable 16-bit relocation offsets required by the VM.
- Object format study led to a two-step pipeline:
  1. LLVM lowering emits MVASM.
  2. Assembler produces `.hxo` (HSX object) files containing sections, symbol tables, and relocations.
- `.hxo` chosen as a simple container (JSON header + raw sections) to ease debugging and keep link-time tooling lightweight.

### Linking Strategy
- Linker (`hld.py`) resolves `.hxo` objects into final executables:
  - Supports **static linking** with relocation records; dynamic linking deemed out-of-scope for resource-constrained nodes.
  - Produces `.hxe` images with a fixed header (magic `HSXE`, version, section lengths, CRC).
  - Design intentionally mirrors ELF concepts (sections, symbols) at reduced complexity, easing future tooling (e.g., symbol lookup in debugger).
- Study concluded that linking should also output optional **listing files** summarising memory layout, symbol addresses, and relocation outcomes for diagnostics.

### File Formats
- **`.hxo` (HSX Object):**
  - Contains code/data sections, relocation entries, symbol table (names, addresses, attributes), and metadata (source file, timestamps).
  - Encoded as JSON + binary payload to keep parsing simple in Python and potential C tools.
- **`.hxe` (HSX Executable):**
  - Fixed-size header with entry point, code/rodata lengths, BSS size, required capabilities, CRC.
  - Append-only payload: code, rodata; BSS zero-initialised at load time.
  - CRC ensures integrity when distributing over CAN or loading from removable media.
- Study emphasised *compatibility*: header versioning allows future extensions (e.g., symbol tables) without breaking existing loaders.

### Symbol & Debug Information
- To support debugger features (disassembly with names, watch lists), we studied symbol metadata strategies:
  - Leverage `.hxo` symbol table and propagate into `.hxe` as optional debug block or sidecar JSON.
  - Symbols include function names, global variables, section info, and type hints (size, scalar vs. half precision).
  - For stack frames, planned to include call-frame information (prologue size, saved registers) enabling debugger to reconstruct frames.
- Decision: initial MVP emits a **sidecar debug JSON** (easily consumed by Python tooling). Later iterations may embed compressed symbol tables in `.hxe`.

### Listing & Diagnostics
- Study recommends generating a **listing file** during assembly/link:
  - Shows address ↔ instruction mapping, resolved labels, immediate values, and optional annotation with source line numbers when available from Clang.
  - Assists manual inspection and provides baseline for debugger disassembly tests.
- Listing format kept text-based so it can be consumed by Git diffs and CI artefacts.

### Debugger Integration
- Debugger requires disassembly tied to symbol names and variable scopes:
  - Use symbol metadata to label breakpoints, call stacks, and watch expressions.
  - Instrument `hsxdbg` to cache mapping of PC → function/label from listing/debug JSON.
- Memory watch lists should correlate addresses with symbol info (e.g., global variables, mailbox buffers).
- Study outcome: maintain a shared metadata schema consumed by both the linker and debugger to avoid divergence.

## Value & Command Access Layer
- **Motivation:** Embedded nodes often need to expose live telemetry or accept operational commands without redeploying firmware. Traditional approaches (ad hoc CAN frames, debug UART commands) lack consistency and are hard to automate.
- **Value system concept:**
  - HSX apps declare `val` entities that are first-class f16 variables, accessible both programmatically and via external interfaces (shell, CAN, UI).
  - Values behave like regular variables inside HSX code—usable in expressions, assignments, and math operations—while simultaneously being addressable by the executive.
  - Supports future extensions for arrays/matrices where indexing semantics dictate how values are seasoned for display (row/column) and transmission.
  - Storage: values live in a dedicated table (per `docs/hsx_spec-v2.md` SVC 0x07) optionally backed by FRAM for persistence.
- **Namespace model:** As described in `docs/hsx_value_interface.md`, values/commands use numeric `group:value` IDs (0–255 each) combined into a 16-bit OID. Optional 12-char names are stored once per group/value for operator tooling but are not kept in the runtime entry.
- **Numeric addressing:** Values are identified by 8-bit group + 8-bit value IDs (yielding a 16-bit OID). Human-readable names are optional hints stored in shared string tables; runtime state keeps only the compact IDs.
- **Metadata:** The runtime keeps a minimal per-value record (`group`, `id`, `flags`, `last_f16`). Optional descriptors provide unit, hysteresis, publish-rate, range, FRAM key, and display names when needed. This keeps RAM usage per value in the 8–12 byte range.
- **Type & structure:** Initial release standardises on f16 scalars (bools represented as 0.0/1.0). Array/matrix support is deferred; when needed, additional metadata blocks can describe shape without bloating the base entry.
- **Validation & rate control:** Optional descriptor fields carry per-item hysteresis (`eps`) and minimum publish interval; absent fields fall back to executive defaults.
- **Command system concept:**
  - HSX apps register callable `cmd` handlers (SVC 0x08) for mode switching, calibrations, diagnostics, etc.
  - Commands carry only group/value IDs and flags; for HSX v1 they accept no arguments (button semantics). Optional descriptors supply names/help text.
  - Commands complement the value system: values expose state, commands effect change.
- **Why f16 basis:**
  - Matches our numeric emphasis, minimises bandwidth, sufficient precision for telemetry; arrays/matrices can extend to structured data (e.g., sensor calibration tables).
  - Consistent with the floating-point study: higher precision operations can run elsewhere or use helper routines.
- **Integration with architecture:**
  - Executive and shell provide discovery, GET/SET, and invocation interfaces (e.g., `val.get`, `val.set`, `cmd.call`).
  - Tooling (debugger, shell, CAN adaptors) can subscribe to value updates or trigger commands over standard protocols.
  - Distinct from mailbox system (which handles general messaging) but interoperates via events (e.g., value change notifications).
- **Transport bindings:** Standardised bindings (per `hsx_value_interface.md`) cover UART shell (`val ls`, `cmd call`), mailbox subscriptions (`val.sub` posting `(oid,f16)` frames), and compact CAN frames (`GET/SET/PUB/CALL/RET` ops using `oid` + f16 payload).
- **CLI ergonomics:** Shell/debugger accept either numeric (`val get 0:3`) or named (`val get motor:rpm`) addressing, both resolved via the shared string/ID tables.
- **Access control:** Study identified need for per-OID authorization. Values carry `auth_level` to constrain write access; commands use flags (e.g., `PIN`) plus optional tokens during invocation so sensitive operations require host authorization.
- **Persistence & FRAM:** `val.persist` allows FRAM-backed load/save, ensuring critical parameters survive power cycles—a common embedded need. Executive uses `ns_id:key_id` mapping to store/retrieve without exposing hardware-specific EEPROM details to HSX apps.
- **Backlog:** Considered batch `val.bulk_get/set` RPCs for high-volume polling. Marked low priority for initial release but recorded as enhancement idea.
 
## Alternatives Considered
| Option | Description | Outcome |
|--------|-------------|---------|
| Full OS inside VM | Run a microkernel or shell task within the MiniVM to schedule apps. | Rejected: adds latency, consumes resources, duplicates host executive responsibilities. |
| Register bank per task | Maintain separate register arrays and copy on switch. | Rejected: higher cost on MCUs; pointer-based approach is simpler and aligns with TMS9900 precedent. |
| FIFO-only mailboxes | Simple queues with single consumer. | Rejected: insufficient for multi-subscriber diagnostics/logging; lacks tap functionality. |
| Native-first implementation | Begin directly with C/embedded code. | Deferred: slower iteration; Python prototype preferred for early validation, with design choices ensuring portability. |

## Key Assumptions
- Host executive (desktop or embedded) remains authoritative; VM merely executes instructions with provided context.
- Mailbox subsystem is the canonical inter-task bridge; other IPC mechanisms considered unnecessary for initial scope.
- Debugger remains host-side, potentially aided by lightweight on-target shims for signal forwarding.
- CAN/J1939 ecosystem expects consistent host firmware across nodes with downloadable domain logic.

## Anticipated Risks
- **Resource constraints on MCUs:** Mitigated by keeping VM footprint small, leveraging pointer-based context switching, and offloading scheduling to native executive code.
- **Complexity of multi-subscriber mailboxes:** Addressed by modelling after proven VMS/RSX-11 semantics and limiting initial modes to those needed for HSX apps and HAL services.
- **Divergence between Python prototype and C port:** Prevented by documenting interfaces early (RPC commands, mailbox APIs) and ensuring prototypes mirror target behaviour.

## Study Outcomes
- Confidence that a host-driven MiniVM with pointer-based register switching suits AVR/Cortex‑M targets.
- Mailbox system chosen as primary IPC due to flexibility and alignment with embedded needs.
- Decision to prototype in Python while maintaining C-portable abstractions.
- Agreement to exclude an in-VM OS/shell, focusing instead on a robust executive + tooling stack.

These conclusions feed directly into the architecture documented in `(3)architecture.md`, ensuring the high-level design reflects deliberate study rather than ad-hoc implementation.

# HSX-ST-003 — Address Spaces, ABI, Unwind, and Variable Locations

- Status: **COMPLETE FOR MASTER SYNTHESIS**
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issue: #47
- Iteration: `DBG-IT-001-003`
- Study baseline: `d135e542b2a959c2ea67e3a1ea65df7e0bcd6baf`
- Scope authority: Study/design documentation and conformance-fixture planning only
- Product/AVR authority: **NONE**

## 1. Question and bounded scope

Which portable HSX contracts must define code, data, and register locations; architectural
widths; byte order, alignment, serialization, and overflow; image/debug-artifact binding;
call/frame/return behavior; stack unwinding; and variable locations so a debugger can inspect
an exact loaded image without copying Python implementation assumptions into the portable
architecture?

This Study answers the address/ABI/unwind portion of `DBG-ST-006`. It compares legacy intent
with the current Python oracle, identifies contradictions and missing evidence, and recommends
contract concepts for Master synthesis. It does **not**:

- allocate numeric `HSX-R-*`, `HSX-A-*`, or `HSX-D-*` IDs;
- accept one historical calling convention as the portable ABI;
- make `0xFFFF`/`0xFFFFFFFF` masks, `R7`, `R15`, `reg_base`, or a Python memory layout
  portable debugger truth;
- change HXE/HXO, compiler, VM, Executive, debugger, tests, or AVR code;
- define snapshot causality, lifecycle identity, event continuity, resource ownership, or
  target-specific memory budgets owned by sibling Studies.

## 2. Authority and evidence classification

The durable authorities read before analysis were `AGENTS.md`, `SDP/README.md`,
`SDP/Shared/Process.md`, both active track READMEs and CurrentIndexes, issues #47/#38,
`HSX-ST-001`, `DBG-ST-006`, `DBG-IT-001-003`, and the active Handoff.

Evidence below is classified as follows:

| Class | Meaning here |
|---|---|
| **legacy-required / legacy-goal** | `DR-*` / `DG-*` provenance from the legacy catalogue; not yet a modern accepted HSX contract. |
| **legacy design intent** | Historical architecture/design text. Useful to expose intended behavior and conflicts, not current authority. |
| **Python oracle** | Behavior demonstrated by current Python code/tests. It is a conformance candidate, not automatically portable semantics. |
| **proposed portable target** | Recommended contract shape for Master synthesis and independent review. It has no implementation authority. |
| **Debugger-owned** | Resolution, presentation, handle, or frontend behavior that consumes HSX evidence without redefining it. |
| **AVR-owned** | Concrete MCU representation, storage map, instruction-fetch backend, limits, timing, or HAL realization. |

### 2.1 Evidence sources inspected

- legacy catalogue and architecture/design:
  `main/02--Study/02.01--Requirements.md`, `main/03--Architecture/03.01--VM.md`,
  `main/03--Architecture/03.02--Executive.md`, `main/04--Design/04.01--VM.md`,
  `main/04--Design/04.02--Executive.md`, `main/04--Design/04.05--Toolchain.md`, and
  relevant `main/05--Implementation` ABI/debug-metadata records;
- current documentation: `docs/hsx_spec-v2.md`, `docs/abi_syscalls.md`,
  `docs/toolchain.md`, `docs/hxe_format.md`, `docs/symbol_format.md`, and
  `docs/sources_json.md`;
- toolchain/runtime: `python/asm.py`, `python/hld.py`, `python/hsx-llc.py`,
  `platforms/python/host_vm.py`, `python/execd.py`, `python/source_map.py`, and
  `python/hsx_dbg/symbols.py`;
- tests for HXE parsing/metadata, assembler/linker/debug output, memory access, CALL/RET and
  call arity, stack guards/walking, local locations, disassembly/symbols, and source maps.

## 3. Evidence findings

### 3.1 Legacy intent is internally inconsistent

The useful legacy provenance is narrow:

- `DR-2.1` and `DG-2.1/DG-2.2` want a 16×32-bit architectural register workspace and
  constant-time context selection;
- `DR-2.2` / `DG-2.3` want an ARM-inspired, toolchain-compatible ABI;
- `DR-3.1`, `DG-3.1`, `DG-3.3`, and `DG-3.5` want deterministic HXE/HXO and debugger
  metadata;
- `DR-1.3` / `DG-1.4` require a Python-to-C path and parity evidence.

Those goals do not settle the contracts. Historical design text conflicts on all material
details:

| Topic | Conflicting historical/current claims |
|---|---|
| Address unit | Legacy VM design says 16-bit **word** addresses translated to bytes; current toolchain, `.sym`, PC, and VM use byte offsets. |
| Data alignment | Legacy VM design says misaligned accesses fault; current Python VM intentionally supports unaligned 8/16/32-bit loads/stores. |
| Argument registers | Legacy VM design says `R0..R3`; current compiler and newer spec use `R1..R3`, with `R0` as return. SVC documentation also has mixed `R0..R3` and `R1..R5` conventions. |
| Saved registers | Legacy VM design says `R4..R7` caller-saved and `R8..R12` callee-saved; newer spec says `R4..R7` callee-saved and `R8..R11` caller-saved. |
| FP/SP/LR | Legacy design assigns frame/link roles to `R14/R15`; current compiler emits an `R7` frame and mirrors SP through `R15`; newer spec says SP is separate and leaves `R15` reserved. |
| Stack alignment/layout | Legacy design says 8-byte call alignment and overflow args at a different base; newer spec and compiler use 4-byte words, current `CALL` pushes a return address, and compiler prologues push the old `R7`. |
| Unwind frame | Legacy Executive pseudocode reads saved values at negative FP offsets; current `execd.py` assumes `[fp] = previous_fp`, `[fp+4] = return_pc`. |

“ARM-inspired” is therefore a goal, not a sufficient ABI specification. No historical
document may be wholesale promoted.

### 3.2 Current Python address and serialization oracle

The Python implementation provides coherent pieces, but not a public architecture contract:

- HXE v1/v2 headers, metadata-table entries, and instruction words are encoded big-endian.
- `.word`/`.half` data, register-window bytes, VM 16/32-bit loads/stores, stack words, and
  current binary runtime records are little-endian.
- code is stored separately from the VM data bytearray. `read_code` and `read_mem` are
  distinct operations even when their numeric offsets are equal.
- code instructions are 4 bytes and valid entry points are checked for 4-byte alignment.
- current data memory is 64 KiB; code/rodata loaders enforce current size ceilings; the
  register window is 16×32 bits and is physically backed by VM data memory in Python.
- raw and effective memory/code addresses, breakpoint addresses, symbol lookups, and several
  Executive views frequently apply 16- or 32-bit masks before validation.
- instruction effective-address helpers mask to 16 bits and then range-check the access.
  Boundary-crossing accesses fault, but high-bit addresses can alias low memory. No test
  establishes that aliasing as intentional portable behavior.
- VM data instructions allow unaligned little-endian access. `test_mem_alignment.py` proves
  it; `test_vm_mem_oob.py` proves that an access crossing the current upper bound faults.
- memory-region records and symbol records use untyped integers. Some region ends are
  inclusive while local-location ranges use a half-open `[start,end)` convention.
- `reg_base` is masked and used as a physical Python memory offset. That is a context-storage
  mechanism, not the identity of the architectural register space.

The current oracle therefore supports a named compatibility profile, but the masks and
physical aliases cannot define portable address semantics.

### 3.3 HXO/HXE and debug-artifact binding gaps

Current artifact behavior is useful but incomplete for trustworthy inspection:

- HXO JSON schema v1 contains code words, rodata bytes, symbols as section+offset, and
  relocations, but no architecture or ABI descriptor identity.
- HXE v1/v2 carry header version, entry/length fields, internal CRC, and optional metadata;
  neither version binds an ABI/unwind schema. HXE header version is not an ABI version.
- HXE code bytes are emitted big-endian while relocated rodata scalars are emitted
  little-endian. The format does not expose those distinctions as an inspectable descriptor.
- linker `.sym` v1 records untyped function/global/instruction addresses, local location
  ranges, memory regions, `hxe_path`, and `hxe_crc`.
- `hxe_crc` is populated from the HXE internal CRC value. The format documentation describes
  it imprecisely as a CRC of the emitted file; it is not a strong content identity.
- `execd.py` loads symbols and instructions but does not validate the top-level schema
  version, `hxe_path`, or `hxe_crc` against the loaded task image.
- `sources.json` is independently versioned and relocatable but is not cryptographically or
  transactionally bound to the HXE and `.sym` used for the session.
- source mapping preserves case in `source_map.py`, while `hsx_dbg/symbols.py` lowercases
  paths, uses basenames as aliases, and masks PCs. Case-colliding or same-basename sources can
  resolve ambiguously without an explicit diagnostic.
- link-time relocation checks cover some PC-relative alignment and encoding cases, but many
  address values are truncated by relocation-kind masks. There is no architecture-descriptor
  compatibility check across HXO inputs, HXE, sidecar, and target.

An HXE CRC can remain an integrity signal and backward-compatibility field. It cannot by
itself authorize use of a debug sidecar.

### 3.4 Current ABI/frame Python oracle

The current compiler/VM pair behaves approximately as follows:

- first three ordinary function arguments use `R1..R3`; later arguments are pushed as
  4-byte words in reverse order;
- `R0` is the ordinary scalar return register;
- `CALL` pushes the next byte-addressed PC as a little-endian 32-bit stack word;
- compiler prologues push the prior `R7`, then copy the SP mirror from `R15` into `R7`;
- compiler-managed local/spill slots use negative offsets from that `R7` value;
- epilogues pop local reservation words and the saved `R7`, then execute `RET`;
- `test_call_arity.py` proves overflow-argument push/pop emission, but does not prove a
  complete mixed-width/aggregate/variadic ABI end-to-end;
- VM CALL/RET tests prove basic and nested return behavior and stack error paths;
- the Python VM also keeps a host-only `call_stack` list to decide whether a top-level `RET`
  ends the task. That list is not guest ABI evidence and cannot be used for portable unwind.

This is enough to define a **legacy Python-oracle recipe fixture**. It is not enough to freeze
the portable ABI. In particular, no evidence proves the newer document's complete caller/
callee-save table, aggregate rules, multiword returns, varargs shim, or a register-independent
frame contract.

### 3.5 Current unwind and variable-location oracle

- `execd.py::stack_info` starts from a register snapshot, prefers explicit `fp` fields and
  otherwise falls back to `R7`, assumes two little-endian words at the frame pointer, checks
  stack range/alignment/cycles, and returns frames plus a global `truncated` flag and string
  errors.
- these checks are valuable defensive behavior; the location of the frame link and return PC
  is nevertheless hard-coded and disagrees with historical pseudocode.
- SP representation is ambiguous. The VM allocator currently stores an absolute SP, while
  `read_regs` also constructs `sp_effective = stack_base + (sp & 0xFFFF)`. This can double-add
  the base. Test doubles avoid the ambiguity by supplying `sp_effective` explicitly.
- `hsx-llc` records local locations as PC ranges with `stack`, `register`, `global`, or
  `const` descriptions. The linker relocates ordinal ranges to final PC byte ranges.
- the Executive interprets stack locations relative to an assumed current-frame FP, register
  locations from the current register snapshot, globals as untyped data addresses, and
  constants as little-endian 32-bit values.
- location selection is half-open by PC and can report “not live,” but there is no portable
  location-expression version, frame identity, piecewise value, unavailable/optimized-out
  marker, type/bit-size contract, endian override, or selected non-top-frame register model.
- failure is generally a thrown/string error. There is no structured partial value showing
  which pieces were recovered.

The current stack-walk and local-watch tests prove defensive Python behavior against crafted
fixtures, not conformance between emitted compiler frames and the Executive unwinder across
all supported constructs.

## 4. Alternatives considered

| Alternative | Benefit | Failure/risk | Decision |
|---|---|---|---|
| Fix all public addresses at 16-bit and preserve every mask | Smallest short-term change. | Conflates code/data/register domains, aliases high bits silently, blocks wider profiles, and treats implementation shortcuts as ISA. | Reject as portable target. Preserve only in a named, tested legacy profile if migration needs it. |
| One unified flat address space | Simple UI and RPC values. | Current code/data reads are already distinct; register backing is implementation-private; equal offsets would have ambiguous meaning. | Reject. Require typed spaces. |
| Freeze the current `R7` frame chain as the universal ABI | Matches current compiler fixtures and `execd.py`. | Conflicts with documents, excludes frameless/optimized code and other implementations, and leaves mixed-width/varargs behavior unproven. | Reject. Describe it as one versioned recipe/profile only. |
| Infer ABI/unwind from architecture name or HXE version | No new manifest data. | HXE versions describe container layout, not ABI; identical architecture can host multiple ABI/debug schema versions. | Reject. Bind explicit descriptors/recipes. |
| Let debugger heuristically try FP layouts and masks | Can display something for malformed/legacy data. | Fabricates frames/values, hides artifact mismatch, and makes cross-target failures nondeterministic. | Reject for normal mode. Any legacy fallback must be named, bounded, diagnostic, and tested. |
| Embed all debug data into HXE immediately | Strong physical colocation. | Changes the image format, increases target storage/transfer cost, conflicts with current external-sidecar workflow, and is outside this Study. | Defer. Use a signed/digested external bundle manifest without requiring an HXE-header change. |
| Versioned `ArchitectureDescriptor` + typed addresses + image-bound ABI/unwind/location recipes | Separates target shape, image ABI, and debug schema; supports current and future profiles without heuristics. | Requires schema work, migration adapters, fixture generators, and explicit unsupported outcomes. | **Recommend.** |

## 5. Proposed portable contract concepts

These names are descriptive placeholders for Master allocation. They are not accepted IDs.

### 5.1 `ArchitectureDescriptor`

Every inspectable target generation should expose an immutable, canonical descriptor with a
descriptor ID, schema version, canonical encoding, and digest. At minimum it defines:

| Field group | Required semantics |
|---|---|
| Architecture | architecture/profile name and revision; descriptor schema version; capability-profile binding. |
| Code space | stable space ID, byte/word addressing unit, offset width, valid ranges/holes, instruction width/alignment, PC width, instruction-byte encoding, and execute/read capability. |
| Data space | stable space ID, address unit, offset width, valid ranges/holes, scalar byte order, supported access widths, guest alignment behavior, raw debugger byte-read behavior, and read/write capability. |
| Register space | stable register IDs/names/aliases, bit width per register, encoding, read/write policy, and logical roles such as PC/SP/status. Physical workspace addresses are excluded. |
| Arithmetic | checked-range rule, range representation, and whether a named legacy profile exposes modulo guest addressing. Debugger/control-plane address arithmetic is always checked. |
| ABI set | supported ABI descriptor IDs/revisions, not an inferred frame-register number. |

Code, data, and register spaces must remain distinct even if one implementation stores them
in one host buffer. A `RegisterId` is not a data address. `reg_base`, workspace pointers, and
target-native pointers may be exposed only as separately typed implementation diagnostics,
never as portable register identities.

The current Python compatibility profile can truthfully advertise 4-byte code instructions,
byte-addressed code/data, little-endian data/register words, a separate big-endian
instruction encoding, 16×32-bit general registers, and unaligned 8/16/32-bit data access.
Whether those exact widths become the first accepted portable profile is a Master/Steering
decision after synthesis. They must be expressed in the descriptor, not inferred from masks.

### 5.2 Typed address and range model

The portable value is conceptually:

```text
Address = { architecture_descriptor_id, space_id, offset }
AddressRange = { start: Address, length_bytes }
RegisterLocation = { architecture_descriptor_id, register_id, bit_offset?, bit_size? }
```

Rules:

1. `offset` is an unsigned mathematical value constrained by the named space's width/ranges.
2. addition/subtraction and `[start,start+length)` construction are checked before conversion;
   negative, overflowed, cross-hole, and cross-space results are typed failures.
3. there is no implicit `& 0xFFFF`/`& 0xFFFFFFFF`, sign reinterpretation, or code↔data cast at
   an RPC, metadata, debugger, relocation, or resource boundary.
4. ranges are uniformly half-open. Empty ranges are permitted; wrapping ranges are not.
5. raw memory responses are bytes. Scalar interpretation names byte order, bit width, signedness,
   and type; host byte order is irrelevant.
6. JSON/wire representation must preserve the entire offset width (for example a canonical
   width-qualified hexadecimal string). It must not depend on lossy JSON floating-point
   numbers. Binary protocols define endian for each serialized integer independently of guest
   scalar endian.
7. code PC/source/symbol/breakpoint locations use the code space; globals/stack/heap use data;
   registers use register IDs. Equal numeric offsets do not imply aliasing.

Recommended new portable target behavior is checked effective-address and PC-range failure,
not silent wrap. If compatibility requires the current masking behavior, negotiation must
name a degraded legacy arithmetic profile and tests must demonstrate its exact boundary
semantics and removal criteria.

### 5.3 `ImageDebugBundle`

An external manifest should bind the executable, target-visible image identity, architecture,
ABI, debug sidecar, and source map without changing the frozen HXE v1 header:

```text
ImageDebugBundle {
  bundle_schema_version
  executable_content_digest
  hxe_container_version
  hxe_internal_crc                 # compatibility/integrity evidence only
  architecture_descriptor_id + digest
  abi_descriptor_id + digest
  symbol_schema_id + version + digest
  unwind_schema_id + version + digest
  location_schema_id + version + digest
  sources_manifest_version + digest
  toolchain_identity
}
```

The executable content digest should be collision-resistant and computed over a canonical
definition documented by the artifact contract. HXE CRC remains useful for corruption checks
but is not an image or bundle identity. The runtime/Executive reports the actual loaded
`ImageId`/generation and content/descriptor binding defined with `HSX-ST-002`; the debugger
accepts a bundle only on exact agreement.

Schema versions are independent: HXE, HXO, architecture, ABI, symbol, unwind, location, and
sources formats can evolve separately. Unknown mandatory versions, descriptor digest
mismatch, executable mismatch, or missing mandatory components fail closed with a typed
diagnostic. Optional line/local data may be unavailable without making instruction-level
inspection dishonest.

`sources.json` entries should gain stable source IDs/content evidence through the future
artifact contract. Resolver policy stays Debugger-owned, but it must preserve case and return
ambiguous/missing/mismatch explicitly rather than choosing the first basename.

### 5.4 `AbiDescriptor`

An ABI descriptor is image-bound and architecture-compatible. It defines, without prose-only
assumptions:

- argument and return placement by scalar width/class, including extension rules;
- aggregate, multiword return, indirect return, and variadic rules;
- caller/callee-saved sets and special-register roles;
- stack direction, slot size, alignment at entry/call, overflow-argument layout, caller/callee
  cleanup, red-zone/home-area rules, and stack-limit semantics;
- `CALL`/`RET` architectural effects, return-address value/bias, and exception/SVC boundaries;
- frame-base/CFA policy and which unwind recipe schema describes optimized or frameless code;
- canonical scalar/value encoding independent of instruction-byte encoding;
- compatibility with an exact `ArchitectureDescriptor` revision.

The descriptor must not require a frame pointer. An ABI may define a conventional frame
register, but actual unwind and variable evaluation are driven by PC-range recipes emitted by
the toolchain. The present `R7`/`R15` sequence should be captured as a Python-oracle ABI
fixture first. It must not be called portable until compiler, assembler/linker, VM,
Executive, and mixed-call tests agree on the same descriptor.

### 5.5 Versioned unwind recipes

The debug bundle should carry bounded, declarative unwind rows keyed by code-address ranges.
Each row names:

- recipe schema/version and ABI descriptor;
- Canonical Frame Address rule;
- caller PC/return-address rule;
- caller SP and optional frame-base rule;
- saved-register rules (`same`, `undefined`, register, CFA-relative memory, or bounded
  expression);
- prologue/epilogue/leaf validity ranges and optional signal/trap boundary kind.

The evaluator starts from registers and memory belonging to one inspection snapshot from
`HSX-ST-004`. It uses only typed addresses and bounded operations; it does not guess another
frame layout when a row is missing or corrupt.

Unwind result is a prefix of trustworthy frames plus per-frame status:

- `complete` — required caller state recovered;
- `partial` — frame identity/PC recovered but some registers or annotations unavailable;
- `unavailable` — no applicable/supported recipe or required bytes absent;
- `corrupt` — range, alignment, cycle, non-progress, or recipe invariant failure;
- `stale` — snapshot/target/image generation changed.

Evaluation stops at the first frame whose caller PC/CFA cannot be established. Already proven
frames remain available; fabricated continuation is forbidden. Maximum depth, expression
steps, dereference bytes, and cycle/non-progress guards are negotiated limits.

### 5.6 Versioned variable-location recipes

Every local/parameter value record should be bound to function/lexical/inline scope, frame,
image, ABI, and a half-open code range. A bounded expression language needs at least:

- register value/slice;
- CFA/frame-base-relative value or address;
- typed global/data address;
- constant/implicit value;
- checked signed offset and dereference with explicit space/size/endian;
- piece/bit-piece composition;
- explicit `undefined` / `optimized_out`.

Results separate location from value and never silently zero-fill missing information:

```text
ValueResult {
  status: complete | partial | unavailable | optimized_out | unsupported | corrupt | stale
  declared_type_or_size
  available_pieces[]
  missing_pieces[]
  diagnostic_code
}
```

A register location for a non-top frame is evaluated from that frame's recovered register
state, not the current register snapshot. A stack location uses the recipe-defined frame base,
not a universal `R7`. A constant wider than the current 32-bit Python helper is preserved at
its declared width. Overlapping location ranges, unsupported opcodes, type/size mismatch, or
missing frame context are explicit failures.

### 5.7 Capability and degraded behavior

The negotiated portable debug profile should independently advertise support for:

- architecture descriptors and typed addresses;
- exact image/debug-bundle binding;
- ABI descriptors;
- unwind recipe schema versions;
- variable-location recipe schema versions and piecewise/partial values;
- arbitrary raw byte reads by named space;
- non-top-frame recovered registers;
- maximum address width, range count, unwind depth, recipe steps, and read size.

Capability absence returns `unsupported`; artifact absence returns `unavailable`; generation
mismatch returns `stale`; malformed evidence returns `corrupt`; target read failure returns a
specific unavailable/partial reason. These outcomes must not be collapsed into address zero,
an empty successful stack, current-frame fallback, or a masked retry.

A migration adapter may consume `.sym` v1 and the current R7-style Python oracle only under a
named legacy capability profile. It must validate the HXE CRC it claims to use, surface that
the binding is weaker than the new bundle, preserve unknown addresses/resources, and carry
positive/negative tests plus a removal condition. Version guessing from PID, HXE version,
path, target name, or register values is prohibited.

## 6. Conformance-fixture plan

The following fixtures should be generated once and consumed by assembler/linker, Python VM,
future portable runtimes, Executive protocol, artifact readers, and debugger contract tests.

| Fixture domain | Required positive and negative evidence |
|---|---|
| Descriptor parsing | Code/data widths that differ; 16/24/32-bit examples; distinct code/data offset zero; renamed register aliases; unknown optional vs mandatory fields; canonical digest stability. |
| Address boundaries | First/last valid byte; zero-length range at end; multi-byte access crossing end/hole; negative/oversize value; `max+1`; high-bit alias attempt; checked add/sub; code↔data mismatch; JSON round-trip without precision loss. |
| Endian/alignment | Big-endian instruction bytes with little-endian data/register scalars; byte/half/word reads; supported unaligned current profile; a descriptor that rejects guest unaligned access; raw debugger reads at every byte offset. |
| HXO/HXE relocation | Local/global text and data relocation; same numeric offset in two spaces; PC-relative alignment; encoding overflow rejected instead of truncated; multiple HXO descriptor mismatch; deterministic output. |
| Bundle binding | Exact bundle accepted; changed HXE with same path; wrong internal CRC; correct CRC but wrong strong digest; swapped `.sym`; changed descriptor/ABI; changed `sources.json`; unsupported schema; optional locals absent. |
| ABI calls | Leaf/nested/recursive calls; 0–6 arguments; signed/unsigned 8/16/32-bit, f16, pointers, aggregates, multiword returns, indirect returns, varargs, caller/callee-save clobber checks, stack alignment and cleanup. |
| Unwind | Current Python-oracle frame as one declared recipe; frameless and frame-pointer forms; prologue/epilogue PCs; leaf; nested/recursive; nonstandard saved registers; terminal frame; missing row; truncated memory; invalid alignment; cycle/non-progress; stale snapshot. |
| Locations | Register→stack→constant transitions; range boundary; lexical shadowing; selected non-top frame; global in data space; signed offsets; value wider than 32 bits; pieces across registers/memory; optimized-out gap; missing/corrupt piece; unsupported expression. |
| Symbols/source | Relocated multi-object functions/locals; duplicate symbols/basenames; files differing only by case; moved project root/prefix map; content mismatch; ambiguous path; missing source with valid instruction metadata. |
| Cross-layer | HXE load returns actual image/descriptor/ABI binding; stopped snapshot supplies matching generation; stack/locals/disassembly all use the same typed code/data values; resume/image replacement makes every prior result stale. |

Targeted existing-oracle verification at the Study baseline ran:

```text
c:/Users/hanse/miniconda3/python.exe -m pytest -q
  test_mem_alignment.py test_vm_mem_oob.py test_vm_callret.py
  test_vm_callret_edges.py test_call_arity.py test_hsx_llc_debug.py
  test_linker.py test_hxe_v2_metadata.py test_hxe_section_order_overlap.py
  test_source_map.py test_executive_sessions.py
  -k "alignment or mem_oob or call or debug or linker or hxe or source_map or
      memory_regions or local or stack_info"

40 passed, 1 skipped, 53 deselected
```

The skip was an environment-dependent source-map symlink case. These tests validate the
reported Python oracle only; they do not satisfy the proposed portable fixture matrix.

## 7. Cross-track and sibling-Study mapping

### 7.1 `DBG-ST-006`

This Study directly answers question 2 (typed spaces/width/endian/alignment/serialization/
overflow) and question 6 (ABI/unwind/frame/variable locations). It contributes to:

- question 1 through image/debug-bundle binding, while `HSX-ST-002` owns image identity and
  generations;
- question 5 by requiring all recipe reads to carry the snapshot/revision owned by
  `HSX-ST-004`;
- question 7 by defining code-address/source-map and unwind prerequisites for exact source
  stepping, while execution/precedence remains `HSX-ST-004`;
- question 8 by requiring load/attach to expose descriptor/ABI/image compatibility, while
  lifecycle authority remains `HSX-ST-002`;
- question 9 by providing typed code/data/register locations for resources, while remote
  identity/provenance/revision remains `HSX-ST-006`.

### 7.2 Proposed Debugger contracts

| Debugger contract | HSX dependency supplied by this Study |
|---|---|
| `DBG-D-003` | `ArchitectureDescriptor`, typed addresses/ranges, image/descriptor/ABI bundle binding, checked staleness inputs, and no PID/address-only identity. Stop-epoch lifetime itself remains `HSX-ST-004`. |
| `DBG-D-004` | Validated debug bundle, typed symbol/region/location records, versioned unwind/location recipes, structured partial/unavailable outcomes, and case/relocation fixtures. Source search/presentation policy remains Debugger-owned. |
| `DBG-D-005` | Breakpoint/watch resolved locations must carry code/data space, image generation, descriptor/ABI binding, and cannot be compared as masked integers. Ownership/reconciliation comes from `HSX-ST-006`. |
| `DBG-D-006` | Source-over/out require applicable unwind recipes and source mapping; absence yields unavailable rather than an instruction-step alias. Execution-plan semantics come from `HSX-ST-004`. |

### 7.3 Sibling HSX Studies

| Study | Boundary/required relation |
|---|---|
| `HSX-ST-002` | Owns Executive/target/image identity, generations, lifecycle and ownership. It supplies the loaded `ImageId`/generation to which this Study binds the bundle/descriptors. |
| `HSX-ST-004` | Owns run/stop evidence, snapshots, exact step and blocked-state stability. It supplies the inspection token used by every unwind/location read and decides whether WAIT/SLEEP are inspectable. |
| `HSX-ST-005` | Owns event cursor/ACK/gaps and negotiated profile continuity. Descriptor/ABI/profile generation changes must be observable through that contract. |
| `HSX-ST-006` | Owns breakpoint/watch identity, provenance and revision. It consumes this Study's typed location and image/descriptor binding. |

## 8. Open questions and explicit gaps

1. Which exact first portable architecture/ABI profile should Steering accept: the current
   byte-addressed/unaligned Python behavior, a corrected checked-address variant, or both as
   target plus named legacy compatibility profile?
2. Does guest effective-address overflow always fault in the new portable profile, and which
   fault classification owns instruction/data/stack range errors? This Study recommends
   checked failure; current high-bit masking requires a compatibility decision.
3. What are the canonical caller/callee-save, aggregate, multiword-return, varargs, stack
   alignment, SP representation, and SVC ABI rules? Current documentation and code do not
   constitute one tested answer.
4. Should the external bundle manifest become a separate versioned artifact or a new `.sym`
   top-level revision? It must not require changing the HXE v1 header, and its digest scope
   must be specified exactly.
5. Which collision-resistant digest and canonicalization are mandatory on constrained
   targets versus computed/validated by the Executive or host? Concrete AVR storage/cost is
   AVR-owned.
6. Which minimal bounded unwind/location opcode set is sufficient for the HSX compiler, and
   which LLVM expressions must be declared unsupported rather than approximated?
7. How are inline frames, tail calls, trap/SVC boundaries, dynamic stack allocation, and
   variable-length objects represented? Current toolchain evidence does not cover them.
8. Can the current compiler's emitted frame chain be mechanically related to `execd.py` for
   every instruction in prologue/epilogue ranges? A generated compiler→VM→unwinder oracle is
   still missing.
9. How will source content identity and case-sensitive source IDs be added without making
   host filesystem case behavior part of HSX semantics? Resolver UX remains Debugger-owned.
10. Which raw register writes are portable debug capabilities, especially PC/SP/status, and
    what validation is applied? This intersects lifecycle/stop authority and needs Master
    synthesis with `HSX-ST-002/004`.

Each unresolved item must be decided in the synthesized Requirements/Architecture/Design
package or routed to a new first-class Study. None may be hidden in implementation.

## 9. Conclusions and proposed decisions

1. Portable HSX debugging requires immutable `ArchitectureDescriptor` and `AbiDescriptor`
   values; architecture, container, ABI, symbols, unwind, locations, and sources are
   independently versioned.
2. Code, data, and register locations are distinct typed domains. Address/range arithmetic at
   metadata, RPC, resource, and debugger boundaries is checked and half-open; implicit masks
   and cross-space casts are prohibited.
3. The first-class debug artifact is an exact image-bound bundle. HXE internal CRC remains
   integrity/compatibility evidence, not image identity; `.sym`/`sources.json` must be bound
   and validated before use.
4. The portable ABI cannot be inferred from “ARM-like,” HXE version, or current register
   values. It needs an explicit descriptor and end-to-end call fixtures.
5. Stack unwind and variable locations use bounded, versioned PC-range recipes. A frame
   pointer is optional. Current `R7`/`R15` behavior is a named Python-oracle fixture only.
6. Partial/unavailable/optimized-out/unsupported/corrupt/stale results are structured and
   preserve trustworthy prefixes/pieces. The runtime/debugger must not fabricate frames,
   zero-fill missing pieces, or retry with masks/heuristics.
7. Source stepping and non-top-frame locals are capabilities derived from verified line,
   unwind, location, image, and snapshot evidence; missing prerequisites yield unavailable.
8. Master synthesis should allocate stable HSX requirement/architecture/design IDs for these
   concepts, define the initial accepted profile(s), and route the ten open gaps before
   `DBG-D-003` or `DBG-D-004` can freeze.

Status is **COMPLETE FOR MASTER SYNTHESIS**. This Study creates no product, AVR, debugger
design-freeze, or Refactor implementation authority.

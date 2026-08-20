# HSX-ST-007 — ABI Profile, Unwind/Location Recipe Schema, and Register Mutation

- Status: **COMPLETE FOR MASTER SYNTHESIS**
- Spawned from: `HSX-ST-003`, review `HSX-RVW-001-001-004`
- Coordinator: `HSX-ST-001`
- Debugger dependency: `DBG-ST-006`
- Issues: #47 / #38
- Iteration: `DBG-IT-001-003`
- Study baseline: `bc8f2aac128b173adb763370f0d67b82438aa480`
- Scope authority: Study/design documentation and conformance-fixture planning only
- Product/AVR authority: **NONE**

## 1. Question and bounded scope

Which concrete ABI profile truthfully describes the calls and frames emitted by the current
HSX compiler and executed by the Python VM; which bounded, versioned unwind and variable-
location recipe schema is sufficient for that profile; and under what authority and revision
rules may a debugger write architectural registers without corrupting stop/snapshot evidence?

This Study closes the ABI/profile, recipe-schema and raw-register questions left open by
`HSX-ST-003`. It does not:

- allocate new numeric `HSX-R-*`, `HSX-A-*`, `HSX-D-*` or `DBG-*` IDs;
- change compiler, linker, VM, Executive, debugger, tests, HXE/HXO or AVR code;
- make the selected ABI universal across future HSX architectures or toolchains;
- decide debug-bundle/source digest canonicalization owned by `HSX-ST-008`;
- claim that the current Python implementation already implements the proposed full profile;
- turn module-specific SVC signatures into ordinary function-call ABI rules.

## 2. Authority and evidence classification

The worker read `AGENTS.md`, `SDP/README.md`, `SDP/Shared/Process.md`, both active track
READMEs and CurrentIndexes, issues #47/#38, review `HSX-RVW-001-001-004`, `HSX-ST-003`,
the proposed HSX requirements/architecture/design, `DBG-ST-006`, the proposed Debugger
requirements/architecture/design and both active Handoffs before analysis.

Evidence classifications remain those of `HSX-ST-003`: current code/tests are a **Python
oracle**, legacy/newer prose is evidence rather than portable authority, and every conclusion
below is a **proposed portable target** for Master synthesis and independent review.

### 2.1 Code, documentation and tests inspected

- `python/hsx-llc.py`: formal-argument mapping, allocator register pool, call lowering,
  prologue/epilogue, frame slots and emitted debug locations;
- `platforms/python/host_vm.py`: `TaskContext`, register window, authoritative PC/SP/PSW,
  `CALL`/`RET`/`PUSH`/`POP`, R15 mirroring, stack guards, `read_regs`, `reg_set` and
  `write_regs`;
- `python/execd.py`: stack walk, local-location reads, register snapshots, memory regions,
  access/locking and absence of a public revision-fenced register-mutation operation;
- `python/vmclient.py`, `python/hsx_dbg/backend.py`, `python/hld.py` and current `.sym` debug
  metadata production/consumption;
- `docs/hsx_spec-v2.md`, `docs/abi_syscalls.md`, `docs/hsx_llc.md`, `docs/asm.md`,
  `docs/executive_protocol.md` and `docs/symbol_format.md`;
- call/stack/debug/register tests named in section 9.

## 3. Evidence findings

### 3.1 The current emitter has one narrow, observable ABI

The following behavior is directly visible in `python/hsx-llc.py`:

1. Ordinary scalar argument slots one through three are assigned left-to-right to `R1..R3`.
2. An ordinary scalar return is moved to `R0` before `RET`.
3. The allocator uses `R4`, `R5`, `R6`, `R8`, `R9`, `R10` and `R11`; it uses `R12..R14`
   as scratch. It does not save those registers around a call or in a callee.
4. Every emitted function prologue is `PUSH R7; MOV R7, R15`. Every normal emitted return
   releases compiler frame words, executes `POP R7`, then `RET`.
5. Fixed locals/spills are 4-byte-rounded slots at negative offsets from `R7`. Frame words
   are reserved with `PUSH R12` and released with `POP R12`.
6. For arguments four and later, a caller pushes the highest-index argument first, calls,
   then pops one word per overflow argument. `test_call_arity.py` proves this caller shape.
7. The compiler records formal overflow arguments in a local `stack_args` list, but never
   materializes those values in the compiled callee. No current test proves an end-to-end
   compiled caller/callee call with four or more arguments.
8. Calls do not spill values live across a call. Because a generated callee may allocate the
   same registers, live-across-call correctness is not presently demonstrated.
9. Aggregate returns, multiword returns, variadic access, dynamic stack allocation, tail-call
   frames and inline-frame metadata are not implemented as a coherent, tested ABI.

Consequently the saved-set statement in `docs/hsx_spec-v2.md` (`R4..R7` callee-saved) is not
the emitted ABI. Only `R7` is mechanically preserved by generated functions. The document's
multiword/aggregate/varargs text is target intent, not current conformance evidence.

### 3.2 VM stack and control effects are exact but R15 is not the SP authority

The Python VM has separate authoritative `pc`, `sp` and `flags`/PSW values. Its stack word is
4 bytes and little-endian; the stack grows toward lower addresses.

- `PUSH Rx`: validates `SP - 4`, writes one little-endian word, sets `SP := SP - 4`, then
  mirrors the new value into `R15`.
- `POP Rx`: reads one word at SP, sets `SP := SP + 4`, mirrors it to `R15`, then writes Rx.
- `CALL`: stores `return_pc = call_pc + 4` exactly as one word using the same push effect,
  mirrors SP into `R15`, and transfers control. Direct/relative targets are current 16-bit
  code offsets even though host containers use 32-bit integers.
- nested `RET`: reads the return PC at SP, increments/mirrors SP and resumes at that exact
  return PC. A top-level `RET` is detected using a host-only `call_stack` and terminates; that
  host list is not unwind evidence.

Task stacks are initially 4-byte aligned and `PUSH`/`POP` preserve that alignment. The VM does
not independently reject a misaligned SP introduced by raw state restoration.

`R15` is therefore a **derived, compiler-visible SP mirror**, not the authoritative stack
pointer. Ordinary instructions and `vm_reg_set` can write `R15` without changing `sp`, while
`write_regs` can change `sp` without re-synchronizing `R15`. A portable debugger must not
expose these two operations as independent successful SP mutations.

### 3.3 Exact emitted frame layout

Let `entry_sp` be SP immediately after `CALL` has pushed the return word. After the two-word
compiler prologue:

```text
higher addresses
  [R7 + 8]  overflow argument #4, if present
  [R7 + 4]  return_pc = call_site_pc + 4
  [R7 + 0]  caller R7
  [R7 - 4]  first local/spill word, if allocated
lower addresses

R7 = entry_sp - 4
```

Additional overflow arguments follow at `R7 + 12`, `R7 + 16`, and so on. Caller cleanup
occurs after return. The current Executive walker agrees with the stable body layout
`[fp] = caller_fp`, `[fp+4] = return_pc`, but it does not handle prologue/epilogue PC ranges
and incorrectly presents one hard-coded layout as an ABI.

For this profile, a saved return PC is the caller **resume PC**. The corresponding call-site
PC is the checked code-space operation `return_pc - 4`. Subtraction underflow, misalignment,
an address outside the same loaded image, or an instruction at `return_pc - 4` that is not
a `CALL` makes `call_site_pc` unavailable/corrupt according to the evidence; it must not wrap.

### 3.4 Current unwind/location APIs are defensive legacy adapters

`execd.py::stack_info` limits walks to 64 frames, checks alignment/range/read failure,
detects FP cycles and returns a trustworthy prefix with string errors. Those are useful
guards. The walker nevertheless hard-codes R7 and two words, reads live state across RPCs,
has no image-bound recipe version and uses `return_pc` directly for caller lookup.

Current local metadata has half-open PC ranges and `stack`, `register`, `global` and `const`
forms. Evaluation masks addresses, assumes top-frame R7, zero-pads short register/constant
values, reads non-atomically and throws string errors. It has no piecewise values, recovered
non-top-frame registers, `optimized_out`, schema/opcode version or structured partial result.

This is sufficient only for `hsx.python-debug-legacy/1`. It is not evidence for
`hsx.portable-debug-runtime/1` conformance.

### 3.5 Raw register writes currently bypass portable authority and coherence

The VM-internal RPC exposes `vm_reg_set` and `write_regs` without TargetRef, LoadedImageRef,
lease, StopToken, expected revisions, stopped-state validation or mutation evidence.
`write_regs` can activate a different PID and can replace PC, SP, flags, running state and
the whole context. Neither path invalidates an inspection snapshot or publishes a new stable
stop. `execd.py` does not expose a corresponding revision-fenced debugger operation.

These calls are trusted implementation plumbing. Advertising them as portable debugger
register-write support would permit stale and internally inconsistent state.

## 4. Decision: the concrete current ABI/profile

### 4.1 Versioned descriptor selection

Master synthesis should select the following string IDs/versions; they are schema/profile
names, not new numeric SDP IDs:

| Item | Selected ID/version | Meaning |
|---|---|---|
| Compatible architecture descriptor | `hsx.arch.vm-byte16-gpr32/1` | Current byte-addressed 16-bit code/data offsets, 4-byte instructions, 16×32-bit GPRs, separate PC/SP/PSW and little-endian stack/data. It remains one descriptor, not all HSX. |
| ABI descriptor schema | `hsx.abi-descriptor/1` | Canonical ABI descriptor envelope and validation rules. |
| Concrete current ABI | `hsx.abi.llc-r7-word32/1` | The narrow compiler/VM ABI defined below. |
| Unwind schema | `hsx.unwind-recipe/1` | Bounded PC-row caller-state recipes. |
| Location schema | `hsx.location-recipe/1` | Bounded PC/scope/frame value-location recipes. |

The selected ABI is image-bound and valid only with the compatible architecture descriptor
digest recorded by the non-recursive bundle model completed with `HSX-ST-008`. Another target
or compiler may choose a different ABI descriptor without changing these schemas.

The intended full profile `hsx.portable-debug-runtime/1` should negotiate these capability
names in addition to the existing architecture/bundle capabilities:

- `hsx.abi.descriptor/1`;
- `hsx.debug.unwind-recipes/1`;
- `hsx.debug.location-recipes/1`;
- optional `hsx.debug.register-write/1`.

The register-write capability is optional because read-only/observer debugging remains valid.
If advertised, every rule in section 7 is mandatory. Capability presence is selected from
the negotiated profile and exact descriptor refs, never inferred from HXE version, target
name, R7 contents or successful legacy RPC calls.

### 4.2 Exact `hsx.abi.llc-r7-word32/1` register contract

| Value | Role | Call preservation/write policy |
|---|---|---|
| `R0` | One 32-bit scalar return word | Caller-clobbered; writable at a stable stop. |
| `R1..R3` | First three 32-bit argument slots | Caller-clobbered; writable at a stable stop. |
| `R4..R6`, `R8..R11` | Compiler-allocated temporaries | Caller-clobbered. No live-across-call guarantee exists until compiler fixtures prove spills. |
| `R7` | Conventional frame pointer for emitted functions | The only callee-preserved GPR. A raw write is accepted only under the frame-pointer rules in section 7. |
| `R12..R14` | Compiler/assembler scratch | Caller-clobbered. |
| `R15` | Derived mirror of authoritative SP used by emitted prologues | Reserved; direct portable writes are rejected. An accepted SP write updates R15 atomically. |
| `PC` | Separate current code offset | Special-register write policy; not a GPR alias. |
| `SP` | Separate authoritative data/stack offset | Special-register write policy; stack grows down. |
| `PSW` | Separate status/condition bits | Caller-clobbered; only descriptor-declared writable bits may change. |

No LR register exists in this profile; `CALL` stores the return PC on the data stack. There is
no red zone, register home area or implicit TLS register. SVC is a non-call trap boundary and
does not create this frame. Each SVC module/function must have an exact signature descriptor
for register inputs/outputs/clobbers; absent that evidence, unwind may cross only unchanged
architectural state already captured in the same snapshot and values affected by SVC are
unavailable. Conflicting legacy SVC prose is not incorporated into the ordinary ABI.

### 4.3 Argument, return and stack contract

- The ABI slot size and minimum call/stack alignment are 4 bytes.
- The profile's conforming value classes are one word: `i32`, zero-extended compatible
  code/data pointers and `f16` bits in the low 16 bits with upper bits zero. Narrower language
  integers must be explicitly sign/zero extended to a word by the frontend before the call.
- Arguments one through three occupy `R1`, `R2`, `R3` left-to-right.
- Overflow word arguments are pushed highest index first. At callee entry, return PC is
  `[SP+0]`, argument #4 is `[SP+4]`, #5 is `[SP+8]`. The caller removes overflow words.
- `R0` carries one word of result. Aggregate by-value rules, aggregate/multiword return,
  indirect return and varargs are `unsupported` in descriptor version 1.
- The current caller-side overflow layout is valid, but compiled callees do not consume it.
  Therefore current compiler conformance is limited to at most three arguments unless the
  callee is separately proven (for example a hand-written MVASM shim). This gap may not be
  normalized away by the descriptor.
- Generated code must not keep a value live in caller-clobbered registers across a call.
  Until the compiler spills such values and fixtures pass, affected compilation is a
  conformance failure rather than an undocumented saved-register extension.

Static allocas only are supported. Tail calls, dynamic stack allocation, inline frames and
trap/signal frames return `unsupported` unless a later descriptor/schema version defines
them. This explicit outcome closes the old open question without pretending current support.

## 5. Common bounded recipe value model

### 5.1 Envelope and selection

Every recipe table carries:

```text
schema_id + schema_version
ArchitectureDescriptorRef + AbiDescriptorRef
LoadedImageRef / accepted bundle binding
code_space_id
limits
rows[]
```

Rows use non-overlapping half-open code ranges in one loaded image. Range selection must
yield zero or one row. Zero rows is `unavailable`; overlap, wrap, wrong space, wrong image or
an invalid range is `corrupt`. Evaluation consumes one exact `InspectionSnapshotRef`; every
register and memory read is fenced to that snapshot. Revision/generation change is `stale`.

### 5.2 Typed values

The evaluator has only these runtime value kinds:

- unsigned or signed scalar with explicit bit width;
- typed `Address { architecture_descriptor_ref, space_id, offset }`;
- recovered register value with exact RegisterId/width;
- unavailable/optimized-out terminal marker.

No opcode silently masks, wraps, changes address space, uses host endian, widens a missing
piece with zeroes or reads outside the snapshot. Arithmetic is checked before conversion.

### 5.3 Schema-version-1 symbolic opcodes

Opcodes are canonical strings, not newly allocated numeric instruction IDs:

| Opcode | Input/output and rule |
|---|---|
| `reg_value` | Push the named register value from the selected frame's recovered register set. |
| `special_value` | Push exact `PC`, `SP` or `PSW` from that frame; other names are unsupported. |
| `const_u` / `const_s` | Push a canonical-width unsigned/signed immediate. |
| `static_address` | Push one image-bound typed address from `space_id` plus canonical offset. |
| `to_address` | Convert a non-negative scalar to a named typed address after descriptor range validation. |
| `cfa` | Push the current unwind row's computed Canonical Frame Address. Valid only after CFA evaluation. |
| `frame_base` | Push the frame-base address defined by the applicable function/frame recipe. |
| `add_sconst_checked` | Add one signed immediate to an address or scalar; reject underflow, overflow, hole or cross-space result. |
| `deref_u` | Read 1, 2, 4, 8 or 16 bytes at a typed address using explicitly declared byte order; push an unsigned scalar. |
| `bit_slice` | Extract a declared bit range from a scalar without implicit extension. |

An expression is a bounded postfix program and must end with exactly one value of the type
required by its rule. There is deliberately no branch, loop, arbitrary register+register
arithmetic, implicit pointer cast or recursive recipe call in version 1. LLVM/DWARF expressions
that cannot be translated exactly to this set are emitted as `unsupported`, never approximated.

Recipe structures also have non-expression terminal rules `same`, `undefined`,
`unavailable(reason)` and `optimized_out(reason)`. Piece composition is structural as defined
in section 6, not an unbounded expression opcode.

### 5.4 Required bounds for the selected current profile

The capability record advertises exact limits. `hsx.abi.llc-r7-word32/1` uses these values:

| Bound | Limit |
|---|---:|
| Opcodes per expression | 32 |
| Evaluator stack depth | 8 |
| `deref_u` operations per expression | 4 |
| Bytes per `deref_u` | 16 |
| Unwind frames per request | 64 |
| Total opcodes per unwind request | 4096 |
| Total dereferenced bytes per unwind request | 1024 |
| Location pieces per value | 16 |
| Declared result size | 4096 bits |
| Total dereferenced bytes per location value | 512 |

Exceeding an advertised/schema bound is `unsupported(limit_exceeded)`, not truncation. A
caller may request fewer frames/pieces. An implementation with lower limits advertises a
different/degraded capability and must not claim this profile. Target storage and execution
strategy remain AVR-owned.

### 5.5 Unknown and malformed behavior

- Unknown schema ID or unsupported schema version: `unsupported_schema`; do not evaluate.
- Unknown opcode: `unsupported_opcode`; stop the affected expression without fallback.
- Unknown field listed by the artifact as mandatory: `unsupported_field`.
- Unknown optional field may be ignored only when the schema marks it optional and it does
  not affect canonical binding; canonicalization itself is owned by `HSX-ST-008`.
- Known opcode with wrong arity/type/width, stack under/overflow, overlapping rows, cyclic or
  non-progressing CFA, invalid address/alignment or malformed piece coverage: `corrupt`.
- Required snapshot byte/register absent or unreadable: `unavailable`/`partial` as allowed by
  the enclosing result.
- Snapshot/target/image/revision mismatch: `stale`.

The evaluator never retries with a fixed R7 rule, masked address or other schema version.

## 6. Unwind and variable-location schema decisions

### 6.1 `hsx.unwind-recipe/1`

Each PC row defines:

- `cfa_expression` yielding one data-space address;
- `caller_pc`, `caller_sp` and optional `caller_frame_base` rules;
- zero or more caller-register rules (`same`, `undefined` or expression);
- boundary kind (`ordinary`, `entry`, `epilogue`, `terminal`, or explicitly unsupported);
- optional `call_site_adjustment`, which is checked `-4` for the selected ABI.

The selected compiler must emit distinct rows for the following machine states:

| Current instruction state | CFA/caller recovery |
|---|---|
| At function-entry `PUSH R7`, before execution | `CFA = address(SP) + 4`; caller PC = `deref_u(CFA-4,4,little)`; caller SP = CFA; caller R7 = `same`. |
| At `MOV R7,R15`, after the push | `CFA = address(SP) + 8`; caller PC = `deref_u(CFA-4,4,little)`; caller SP = CFA; caller R7 = `deref_u(CFA-8,4,little)`. |
| Stable body, local-release POPs and before `POP R7` executes | `CFA = address(R7) + 8`; caller PC = `deref_u(CFA-4,4,little)`; caller SP = CFA; caller R7 = `deref_u(CFA-8,4,little)`. |
| At `RET`, after `POP R7` | Same as entry: `CFA = address(SP) + 4`, caller PC at CFA-4, caller SP = CFA, caller R7 = `same`. |
| Top-level entry/return | Terminal row; no fabricated caller. |

Rows are derived from exact linked PC ranges, not opcode pattern matching at debug time.
`call_site_pc` is returned separately from `resume_pc` and uses the checked `-4` rule.

An unwind result contains a trustworthy frame prefix. Each frame includes frame identity,
resume PC, optional call-site PC, CFA/SP/frame base, recovered-register availability and
`complete` or `partial`. The terminating status is exactly one of `complete`, `partial`,
`unavailable`, `unsupported`, `corrupt` or `stale`, with a stable diagnostic code and the
offending frame/row/op index. Failure to recover caller PC or a non-progressing/cyclic CFA
ends the walk; proven prefix frames remain usable.

### 6.2 `hsx.location-recipe/1`

Each location entry is bound to exact image, ABI, function/lexical scope, declared type/bit
size, frame identity and a half-open PC range. It has one form:

- `address`: expression returns a typed address; declared bytes are read in the snapshot;
- `value`: expression returns immediate/register/dereferenced bits;
- `pieces`: at most 16 independently evaluated `{destination_bit_offset, bit_size,
  expression, source_bit_offset}` records with non-overlapping declared destinations;
- `optimized_out` or `unavailable` with reason.

Stack locations use `frame_base` plus checked signed offset. Globals use `static_address`.
Register locations use `reg_value` from the selected frame's recovered state. A non-top-frame
register that unwind did not recover is unavailable; the evaluator never substitutes the
current register snapshot. Constants retain declared width. Endian belongs to the declared
value/read, not the host.

`ValueResult` contains `status` (`complete`, `partial`, `unavailable`, `optimized_out`,
`unsupported`, `corrupt`, `stale`), declared type/size, available pieces with exact bit ranges,
missing pieces/reasons and diagnostic row/op indices. Partial is legal only for `pieces`; a
missing scalar is unavailable rather than zero-padded.

## 7. Raw register-write authority and stop/snapshot coherence

### 7.1 Required request and preconditions

`hsx.debug.register-write/1` exposes one atomic `WriteRegisterSet` operation. A request carries:

- operation ID, exact `ExecutiveInstanceRef`, `SessionRef`, exclusive mutator
  `AttachmentLease`, `TargetRef` and `LoadedImageRef`;
- origin `StopToken` and `InspectionSnapshotRef`;
- expected transition, inspection and register-set revisions;
- one or more typed `{RegisterId, width, value}` writes and the exact ABI/architecture refs.

The Executive accepts it only while the target is in an inspection-stable explicit debug
stop, with no resume/step/lifecycle operation accepted or linearized first. Observer leases,
running targets, legacy live reads and WAIT_MBX/SLEEPING snapshots are read-only; a separate
future capability would be required to mutate a blocked snapshot. All identity, authority,
generation and revisions are checked before any write.

### 7.2 Register-specific validation

- `R0..R6`, `R8..R14`: exact 32-bit values accepted.
- `R7`: value must be zero or a 4-byte-aligned address inside the current task stack range.
  A successful change may make current-frame unwind unavailable but may not escape the range.
- `R15`: direct write rejected as `derived_register`; it is updated only with SP.
- `SP`: must be 4-byte aligned, within `[stack_low, stack_high]`, satisfy the stack guard and
  be representable in the descriptor. Acceptance writes authoritative SP and R15 together.
- `PC`: must be an executable, 4-byte-aligned code-space address in the same LoadedImageRef.
- `PSW`: only descriptor-declared writable bits may differ; reserved/unknown bits cause
  atomic rejection rather than masking.
- Unknown registers, duplicate/conflicting entries, wrong widths and cross-space values are
  rejected. No partial register set is committed.

### 7.3 Linearization and revision effects

An accepted write linearizes as one stopped-state mutation:

1. validate and stage the entire set against the origin stop/snapshot;
2. atomically apply registers/special registers;
3. increment transition, inspection and register-set revisions;
4. invalidate the origin StopToken, SnapshotRef and all epoch-bound unwind/location/variable/
   memory/disassembly handles;
5. publish ordered `TransitionEvidence` with prior/new state both stopped and cause
   `debug_register_write`, then a new `StableStopEvidence`, StopToken and SnapshotRef;
6. return a commit containing before/after revisions and the new stop/snapshot evidence.

The target never becomes running merely because registers were written. Any later resume or
step must name the new StopToken. Rejection changes no revision. Loss/fault during an operation
must prove either no commit or the complete committed after-state; ambiguous/partial mutation
cannot satisfy the capability and returns `unrecoverable` after reconciliation.

This rule consumes `HSX-D-001` authority and `HSX-D-003` stop/snapshot semantics while the
register roles/validation live under `HSX-A-002`/`HSX-D-002`.

### 7.4 Degraded behavior

`hsx.python-debug-legacy/1` may expose read-only R7-chain stack/local inspection with explicit
weak-binding diagnostics. Its current `vm_reg_set`/`write_regs` paths are **not** portable
register-write capability and should be reported `unsupported` at the debugger boundary.
There is no safe degraded mode that advertises a successful unfenced write. The removal gate
is passage of identity/authority/stopped-state/atomicity/revision/invalidation fixtures through
the production Executive route.

## 8. Conformance-fixture plan

| Fixture family | Required positive/negative evidence |
|---|---|
| Descriptor selection | Exact architecture/ABI/schema refs accepted; wrong digest/version/architecture and inferred HXE/R7 profile rejected. |
| Register preservation | Generated nested calls prove R7 preservation; deliberate clobbers prove R0..R6/R8..R14 caller-clobbered; live-across-call compiler case must spill or fail conformance. |
| Arguments/return | 0–3 word arguments and R0 result end-to-end; f16/pointer word encoding; explicit extension fixtures; aggregate/multiword/varargs unsupported. |
| Overflow layout | Caller pushes 4–6 arguments high-to-low; VM memory proves entry-SP and R7-relative layout; hand-written callee positive; compiled callee >=4 remains an explicit failing/removal fixture until implemented. |
| Frame PC ranges | Stops at entry PUSH, MOV, stable body, each local-release POP, POP R7 and RET recover the same caller; nested/recursive/leaf/terminal cases. |
| Return/call-site PC | Stored resume PC is call+4; call-site is checked -4; underflow, wrong opcode, alignment and image/range mismatch do not wrap. |
| Unwind schema | Complete/partial prefix; missing row; unknown schema/op; malformed operands; overlap; limit; unreadable memory; FP/CFA cycle/non-progress; stale snapshot. |
| Locations | Top/non-top registers; frame offset; global/static address; constant widths; range boundary; pieces and missing piece; optimized-out; unsupported expression; stale image/snapshot. |
| Register mutation | Wrong lease/state/Target/Image/StopToken/revisions; atomic multiwrite; invalid PC/SP/R7/PSW; direct R15 rejection; SP+R15 coherence; old epoch staleness and new ordered stop; target-loss no-partial proof. |
| Degraded profile | Legacy R7 adapter is labeled weak/read-only; hard-coded fallback and legacy raw register write cannot claim full capability. |

Fixtures must cover current-profile success, named degraded behavior and unsupported outcomes.
They are reusable across the Python oracle and future native implementations; no AVR work is
authorized by planning them.

## 9. Targeted evidence run

Read-only tests at the Study baseline:

```text
c:/Users/hanse/miniconda3/python.exe -m pytest -q
  python/tests/test_call_arity.py
  python/tests/test_vm_callret.py
  python/tests/test_vm_callret_edges.py
  python/tests/test_vmclient_reg_api.py
  python/tests/test_hsx_llc_debug.py

15 passed

c:/Users/hanse/miniconda3/python.exe -m pytest -q
  python/tests/test_executive_sessions.py
  -k "stack_info or watch_add_local or watch_local_register or memory_regions"

7 passed, 56 deselected
```

The tests prove the reported caller push/pop shape, VM call/return behavior, raw RPC masking,
current debug-location emission and defensive legacy stack/local handling. They do **not**
prove the proposed recipe or mutation capabilities; the fixture plan above is required.

Static evidence also found that the formal-callee `stack_args` list is constructed but never
consumed, while the separate call-site `stack_args` variable emits only caller pushes. This
is why overflow arguments are a declared compiler conformance gap rather than a claimed pass.

## 10. Exact synthesis changes required

### 10.1 HSX requirements

- **`HSX-R-016`:** name `hsx.abi-descriptor/1` and the selected
  `hsx.abi.llc-r7-word32/1`; add exact register roles/saved sets, special PC/SP/PSW/R15 rules,
  4-byte stack/call frame, checked call-site `return_pc-4`, supported value classes and
  explicit unsupported aggregate/multiword/varargs/dynamic/tail/inline behavior. State that
  SVC signatures are separate exact descriptors. Add atomic, authority- and revision-fenced
  register-write policy or explicit unsupported outcome.
- **`HSX-R-017`:** name `hsx.unwind-recipe/1`; require image/ABI/snapshot-bound non-overlapping
  PC rows, the version-1 opcodes/bounds/unknown behavior, prologue/body/epilogue coverage,
  recovered-register availability and structured `unsupported` in addition to the existing
  complete/partial/unavailable/corrupt/stale outcomes.
- **`HSX-R-018`:** name `hsx.location-recipe/1`; require exact scope/frame/PC binding,
  address/value/pieces/optimized/unavailable forms, bounded opcode evaluation, non-top-frame
  recovered registers and structured piece diagnostics without zero fill.

No new numeric requirement is needed. `HSX-R-005`, `R-008`, `R-019`, `R-020`, `R-022` and
`R-023` are consumed unchanged as authority/revision prerequisites for register mutation;
Master may clarify their relations without allocating a new ID.

### 10.2 HSX architecture/design

- **`HSX-A-002`:** make an immutable descriptor registry plus bounded recipe evaluator the
  owner of ABI selection, register roles/write validation and unwind/location interpretation.
  Explicitly exclude runtime-state authority (A-001/A-003), debugger policy, fixed R7
  fallback and AVR realization. Add the dependency that register mutation consumes A-001
  lease authority and A-003 stop/snapshot revisions.
- **`HSX-D-002`:** replace prose-only ABI/recipe text with the IDs, exact profile table,
  emitted frame rows, symbolic opcodes, limits, unknown behavior and structured result
  schemas above. Add `WriteRegisterSet` request/commit and special-register validation,
  cross-linked to D-001/D-003. Keep bundle canonicalization/binding changes from ST-008
  non-recursive.
- **Profile registry/fixtures:** add the three named ABI/recipe capabilities to the full
  profile, keep register write optional, and state that the current implementation remains
  `hsx.python-debug-legacy/1` until exact fixtures pass.

### 10.3 Debugger contracts and `DBG-ST-006`

- **`DBG-D-002`:** gateway only transports typed descriptor/recipe/register-mutation
  envelopes and negotiated capabilities; it never turns legacy RPC success into authority.
- **`DBG-D-003`:** a successful register edit is a controller-serialized epoch transition;
  invalidate the origin epoch/handles and install only the returned new StableStopEvidence.
- **`DBG-D-004`:** Artifact Index validates exact ABI/recipe refs; Inspection Service uses
  the bounded evaluator and preserves complete/partial/unavailable/optimized/unsupported/
  corrupt/stale diagnostics. Register editing is a controller command, not a service-side
  cache mutation or direct VM call.
- **`DBG-D-006`:** source over/out require applicable unwind rows and recovered frame state;
  missing/unsupported rows yield unavailable. Register mutation cannot race an active
  execution plan and any plan must restart from the new StopToken.
- **`DBG-ST-006`:** question 6 becomes owned by `HSX-ST-003` + `HSX-ST-007`; its matrix must
  name the exact profile/schema capabilities and the prologue/epilogue, unknown-op,
  partial-result and register-mutation fixtures. Question 5 must record register writes as
  snapshot-invalidating mutations.

These are proposal edits for Master synthesis and fresh review. They do not freeze any
`DBG-D-*` contract or authorize `DBG-RF-002..009`.

## 11. Conclusions and traceability

1. The concrete current portable ABI target is `hsx.abi.llc-r7-word32/1` paired with
   `hsx.arch.vm-byte16-gpr32/1`, not a universal HSX ABI.
2. Only R7 is callee-preserved by emitted code. R15 is a derived SP mirror; PC/SP/PSW are
   separate special registers. The broader saved sets and multiword/varargs claims in current
   prose are not conformance evidence.
3. The exact stable frame is `[R7]=caller R7`, `[R7+4]=resume PC`, with call-site PC checked
   as resume PC minus one 4-byte CALL. Overflow argument #4 begins at `[R7+8]`.
4. Caller overflow emission exists, but compiled-callee consumption and live-across-call
   preservation are explicit implementation gaps and fixtures, not silently accepted rules.
5. `hsx.unwind-recipe/1` and `hsx.location-recipe/1` are bounded declarative schemas with the
   listed symbolic opcodes, typed addresses, explicit limits and fail-closed unknown behavior.
6. Portable raw register writes are atomic, exclusive-owner, stable-stop and revision fenced.
   They invalidate and replace the stop/snapshot epoch; direct R15 and unfenced legacy writes
   cannot claim the capability.
7. `HSX-R-016..018`, `HSX-A-002`, `HSX-D-002` and the named Debugger contracts can absorb
   these decisions without allocating any new numeric contract IDs.

Traceability relations:

- `HSX-ST-003` and `HSX-RVW-001-001-004` spawn/inform this Study.
- This Study informs `HSX-R-016..018`, `HSX-A-002`, `HSX-D-002` and the full/degraded profile
  fixture registry.
- It supplies portable dependencies to `DBG-ST-006`, `DBG-D-002`, `DBG-D-003`,
  `DBG-D-004` and `DBG-D-006`.
- `HSX-ST-008` supplies the non-recursive bundle/source identity binding used by recipe refs.
- `HSX-D-001` and `HSX-D-003` remain the authority and stop/snapshot evidence owners consumed
  by register mutation.

Status is **COMPLETE FOR MASTER SYNTHESIS**. No product code, AVR work, Debugger design freeze
or Refactor implementation authority follows from this Study.

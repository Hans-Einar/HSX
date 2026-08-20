# HSX-ST-001 — Legacy HSX Traceability Migration Study

- Status: **COMPLETE FOR PORTABLE DEBUG CONTRACT SYNTHESIS**
- Broader HSX migration: **OPEN; INVENTORIED AND ROUTED, NOT COMPLETE**
- Owner: HSX SDP Master
- Study worker baseline: `d135e542b2a959c2ea67e3a1ea65df7e0bcd6baf`
- Active issue: #47
- Steering activation: comment `5348192567`
- Master activation: comment `5348405909`
- Coordinated Debugger dependency: `DBG-ST-006`, issue #38
- Iteration: `DBG-IT-001-003`

## 1. Question and bounded scope

Which legacy HSX requirements, goals, options, architecture/design statements, implementation
records, current Python behavior, and target constraints are usable provenance for the
portable runtime contracts required by `DBG-ST-006`?

This Study is a migration and inventory coordinator. It does not choose new semantics. The
five technical domains are resolved by `HSX-ST-002..HSX-ST-006`; the Master owns allocation
of stable `HSX-R-*`, `HSX-A-*`, and `HSX-D-*` IDs and synthesis of the reviewed contract
package.

The current phase covers detailed provenance for:

- runtime, stream, target and loaded-image identity/generations;
- address spaces, ABI, unwind and variable locations;
- run/stop evidence, inspection consistency, exact stepping and blocked states;
- event cursor, ACK, loss and capability behavior;
- lifecycle authority and resource identity/provenance/revisions.

The broader migration of ISA, toolchain, mailbox, value/command, provisioning, persistence,
security, HAL and target material remains open after this bounded phase.

## 2. Authority and classification rules

The evidence snapshot is the activation head above. The durable authorities read before the
inventory were `AGENTS.md`, `SDP/README.md`, `SDP/Shared/Process.md`, both active track
READMEs and CurrentIndexes, issues #47/#38, `DBG-ST-006`, `DBG-IT-001-003`, and the active
Handoff.

Every finding below uses one of these classifications:

| Classification | Meaning in this Study |
|---|---|
| **legacy-required** | Catalogued as a non-negotiable `DR-*` in `main/02--Study/02.01--Requirements.md`. This is accepted only within the legacy catalogue; it is not yet an accepted modern `HSX-R-*`. |
| **legacy-goal** | A `DG-*` architectural objective that can inform a portable contract but cannot by itself impose one. |
| **legacy-option** | A `DO-*` exploration/backlog item; never current authority. |
| **Python oracle** | Behavior observable in current Python code and/or tests. It is evidence for conformance planning, not automatically the portable contract. |
| **stale document** | Historical statement contradicted by newer code, tests, another document, or the present SDP ownership model. |
| **unresolved gap** | Required behavior is missing, ambiguous, internally inconsistent, or not proven by evidence. |
| **Debugger-owned** | User interaction, DAP/CLI policy, expression semantics, presentation, or orchestration that consumes HSX evidence but does not define portable runtime semantics. |
| **AVR-owned constraint** | Device/resource/HAL/transport/timing choice reserved for `SDP/AVR`; it may constrain a profile but must not redefine portable HSX. |

Legacy numbered documents are provenance labels, not modern stable IDs. Archived documents,
dated reviews, GapAnalysis plans and implementation notes are retained as historical evidence
only. Current code/test evidence wins when this Study describes the Python oracle; neither
wins automatically when the portable target contract is still open.

## 3. Legacy DR catalogue inventory

`main/02--Study/02.01--Requirements.md` defines 15 legacy-required entries. They are preserved
verbatim by ID and routed rather than renamed.

| Legacy ID | Legacy intent | Current migration disposition |
|---|---|---|
| `DR-1.1` | Runtime-load and execute apps without reflashing host firmware. | Portable lifecycle/load capability candidate; identity and atomic lifecycle questions route to `HSX-ST-002`. CAN/SD/MCU realization is AVR-owned. |
| `DR-1.2` | One host firmware with consistent app provisioning. | Portable image/provisioning intent; loaded-image identity routes to `HSX-ST-002`, general provisioning remains a future HSX Study, target boot media is AVR-owned. |
| `DR-1.3` | Python reference must permit a future C port. | Cross-implementation conformance candidate; no parity acceptance matrix exists. Future conformance Study required. |
| `DR-2.1` | Constant-time context switch through workspace-pointer swaps. | Workspace/address provenance for `HSX-ST-003`; execution/context evidence also informs `HSX-ST-004`. O(1) target timing remains unmeasured and target verification is AVR-owned. |
| `DR-2.1a` | Measurable CI acceptance for `DR-2.1`. | Unresolved gap: current tests prove isolation/behavior but not a portable timing acceptance method. Future conformance/performance Study. |
| `DR-2.2` | ARM-aligned calling convention. | Ambiguous legacy intent; competing register/frame/stack rules exist. Entirely routed to `HSX-ST-003`. |
| `DR-2.3` | f16 through toolchain/runtime/tooling. | Current Python evidence exists; broad numeric conformance is outside debugger priority. Retain for a future ISA/numeric Study. |
| `DR-2.5` | Shared ABI definition plus `EXEC_GET_VERSION`. | Unresolved gap. No implemented module-version query or stable capability descriptor. Protocol capability/profile aspects route to `HSX-ST-002`/`HSX-ST-005`; SVC namespace/versioning needs a future Study. |
| `DR-3.1` | Frozen HXE header/compatibility plus deterministic debug sidecar. | Current v1/v2/code/governance statements conflict. Image/debug-artifact binding routes to `HSX-ST-002`/`HSX-ST-003`; full HXO/HXE migration requires a future artifact Study. |
| `DR-5.1` | Scheduler quantum, fairness, blocking and time base. | Exact retirement and blocked-state questions route to `HSX-ST-004`; event evidence to `HSX-ST-005`. Broader scheduler fairness/priority/time-base migration remains future work. |
| `DR-5.2` | Per-target RAM/flash/runtime budgets. | Portable profile/capability candidate, but all concrete AVR numbers are estimates and AVR-owned. Future profile/conformance Study plus `AVR-ST-001`. |
| `DR-5.3` | Persistence keyspace, CRC/rollback and lifecycle. | Broad migration remains open. Persistence implementation evidence is not required to answer `DBG-ST-006`; target storage/wear is AVR-owned. |
| `DR-6.1` | Normative mailbox delivery, back-pressure and overflow. | Current Python oracle is extensive, but full portable mailbox migration remains a future Study. Wait/wake inspection implications route to `HSX-ST-004` and event continuity to `HSX-ST-005`. |
| `DR-7.1` | Value/command security and cross-transport policy. | Broad security/value-command migration remains open. Debugger must not invent policy. |
| `DR-8.1` | Debug session locks, event categories, rate control and reconnect. | Portable runtime portions route to `HSX-ST-002`, `HSX-ST-004`, `HSX-ST-005`, and `HSX-ST-006`; frontend/controller policy remains Debugger-owned. |

Catalogue integrity findings:

- `DR-7.3` is cited repeatedly in `04.04--ValCmd.md`, implementation notes, DoD and tests, but
  has no entry in the legacy DR catalogue. It is a dangling legacy reference, not authority.
- `04.00--Design.md` contains `DR-5.15.3`, evidently a malformed range/reference.
- There is no `DR-4.*`; VM debugger/sleep intent exists only as goals `DG-4.2/4.3` and later
  design text.
- The legacy catalogue calls DRs “current release” requirements, but no modern review/sign-off
  demonstrates that each remains accepted. Master synthesis must preserve provenance and
  make an explicit accept/revise/retire decision per migrated requirement.

## 4. Legacy DG and DO inventory

### 4.1 Design goals

| Group | Preserved IDs and intent | Migration route |
|---|---|---|
| Runtime | `DG-1.1` runtime updates, `DG-1.2` unified firmware, `DG-1.3` Python-to-C path, `DG-1.4` parity tests | Lifecycle/image identity: `HSX-ST-002`; parity and target realization: future conformance Study / AVR. |
| ISA/ABI | `DG-2.1` 16×32-bit register window, `DG-2.2` workspace addressing, `DG-2.3` calling convention, `DG-2.4` f16 model | Address/ABI/unwind: `HSX-ST-003`; numeric detail stays in a future ISA Study. |
| Toolchain | `DG-3.1` HXO/HXE/relocations, `DG-3.2` lowering/allocation, `DG-3.3` debug metadata, `DG-3.4` shared SVC source, `DG-3.5` deterministic listing/sidecar | Debug metadata/address binding: `HSX-ST-003`; image identity: `HSX-ST-002`; general artifact/SVC migration: future Studies. |
| MiniVM | `DG-4.1` workspace implementation, `DG-4.2` break/trace, `DG-4.3` sleep/wait | `HSX-ST-003`, `HSX-ST-004`, and resource provenance `HSX-ST-006`. |
| Executive | `DG-5.1` scheduler, `DG-5.2` events, `DG-5.3` PID/session/capabilities, `DG-5.4` one-instruction yield | `HSX-ST-002`, `HSX-ST-004`, `HSX-ST-005`. |
| Mailbox | `DG-6.1` delivery, `DG-6.2` back-pressure, `DG-6.3` handles/namespaces, `DG-6.4` stdio | Blocked-state/event implications: `HSX-ST-004/005`; full mailbox contract: future Study. |
| Value/command | `DG-7.1` registry, `DG-7.2` invocation, `DG-7.3` transport/persistence, `DG-7.4` numeric canonical addressing | Future value/command and persistence Studies; not silently pulled into debugger contracts. |
| Toolkit | `DG-8.1` CLI/TUI, `DG-8.2` client event/back-pressure, `DG-8.3` packaging/cross-platform | Primarily Debugger-owned. Runtime dependencies are extracted through `DBG-ST-006`; UI/package policy stays in Debugger. |

### 4.2 Design options

The catalogue preserves `DO-2.a`, `DO-3.a`, `DO-4.a`, `DO-5.a`, `DO-6.a`, `DO-7.a`,
`DO-8.a`, `DO-VM-hotset`, `DO-VM-adaptive`, `DO-mailbox-ns`, `DO-val-bulk`,
`DO-tool-altIR`, `DO-hxe-sym`, and `DO-relay`. Later documents introduce uncatalogued
`DO-4.b` (FRAM-backed code cache) and `DO-7.b` (array/matrix values).

All remain legacy-options. None can justify a portable debugger dependency. In particular:

- embedded symbols (`DO-hxe-sym`) do not override the current external `.sym` evidence;
- priority scheduling (`DO-5.a`) does not weaken the exact-instruction question;
- register hotsets/adaptive copies do not replace the visible architectural register model;
- relay/TUI options are Debugger-/AVR-owned presentation/transport choices;
- FRAM-backed cache, paging, vector opcodes and target QoS are outside this phase.

## 5. Numbered architecture/design/implementation evidence inventory

| Evidence | Classification and usable content | Limits / route |
|---|---|---|
| `main/03--Architecture/03.00--Architecture.md` | Legacy architecture direction: MiniVM ↔ Executive ↔ HAL separation and host-side rich debugger. | Portable layering is useful provenance. Embedded backend/transport choices are AVR-owned. |
| `03.01--VM.md` | Legacy architecture: single-task VM, executive scheduling, register windows, HXE load hooks. | Contains stale claims about snapshot copying and unresolved storage/paging. Address/execution portions route to `HSX-ST-003/004`. |
| `03.02--Executive.md` | Legacy architecture: task scheduling, sessions, event stream, provisioning and runtime services. | Describes desired events/ACK/locks but not stable identity, revision or loss contracts. Routes to `HSX-ST-002/004/005/006`. |
| `03.03--Mailbox.md` | Delivery, wait/wake, namespace and observability intent. | Useful blocked-state provenance; target pool sizes are AVR-owned. Full mailbox migration remains. |
| `03.04--ValCmd.md` | Numeric OID, f16, persistence and transport intent. | Broad value/command migration remains; no debugger contract authority. |
| `03.05--Toolkit.md` | Host debugger consumes Executive RPC/events and symbols. | Debugger-owned except for explicit cross-track dependencies. |
| `03.06--Provisioning.md` | Load/restart/persistence lifecycle intent. | Host load is Python-oracle evidence; CAN/SD/FRAM and boot policy are AVR-owned. |
| `HSX_architecture_review_3x.md` | Historical review says direction is sound but ABI, scheduler, event, HXE, budgets, persistence and security were P0 gaps. | Strong evidence that later design text was not a frozen contract. |
| `main/04--Design/04.00--Design.md` | Catalogue of numbered designs. | DRAFT-era umbrella with malformed/dangling references; not authority. |
| `04.01--VM.md` | DRAFT design with opcode/register/memory/context/control API proposals. | Internally contradicts itself and newer code on standalone mode, ABI, SP/frame register, address units, alignment, and ownership. Split to `HSX-ST-003/004`; do not wholesale migrate. |
| `04.02--Executive.md` | DRAFT state/session/event/inspection/scheduler design. | Many mechanisms now exist in Python, but identity/revision/snapshot/gap semantics remain absent. Routes to all five domain Studies. |
| `04.03--Mailbox.md` | Detailed descriptor, wait queue, mode, timeout and event design. | Current tests supersede several old “missing” notes; portable mailbox acceptance still separate. |
| `04.04--ValCmd.md` | Detailed registry/descriptor/persistence/CAN/SVC proposal. | Contains dangling `DR-7.3`; broad migration deferred. |
| `04.05--Toolchain.md` | HXO/HXE/debug pipeline, source paths and debug metadata design. | Current code implements much of it; artifact versions/binding still need a dedicated migration Study. Debug-relevant metadata routes to `HSX-ST-003`. |
| `04.06--Toolkit.md`, `04.09--Debugger.md`, `04.10--TUI_Debugger.md`, `04.11--vscode_debugger.md`, `DebuggerDesignReview.md` | Historical debugger protocol/UI/design proposals. | Debugger-owned and superseded for target architecture by `SDP/Debugger`; retain only HSX dependency provenance. |
| `04.07--Provisioning.md` | Monolithic/streaming load state machine, errors, rollback and progress proposals. | Current host streaming load is partial oracle; transport, rollback and target policy remain future HSX/AVR Studies. |
| `04.08--HAL.md` and HAL implementation narratives | HAL module/API proposals and target-facing library sketches. | AVR-owned realization; historical Markdown contains proposed code, not an implementation baseline. |
| `main/05--Implementation/system/*` | Short planned module checklists for MiniVM, Executive, Mailbox, ValCmd, Provisioning, HAL and shell. | Historical implementation intent. Must be compared with current code/tests, not treated as status. |
| `main/05--Implementation/toolchain/*` and `formats/*` | Planned assembler/lowering/linker/debug metadata and placeholder format records. | Several placeholders are superseded by `docs/*` and code. Preserve as provenance only. |
| `main/05--Implementation/shared/*` | Draft ABI, event/resource/persistence/security fragments. | Some module maps are inconsistent with current code. Route by domain; do not promote. |
| `main/05--Implementation/01--GapAnalysis/*` | Dated implementation snapshots and plans. | Stale for current status: many items labelled missing now exist. Useful only to establish chronology and former gaps. |
| `main/06--Test/*` | Historical test plans. | Planned evidence, not proof. Current `python/tests` are the Python-oracle evidence. |

The archived `main/04--Design/_archive_old/*` variants and `docs/outdated/*` are explicitly
stale documents. They may explain ancestry but are excluded from contract synthesis unless a
domain Study cites a unique unresolved fact.

## 6. Current Python-oracle inventory by subsystem

| Subsystem | Current behavior/evidence | Classification and limit |
|---|---|---|
| HXO/HXE | `python/asm.py` emits JSON HXO schema v1; `python/hld.py` is the HXE creation path; `host_vm.py` parses HXE v1 and v2 with big-endian headers and CRC validation. Tests include `test_build_determinism`, `test_hxe_v2_metadata`, `test_hxe_section_order_overlap`, `test_vm_stream_loader`. | Python oracle. Governance text still says HXE `0x0001` must not change while `docs/hxe_format.md` calls `0x0002` current. No portable compatibility decision exists. |
| Debug artifacts | Linker emits `.sym` v1 with `hxe_crc`, symbols, instructions, regions and local-location ranges; `sources.json` is deterministic and relocatable. Tests include `test_linker`, `test_hsx_llc_debug`, `test_source_map`. | Python oracle. Executive symbol loading discards/does not validate top-level `version`, `hxe_path`, or `hxe_crc`; image/artifact provenance is therefore unproven. |
| VM architecture | 16×32-bit registers in a memory-backed little-endian window; 64 KiB VM data memory; code is separately stored; register/stack arenas are assigned per PID; PC/SP/context fields are carried as masked u32 in many paths. | Python oracle. Effective addresses are frequently masked to 16 bits. Public typed address spaces, overflow and alias rules are absent. |
| ABI/unwind | CALL/RET/PUSH/POP and >3-argument compiler tests exist. Executive stack walk currently assumes `R7` frame pointer and `[prev_fp, return_pc]` at `fp`; local locations support stack/register/global/const ranges. | Python oracle with conflicting docs. No accepted portable ABI/unwind contract or partial-location model. |
| Task identity | `VMController.next_pid` increments from 1, streaming-load begin reserves a PID, kill removes the record, reset sets `next_pid = 1`; PID 0 has legacy meaning in protocol text. App names may be suffixed for multiple instances. | Python oracle. PID alone is reusable and has no target generation; app/path/name is not immutable image identity. |
| Sessions/lifecycle | Executive sessions use process-local UUIDs, heartbeat expiry and PID locks. `load` creates and immediately activates/runs a task; pause/resume/kill are separate; global attach/detach and per-PID VM debug attach are different concepts. | Python oracle. No atomic create/load/start/claim contract, stable executive identity, reconnect continuity, observer authority type, or detach/release/terminate ownership contract. |
| States/events | `TaskState` validates READY/RUNNING/WAIT_MBX/SLEEPING/PAUSED/RETURNED/TERMINATED/KILLED transitions. `task_state` reasons are partly pending-command annotations and partly inferred from refreshed snapshots. | Python oracle. There is no state revision/causal token; acknowledgement of a command is not distinguished by a stable contract from observed transition evidence. |
| Exact stepping | `VMController.step` retires one instruction per loop/round-robin turn; targeted step can restrict PID. Tests include `test_round_robin_single_instruction` and manual single-step re-pause. | Python oracle. `source_only` uses compiler-instruction metadata heuristics; outcome/precedence and target-epoch binding are unspecified. |
| Breakpoints | VM and Executive store per-PID sets of addresses masked to 16 bits. Pre/post checks exist; resume can request one-shot skip at the current stop PC. Breakpoints disappear on task cleanup. | Python oracle. No stable remote resource ID, owner/provenance, revision, conditional update, image generation or complete precedence contract. |
| Watches | Executive allocates process-global monotonically increasing integer IDs and stores per-PID records; values are sampled after steps; kill removes records. Local watch resolution consumes `.sym` ranges. | Python oracle. Session ownership/cleanup, provenance, generation/revision and compare-and-set are absent. Snapshot Watch expressions remain Debugger-owned. |
| Inspection | Registers, memory, code, stack, disassembly, symbols and resource lists are separate RPCs. Inactive tasks are served from stored task snapshots; active tasks may be read live. | Python oracle. No atomic inspection bundle, snapshot token, state revision or stale-read rejection exists. |
| Blocked tasks | WAIT_MBX and SLEEPING tasks are removed from the runnable set and have saved state/context. Mailbox data, timeout heaps and sleep deadlines can independently wake/update them. | Python oracle. “Saved” does not prove a stable multi-read inspection epoch; blocked-state stability requires an explicit capability/transition contract. |
| Events | `event_seq` is process-local and monotonic; history is a 4096-entry deque; sessions have one subscription with queue/drop counters. `since_seq` replays matching retained history. ACK is monotonic by `max`. | Python oracle. No stream ID/generation is sent; evicted `since_seq` is not rejected despite the documented `seq_evicted`; queue overflow advances `last_ack` internally and emits warnings, so documented loss/ACK semantics are not a proven contract. |
| Mailbox/value-command | Mailbox wait/wake/timeout/fan-out and value/command registries have extensive current code/tests; HXE v2 metadata can precreate/register resources. | Python oracle. Broad portable subsystem acceptance is outside this phase; debugger consumes only explicit state/event/resource contracts. |

## 7. Portable debugger-runtime provenance matrix

| `DBG-ST-006` question | Legacy provenance | Current oracle and uncertainty | Owning route |
|---|---|---|---|
| 1. Executive/stream/target/image identity and generations | `DR-1.1/1.2/2.5/8.1`; `DG-5.2/5.3`; `03.02`; `04.02` §§4.2, 6.5, 6.9, 7 | UUID sessions, process-local event seq, reusable PIDs, mutable paths/names and unvalidated `.sym` CRC. No executive/stream/target/image generations. | `HSX-ST-002`; stream identity cross-check in `HSX-ST-005`. |
| 2. Named address spaces, widths, byte order, alignment, serialization, overflow | `DR-2.1/2.2/3.1`; `DG-2.1..2.3`, `DG-3.1/3.3`; `04.01` §§4.3/4.4; HXE/HXO docs | Guest register/data bytes are little-endian; HXE headers/code serialization are big-endian; code and data are separate; masks and u32 fields mix. `test_mem_alignment` proves unaligned little-endian loads while DRAFT design says misalignment faults. | `HSX-ST-003`. |
| 3. Authoritative run/stop/block/fault/termination evidence | `DR-5.1/8.1`; `DG-4.2/4.3`, `DG-5.1/5.2/5.4`; `04.02` §§7/8 | State machine and events exist, but reasons can be inferred and carry no revision, command causality, stop token or target generation. Fault evidence is not normalized with terminal/state events. | `HSX-ST-004`; ordering/loss dependency `HSX-ST-005`; identity dependency `HSX-ST-002`. |
| 4. Event cursor, `since_seq`, gaps, ACK and capabilities | `DR-8.1`; `DG-5.2/5.3`, `DG-8.2`; `04.02` §7; `docs/executive_protocol.md` event sections | Replay/ACK/drop mechanisms exist, but `seq_evicted` and stream generation do not. ACK accepts values beyond delivery; queue drop mutates ACK position. Feature negotiation is a string intersection, not a named protocol profile. | `HSX-ST-005`, depending on `HSX-ST-002`. |
| 5. Stopped inspection consistency | Legacy state-inspection proposals in `04.02` §§5.3..5.7 and `04.09` §5.5; `DR-8.1` | Separate register/memory/stack/disassembly/resource reads can observe different moments. Stored inactive state is not exposed with a revision or atomicity guarantee. | `HSX-ST-004`; image/address dependencies `HSX-ST-002/003`. |
| 6. ABI/unwind/frame/variable-location semantics | `DR-2.2`; `DG-2.3`, `DG-3.3/3.5`; `02--Study` calling convention; `04.01` §§4.6/6; `DebuggerDesignReview` §3 | At least three conflicting frame/register conventions exist. Current stack walk uses R7 and partial-error arrays; compiler emits ranged stack/register/global/const locations. `.sym` binding is unchecked. | `HSX-ST-003`. |
| 7. Exact instruction step, bypass/precedence and source prerequisites | `DR-5.1`; `DG-4.2`, `DG-5.1/5.4`; `04.01` VM step; `04.02` §§8.3/8.6 | One-instruction oracle is strong; one-shot skip exists. Pre/post Executive checks and VM `debug_stop` coexist, and source stepping uses metadata heuristics. No single outcome envelope or stop-condition precedence. | `HSX-ST-004`; resources `HSX-ST-006`; metadata prerequisite `HSX-ST-003`. |
| 8. Create/load/start/claim, attach/observer, release/terminate ownership | `DR-1.1/1.2/8.1`; `DG-5.3`; `03.06`; `04.07`; `04.02` session/lifecycle sections | Load auto-runs, stream begin reserves PID, sessions lock mutations, global attach differs from debug attach, reconnect creates a new UUID. Atomic lifecycle and authority transfer are absent. | `HSX-ST-002`. |
| 9. Breakpoint/watch remote identity, provenance and revisions | `DG-4.2`, `DG-5.2/5.3`; `04.02` §§5.7/8.6; `04.09` §§5.4/5.6 | Breakpoints are address-only sets; watches are PID + integer ID. No session owner, source/provenance, generation, revision, conditional update or reconnect reconciliation evidence. | `HSX-ST-006`, depending on `HSX-ST-002/003/005`. |
| 10. Mailbox-wait/sleep inspection stability | `DR-5.1/6.1`; `DG-4.3`, `DG-5.1`, `DG-6.1/6.2`; `04.02` §§8.1/8.4; `04.03` wait/wake | Blocked task state is stored, but external mailbox/timer paths can wake it between reads. No stable blocked epoch, stale response or transition barrier. | `HSX-ST-004`; lifecycle/event dependencies `HSX-ST-002/005`. |

## 8. Material contradictions and stale claims that must not migrate silently

1. **Calling convention:** `02--Study` and the first `docs/hsx_spec-v2.md` ABI section use
   return `R0`, args `R1..R3`, callee-saved `R4..R7`, 4-byte stack slots/alignment. DRAFT
   `04.01--VM.md` uses args `R0..R3`, caller-saved `R4..R7`, callee-saved `R8..R12`, frame
   pointer `R14`, link `R15`, 8-byte alignment and a different overflow offset. Current
   unwind code assumes frame pointer `R7`. `HSX-ST-003` must resolve; none is silently
   “canonical.”
2. **Address model:** DRAFT `04.01` says 16-bit word addresses translated to bytes and future
   24-bit effective addresses. Current assembler, symbols, Executive and VM generally expose
   byte PCs, hold many values as u32, then mask memory/code/breakpoints to 16 bits. Typed
   address spaces and overflow behavior are missing.
3. **Alignment:** DRAFT design requires misaligned access faults; current
   `test_unaligned_little_endian_loads` establishes successful unaligned little-endian loads.
4. **Stack bounds:** DRAFT `stack_base <= sp < stack_limit` conflicts with the Python allocator,
   where `stack_limit == stack_base` and SP starts at the top of the allocation.
5. **HXE version authority:** repository constraints preserve HXE magic/version `0x0001`, while
   `docs/hxe_format.md` calls v2 current and the Python loader/toolchain supports both. A stable
   compatibility/profile decision is still required.
6. **SVC module map:** `docs/hsx_spec-v2.md` contains an EXEC/VAL mapping inconsistent with
   `docs/abi_syscalls.md`, current Python code and the legacy `0x06`/`0x07` alias history.
7. **Standalone mode:** legacy Study/architecture and parts of `04.01` allow standalone test or
   tiny-target execution, while the same design says production always has an Executive.
   Current MiniVM includes local stubs. This is a profile question, not a debugger assumption.
8. **Event resume:** documentation promises `seq_evicted`, retention-based recovery and owner
   protection that current subscription code does not implement as stated.
9. **Artifact binding:** `.sym` includes `hxe_crc`, but Executive parsing omits it; source and
   symbol data can therefore be plausible yet belong to another image.
10. **Historical status records:** dated GapAnalysis files say sessions/events/stack/disassembly,
    HXE v2/debug metadata, value/command and mailbox timeout behavior are missing. Current code
    and tests implement them. Those files are chronology, not present status.
11. **Resource budgets:** AVR sizes are explicitly estimates pending C/on-target measurements;
    they cannot become portable limits or proof that a feature profile fits.
12. **Debugger documents:** legacy CLI/TUI/VS Code design belongs to Debugger ownership and is
    superseded for architecture direction by `SDP/Debugger`. Only its runtime dependency facts
    cross tracks.

## 9. Descriptive contract concepts proposed for Master allocation

These names describe synthesis candidates; they deliberately allocate no numeric `HSX-R-*`,
`HSX-A-*`, or `HSX-D-*` IDs.

| Concept | Minimum content required from domain Studies |
|---|---|
| **RuntimeInstanceIdentity** | Opaque executive-instance ID/generation and restart boundary. |
| **EventStreamIdentityCursor** | Stream ID/generation, sequence scope, valid cursor interval, ACK-after-apply, explicit gap/eviction outcome and reconcile requirement. |
| **TargetIdentityGeneration** | Stable target handle distinct from display PID, generation change rules and stale-target rejection. |
| **LoadedImageIdentity** | Content/schema identity, load generation, HXE/debug-artifact binding and immutable image metadata. |
| **LifecycleAuthorityLease** | Create/load/start/claim/observe/release/detach/terminate operations, atomicity, owner/observer rights and reconnect/loss outcomes. |
| **ArchitectureAddressDescriptor** | Named code/data/register spaces, widths, units, endian/alignment/serialization/overflow and capability profile. |
| **ABIUnwindLocationDescriptor** | Register roles, stack/frame/call rules, unwind termination/errors, ranged variable locations and unavailable/partial values. |
| **ExecutionEvidenceEnvelope** | State, cause, target/image generation, monotonic state revision, stop token, command correlation and ordered terminal/fault evidence. |
| **InspectionEpoch** | Immutable or revision-validated multi-read view, stale response, lifetime and allowed stopped/blocked states. |
| **ExactStepOutcome** | Accepted command vs authoritative completion, exact retired count, final PC/state/cause, one-shot breakpoint bypass and precedence. |
| **RemoteResourceRecord** | Logical/remote resource ID, kind, owner, provenance, target/image generation, revision, conditional mutation and cleanup/reconnect events. |
| **CapabilityProfile** | Explicit current and named degraded profiles, unsupported outcomes, version boundary and removal criteria; no version guessing. |

## 10. Broader migration routes and future Study recommendations

The following are explicitly outside the portable debugger-contract synthesis and should be
opened as separate Master-numbered Studies before broad HSX design is frozen:

1. **HXO/HXE and debug-artifact compatibility Study** — reconcile v1/v2 governance, header,
   CRC, section, manifest, capability and `.sym`/`sources.json` binding rules.
2. **SVC namespace and ABI-version Study** — one module/function source of truth,
   `EXEC_GET_VERSION` replacement/profile, argument/return/error/time-base rules.
3. **Portable ISA and numeric conformance Study** — opcode/address semantics, PSW, f16, memory
   alignment, fault and serialization vectors across implementations.
4. **Scheduler fairness/time-base/profile Study** — priority overlays, standalone profile,
   timeout clocks and deterministic accounting beyond debugger exact-step needs.
5. **Mailbox portable contract Study** — delivery/retention/back-pressure/fan-out/tap,
   descriptor/handle lifetime, quotas and cross-implementation fixtures.
6. **Value/command/security Study** — registry/OID semantics, auth policy, subscription,
   throttling and transport-independent behavior.
7. **Provisioning/persistence/security Study** — load/rollback, FRAM key lifecycle, integrity
   versus authenticity, atomic upgrade and recovery.
8. **Python-to-native conformance Study** — normative oracle selection, shared fixtures,
   differential test tolerances and release acceptance.
9. **AVR-ST-001** — target choice, HEOS integration, Harvard/storage model, SRAM/flash/FRAM
   budgets, target HAL/transport/timing and on-target verification. No AVR conclusions are
   made here.

Master assigns the actual next available Study IDs and ordering. None is implementation
authority.

## 11. Affected/proposed requirement themes

The portable package should propose, with stable IDs allocated only by Master:

- runtime/target/image/stream identity and stale-reference rejection;
- explicit lifecycle authority and atomic operation boundaries;
- typed architecture/address/ABI/unwind/location descriptors;
- authoritative causal execution evidence and immutable/validated inspection epochs;
- exact stepping and deterministic stop-condition outcome;
- event continuity, loss and named capability profiles;
- owner/provenance/revision-aware remote resources;
- blocked-state inspection capability and transition rules;
- conformance fixtures and current/degraded/unsupported outcomes for each contract.

Legacy `DR-1.1`, `DR-1.2`, `DR-1.3`, `DR-2.1`, `DR-2.1a`, `DR-2.2`, `DR-2.5`,
`DR-3.1`, `DR-5.1`, `DR-5.2`, `DR-6.1`, and `DR-8.1` are affected provenance.
The relevant goals are `DG-1.1..1.4`, `DG-2.1..2.3`, `DG-3.1`, `DG-3.3..3.5`,
`DG-4.1..4.3`, `DG-5.1..5.4`, `DG-6.1..6.3`, and `DG-8.2`.

## 12. Open questions retained for domain Studies/Master

1. What identity survives Executive reconnect, and what always changes on restart?
2. Can PID remain a display/local scheduling number while an opaque target ID+generation is
   authoritative?
3. Which digest/schema binds HXE, `.sym`, sources and runtime image?
4. Is the portable address model 16-bit byte-addressed, multiple named spaces, or a profile
   descriptor that admits wider implementations without masking?
5. Which ABI/frame model matches emitted code today, and what incomplete unwind result is
   portable?
6. Which state transition is authoritative when command response, VM debug event,
   `task_state`, scheduler event and refreshed snapshot disagree or are lost?
7. Are WAIT_MBX and SLEEPING inspectable through a frozen epoch, revision validation, or only
   best-effort notification in some profiles?
8. Must event ACK be rejected beyond delivered/applied sequence, and what exact data reports
   the first/last missing interval?
9. What is the normative one-shot breakpoint bypass and ordering among breakpoint, BRK,
   async pause, fault, termination and step completion?
10. Are breakpoint/watch resources session-private, shareable, adopted after reconnect, or
    automatically destroyed, and how is each policy observed?
11. Which current Executive profile is the intended migration baseline, and which legacy
    degraded behaviors have explicit exit criteria?
12. How will current Python behavior be captured as conformance fixtures without freezing
    accidental masks, heuristics, timer behavior or data races?

## 13. Traceability relations

- `HSX-ST-001` preserves and classifies legacy `DR-*`, `DG-*`, `DO-*`, numbered
  architecture/design/implementation evidence and the Python oracle.
- `HSX-ST-001` **informs** `HSX-ST-002..HSX-ST-006`; those Studies own technical
  recommendations and uncertainty resolution.
- `HSX-ST-002..HSX-ST-006` informed the initial Master synthesis; review-routed
  `HSX-ST-007..HSX-ST-008` closed the remaining ABI/recipe/register and bundle/source
  subdomains for the resynthesized Requirements/Architecture/Design proposal.
- The reviewed HSX proposal will **satisfy the dependency of** `DBG-ST-006` and map to
  proposed `DBG-D-002..DBG-D-006`; it does not freeze those Debugger designs.
- `SDP/Debugger` owns controller/frontend/expression/presentation behavior; `SDP/HSX` owns
  portable runtime semantics; `SDP/AVR` owns embedded realization and constraints.
- Issues #47 and #38 remain the durable Steering coordination and acceptance gates.

## 14. Conclusions and completion limits

The legacy repository contains strong intent and a substantial Python oracle, but it does not
contain one coherent portable debugger-runtime contract. The useful provenance has now been
inventoried, classified and routed. The five numbered domain Studies have enough explicit
inputs to synthesize identity, address/ABI, execution/snapshot, event and resource contracts
without treating old DRAFT text or current implementation accidents as authority.

This Study is therefore **COMPLETE FOR PORTABLE DEBUG CONTRACT SYNTHESIS**.

Completion does **not** mean:

- broader HSX legacy migration is complete;
- any legacy DR/DG/DO has been assigned a stable modern ID;
- the descriptive contract concepts above are accepted requirements/designs;
- Python behavior is the final portable semantics;
- any `DBG-D-*` is frozen;
- any Debugger Refactor, product change, native implementation or AVR work is authorized.

At Study completion, the next valid action was Master synthesis after the bounded domain
Studies, followed by independent exact-head review and Steering packages.

## 15. Master synthesis allocation

After all domain Studies completed, Master allocated stable proposed IDs:

- `HSX-R-001..HSX-R-036`;
- `HSX-A-001..HSX-A-005`;
- `HSX-D-001..HSX-D-005`.

The contract package and `DBG-ST-006` mapping are complete. Review attempts
`HSX-RVW-001-001-001..005` required rework. Supplemental `HSX-ST-007` and `HSX-ST-008`
are complete and review-005 corrections are active. The next review is
`HSX-RVW-001-001-006`, followed by decision packages in issues #47/#38. Broader HSX
migration remains open exactly as routed above. No ID is accepted or
implementation-authoritative merely because it is stable.

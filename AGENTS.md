# HSX Agent Instructions

This repository follows the local Standard Document Procedure (SDP).
The repository documents and GitHub issue records, not chat history, are the durable source
of truth for planning, design, implementation, review, verification, and handoff.

## Mandatory Master startup reading order

Before planning or delegating work, the Master agent must read:

1. `AGENTS.md`
2. `SDP/README.md`
3. `SDP/Shared/Process.md`
4. the active track `README.md`
5. the active track `Traceability/CurrentIndex.yaml`
6. the active GitHub issue(s) named by that index or owning the current work
7. the active Study / Requirements / DesignAnalysis / Design / Feature / Refactor / Slice documents referenced by traceability

Do not begin product-code work from an issue title alone.

## Governance: Steering Group and Master agent

The project has a human-facing **Steering Group chat** that provides product/architecture
direction and resolves questions with the Codex Master agent. The Steering Group chat itself
is not durable project state.

**GitHub issues are the durable coordination interface between the Codex Master and the
Steering Group.** Important proposals, questions, decisions, scope changes, blockers,
reviews, and handoffs that require Steering Group awareness or approval must be recorded in
the relevant issue.

The expected loop is:

1. Master reads the active SDP state and issue(s).
2. Master performs/delegates bounded analysis or implementation work.
3. Master records findings, questions, proposed decisions, status, and evidence in GitHub
   issues and SDP documents.
4. Steering Group reviews or gives direction through the issue/chat workflow.
5. Master updates the durable SDP/issue state before continuing work that depends on the
   decision.

Do not rely on undocumented chat instructions when an implementation or design decision
would be difficult for a fresh agent to reconstruct.

## SDP tracks

HSX uses three independent SDP tracks under `SDP/`:

- `SDP/HSX/` — portable HSX architecture, ISA/ABI, VM, executive, toolchain, and platform-independent runtime behavior.
- `SDP/Debugger/` — debugger core, executive debug protocol, DAP adapter, CLI debugger, VS Code integration, and debugger-specific verification.
- `SDP/AVR/` — the future AVR embedded implementation of HSX and its target-specific constraints and verification.

Each track owns its own requirements, design, traceability IDs, CurrentIndex, review,
and verification. Cross-track dependencies must be explicit rather than silently
copying requirements between tracks.

## Study is first-class

A Study is a first-class SDP artifact with its own stable `*-ST-###` ID. Studies are used
whenever evidence, alternatives, unknowns, experiments, or technical questions must be
resolved before requirements/design/work scope can be trusted. Multiple numbered Studies are
normal; do not force unrelated investigations into one growing study document.

A Study may inform requirements, architecture, DesignAnalysis, a Feature, a Refactor, or a
cross-track dependency. Study conclusions are evidence; they do not silently become product
requirements until traceability records that transition.

## Agent roles

If an agent is not explicitly running as a spawned sub-agent, it is the Master agent.

The Master agent owns:

- identifying the active SDP track and reading its `Traceability/CurrentIndex.yaml`
- reading the active GitHub issue(s) used for Steering Group coordination
- maintaining requirements, design contracts, dependency ordering, traceability, and handoff
- decomposing active Feature or Refactor work into bounded slices/worker tasks
- assigning product-code changes to fresh worker agents
- assigning independent review to fresh reviewer agents
- reporting decisions, blockers, evidence, and completion state through the relevant GitHub issue
- requiring verification evidence and exact-head sign-off before declaring a refactor, feature, or slice complete
- preventing work from drifting away from the accepted requirements/design

The Master agent must not perform substantial product-code implementation directly.
Documentation-only SDP work may be performed by the Master.

Worker agents own one bounded implementation scope. A worker must be told the exact
requirements/design/Feature-or-Refactor/slice IDs, owned modules, non-goals, expected
verification, and any concurrent work it must not overwrite.

Reviewer agents are independent from the worker. They inspect the accepted contract,
changed files, regression risk, requirements coverage, and verification evidence.
Reviewers do not implement fixes unless explicitly reassigned as a worker.

## Work converges on Feature or Refactor

Product-code implementation work should normally belong to one of two durable work domains:

- **Feature (`*-FEAT-###`)** — creates or extends intended product capability from mandate,
  Study, requirements, architecture, and design.
- **Refactor (`*-RF-###`)** — remediates or restructures existing behavior/code, normally
  originating from CodeReview/GapAnalysis or an explicitly identified structural need.

Do not create implementation work that is neither owned by a Feature nor a Refactor unless
the Master records why a separate work class is necessary.

## Slices are the implementation unit

Features and Refactors are implemented through bounded **Slices (`*-SL-*`)**.

A Slice should normally be **vertical**: the smallest coherent, testable behavior that passes
through every system layer required to demonstrate useful end-to-end progress. Avoid
horizontal/file-by-file slices created only because they are convenient to assign.

A Refactor may use a slice constrained to one refactor domain or layer when the behavior,
contract, and verification boundary are genuinely contained there (for example a transport
serialization slice inside the Debugger transport Refactor). Such a slice must still produce
a coherent verified outcome and state how it connects to later vertical integration.

Each Slice has its own contract, worker, independent review, verification evidence, and
completion signal. Multiple Slices may implement one Feature or Refactor.

## CodeReview -> GapAnalysis -> Refactor rule

A CodeReview records evidence and findings. It does not directly become a large
implementation task.

1. CodeReview findings receive stable review/finding IDs.
2. GapAnalysis maps each finding to requirements and identifies the architectural or
   implementation gap.
3. Independent remediation domains become separate Refactor tracks.
4. Dependencies between Refactors are captured before implementation begins.
5. Structural Refactors require an accepted DesignAnalysis/Design contract first.
6. Each Refactor is decomposed into coherent Slices as needed.
7. Each Slice runs its own worker -> reviewer -> verification -> sign-off loop; the Refactor
   receives final sign-off only when its required Slices converge on the Refactor completion signal.

Small correctness fixes that are necessary to obtain a trustworthy baseline may run
before structural redesign, but must remain narrowly scoped and traceable.

## Anti-monolith rule

No new or redesigned module may simultaneously own unrelated concerns such as
transport framing, debugger lifecycle/state policy, resource ownership/reconciliation,
symbol interpretation, and IDE presentation.

Every structural design must state responsibilities and explicit non-responsibilities.
If an existing monolith is being replaced, compatibility behavior must be captured by
tests before responsibility is moved.

## Existing HSX build and contribution constraints

The following repository-specific guidance remains authoritative together with the SDP rules.

# AGENTS.md -- HSX Build/Contrib Guide

## Dokumenter
- `docs/hsx_spec.md` -- kjernearkitektur, ISA, SVC-moduler, mailboxes, scheduler.
- `docs/hsx_value_interface.md` -- values (f16) og commands; UART/CAN/mailbox-bindinger.
- `docs/python_version.md` -- beskriver Python-prototypen av HSX (asm, host VM, .hxe-format, testeksempler).
- `docs/ARCHITECTURE.md` -- inngangspunkt til hele doksettet (Doxygen mainpage).

## Tools
- `make`: `C:/Users/hanse/tools/make-4.4/make.exe`
- `python`: `c:/Users/hanse/miniconda3/python.exe`

## Repo-forslag
```
/hsx
  Makefile
  agents.md
  MILESTONES.md
  /docs
    Doxyfile
    Makefile
    ARCHITECTURE.md
    hsx_spec.md
    ...
  /python
    asm.py
    hsx-llc.py
    hld.py
    tests/
    toolchain_util.py
  /platforms
    /python
      host_vm.py  # hovedimplementasjon av host VM
  /examples
    /tests
      Makefile
      README.md
      build/     # gitignored
      test_vm_exit/
        main.c
      test_ir_call_phi/
        main.c
      ...
    /legacy
      README.md
      tests_flat/
      *.bat
  /tools
    pack.py
```

## Milepaler
1. **Python-prototype:** kjørbar VM (`platforms/python/host_vm.py`), assembler (`asm.py`), og testeksempler.
2. **Executive:** utvid scheduler med run-queue og blokkering på mailbox/event.
3. **Mailbox:** mod=0x5; producer/consumer-demo.
4. **Values/Commands:** mod=0x7/0x8; shell-kommandoer `val/cmd`.
5. **UART/CAN binding:** GET/SET/PUB/CALL/RET protokoll.
6. **Persist:** FRAM binding for `val.persist`.
7. **FS:** SD (PetitFatFs) + LittleFS backend, `.hxe` loader.

## Kodestil
- Python for simulering og test (første implementasjon).
- C for kjernen (avr-gcc/clang), minimal allokering; faste tabeller.
- Ingen exceptions/rtti i små C++-biter; `-fno-exceptions -fno-rtti`.
- Klare grensesnitt mellom VM/Exec/HAL/Platform.

## Test
- Python VM kjøres mot `.hxe` eksempler.
- Golden frame-dumper for CAN-binding, f16 konverteringstester.
- Stress: hundrevis av `val.set`/`GET` per sekund, rate-limits på PUB.

## Oppgaver for agenter
- Fullfør Python-prototype (`asm.py`, `platforms/python/host_vm.py`, FS/MBX/VAL/CMD`).
- Generer C-header for SVC-mod 0x5/0x7/0x8 inkl. structs.
- Implementer `exec_value.c` og `exec_cmd.c` tabeller + FRAM-persist.
- Lag `shell_val.c` og `shell_cmd.c` (UART CLI), og CAN adaptor.
- Utvid `asm.py` med `.hxe` header (`HSXE` magic) og `.val`/`.cmd` pseudoops (valgfritt).

## TODO - HSX Python-toolchain-utvidelser (Completed)
- [x] hsx-llc.py: ignore nsw/nuw/noundef/dso_local; generalize opcode parsing
- [x] hsx-llc.py: add load/store lowering
- [x] hsx-llc.py: add icmp lowering with CMP+JNZ boolean temps
- [x] hsx-llc.py: add br/call/phi handling and half precision fadd/fmul/fpext/fptrunc
- [x] hsx-llc.py: emit .extern/.import for external calls
- [x] asm.py: support .extern/.import/.text/.data and stable 16-bit offsets
- [x] host_vm.py: implement --entry-symbol/--max-steps, dev-libm, and SVC EXIT
- [x] host_vm.py: add --trace-file sink for instruction logging
- [x] asm.py/hld.py: add .hxo output and linker that writes HSXE with _start entry
- [x] Pytest: add test_crc, test_ir2asm, test_vm_exit
- [x] Pipeline: run hello.c through full toolchain to host VM [EXIT 42]

## TODO - Refactor Plan (Completed)
- [x] Flytt `host_vm.py` til `platforms/python/host_vm.py` og fjern legacy-skim i `python/`.
- [x] Scaffold top-level og `examples/tests` Makefiles med auto-discovery for `test_*`-mapper.
- [x] Gi `make venv`/`make dev-env` mål som erstatter plattformspesifikke batch-skript.
- [x] Flytt markdown inn i `docs/`, behold `README.md`/`agents.md`/`MILESTONES.md` i rot, og legg til enkel Doxygen-konfig.
- [x] Legg til `make package`/`make release` for å bygge distribuerbare arkiver.

## TODO - Future Refactor Items (Open)
- [x] Mirror hver pytest-scenario med en C-sample under `examples/tests/test_<name>/`.
- [x] Arkiver legacy batch-filer under `examples/legacy/` med README.
- [ ] Evaluer langsiktig hosting for genererte docs (commit statisk HTML vs GitHub Pages).
- [ ] Definer cache/cleanup-strategi for store toolchain-artefakter når volumet øker.
- [ ] Erstatt polling-løkken i `hsx_stdio_read` med en blokkende stdin-wrapper når full vent/vekke-støtte foreligger.

## TODO - Shell Demo & Debug Foundations (Cancelled)
> Deferred until debugger requirements are revisited. All completed tasks remain documented above.


## Implementation constraints (Codex agents)
- MiniVM remains a single-task interpreter; multitasking, scheduling, and mailbox wait/wake decisions live in the executive (`python/execd.py` on host, native firmware on hardware).
- `VMController` is the RPC façade that wraps one MiniVM instance; keep it thin and backwards compatible so shell/executive clients can attach/detach without depending on scheduler internals.

- Behold alle eksisterende CLI-flagg og imports; legg heller til nye flagg enn å endre navn.
- Ikke endre .hxe-headerformatet (HSXE magic, versjon 0x0001, 8-byte CRC).
- Legg nye opcode-utvidelser etter 0x30 i instruksjonstabellen.
- Når .extern/.import legges til, må eksisterende .mvasm fortsatt assembleres uten endringer.
- Hold `platforms/python/host_vm.py` bakoverkompatibel med eksisterende .hxe-filer og op-dekoding.
- Legg til pytest-enhetstester for nye funksjoner uten å reorganisere prosjektstrukturen.
- Dokumenter nye SVC-moduler (0x5/0x7/0x8) i HSX_SVC_API.md med Python-eksempler.
- Oppdater AGENTS.md-progressbokser etter verifiserte milepæler; ikke push andre filer samtidig.


## TODO - VM/Executive/Shell Orchestration (Active)
- [x] Implement Python executive process that maintains HSX task table and drives VM via RPC.
- [x] Add interactive TCP shell client supporting ps/exec/kill commands.
- [x] Define message protocol between shell and executive (JSON over TCP).
- [x] Support loading `.hxe` payloads through executive while VM is attached.
- [x] Provide smoke tests / scripts covering attach-run-detach workflow.
- [x] Document VM context/quantum model in hsx_spec-v2.md.
- [x] Prototype register/stack base context handling in Python MiniVM.
- [x] Extend executive scheduler to manage per-task contexts and quantum/priority policies.
- [ ] Mirror context struct and swap API in the C executive implementation.

## TODO - Mailbox & STDIO Integration (Milestone 4)
- [x] Finalize mailbox descriptor/namespace implementation for SVC 0x05 (MAILBOX_OPEN/BIND/SEND/RECV/TAP).
- [x] Publish shared C header (hsx_mailbox.h) and auto-sync constants into Python tooling/tests.
- [x] Provide HSX stdio shim mapping stdout/stderr onto svc:stdio.* mailboxes with lightweight wrappers (initial read helpers included for polling use).
- [x] Implement shell listen/send commands with optional PID filters plus pytest coverage.
- [x] Ship sample HSX apps (producer/consumer + stdout stream) demonstrating mailbox messaging.
- [x] Add integration tests covering mailbox send flows and shell listen workflows (polling + host inspection).
- [x] Mirrored mailbox/stdio samples in C with reusable wrappers (`examples/tests/test_mailbox_*_c`, `examples/tests/test_stdio_mailbox_c`).

## TODO - Milestone 4 Follow-Up
- [ ] first, check if this milestone still is valid. a lot has been done on this via bugs that surfaced during other milestones
- [ ] Expand the stdio shim with blocking stdin helpers and finalize the canonical C wrappers.
- [ ] Update consumer samples to exercise the blocking helpers once they land (replace current polling loops).
- [ ] Broaden integration coverage for mailbox back-pressure and tap tracing scenarios.

## TODO - Mailbox System Compiler Enablement (Completed)
- [x] Introduce a lightweight SSA liveness tracker in `python/hsx-llc.py` to recycle registers once values reach zero remaining uses.
- [x] Add a register allocator shim in `python/hsx-llc.py` that spills to compiler-managed stack slots and reloads on demand when the pool is exhausted.
- [x] Extend IR lowering to cover dynamic-index getelementptr, float loads/stores, %union allocas, and the other deferred patterns once allocation is stable.
- [x] Exercise spill/reload flows via `python/tests/test_host_vm_cli.py` and `python/tests/test_mailbox_manager.py`, updating `examples/tests/` inputs as needed.
- [x] After each capability lands, rerun `make -C python test` and targeted integration suites to confirm mailbox and half demos stay green.

## TODO - Mailbox update implementation (Active)
 - see mailbox_update_implementation.md for details

## TODO - hsx-llc IR Expansion (open)
- [ ] Lower integer `trunc` from i32→i16/i8 (and related paths) without dropping sign bits.
- [ ] Extend `sext`/`zext` handling for i8/i16 operands so results land in i32 registers.
- [ ] Teach dynamic-index GEP lowering to scale offsets for 2- and 4-byte element types.
- [ ] Restore pytest coverage for the new lowering (casts + GEP) once the implementation is stable.

## TODO - Calling Convention & ABI Enhancements (Open)
- [ ] first, look through the code and see what has already been implemented, and what's missing. a lot has been done on this via bugs that surfaced during other milestones
- [ ] Document the canonical HSX calling convention in `docs/hsx_spec-v2.md`, covering register roles (caller vs callee saved), argument/return placement, overflow stack layout for arguments ≥4, and the rules for aggregates/varargs.
- [ ] Extend `python/hsx-llc.py` (and the native assembler/linker) so calls with more than three arguments automatically spill overflow parameters to the caller stack frame using 4-byte slots and generate callee-side loads/stores that honour the spec.
- [ ] Update assembly shims (`examples/lib/hsx_stdio.mvasm`, `examples/lib/hsx_mailbox.mvasm`, etc.) and runtime helpers so they read overflow arguments from the stack, preserve callee-saved registers, and expose helper macros for hand-written MVASM.
- [ ] Add regression samples/tests (C + MVASM) that exercise four-plus argument calls, mixed-width arguments, and varargs stubs to verify round-tripping through the VM and executive.

## TODO - Mailbox Fan-Out Follow-Up (Open)
- [ ] first, look through the code and see what has already been implemented, and what's missing. a lot has been done on this via bugs that surfaced during other milestones
- [x] Prototype fan-out sequence tracking and retention policies in the Python mailbox manager with pytest coverage.
- [x] Extend shell listen/send tooling to expose fan-out policy selection for stdio channels.
- [ ] Update docs/hsx_spec.md and HSX_SVC_API references once behavior is validated.



## TODO - Clock step semantics & docs (Completed)

- [x] Verified the scheduler now retires exactly one guest instruction per round-robin turn (`platforms/python/host_vm.py::MiniVM.step`, `VMController.step`, `python/tests/test_vm_pause.py::test_round_robin_single_instruction`).
- [x] Confirmed RPC/shell plumbing accepts `clock step <N>` and `clock step <N> -p <pid>` with instruction counts only (no remaining `cycles` fields anywhere critical).
- [x] Update operator help (`help/clock.txt`, `help/step.txt`) to describe the step-only model and document `-p/--pid`.
- [x] Refresh protocol/docs (`docs/executive_protocol.md`) and client shims (`python/blinkenlights.py`, `python/exec_smoke.py`, `python/executive.py`, `python/vmclient.py`) to stop emitting `cycles` payloads and to mention per-instruction semantics.
- [x] Smoke the GUI/CLI tooling once the docs/help updates land to ensure mixed PID/manual stepping behaves as expected (<3).

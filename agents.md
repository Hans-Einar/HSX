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

## TODO - Mailbox System Compiler Enablement (Active)
- [x] Introduce a lightweight SSA liveness tracker in `python/hsx-llc.py` to recycle registers once values reach zero remaining uses.
- [x] Add a register allocator shim in `python/hsx-llc.py` that spills to compiler-managed stack slots and reloads on demand when the pool is exhausted.
- [x] Extend IR lowering to cover dynamic-index getelementptr, float loads/stores, %union allocas, and the other deferred patterns once allocation is stable.
- [x] Exercise spill/reload flows via `python/tests/test_host_vm_cli.py` and `python/tests/test_mailbox_manager.py`, updating `examples/tests/` inputs as needed.
- [x] After each capability lands, rerun `make -C python test` and targeted integration suites to confirm mailbox and half demos stay green.

## TODO - Mailbox Fan-Out Follow-Up (Open)
- [x] Prototype fan-out sequence tracking and retention policies in the Python mailbox manager with pytest coverage.
- [x] Extend shell listen/send tooling to expose fan-out policy selection for stdio channels.
- [ ] Update docs/hsx_spec.md and HSX_SVC_API references once behavior is validated.

<3




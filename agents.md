# AGENTS.md -- HSX Build/Contrib Guide

## Dokumenter
- `docs/hsx_spec.md` -- kjernearkitektur, ISA, SVC-moduler, mailboxes, scheduler.
- `docs/hsx_value_interface.md` -- values (f16) og commands; UART/CAN/mailbox-bindinger.
- `docs/python_version.md` -- beskriver Python-prototypen av HSX (asm, host VM, .hxe-format, testeksempler).
- `docs/ARCHITECTURE.md` -- inngangspunkt til hele doksettet (Doxygen mainpage).

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

## Implementation constraints (Codex agents)
- Behold alle eksisterende CLI-flagg og imports; legg heller til nye flagg enn å endre navn.
- Ikke endre .hxe-headerformatet (HSXE magic, versjon 0x0001, 8-byte CRC).
- Legg nye opcode-utvidelser etter 0x30 i instruksjonstabellen.
- Når .extern/.import legges til, må eksisterende .mvasm fortsatt assembleres uten endringer.
- Hold `platforms/python/host_vm.py` bakoverkompatibel med eksisterende .hxe-filer og op-dekoding.
- Legg til pytest-enhetstester for nye funksjoner uten å reorganisere prosjektstrukturen.
- Dokumenter nye SVC-moduler (0x5/0x7/0x8) i HSX_SVC_API.md med Python-eksempler.
- Oppdater AGENTS.md-progressbokser etter verifiserte milepæler; ikke push andre filer samtidig.

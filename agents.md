# AGENTS.md -- HSX Build/Contrib Guide

## Dokumenter
- `HSX_SPEC.md` -- kjernearkitektur, ISA, SVC-moduler, mailboxes, scheduler.
- `HSX_VALUE_INTERFACE.md` -- values (f16) og commands; UART/CAN/mailbox-bindinger.
- `python_version.md` -- beskriver Python-prototypen av HSX (asm, host_vm, .hxe-format, testeksempler).

## Repo-forslag
```
/hsx
  HSX_SPEC.md
  HSX_VALUE_INTERFACE.md
  python_version.md
  AGENTS.md
  /python
    asm.py
    host_vm.py
    sampleprog.mvasm
    sample2.mvasm
  /src
    /vm         # bytekodedekoder, tolk, f16-ops
    /exec       # scheduler, mailbox, events, value/cmd registries
    /hal        # uart, can, spi, i2c, fs, gpio, pwm, adc, dac
    /platform   # avr/stm/esp drivere (spi-dma, can, timers, fram/nor)
  /tools
    pack.py     # pakker .hxe (header+crc)
  /examples
    sample_uart.hxe
    sample_can.hxe
    sample_values.hxe
```

## Milepaler
1. **Python-prototype:** kjorbar VM (`host_vm.py`), assembler (`asm.py`), og testeksempler.
2. **Executive:** utvid scheduler med run-queue og blokkering paa mailbox/event.
3. **Mailbox:** mod=0x5; producer/consumer-demo.
4. **Values/Commands:** mod=0x7/0x8; shell-kommandoer `val/cmd`.
5. **UART/CAN binding:** GET/SET/PUB/CALL/RET protokoll.
6. **Persist:** FRAM binding for `val.persist`.
7. **FS:** SD (PetitFatFs) + LittleFS backend, `.hxe` loader.

## Kodestil
- Python for simulering og test (forste implementasjon).
- C for kjernen (avr-gcc/clang), minimal allokering; faste tabeller.
- Ingen exceptions/rtti i sma C++-biter; `-fno-exceptions -fno-rtti`.
- Klare grensesnitt mellom VM/Exec/HAL/Platform.

## Test
- Python VM kjoeres mot `.hxe` eksempler.
- Golden frame-dumper for CAN-binding, f16 konverteringstester.
- Stress: hundrevis av `val.set`/`GET` per sekund, rate-limits paa PUB.

## Oppgaver for agenter
- Fullfoer Python-prototype (`asm.py`, `host_vm.py`, FS/MBX/VAL/CMD`).
- Generer C-header for SVC-mod 0x5/0x7/0x8 inkl. structs.
- Implementer `exec_value.c` og `exec_cmd.c` tabeller + FRAM-persist.
- Lag `shell_val.c` og `shell_cmd.c` (UART CLI), og CAN adaptor.
- Utvid `asm.py` med `.hxe` header (`HSXE` magic) og `.val`/`.cmd` pseudoops (valgfritt).

## TODO - HSX Python-toolchain-utvidelser
- [x] hsx-llc.py: ignore nsw/nuw/noundef/dso_local; generalize opcode parsing
- [x] hsx-llc.py: add load/store lowering
- [x] hsx-llc.py: add icmp lowering with CMP+JNZ boolean temps
- [x] hsx-llc.py: add br/call/phi handling and half precision fadd/fmul/fpext/fptrunc
- [x] hsx-llc.py: emit .extern/.import for external calls
- [x] asm.py: support .extern/.import/.text/.data and stable 16-bit offsets
- [x] host_vm.py: implement --entry-symbol/--max-steps, dev-libm, and SVC EXIT
- [x] host_vm.py: add --trace-file sink for instruction logging
- [x] asm.py/hld.py: add .hxo output and linker that writes HSXE with _start entry
- [ ] Pytest: add test_crc, test_ir2asm, test_vm_exit
- [x] Pipeline: run hello.c through full toolchain to host VM [EXIT 42]

## Implementation constraints (Codex agents)
- Behold alle eksisterende CLI-flagg og imports; legg heller til nye flagg enn aa endre navn.
- Ikke endre .hxe-headerformatet (HSXE magic, versjon 0x0001, 8-byte CRC).
- Legg nye opcode-utvidelser etter 0x30 i instruksjonstabellen.
- Naar .extern/.import legges til, maa eksisterende .mvasm fortsatt assembleres uten endringer.
- Hold host_vm.py bakoverkompatibel med eksisterende .hxe-filer og op-dekoding.
- Legg til pytest-enhetstester for nye funksjoner uten aa reorganisere prosjektstrukturen.
- Dokumenter nye SVC-moduler (0x5/0x7/0x8) i HSX_SVC_API.md med Python-eksempler.
- Oppdater AGENTS.md-progressbokser etter verifiserte milepeler; ikke push andre filer samtidig.

# HSX Python Version

## Formål
Python-versjonen av HSX fungerer som en **referanseimplementasjon** og **testplattform** for utvikling av ISA, SVC, og Executive-funksjonalitet før portering til C for AVR/STM.

Den gjør det mulig å:
- Eksperimentere med instruksjonssettet og filformatet (.hxe)
- Teste SVC-moduler (UART, CAN, FS, Mailbox, Value)
- Verifisere logikk for eventer, context switching og f16-operasjoner
- Kjøre reelle testprogrammer (assemblerte .hxe-filer) direkte på PC

---

## Filstruktur
```
/python
  asm.py          # Assembler: fra .mvasm → .hxe (tidl. .exe)
  host_vm.py      # Vertstolk (simulert CPU/HSX Executive)
  sampleprog.mvasm  # Eksempel 1: UART/CAN
  sample2.mvasm     # Eksempel 2: FS + f16
  sample2b.mvasm    # Planlagt: enklere f16/FS test
```

---

## Hovedkomponenter

### 1. `asm.py`
Assembler for HSX ISA. Parserer mnemonics som:
```
LDI R1, 42
SVC 0x100
```
...og skriver ut et binært **.hxe**-program (tidligere .exe).

**.hxe-headerformat:**
| Felt | Beskrivelse |
|------|--------------|
| Magic | `HSXE` (0x48535845) |
| Version | 0x0001 |
| Entry | Startadresse |
| Code_len | Lengde på bytekode |
| RO_len, BSS, Caps, CRC | Metadata |

Assembleren håndterer nå:
- `LDI, MOV, ADD, SUB, CALL, RET`
- `LDB/LDH/STB/STH` (byte/half ops)
- `FADD, FSUB, FMUL, FDIV, I2F, F2I` (f16)
- `SVC mod,fn` (system calls)

### 2. `host_vm.py`
En Python-basert VM som:
- Leser .hxe-filer (tidl. .exe)
- Dekoder og utfører instruksjoner
- Holder `regs[16]` og `mem[64KB]`
- Simulerer SVC-moduler:
  - UART (`mod=0x1`): print til stdout
  - CAN  (`mod=0x2`): log til skjerm
  - FS   (`mod=0x4`): enkel RAM-basert filsystem
  - MBX  (`mod=0x5`): stub (planlagt utvidet)

Støtter også preloading av data til minne (f.eks. filnavn eller inputstrings), slik at HSX-programmet kan utføre I/O kall uten ekte hardware.

---

## Eksempler

### `sampleprog.mvasm`
Demonstrerer UART og CAN utskrift:
```asm
LDI  R1, str_hello
LDI  R2, 13
SVC  0x100     ; uart.tx(ptr,len)
SVC  0x200     ; can.tx(ptr,len)
HALT
```
Kompiler og kjør:
```bash
python3 asm.py sampleprog.mvasm -o sampleprog.hxe
python3 host_vm.py sampleprog.hxe
```

Output:
```
[UART] Hello HSX!
[CAN]  Hello HSX!
```

### `sample2.mvasm`
Tester FS-systemet:
```asm
LDI R1, path_hello
LDI R2, 0
SVC 0x400       ; FS.open
MOV R4, R0      ; fd
MOV R1, R4
LDI R2, buf
LDI R3, 32
SVC 0x401       ; FS.read
MOV R1, R2
MOV R2, R0
SVC 0x100       ; uart.tx
HALT
```
Resultat: `Hi from FS!` vises i konsollen.

---

## Planlagte utvidelser
- Implementere `mod=0x5` Mailbox med FIFO-buffer.
- Scheduler (round-robin) og event-masker.
- FS backend som leser faktiske filer fra /tmp/hsxfs.
- f16-konvertering via IEEE754-pakkede funksjoner.
- Testing av `VAL` og `CMD` SVC (mod=0x7/0x8).

---

## Filformat-endring
Tidligere brukte Python-prototypen `.exe`. Dette erstattes nå av **`.hxe`** for å matche HSX-spesifikasjonen.

**Endringer som må gjøres i kildekode:**
- `asm.py`: bytt filendelse i argumentparser.
- `host_vm.py`: oppdater `magic` til `HSXE` (0x48535845).
- Oppdater alle referanser i examples, tools og AGENTS.md.

---

## Testing og bruk
1. Rediger eller lag nye `.mvasm`-filer.
2. Kjør assembleren for å generere `.hxe`.
3. Kjør `host_vm.py` for å simulere.
4. Overvåk output på stdout (UART/CAN) og logg eventuelle FS/Mailbox-operasjoner.

Dette danner grunnlaget for videre utvidelse til **HSX Executive Simulator**, hvor flere tasks, events og f16-values samhandler.


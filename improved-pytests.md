# HSX – Improved PyTests Plan (v1.1)

**Mål:** Øke robusthet og dekningsgrad for HSX toolchain/VM ved å legge til målrettede pytest‑caser som avdekker feil i
- assembler/linker (relok, symboler, endianness),
- HXE‑container (header/CRC/områdesjekk),
- SVC/FS/STDIO/IPC‑mailboxes,
- CALL/RET og minnegrenser,
- FP16‑hjørnetilfeller,
- registerallokering/peephole,
- branch‑flagg‑livstid.

Hver seksjon under har **hva** vi ønsker å sikre + **TODO‑liste** med konkrete testfiler/asserter Codex kan implementere. Hold testene korte, deterministiske og med tydelige “acceptance criteria”.

---

## 1) Assembler – lokal relok‑oppløsning (image‑mode)

**Mål:** I `assemble()` for endelig bilde skal **alle intra‑unit** symbolreferanser patches; `relocs == []` (kun `.hxo` beholder reloks).

**TODO**
- Opprett `python/tests/test_asm_local_relocs.py` med én kilde som inneholder:
  ```asm
  .data
  msg:    .asciz "hi"
  table:  .word msg
  .text
  .entry start
  start:
      LDI32 R1, msg
      CALL foo
      JMP start
  foo:  RET
  ```
- Kall assembler (`assemble_source(...)`) → `assert relocs == []`.
- Verifiser at `table` faktisk inneholder **absolutt adresse** til `msg` (ikke reloc).

**Impl‑hint:** Kjør `resolve_local_relocs()` i image‑modus; bygg symboltabell med absolutte adresser for `.text`, `.data`, `.rodata`.

---

## 2) Patching av immediater pr. instruksjonstype

**Mål:** Korrekt bredde/endianness og range‑sjekk ved patch av `LDI`, `LDI32`, `Jxx`, `CALL`.

**TODO**
- `python/tests/test_reloc_patch_unit.py`: manuelle cases for hver instruksjonstype; `assert` på binærordet etter patch.
- (Valgfritt) `python/tests/test_reloc_patch_property.py` (Hypothesis): generér små programmer med 10–50 labels/hopp; verifiser at utføring lander på riktig adresse etter patch.

---

## 3) Linker – dupliserte symboler

**Mål:** To objekter som eksporterer samme symbol → **feil** med tydelig melding.

**TODO**
- `python/tests/test_linker_dupdef.py`: lag to `.hxo` med `.export foo` i begge; link → forvent `LinkError`/klar feilmelding.

---

## 4) HXE‑container – header/CRC/område

**Mål:** Loader avviser skadde bilder kontrollert; korrekt CRC/områdesjekk/entry‑range.

**TODO**
- `python/tests/test_hxe_fuzz.py`:
  - Bygg gyldig `.hxe`, så mutér felter (sizes, entry, CRC, offsets) i ~50 iterasjoner.
  - Forvent “nice failure” (errno/exception med melding), aldri crash.
- Særskilt: verifiser
  - `entry` ∈ `[code_base, code_base+code_size)`
  - offsets er 4‑alignet
  - ingen seksjonsoverlapp
  - rimelige øvre grenser for størrelser (fail hvis overskrides)

---

## 5) SVC‑dispatch – invalid mod/fn

**Mål:** Ugyldige SVCer returnerer definert errno (f.eks. ENOSYS) og påvirker ikke VM‑tilstand.

**TODO**
- `python/tests/test_svc_invalid.py`: program som gjør `SVC 0xFF, 0xFF` én gang; `assert errno == ENOSYS` (eller valgt kode).

---

## 6) FS‑sandbox

**Mål:** Hindre path‑traversal og absolutte paths i host‑FS backend.

**TODO**
- `python/tests/test_fs_sandbox.py`:
  - `open("../../etc/passwd")` → errno (EPERM/EINVAL).
  - På Windows: `open("C:\\windows\\system32")` → errno.
- Dokumentér i SYSCALLS.md policy for base‑dir og path‑normalisering.

---

## 7) STDIO‑bro (FD→mailbox) – edge cases

**Mål:** Skriving til `fd=1/2` sender meldinger som Python‑siden kan lese via `text`‑feltet; `len=0` er no‑op.

**TODO**
- `python/tests/test_stdio_edgecases.py`:
  - `puts("")` → ingen meldinger, ingen crash.
  - `write(fd=1, "abc\0def", 7)` → valider policy (3 vs 7 bytes). Oppdater test etter valgt semantikk.
- Sørg for at payload inkluderer feltet **`text`** i mailbox‑meldingen.

---

## 8) Mailbox – navnerom & globalitet

**Mål:** `app:*` er globalt; `svc:stdio.*@pid` er per‑prosess. Lazy create fungerer for `app:*`.

**TODO**
- `python/tests/test_mailbox_namespace.py`:
  - Prosess A: send til `app:foo`.
  - Host: `open("app:foo")` og `recv` → mottar melding.
  - `svc:stdio.out@pidA` er **ikke** åpenbar uten `@pidA`.

---

## 9) CALL/RET – kanttilfeller

**Mål:** Underflow/overflow av stakk fanges; RET uten CALL trapper kontrollert.

**TODO**
- `python/tests/test_vm_callret_edges.py`:
  - Program med `RET` først → trap/errno.
  - Dyp rekursjon > stakkgrense → trap (ikke host‑crash).

---

## 10) FP16 – hjørnetilfeller

**Mål:** Definert semantikk for `F2I`, `+/-0`, NaN/Inf/subnormals. Dev‑libm halv‑retur maskes til 16‑bit.

**TODO**
- `python/tests/test_ir_f16_edges.py`:
  - Caser: `+0.0`, `-0.0`, `NaN`, `+Inf`, `-Inf`, `65504`, min‑subnormal.
  - For `F2I`: dokumentér og test “truncate mot 0” (eller valgt variant).

---

## 11) LD/ST – unaligned & endianness

**Mål:** VM er **little‑endian**; misalignment enten støttes eller avvises konsistent.

**TODO**
- `python/tests/test_mem_alignment.py`:
  - Skriv/les `i32` og `half` på adresser `base+1`/`base+2` og verifiser valgt oppførsel (eller errno).
- Oppdater spes i `hsx_spec*.md` for endelig policy.

---

## 12) `.half` direktiv – rå bits vs FP16

**Mål:** Unngå tvetydighet; `.half` bør være **rå 16‑bit** (ikke automatisk float‑konvertering).

**TODO**
- `python/tests/test_data_half_bits.py`: `.half 0x3C00` i `.data`, les bits → forvent identisk 0x3C00.
- Dokumentér tolkning i MVASM_SPEC.md/hsx_spec*.md.

---

## 13) ABI – arity/varargs

**Mål:** >3 argumenter avvises eksplisitt (inntil støtte finnes).

**TODO**
- `python/tests/test_call_arity.py`:
  - Kall med 4 arg via IR/asm → feilmelding i kompilering/assembler (klare ord).

---

## 14) Peephole – ekstra optimaliseringer

**Mål:** Redusér støy; eliminer trivielle MOV/LDI‑kjeder.

**TODO**
- `python/tests/test_opt_peephole_extra.py`:
  - Fjern `MOV Rx,Rx`.
  - Fold `LDI R12,imm; MOV R5,R12` ⇒ `LDI R5,imm` (og tilsvarende for `LDI32`).
- Kjør sammen med eksisterende `test_opt_movs.py`.

---

## 15) Branch‑flagg – levetid

**Mål:** Ingen instruksjon mellom `CMP` og `Jcc` som clobber flags. (Definér flagg‑regler i ISA‑spes.)

**TODO**
- `python/tests/test_branch_flag_lifetime.py`:
  - Generér sekvens med `CMP`, deretter `MOV/LDI`, så `JZ`. Forvent at senkeren unngår slik sekvens, eller at VM bevarer flags. Avklar én av to strategier og test den.

---

## 16) Minnegrenser (OOB)

**Mål:** Håndter last/store utenfor minne uten host‑crash.

**TODO**
- `python/tests/test_vm_mem_oob.py`:
  - `LD R1, [R2+big]` der `R2+big` er utenfor allokert RAM → errno/trap.

---

## 17) (Valgfritt) Property‑baserte assembler‑tester

**Mål:** Fange uventede hjørner ved patch av mange labels/hopp.

**TODO**
- Hypothesis‑drevet generering av små `.mvasm` med label‑topologi; sammenlign oppslåtte adresser mot interpretert PC‑flyt.

---

## Implementasjonsrekkefølge (anbefalt)

1. **#1** lokal relok‑verifikasjon (sikrer invarianten vi nylig innførte).  
2. **#4** HXE header/CRC fuzz (hardener containeren).  
3. **#5–#8** SVC/FS/STDIO/IPC robusthet.  
4. **#9–#12** CALL/RET kanter, FP16, minnejustering, `.half` bits.  
5. **#13–#16** ABI/peephole/flags/OOB.  
6. **#17** Property‑tester (om ønskelig).

---

## Akseptansekriterier (overordnet)

- Nye tester passerer deterministisk på CI.  
- Ingen test “passerer ved crash”: all feil er kontrollert (errno/exception).  
- `.hxe` i testene har **tom reloktabell** (alle lokale reloks oppløst) og gyldig header/CRC.  
- SYSCALLS.md/hsx_spec*.md oppdateres når nye errno/semantikker introduseres.

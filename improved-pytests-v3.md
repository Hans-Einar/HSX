# HSX – Improved PyTests (v3, add‑ons beyond current 83/83)

**Status:** 83/83 grønt. Denne planen foreslår *ekstra* tester som kompletterer dagens dekning.
Hver blokk: **Mål** + **TODO** (filnavn/asserter) + (ev. impl‑hint).

---

## 1) IR‑lowering utvidelser (GEP, casts, (s|z)ext/trunc)

**Mål:** Dekke dynamiske pekerberegninger og integer‑konverteringer uten UB.
**TODO**
- `python/tests/test_ir_gep_dynamic.py`
  - GEP med runtime‑index (`i32`), både positive/negative, over `i8/i16/i32` arrays i `.data`.
  - Assert korrekt lastet/stored verdi for flere indeks‑kombinasjoner.
- `python/tests/test_ir_casts_intptr.py`
  - Happy‑path: `ptrtoint`/`inttoptr` på egne adresser, *avvis* blandede typer (f.eks. `half* → i32*`).
  - BITCAST mellom `i32*` og `ptr` der representasjon er lik → OK.
- `python/tests/test_ir_sext_zext_trunc.py`
  - `sext i8/i16→i32`, `zext i8/i16→i32`, `trunc i32→i16/i8`; test kantverdier `0x7F/0x80`, `0x7FFF/0x8000`.

(Impl‑hint: konsolider maskering/signbit‑håndtering i `hsx-llc`.)

---

## 2) Assembler/Linker strengere feiler

**Mål:** Ryddige feilmeldinger for vanlige brukerfeil.
**TODO**
- `python/tests/test_asm_duplicate_label.py`
  - Samme label definert to ganger i `.text` → assemblerfeil.
- `python/tests/test_linker_missing_entry.py`
  - Link `.hxo` uten `.entry`/mangler `_start` ved `--entry-symbol` → tydelig feil.
- `python/tests/test_branch_range.py`
  - Kunstig stort program (stor `.rodata`) → `J*`/`CALL` utenfor rekkevidde → `RelocRangeError` (eller tilsvarende).

---

## 3) HXE‑container: struktur‑validering (utover header/CRC)

**Mål:** Ikke stol på innhold/feltordning.
**TODO**
- `python/tests/test_hxe_section_order_overlap.py`
  - Bytt rekkefølge på seksjons‑offsets → loader avviser.
  - Overlappende seksjoner (code/data) → avvis.
  - Offsets ikke 4‑alignet → avvis.
- `python/tests/test_import_unresolved.py`
  - Importtabell som refererer til symbol uten stub etter link → loader/linker feiler.

---

## 4) SVC/FS semantikk (ikke bare sandbox)

**Mål:** Konsistent errno ved normal feil.
**TODO**
- `python/tests/test_fs_semantics.py`
  - `open("no_such_file")` → `ENOENT`.
  - `open("file", O_RDONLY)` + `write()` → `EBADF`/`EACCES` (velg én og dokumentér).
  - `seek` langt forbi EOF + `read` → `0` bytes; `write` ekspanderer fil (eller avvis) – lås policy og test.

---

## 5) Mailbox livssyklus (handles & prosessdød)

**Mål:** Ingen ghost‑handles; ryddig opprydding.
**TODO**
- `python/tests/test_mailbox_lifecycle.py`
  - `send`/`recv` på **lukket** handle → `EBADF`.
  - Kill/exit prosess → stdio‑mailboxes frigjøres; `open("svc:stdio.out@pid")` feiler.
  - `app:*` meldinger kan fortsatt sendes/leses av host (globalt navn).

---

## 6) FP16 avrunding og flags

**Mål:** Avrunding definert, flags ikke misbrukt.
**TODO**
- `python/tests/test_ir_f16_rounding.py`
  - Gullvektorer for `FADD/FMUL/FDIV` med ties‑to‑even; sammenlign bitmønster (16‑bit).
- `python/tests/test_ir_cmp_after_fp.py`
  - Sikre at lowering alltid bruker `CMP` før `J*` (aldri avhenger av FP‑instruks flags).
  - Parse generert `.mvasm` og assert at `J*` etter `icmp` har `CMP` rett før (kun labels/kommentarer imellom).

---

## 7) Peephole – ekstra mønstre

**Mål:** Mindre støy i hot‑paths.
**TODO**
- `python/tests/test_opt_patterns_more.py`
  - `LDI Rk, 0; ADD Rd, Rs, Rk` ⇒ `MOV Rd, Rs`.
  - `MOV Rx,Ry; MOV Ry,Rx` uten mellomliggende bruk ⇒ vurder optimalisering eller dokumentér hvorfor ikke.

---

## 8) Dev‑libm utvidelse (hvis brukt)

**Mål:** Ensartet FP16‑retur i dev‑modus.
**TODO**
- `python/tests/test_vm_devlibm_extra.py`
  - `cos/exp` (om implementert) → retur maskes til 16‑bit, samme NaN‑policy som `sin`.

---

## 9) “Don’t write rodata” (valgfri, hvis dere ønsker RW‑vern)

**Mål:** Catch tidlige logiske feil.
**TODO**
- `python/tests/test_mem_ro_protection.py`
  - `ST*` inn i `.rodata`‑adresse → EPERM (eller tillat og dokumentér).

---

## 10) Property‑tester (Hypothesis) – kontrollflyt

**Mål:** Ingen stakklekasje/PC‑feil ved vilkårlig grenstruktur.
**TODO**
- `python/tests/test_prop_cfg_random.py`
  - Generér små CFG’er med `CALL/RET/J*`; kjør N steg; forvent ingen unntak, og at antall `CALL` minus `RET` aldri blir negativt.

---

## 11) CI & Dekning (pipeline)

**Mål:** Hindre regresjoner på tvers av plattformer.
**TODO**
- GitHub Actions workflow:
  - Matrix: {Windows, Ubuntu} × {Python 3.9, 3.11}.
  - Kjør `pytest -q`, og `coverage run -m pytest` → `coverage report -m`; sett terskel (f.eks. 85%) for `python/host_vm.py` og `python/hsx-llc.py`.

---

## Prioritet (foreslått rekkefølge)

1) §1 (GEP/casts/ext/trunc), §2 (ASM/LINK feilmeldinger)  
2) §3 (HXE struktur), §4 (FS‑semantikk)  
3) §5 (mailbox livssyklus), §6 (FP16 avrunding/flags)  
4) §7 (§8 valgfritt), §9 valgfri RO‑policy, §10 property  
5) §11 CI/dekning

**Akseptkriterier:** Nye tester er deterministiske; `.hxe` i testene har tom reloktabell; feiler gir kontrollert errno/exception; spes/MD‑filer oppdateres ved nye policies.

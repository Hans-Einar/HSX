# HSX_VALUE_INTERFACE.md — Values (f16) & Commands

**Formål:** Standard måte for tasks i HSX å eksponere **verdier** (f16) og **kommandoer** (call) med ensartet API over VM/SVC, mailbox, UART-shell og CAN.

> Grunntype: `hsx_value_t = f16` (IEEE754 half). Verdier er alltid f16 *på grensen* (over SVC/IPC/wire). Internt kan task bruke hvilken som helst presisjon, men konverterer ved registrert grenseflate.

---

## 1. Objektmodell

| Element | Beskrivelse |
|---|---|
| **Namespace** | Kort streng (max 12), f.eks. `motor`, `temp`, `sys`. |
| **Key** | Kort nøkkel (max 12), f.eks. `rpm`, `target`, `state`. |
| **OID** | 16-bit identifikator allokert av executive (`oid = ns_id<<8 | key_id`). |
| **Value (f16)** | Les-/skrivbar sanntidsverdi. |
| **Command** | Kallbar funksjon med 0..N f16-argumenter, f16-retur. |
| **Meta** | Range (`min/max` f16), `unit` (4-char), `flags` (RO/RW/Sticky/Persist). |

> Navn → `ns:key` (eks. `motor:rpm`). Executive gir `ns_id`/`key_id` når task registrerer første gang. OID er stabil mens task kjører.

---

## 2. SVC-API (VAL: mod=0x7)

**Register / list / get / set / subscribe**

| fn | Prototype (regs) | Retur i `R0` | Notat |
|---:|---|---|---|
| 0 | `val.register(ns*, key*, flags, min_f16, max_f16, unit4)` | `oid` | Oppretter/oppdaterer value. |
| 1 | `val.lookup(ns*, key*)` | `oid or -1` | Finn eksisterende uten å lage. |
| 2 | `val.get(oid)` | `f16` | Leser gjeldende verdi. |
| 3 | `val.set(oid, f16)` | `0/errno` | Skriver verdi. |
| 4 | `val.list(ns*, out_ptr, max_items)` | `count` | Fyller tabell av `(oid,f16)` par. |
| 5 | `val.meta(oid, out_ptr)` | `0/errno` | Skriver meta‐struct. |
| 6 | `val.sub(oid, mbx_name*)` | `0/errno` | Push onChange til mailbox (edge/coalesce). |
| 7 | `val.persist(oid, mode)` | `0/errno` | Knytter til FRAM-nøkkel (auto-load/save). |

**ABI (regs):**
- Inndata: `R1..R3` + pekere til strukturer i task-RAM.
- f16 i low 16 bits. Enkeltfelt like `flags`, `unit4` i `R2`/`R3`.

**Meta-struct (layout i task-RAM):**
```
struct hsx_val_meta {
  uint16_t flags;     // bit0:RO, bit1:Persist, bit2:Sticky
  uint16_t unit;      // 4-char unit packes f.eks. "C  "
  uint16_t f16_min;
  uint16_t f16_max;
  uint16_t f16_last;  // siste publiserte verdi
};
```

---

## 3. SVC-API (CMD: mod=0x8)

**Registrer kommando, kall synkront/asykront**

| fn | Prototype (regs) | Retur `R0` | Notat |
|---:|---|---|---|
| 0 | `cmd.register(ns*, key*, argc, flags)` | `oid` | Kommandodefinisjon. |
| 1 | `cmd.lookup(ns*, key*)` | `oid/-1` | Finn eksisterende. |
| 2 | `cmd.call(oid, argv_ptr, argc)` | `f16 or 0/errno` | Synkront kall; retur f16. |
| 3 | `cmd.call_async(oid, argv_ptr, argc, mbx*)` | `0/errno` | Svar meldes som `(oid,f16,rc)` på mailbox. |
| 4 | `cmd.help(oid, out_ptr)` | `0/errno` | Returnerer kort signatur/tekst. |

**Argblokk:** `argv_ptr` peker til en tabell av `uint16_t f16_args[argc]` i task-RAM.

---

## 4. UART Shell binding

**Lister, get/set, call**

```
> val ls motor
motor:rpm=  1250.0 rpm
motor:target= 1400.0 rpm (RW)

> val get motor:rpm
1250.0

> val set motor:target 1500
OK

> cmd ls motor
motor:cal (argc=2)

> cmd call motor:cal  1.0  0.2
OK  (ret=0.0)
```

- Parser konverterer desimaltall ↔ f16.
- `val sub` kan kobles til shell for live‐stream: `val watch motor:rpm` (oppdatering via mailbox → UART print).

---

## 5. CAN binding (11-bit ID, 8-byte payload)

**Enkel, kompakt mapping for f16‐verdier og kommandoer.**

- **CAN-ID:** `base | (topic<<3) | op`  
  `base`: node‐prefix, `topic`: 8-bit (`ns:key` komprimert til `oid`), `op`: 3-bit (`GET=0, SET=1, PUB=2, CALL=3, RET=4`).
- **Payload (SET/GET/RET/PUB):**
  - Byte0..1: `oid`
  - Byte2..3: `f16` (verdi / retur)
  - Byte4..7: opsjonelt: sequence, errno, ekstra f16 for `CALL` (enkeltargument‐variant)  

**Strøm:**
- Ekstern noden sender `GET(oid)` → HSX svarer `RET(oid, f16)`
- Ekstern noden sender `SET(oid, f16)` → HSX kvitterer `RET(oid, rc)`
- Task publiserer endringer via `PUB(oid, f16)` (on change / rate limit).
- Kommandokall (`CALL`) leverer valgfritt første argument i Byte4..5 (f16). For flere argumenter bruk mailbox/fragmentering eller UART.

> Måltall: 1 verdi = 2 byte f16 + 2 byte oid ⇒ svært kompakt på CAN.

---

## 6. Mailbox integrasjon

- `val.sub(oid, "mbx")` abonnerer på endringshendelser: Executive sammenligner f16 mot `f16_last` (m/ hysterese/epsilon) og poster `(oid, f16)` på mailbox.
- Kommandoer med `call_async` svarer på mailbox `(oid, ret_f16, rc)`.

**Meldingsformat (bytes):**
```
VAL_PUB:  [type=0x01, oid(2), f16(2)]
CMD_RET:  [type=0x02, oid(2), f16(2), rc(1)]
```

---

## 7. Persistens (FRAM)

- `val.persist(oid, mode)` binder verdi til FRAM‐nøkkel: `ns_id:key_id`.
- Executive laster ved task‐start og lagrer ved `set()`/shutdown.

**Mode:** `0=volatile`, `1=load`, `2=load+save`.

---

## 8. Eksempelkode (assembly)

### 8.1 Registrere og publisere en verdi
```asm
; Register motor:rpm   unit "RPM ", [0..10000], RW
LDI   R1, ns_motor    ; "motor\0"
LDI   R2, key_rpm     ; "rpm\0"
LDI   R3, 0x0002      ; flags: RW
LDI   R4, F16(0.0)
LDI   R5, F16(10000.0)
LDI   R6, 'RPM '      ; 4-char pack
SVC   0x700           ; val.register -> R0=oid
MOV   R8, R0

; ... oppdater løpende
; måling i R9 (i32), konverter og publiser hvis endret
I2F   R10, R9
SVC   0x702           ; val.set(oid=R8, f16=R10.low16)
```

### 8.2 Kommando med to argumenter
```asm
; Definer motor:cal (argc=2)
LDI   R1, ns_motor
LDI   R2, key_cal
LDI   R3, 2          ; argc
LDI   R4, 0          ; flags
SVC   0x800          ; cmd.register -> R0=oid
MOV   R11, R0

; Kalles synkront fra shell/CAN:
; host fyller argv[0..1] f16 i RAM og peker i R2
LDI   R1, R11
LDI   R2, argv_ptr
LDI   R3, 2
SVC   0x802          ; cmd.call -> R0=f16 return
```

---

## 9. Implementasjonsnotater (Executive)

- OID‐tabeller: små, faste arrays (f.eks. 64 values, 32 commands).  
  `ns_id` og `key_id` kan være hash på 8-bit m/ kollisjonsliste (liten, deterministisk).
- Epsilon for endringsdeteksjon: `eps = max(unit_scale*1e-3, 1 LSB)`.
- Rate limit for `PUB`: N ms min-interval pr OID.
- UART shell: auto‐complete `ns:key`, `val watch` bruker mailbox.
- CAN: node‐ID og `base` settes av plattform; mapping i en liten LUT.

---

## 10. Testmatrise

- Register/lookup/list/meta for 10+ values
- Bulk `set/get` via UART loop
- CAN `GET/SET/PUB` runde‐trip (scope f16)
- `sub()` til mailbox + shell `watch`
- FRAM persist (power cycle simulert)

---

## 11. Oppsummering

HSX Value/Command gjør systemet eksternt **observerbart og styrbart** med minimal overhead:
- f16 overalt på grensen → kompakt, konsistent
- SVC-API for tasks, bindings for UART og CAN
- Eventdrevet via mailbox for både push og async command‐retur


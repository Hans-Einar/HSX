# HSX_VALUE_INTERFACE.md — Values (f16) & Commands

**Formål:** Standard måte for tasks i HSX å eksponere **verdier** (f16) og **kommandoer** (call) med ensartet API over VM/SVC, mailbox, UART-shell og CAN.

> Grunntype: `hsx_value_t = f16` (IEEE754 half). Verdier er alltid f16 *på grensen* (over SVC/IPC/wire). Internt kan task bruke hvilken som helst presisjon, men konverterer ved registrert grenseflate.

---

## 1. Objektmodell

| Element | Beskrivelse |
|---|---|
| **Group ID** | 8-bit numerisk gruppe (`0..255`). Eksempel: `0 = motor`, `1 = temp`. Gir komprimert adressering (`group:value`). |
| **Value ID** | 8-bit numerisk verdi innen gruppen (`0..255`). Kombineres med gruppe til et 16-bit OID (`oid = group<<8 | value`). |
| **Navn (valgfritt)** | Kort tekst (≤12 tegn) lagres i en separat strengtabel i executive/shell. Egen tabell for gruppenavn og verdinavn. |
| **Value (f16)** | F16-basert sanntidsverdi (bool representert som 0.0/1.0). |
| **Command** | Null-argument operasjon knyttet til gruppe/verdi-id (tolkes som “knapp”). |
| **Flags** | Bitfelt: `RO`, `Persist`, `Sticky`, `Pin` (krever autorisasjon), `Bool` (tolk verdi 0/1). |

> HSX apps registrerer både numerisk ID og (valgfritt) menneskelige navn. I RAM beholder executive kun de kompakte ID-ene og flaggene; navn ligger i delte strengtabeler for shell/debugger. CLI støtter begge former (`val get motor:rpm` eller `val get 0:3`).

---

## 2. SVC-API (VAL: mod=0x7)

**Register / list / get / set / subscribe**

| fn | Prototype (regs) | Retur i `R0` | Notat |
|---:|---|---|---|
| 0 | `val.register(group, value, flags, desc_ptr)` | `oid` | Oppretter/oppdaterer value. `desc_ptr` peker til valgfri deskriptor (navn, meta). |
| 1 | `val.lookup(group, value)` | `oid or -1` | Finn eksisterende uten å lage. |
| 2 | `val.get(oid)` | `f16` | Leser gjeldende verdi. |
| 3 | `val.set(oid, f16)` | `0/errno` | Skriver verdi. Krever at caller oppfyller `auth_level`/flags. |
| 4 | `val.list(group, out_ptr, max_items)` | `count` | Fyller tabell av `(oid,f16)` par for valgt gruppe (`group=0xff` ⇒ alle). |
| 5 | `val.meta(oid, out_ptr)` | `0/errno` | Skriver meta‐struct. |
| 6 | `val.sub(oid, mbx_name*)` | `0/errno` | Push onChange til mailbox (edge/coalesce). |
| 7 | `val.persist(oid, mode)` | `0/errno` | Oppdaterer last/save-modus for verdi. |

**ABI (regs):**
- `R1 = group_id`, `R2 = value_id`, `R3 = flags`, `R4 = desc_ptr` (0 hvis ingen). `val.set/get` behandler f16 i low 16 bits, `val.sub` mottar peker til mailbox-navn.

**Minimalt runtime-oppslag:**
```
struct hsx_val_entry {
  uint8_t group_id;
  uint8_t value_id;
  uint16_t flags;
  uint16_t last_f16;
  uint8_t auth_level;   // minimum nivå for skriveoperasjoner
  uint8_t reserved;
};
```

Optional metadata registreres via `desc_ptr` og kopieres til kompakte tabeller:
```
struct hsx_val_desc {
  const char *group_name;   // valgfritt
  const char *value_name;   // valgfritt
  uint16_t unit4;           // valgfritt (0 => ingen)
  uint16_t eps;             // hysterese (f16)
  uint16_t rate_ms;         // min publiseringsintervall
  uint16_t range_min;       // kun for verdier med grense
  uint16_t range_max;
  uint16_t persist_key;     // FRAM-nøkkel (0xffff => ikke persistent)
};
```
Executive kan velge å slippe felter som ikke er satt; per-verdi minnetrykk forblir 8–12 byte.

---

## 3. SVC-API (CMD: mod=0x8)

**Registrer kommando, kall synkront/asykront**

| fn | Prototype (regs) | Retur `R0` | Notat |
|---:|---|---|---|
| 0 | `cmd.register(group, value, flags, desc_ptr)` | `oid` | Kommandodefinisjon (ingen argumenter). |
| 1 | `cmd.lookup(group, value)` | `oid/-1` | Finn eksisterende. |
| 2 | `cmd.call(oid, token)` | `0/errno` | Synkront kall uten argumenter; `token` validerer tilgang (0 => ingen krav). |
| 3 | `cmd.call_async(oid, token, mbx*)` | `0/errno` | Async svar `(oid,rc)` på mailbox. |
| 4 | `cmd.help(oid, out_ptr)` | `0/errno` | Returnerer help-string / tilgangskrav. |

**Flagg:** `HSX_VAL_FL_RO`, `HSX_VAL_FL_PERSIST`, `HSX_VAL_FL_STICKY`, `HSX_VAL_FL_PIN`, `HSX_VAL_FL_BOOL`. 0 betyr les/skriv f16-scalar. Bool tolkes som f16 0.0/1.0. `HSX_CMD_FL_PIN` markerer kommandoer som krever autorisasjon.

**Kompakt lagring:**
```
struct hsx_cmd_entry {
  uint8_t group_id;
  uint8_t value_id;
  uint16_t flags;
  uint16_t auth_level;
};

struct hsx_cmd_desc {
  const char *group_name;
  const char *cmd_name;
  const char *help;
  uint16_t    auth_level;
};
```

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
motor:reset (secure)

> cmd call motor:reset
OK
```

- Parser konverterer desimaltall ↔ f16.
- `val sub` kan kobles til shell for live‐stream: `val watch motor:rpm` (oppdatering via mailbox → UART print).
- Alle kommandoer aksepterer også numerisk adresse (`val get 0:3`, `cmd call 0:5`).

---

## 5. CAN binding (11-bit ID, 8-byte payload)

**Enkel, kompakt mapping for f16‐verdier og kommandoer.**

- **CAN-ID:** `base | (topic<<3) | op`  
  `base`: node‐prefix, `topic`: 8-bit (`ns:key` komprimert til `oid`), `op`: 3-bit (`GET=0, SET=1, PUB=2, CALL=3, RET=4`).
- **Payload (SET/GET/RET/PUB):**
  - Byte0..1: `oid`
  - Byte2..3: `f16` (verdi / retur)
  - Byte4..7: opsjonelt: sequence, errno/reservert

**Strøm:**
- Ekstern noden sender `GET(oid)` → HSX svarer `RET(oid, f16)`
- Ekstern noden sender `SET(oid, f16)` → HSX kvitterer `RET(oid, rc)`
- Task publiserer endringer via `PUB(oid, f16)` (on change / rate limit).
- Kommandokall (`CALL`) består kun av `oid` + valgfri sekvens/autorisasjonsinfo; ingen argumenter sendes.

> Måltall: 1 verdi = 2 byte f16 + 2 byte oid ⇒ svært kompakt på CAN.

---

## 6. Mailbox integrasjon

- `val.sub(oid, "mbx")` abonnerer på endringshendelser: Executive sammenligner f16 mot `f16_last` (m/ hysterese/epsilon) og poster `(oid, f16)` på mailbox.
- Kommandoer med `call_async` svarer på mailbox `(oid, rc)` (ingen returverdi).

**Meldingsformat (bytes):**
```
VAL_PUB:  [type=0x01, oid(2), f16(2)]
CMD_RET:  [type=0x02, oid(2), rc(1)]
```

---

## 7. Persistens (FRAM)

- `val.persist(oid, mode)` binder verdi til en 16-bit `persist_key` definert inndata i `hsx_val_desc`.
- Executive laster ved task‐start og lagrer ved `set()`/shutdown basert på `mode`.

**Mode:** `0=volatile`, `1=load`, `2=load+save`. Når `persist_key` er satt til `0xFFFF` ignoreres persistensflagget.

---

## 8. Eksempelkode (assembly)

### 8.1 Registrere og publisere en verdi
```asm
; group=0 (motor), value=3 (rpm)
val_desc_motor_rpm:
  .word name_motor     ; group name
  .word name_rpm       ; value name
  .word 'RPM '         ; unit
  .word F16(0.1)       ; eps
  .word 50             ; rate_ms
  .word F16(0.0)       ; range_min
  .word F16(10000.0)   ; range_max
  .word 0x0103         ; persist_key (valgfritt)

LDI   R1, 0           ; group_id
LDI   R2, 3           ; value_id
LDI   R3, 0            ; flags (0 = RW)
LDI   R4, val_desc_motor_rpm
SVC   0x700           ; val.register -> R0=oid
MOV   R8, R0          ; lagre oid

; ... oppdater løpende
; måling i R9 (i32), konverter og publiser hvis endret
I2F   R10, R9
SVC   0x702           ; val.set(oid=R8, f16=R10.low16)
```

### 8.2 Kommando uten argumenter
```asm
; group=0 (motor), cmd=5 (reset)
cmd_desc_motor_reset:
  .word name_motor     ; group name
  .word name_reset     ; command name
  .word help_reset     ; help text
  .word AUTH_MAINT     ; auth level

LDI   R1, 0           ; group_id
LDI   R2, 5           ; value_id (command slot)
LDI   R3, HSX_CMD_FL_PIN
LDI   R4, cmd_desc_motor_reset
SVC   0x800           ; cmd.register -> R0=oid
MOV   R11, R0

; Kalles synkront fra shell/CAN:
LDI   R1, R11
LDI   R2, token_ptr   ; peker til autorisasjons-token (0 hvis ikke brukt)
SVC   0x802           ; cmd.call -> R0=0 (errno)
```

`name_*`/`help_*` peker mot null-terminerte strenger i en delt tabell. Executive dedupliserer strengene slik at de ikke krever ekstra per-verdi RAM.
```
name_motor: .asciz "motor"
name_rpm:   .asciz "rpm"
name_reset: .asciz "reset"
help_reset: .asciz "Reset motor state"
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


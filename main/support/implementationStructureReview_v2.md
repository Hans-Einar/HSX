# Implementation Structure Review — HSX (v2)
Dato: 2025-10-25

**Scope:** Oppdatert review som legger til **modulære bibliotekgrenser per syscall** og **speiling DESIGN ⇄ IMPLEMENTATION**, uten å generere C‑kode (vi er fortsatt i designfasen). Basert på `(3)architecture` og sporbarheten i (2.x).

**Branch:** `chores/document_merge_2`  
**URL‑tips for parenteser:** `(`→`%28`, `)`→`%29` (bruk i alle interne lenker).

---

## 1) Executive summary
- **Behold struktur** med `(5)implementation/` + `(6)test/`, men **formalisér modulgrenser** rundt *syscall‑flater* slik at de kan implementeres som **separate biblioteker** senere (uten å endre executive/VM).  
- **Executive‑events** (session lock, event‑stream, ACK/rate‑limit) **forblir i Executive** — tett kobling er ønsket.  
- **Speil DESIGN ⇄ IMPLEMENTATION:** én implementasjonsfil og én testplan per design/arkitektur‑view.  
- **Ingen kodergenerering nå**; kun dokumentmaler, kontraktstabeller og testplaner.

---

## 2) Katalogstruktur (uendret kjernestruktur + *shared* docs)
```
(5)implementation/
  system/            # moduler som maps mot (3)architecture
    MiniVM.md
    Executive.md
    Mailbox.md
    ValCmd.md
    Provisioning.md
    HAL.md
  toolchain/
    mvasm.md
    hsx-llc.md
    linker.md
    formats/{hxo.md,hxe.md,listing.md}
  toolkit/
    shell.md
    disassembler.md
    debugger.md
  shared/            # normative, felles kontrakter
    abi_syscalls.md        (kopier inn fra doc/)  # én kilde for SVC-moduler/ID/func (codegen senere)
    executive_protocol.md  (kopier inn fra doc/)   # event-typer, session/ACK/rate-limit (bor i executive)
    resource_budgets.md
    persistence_layout.md
    security.md
  guidelines.md
  dod.md

(6)test/
  minivm.md, executive.md, mailbox.md, valcmd.md, provisioning.md, toolchain_linker.md, toolkit_debugger.md
  fixtures/, mocks/
```

---

## 3) Modulære bibliotekgrenser (konseptuelt — *ingen* kode nå)
**Prinsipp:** Hver *syscall‑flate* blir et separat “pakke-/bibliotek‑domene”. Executive sin SVC‑bro **dispatcher** kun; logikk bor i modulens domene. Dette gjør add‑ons mulig uten å endre systemkjernen.

| Domene | Syscall‑modul (ID) | Foreslått lib‑domene | Hvorfor separere |
|---|---|---|---|
| **Executive‑kontroll** | `0x06` (EXEC) | *i Executive* | Sessions, event‑stream, scheduler‑kontrakt er tett koblet → behold her. |
| **Mailbox** | `0x05` | `mailbox` | IPC‑kjerne, egne leveringsmodi, kan testes isolert. |
| **Values** | `0x07` | `val` | f16‑lager, OID, persist hooks; nyttig alene i tester. |
| **Commands** | `0x08` | `cmd` | Zero‑arg kommandoer, policy/flags, async retur via mailbox. |
| **UART** | `0x10` (reserver) | `uart` | HAL‑binding via syscall‑flate; enkel å mokke. |
| **CAN** | `0x11` (reserver) | `can` | Transport‑spesifikke rammer, filter, tx/rx‑flow. |
| **FRAM/EEPROM** | `0x12` (reserver) | `fram` | Persistensoperasjoner; kobles til `persistence_layout`. |
| **FS/Storage** | `0x13` (reserver) | `fs` | Enkle fil/objekt‑API (manifest/artefakter). |
| **GPIO/Timers** | `0x14` (reserver) | `gpio`/`timers` | Vanlige HAL‑tjenester; nyttig for eksempelkode. |
| **Time/Clock** | `0x15` (reserver) | `timebase` | Enhetlig tidsbase og timeouts for hele systemet. |
| **Provisioning** | `0x16` (reserver) | `prov` | HXE ingest/status; skil fra EXEC for add‑ons. |

> **Merk:** ID‑ene over er forslag for **design**. Den autoritative listen vedlikeholdes kun i `(5)/shared/abi_syscalls.md` (én kilde, senere brukt til codegen).

**Implikasjoner i dokumenter:**
- `Executive.md`: beholder **session/attach/step** + **event‑protokoll** og **SVC‑bro** (kun dispatch).  
- `Mailbox.md`, `ValCmd.md`, `Provisioning.md` + *HAL‑domener* dokumenterer sine egne **API‑tabeller** (ID, Func, R0..R3, Ret, Errors, Timebase) og semantikk.  
- `HAL.md`: beskriver **bindings** mot `uart/can/fram/fs/gpio/timers` som *kan* mappes til syscall‑modulene over.

---

## 4) Hva i VM/Executive bør være “separat” (bibliotek‑vennlig)
- **Separat (god kandidat):** `Mailbox`, `Val`, `Cmd`, `Provisioning`, samt HAL‑orienterte domener (`uart/can/fram/fs/gpio/timers`, `timebase`).  
- **Forbli i Executive:** `exec_core` (scheduler, PID/session‑lås, single‑instruction‑kontrakt), `exec_events` (event‑stream, ACK/rate‑limit), `svc_bridge` (kun dispatch).  
- **VM:** behold kjerne (decode/exec, BRK/SVC, context) i én enhet; *event‑hooks* beskrives som grensesnitt, men hører praktisk til i Executive fordi streamen og rate‑policy er der.

---

## 5) Mal (uendret) og “Refs” (DR/DG/DO)
Bruk modul‑malen fra v1 (Scope, Refs, Public interfaces, Data structures, Execution & state, Implementation playbook, Implementation notes, Tests, DoD, Commit log).  
Fyll **Refs:** til DR/DG/DO fra `(2.1)` og label‑oppsettet i studien.

---

## 6) Testdrevet speil i `(6)/`
For hver modul:
- **Contract‑tester:** API/SVC‑tabeller (retur/feil/tidsbase).  
- **Atferd:** sekvenser (f.eks. mailbox: first/all/tap, overflow/back‑pressure).  
- **Grenser:** ressurs‑/latens‑budsjetter (fra `resource_budgets.md`).  
- **Fixtures/mocks:** legg i `fixtures/` og `mocks/` — ingen kjørbar kode ennå, kun beskrevet som plan.

---

## 7) DoD‑matrise (påminnelse)
Opprett/fyll `(5)/dod.md` med **Modul ↔ DR/DG/DO ↔ Min tester (lenke til `(6)/…`)**.

---

## 8) Neste steg (kun dokumenter nå)
- [ ] Opprett/fyll **`(5)/shared/abi_syscalls.md`** med den **foreslåtte modul‑tabellen** over (marker `UART..TIMEBASE..PROV` som “TBD IDs”).  
- [ ] Flytt/forsterk **event‑protokollen** i `shared/executive_protocol.md` og pek fra `Executive.md`.  
- [ ] Legg **public interface‑tabeller** inn i `Mailbox.md`, `ValCmd.md`, `Provisioning.md` (+ HAL‑domener).  
- [ ] Oppdater `(6)/*.md` til å speile modulene 1:1 (inkl. `fixtures/`, `mocks/`).  
- [ ] Forsikre **URL‑encoding** i alle interne lenker til `/(3)`, `/(4)`, `/(5)`, `/(6)`.

---

## 9) FAQ (kort)
- **Kan vi senere gjøre add‑ons via nye syscalls?** Ja—ny modul i `abi_syscalls.md` + ny modul‑MD + tilhørende testplan; Executive trenger kun dispatch‑kabling.  
- **Hvorfor ikke legge event‑strukturen i eget lib?** Den er tett bundet til scheduler/sesjon/rate‑policy i Executive → enklere og mer robust å ha på ett sted.

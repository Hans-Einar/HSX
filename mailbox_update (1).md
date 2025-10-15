# HSX Mailbox System — Code‑Verified Update

**Status:** Reviewed in “pro mode” against current repo (Python executive + C headers + demos).  
**Scope:** Clarify *actual* semantics implemented in code, explain why the `examples/demos/mailbox` producer/consumer didn’t show up under `mbox`, and give precise TODOs to make the demo work and the shell tooling observably correct.

---

## 1) What the code actually implements (today)

### Namespaces and prefixes (from `include/hsx_mailbox.h`)
- Namespaces: `PID=0x00`, `SVC=0x01`, `APP=0x02`, `SHARED=0x03`
- Prefixes: `"pid:"`, `"svc:"`, `"app:"`, `"shared:"`
- Modes/flags exist for `RDONLY/RDWR`, tap/fanout/overrun, etc. (e.g. `HSX_MBX_MODE_TAP`, `HSX_MBX_MODE_FANOUT[_DROP|_BLOCK]`).
- Function IDs: `OPEN=0`, `BIND=1`, `SEND=2`, `RECV=3`, `PEEK=4`, `TAP=5`, `CLOSE=6`.

### Python executive (`python/mailbox.py`) — authoritative runtime behaviour
- All **descriptors are global** in the manager; they’re keyed by `(<namespace>, <name>, <owner_pid>)`.
- Target parsing rules:
  - `pid:<n>` → `(PID, name="pid:n", owner_pid=n)`
  - `svc:<name>[@owner]` → `(SVC, name, owner_pid=owner or caller PID)`
  - `app:<name>[@owner]` → `(APP, name, owner_pid=owner or **None if absent**)`
  - `shared:<name>` → `(SHARED, name, owner_pid=None)` (no owner suffix)
  - Bare names default to `svc:` for convenience.
- **Implications:**
  - `shared:foo` is **global** across all prosesser (key uses `owner=None`).
  - `app:bar` **is also global by default** (owner is `None` unless you add `@pid`).
  - Hvis du vil ha en *eier‑scopet* app‑mailbox: bruk `app:bar@<pid>`.
- Manageren eksponerer `descriptor_snapshot()` som returnerer **alle** descriptors (uansett namespace/owner).

### Demo‑koden (`examples/demos/mailbox`)
- `procon.h` definerer **`PROCON_MAILBOX_TARGET "app:procon"`** (ingen `@pid`) → global `APP` mailbox.
- `consumer.c` gjør `hsx_mailbox_bind("app:procon", …)` og `open()` → skal opprette/åpne én felles descriptor.  
- `producer.c` gjør `open("app:procon")` og sender; leser linjer fra `stdin` mailbox (`svc:stdio.in`).

**Konklusjon:** Runtime‑koden støtter både `app:` og `shared:` slik at *en* felles descriptor blir brukt på tvers av prosesser. Problemet er primært at `mbox`‑kommandoen i shell **ikke viser** `APP/SHARED`‑descriptors, så det ser ut som om det ikke finnes — selv om produsent/konsument i prinsippet *kan* snakke sammen.

---

## 2) Hvorfor `mbox` ikke viser den felles mailboxen

- Shell‑kommandoen `mbox` lister i dag kun `svc:` og `pid:` (handles/descriptors knyttet til hver PID’s stdio/kontroll).  
- MailboxManager har allerede en API for å hente **global** liste (`descriptor_snapshot()`), men shellen bruker ikke dette (eller filtrerer det for hardt).  
- Resultatet er at **`app:`/`shared:` ikke syns**, selv om de finnes.

> I outputet du viste var `svc:stdio.in` for produsenten (`PID=2`) *ikke tom* (Depth=2, Bytes=26), så produsenten mottok stdin‑data — men `app:procon` var ikke i listen. Det peker på et *visningsproblem* i shell, ikke mangel i selve mailbox‑kjernen.

---

## 3) Hva som mangler (gap‑analyse)

**Implementasjon finnes, men er ikke eksponert i shell:**
- Global descriptor‑enumerering (`APP`/`SHARED`) i `mbox`

**Små semantiske avklaringer/dokumentasjon:**
- `app:` uten `@pid` er globalt i praksis (owner `None`). Det er ok, men bør stå eksplisitt i docs + shell‑help.
- `shared:` støtter ikke `@owner` (alltid global).

**Potensielle forbedringer (valgfrie):**
- `mbox` burde kunne filtrere: `mbox all|svc|pid|app|shared`, og vise eierskap (`owner_pid` eller `-`/`*` for `None`).
- CLI‑kommandoer for å **tap’e** mailboxes (`tap on/off`) og for fanout‑moduser for enkel feilsøking.

---

## 4) Presis TODO for å få `examples/demos/mailbox` til å fungere *og* være synlig

### A. Shell/CLI (`mbox`)
1. Bytt til global snapshot i mbox‑handleren:  
   - Kall `MailboxManager.descriptor_snapshot()` og vis *uten* å filtrere bort `APP/SHARED`.
2. Legg til kolonner som allerede finnes i snapshot:  
   - `ID`, `Namespace` (`pid|svc|app|shared`), `Owner`, `Depth` (= `queue_depth`), `Bytes` (`bytes_used`), `Mode` (`mode_mask`), `Name`.
3. Sortér som i snapshot (`descriptor_id`), eller grupper per namespace.
4. (Valgfritt) Filtre: `mbox shared`, `mbox app`, `mbox pid <n>`.

### B. Demo (ingen kodeendring nødvendig for funksjon, men nyttig observabilitet)
1. **Behold** `PROCON_MAILBOX_TARGET "app:procon"` (global). Alternativt bruk `shared:procon` for å gjøre intensjonen eksplisitt.
2. Start `consumer.hxe` først (binder `app:procon`). Start `producer.hxe` etterpå.
3. I shell: send en linje til produsentens stdin (f.eks. `send svc:stdio.in@<pid_producer> "hello\n"`), og lytt på `consumer` stdout (`listen svc:stdio.out@<pid_consumer>`).  
   - Eksakt syntaks avhenger av shell‑klienten; poenget er at prod leser fra `svc:stdio.in`, sender til `app:procon`, og konsument skriver til `svc:stdio.out`.
4. Sjekk `mbox` — nå skal `app:procon` synes, med voksende `Depth/Bytes` når meldinger går igjennom.

### C. Eksekutiv/VM (kun hvis du ønsker ekstra sikkerhet)
- Legg inn logging/taps ved `SEND/RECV` for `app:procon` (bruk `HSX_MBX_MODE_TAP`) og vis disse hendelsene i shell (`mbox tap <id> on`).

---

## 5) Klargjør docs og help‑tekster

**Docs å oppdatere:**
- `docs/hsx_spec-v2.md`: presiser at i Python‑executive er *både* `app:` **og** `shared:` globalt scopa når `@owner` utelates (for `app:`). Foreslå bruk av `app:<name>@<pid>` for eier‑spesifikk instans.
- `agents.md` / `MILESTONES.md`: noter at `APP/SHARED` er implementert i host‑executive; gjenstår bare å gjøre dem synlige i shell.

**Shell‑help:**
- `help/mbox.txt` (eller tilsvarende): beskriv namespaces, `@owner`, og eksempler på `send/listen` med `svc:stdio.*@pid`.

---

## 6) Ekstra forslag (lav kost, høy nytte)

- **`--mode` i bind:** gi shell‑kommando for å sette `FANOUT`/`FANOUT_DROP/BLOCK` og `TAP` på en descriptor (nyttig for fler‑konsument scenario).
- **Overrun‑flagg i UI:** vis `OVERRUN` i `peek`/`recv` status så det er tydelig dersom meldinger er droppet.
- **Enhetstester:** legg til en test som starter to PIDs, `bind("app:x")` i den ene og `open("app:x")` i den andre, og bekreft at `descriptor_id` er lik og trafikk flyter.

---

## 7) Minimal akseptansekriterier for demoen

- `mbox` viser en rad for `app:procon` med `Namespace=app`, `Owner=-/None`, `Depth>=0`, `Bytes>=0`.
- En tekstlinje sendt til `producer`’s `stdin` resulterer i **samme tekst** skrevet ut av `consumer` på `stdout`.
- `peek` på `app:procon` viser voksende `head_seq/next_seq` når meldinger flyter.
- `ps` viser begge PIDs i `ready`/`running`, ikke i `sleep` (med mindre `RECV` blokkerer, som er ok).

---

## 8) Quick‑reference: `app:` vs `shared:` (slik koden er nå)

| Prefix          | Namespace | Owner‑suffix | Global/Local | Bruksnotat |
|-----------------|-----------|--------------|--------------|------------|
| `pid:<n>`       | PID       | n/a          | Per prosess  | Kontroll/stdio routing |
| `svc:<name>`    | SVC       | `@pid` **valgfritt** | Privat til eier (default) | `svc:stdio.in@<pid>` etc. |
| `app:<name>`    | APP       | `@pid` **valgfritt** | **Global** uten suffix | Bruk `@pid` hvis du ønsker eier‑scoping |
| `shared:<name>` | SHARED    | ikke støttet | **Global**   | Alltid global |

---

## 9) Handlingsliste (kan kopieres til issues)

- [ ] **Shell:** Bytt `mbox` til `descriptor_snapshot()` og vis `APP/SHARED`  
- [ ] **Shell:** Legg til filtere (`mbox shared|app|svc|pid <n>`)  
- [ ] **Docs:** Avklar `app:` som global uten `@pid`; dokumenter `@pid`  
- [ ] **Samples:** Legg brukseksempel i `examples/demos/mailbox/README.md` (send/listen)  
- [ ] **Tests:** Kryss‑PID test for `app:` og `shared:` åpent via to prosesser  
- [ ] **(Valgfritt)** Tap/Fanout CLI‑kommandoer for feilsøking

---

## 10) Hurtig feilfinner for deg

1. Start **consumer** først (binder må eksistere).  
2. Start **producer**.  
3. Bruk `send` for å legge noe i `svc:stdio.in@<pid_producer>` (f.eks. `"hello\n"`).  
4. Se `consumer`’s stdout (f.eks. `listen svc:stdio.out@<pid_consumer>`).  
5. Kjør `mbox` — nå skal `app:procon` synes og `Depth/Bytes` endres når du sender.

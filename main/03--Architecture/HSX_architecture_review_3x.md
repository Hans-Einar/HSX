# HSX Architecture Review — (3.x) Document Set
Dato: 2025-10-21

## Scope
Gjennomgått filer i `(3)architecture/`:
- (3.0)architecture.md — Project Architecture — HSX Runtime & Tooling
- (3.1)vm.md — Architecture View — MiniVM
- (3.2)executive.md — Architecture View — Executive
- (3.3)mailbox.md — Architecture View — Mailbox Subsystem
- (3.4)val_cmd.md — Architecture View — Value & Command Access Layer
- (3.5)toolkit.md — Architecture View — Tooling (Shell & Debugger)
- (3.6)provisioning.md — Architecture View — Provisioning & Persistence

## Kort konklusjon (Design readiness)
**Status:** God *arkitektur-retning* og dekomponering foreligger. Dere kan starte design på verktøylag (shell/debugger), provisioning‑CLI og deler av executive (scheduler‑skjelett, prosess/PCB, stdio/FD-multiplex). For full, effektiv design på tvers trengs noen normative kontrakter og budsjetter ferdigstilt først (se P0 nedenfor).

**Anbefaling:** Start design for host‑tooling og executive‑grunnmur parallelt, men timeboxing på 1–2 uker for å fryse P0‑kontraktene før man dykker for dypt i inter‑modul implementasjonsdetaljer.

## Styrker
- Tydelig lagdeling (MiniVM ↔ Executive ↔ HAL) og host‑first debughistorie.
- Enhetlig IPC via mailbox med støtte for fan‑out/tap; verdier/kommandoer bygget på samme rygg.
- Klart skille mellom prototype i Python og senere C‑port, med samme arkitektur.

## P0 – Må på plass før full design
| Tema | Hva må avklares | Artefakt (foreslått) |
|---|---|---|
| Syscall/ABI kontrakt | Modul‑IDer, kall‑ID, reg‑mapping (R0–R3), retur/feilkoder, tidsouts | `docs/abi_syscalls.md` med tabeller |
| Mailbox semantikk | Leveringsmodi (first‑reader/all‑readers), kapasitet, back‑pressure, overflow/timeout, fairness | Normativt kapittel i `(3.3)mailbox.md` + sekvensdiagrammer |
| Scheduler & venting | State‑maskin for `ready/sleep/wait`, blokkeringspunkter, klokking (attached/standalone), tidsenheter | `(3.2)executive.md` – «Scheduling semantics» |
| Ressursbudsjetter | RAM/flash pr. target, descriptor pool‑størrelser, FD‑tabell, stack/arena pr. PID | `docs/resource_budgets.md` |
| HXE/objektformat | Felt, versjon, CRC/signatur, kompatibilitet, min‑/max‑grenser | `docs/hxe_format.md` |
| Debug/event‑protokoll | Hendelsestyper, felter, hastighet/rate‑limit, sesjonslås | `docs/executive_protocol.md` (normativt) |
| Persistenslayout | FRAM/E2 layout (keys, størrelser), livssyklus, transaksjon/CRC | `(3.6)provisioning.md` utvides |
| Sikkerhet/policy | Kommandoflagg, privilegier, autentisering (host/CAN), signering | `docs/security.md` |

## P1 – Bør avklares tidlig i design
- C4‑diagrammer (L1/L2) og komponent‑interfaces (sekvensdiagrammer for boot, exec, attach, provisioning).
- HAL‑kontrakt: drivernavn, init, non‑blocking IO, feilmodell.
- Observability: loggnivå, event‑kategorier, sampling, målepunkt.
- Kompatibilitet Python↔C: testmatrise, referansevektor for corner‑cases.

## Design‑start nå (trygge områder)
- **Tooling:** CLI/TUI, event‑stream, JSON‑RPC klient, sesjonslås/testing.
- **Executive‑grunnmur:** prosess/PCB, FD/stdio‑rørlegging, `attach/step/clock`, minimal scheduler (kooperativ).
- **Provisioning‑CLI:** `load/restart/status`, SD‑manifest tooling, FRAM‑nøkler.
- **Debugger V1:** breakpoints, run/step/next, basic symbol/line mapping.

## Per‑view vurdering
| View | Status | Mangler før full design |
|---|---|---|
| (3.0) Architecture overview | **Solid** | Legg inn C4 skisser og eksplisitte grenseflater mellom lag (API‑peker). |
| (3.1) MiniVM | **God retning** | ABI‑detaljer (stack layout, kall‑konvensjon), state‑feltliste, standalone vs. attached klokking. |
| (3.2) Executive | **God retning** | Scheduler‑semantikk, event‑stream kontrakt, prosess/FD‑tabell og livssyklus. |
| (3.3) Mailbox | **Nær komplett** | Normativ semantikk (overrun/back‑pressure), kapasitet/policy og fairness. |
| (3.4) Values/Commands | **Ok** | Adresse‑skjema, type/skalering, sikkerhet/policy, persistensgrenser. |
| (3.5) Tooling | **Klar** | Protokolldetaljer og testmatrise. |
| (3.6) Provisioning | **Ok** | FRAM layout, feil/rollback, manifest/versjonering, sikkerhet. |

## Foreslåtte tabell‑skjemaer (kopier‑inn i specs)
### Syscall tabell (eksempel)
| Modul | ID | Navn | Args (R0–R3) | Retur | Feil | Tidskrav |
|---|---|---|---|---|---|---|
| MAILBOX | 0x05 | SEND | h, msg_ptr, len, flags | 0/−errno | EAGAIN/ETIMEDOUT | ≤ X µs |
| VALUE   | 0x07 | GET  | id, buf, len, − | n | ENOENT | ≤ X µs |
| CMD     | 0x08 | EXEC | id, a0, a1, flags | rc | EPERM | ≤ X ms |

### Mailbox semantikk (normativt)
- **first‑reader‑clears:** nøyaktig én mottaker; drop for andre.
- **all‑readers‑clears:** alle bundne mottakere må `RECV` før clear.
- **tap:** ikke‑destruktiv kopi; må være back‑pressure nøytral.
- **overflow:** avsender får −EAGAIN eller blokk (policy).

## Åpne spørsmål
- Hvilken tidsbase (ticks/us/ms) brukes i SVC‑APIer og timeouts?
- Maks antall samtidige PIDs og FD‑er per PID?
- Hvordan versjoneres `.hxe` og SVC‑ABI på tvers av noder?
- Trengs ACL/rollemodell for `cmd` over CAN?

## Forslag til neste steg (2 uker)
1) Frys **Syscall/ABI** og **Mailbox semantikk** (P0).  
2) Definer **resource budgets** per target (tabell).  
3) Skriv **event‑stream** og **debug‑protokoll**.  
4) Start implementasjon av **PCB/FD/stdio** og **shell** i parallell.

---

*Denne reviewen fokuserer på design‑klarhet (kontrakter, budsjetter, sekvenser). Når P0 er på plass, anbefales detaljdesign per modul med sekvensdiagrammer og testkrav (DoD) som vedlegg.*

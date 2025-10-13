# HSX Debugger Implementation

**Status:** Draft  
**Audience:** VM/assembler/toolchain maintainers, shell/CLI maintainers  
**Scope:** Legg til grunnleggende debugger-funksjoner i HSX-VM og -verktøykjede: programvare‑breakpoints, continue/step, backtrace, visning av variabler, og enkel kilde‑navigasjon.  

---

## TL;DR
- Legg til en **BRK**-instruksjon i ISA (+ valgfri umiddelbar «reason code»).
- Implementér en **stoppemekanisme i VM‑løkken** (stop reasons: BRK, SWBREAK, STEP, WATCH).
- Realisér breakpoints **uten kodepatching** i første runde (tabelloppslag på `pc`).
- Implementér **step/next/finish** med *midlertidige breakpoints* for kall/retur.
- Utvid `hxe` med **debug‑metadata**: `.symtab/.strtab`, `.line`, `.frame`, `.dbgmeta`.
- Shell‑kommandoer: `dbg attach/bp/cont/step/next/finish/regs/vars/bt`.
- Fasevis utrulling: Fase 1 (BRK + bp by address + step + cont), Fase 2 (next/finish + bt), Fase 3 (line/vars).

---

## 1) Mål og ikke‑mål

**Mål**
- Settable og treffe‑sikre programvare‑breakpoints.
- Kjøring: `continue`, `step (into)`, `next (over)`, `finish (out)`.
- `dbg vars`: rekonstruksjon av lokale/argumenter/globale med navn → verdi.
- `dbg bt`: backtrace basert på FP‑kjede/ret‑adresser.
- «Kildeposisjon»: vis `fil:linje` for gjeldende `pc` når metadata finnes.

**Ikke‑mål (første versjon)**
- Full DWARF‑kompatibilitet.
- Patching‑breakpoints (INT3‑stil) og hardware watchpoints.
- Remote debugging via GDB RSP (kan komme senere).

---

## 2) Overordnet tilnærming

1. **BRK i instruksjonssettet** – eksplisitt trap for kode‑innsatte stopp (og for `BREAK()` i C).
2. **Interpreter‑stopp** – kjerneløkken returnerer kontroll til debugger når:
   - `pc` matcher et aktivt breakpoint (tabelloppslag), eller
   - opkodet er `BRK`, eller
   - `single_step` er aktiv (etter én instruksjon).
3. **Debug‑metadata** i `hxe` muliggjør kilde‑nivå features (navn, linje, stackrammer).
4. **CLI‑shell** (`dbg ...`) som kontrollerer VM og presenterer tilstand.

---

## 3) ISA‑utvidelse: `BRK`

- **Mnemonic:** `BRK` eller `BRK imm8`
- **Semantikk:** Stopper kjøring og returnerer debug‑hendelse til kontroll‑sløyfen.
- **Variant med kode:** `imm8` kan angi årsak (0=SWBP, 1=assert, 2=user, …).  
- **Assembler:** Legg til opkodemapping for `BRK`.  
- **C‑makro (senere når toolchain støtter inline asm/pseudo‑op):**
  ```c
  #ifndef BREAK
  #define BREAK() __asm__ volatile("BRK")
  #endif
  ```

---

## 4) VM‑endringer

### 4.1 Stop‑årsaker (enumerasjon)
- `BRK` – BRK‑instruksjon truffet
- `SWBREAK` – programvare‑breakpoint via tabell
- `STEP` – single‑step fullført
- `WATCH` – watchpoint (senere)

### 4.2 Kjøreløkke (skisse)
```python
def run_until_event(pid):
    ctx = vm.ctx[pid]
    while True:
        pc = ctx.pc

        # Async break (Ctrl-C) – stopp ved neste instruksjon
        if ctx.debug_async_break:
            ctx.debug_async_break = False
            return Stop(reason="BRK", pc=pc)

        # Breakpoint-tabell (ikke patching i V1)
        if pc in vm.bp_table[pid]:
            return Stop(reason="SWBREAK", pc=pc)

        opcode = fetch(pc)

        if opcode == BRK:
            return Stop(reason="BRK", pc=pc)

        if ctx.single_step:
            execute_one(ctx)
            return Stop(reason="STEP", pc=ctx.pc)

        execute_one(ctx)  # normal kjøring
```

### 4.3 Tilstand som må eksponeres
- `pc, sp, fp, regs[], flags`
- Sist stopp‑årsak, prosess‑status, evt. tråd‑ID hvis VM har tråder.

### 4.4 Kontrollkommandoer (API)
```python
dbg.attach(pid)
dbg.cont(pid)
dbg.step(pid, n=1)       # into
dbg.next(pid, n=1)       # over
dbg.finish(pid)          # out
dbg.bp_add(pid, addr, temp=False)
dbg.bp_rm(pid, bp_id)
dbg.bp_ls(pid)
dbg.regs(pid)
dbg.vars(pid, scope="locals|args|globals")
dbg.bt(pid)
```

---

## 5) Breakpoints

### 5.1 Datamodell
- `vm.bp_table: dict[pid, set[int]]`  – «hurtig» medlemskapstest på `pc`.
- `vm.bp_meta: dict[pid, dict[bp_id, {addr, temp, spec}]]`
- `spec` beholder originalinput (funksjonsnavn, `fil:linje`) for listingen.

### 5.2 Legge til / fjerne / liste
- `dbg bp add <addr | func | fil:linje>`  
  - `func` og `fil:linje` løses via debug‑metadata (se §7).
- Midlertidige breakpoints (`temp=True`) brukes av `next/finish` og slettes automatisk når de treffer.

### 5.3 Patching‑breakpoints (senere)
- For ytelse/JIT kan opkodet patche til `BRK`. Da må man:
  1) restore original opkode,  
  2) single‑step’e instruksjonen,  
  3) re‑arm’e breakpointet.

V1 holder seg til tabelloppslag (enkelt og sikkert i en interpreter).

---

## 6) Stepping

### 6.1 `step` (into)
- Sett `ctx.single_step = True`, kjør `run_until_event(pid)`.

### 6.2 `next` (over)
- Hvis neste instruksjon er `CALL`:
  - Beregn **retur‑PC** (pc etter CALL).  
  - Legg et *midlertidig* breakpoint på retur‑PC.  
  - `continue()` til stopper (treffer temp‑BP etter retur).  
- Ellers: som `step`.

### 6.3 `finish` (out)
- Finn **caller‑retur‑PC** via frameinfo (`fp`‑kjede eller link‑reg).  
- Sett temp‑BP på retur‑PC, `continue()`.

### 6.4 Greie antagelser (V1)
- Funksjonsprolog etablerer `fp` og lagrer `ret` konsekvent.  
- Kall/ret kan identifiseres via distinkte opkoder.

---

## 7) Debug‑metadata i `hxe`

### 7.1 Seksjoner (forslag)
- **`.symtab` + `.strtab`** – funksjonsnavn, globale symboler.
- **`.line`** – kartlegging `pc → (file_id, line)`.
- **`.frame`** – variabel‑lokasjoner per funksjon (args/locals), ramme‑layout.
- **`.dbgmeta`** – versjonering, kompilatorflagg, osv.

> Metadata er *valgfrie* og kan ignoreres ved vanlig kjøring (null overhead).

### 7.2 Eksempelskjema (`.frame` + `.line`) – JSON‑likt (kan også være binært)
```json
{
  "files": [{"id":1,"name":"main.hsx"}],
  "funcs": [{
    "name":"foo",
    "addr":4096,
    "frame": {
      "stack_size": 32,
      "args":[ {"name":"n","loc":{"stack_off":+16,"type":"i32"}} ],
      "locals":[
        {"name":"i","loc":{"stack_off":-8,"type":"i32"}},
        {"name":"p","loc":{"reg":3,"type":"ptr<u8>"}}
      ]
    }
  }],
  "lines": [
    {"pc":4096,"file":1,"line":12},
    {"pc":4100,"file":1,"line":13}
  ],
  "globals":[
    {"name":"counter","addr":8192,"type":"i64"}
  ]
}
```

**Lokasjonskilder (V1):**
- `stack_off` relativt til `fp`  
- `reg` (register‑indeks)  
- `addr` (absolutt/global)  
- (Senere: lokasjons‑lister med `pc`‑intervaller)

### 7.3 Bruk i `dbg vars`
1. Finn aktiv funksjon via `pc → func` (fra `.symtab`/`addr`‑range).  
2. Hent rammebeskrivelse.  
3. For hver variabel: beregn adresse/verdi fra `fp/regs/globals`.  
4. Formater pent (klipp arrays/strings til `N` bytes for sikkerhet).

### 7.4 Backtrace (`dbg bt`)
- Les `ret`/`prev_fp` fra nåværende ramme; gjenta opp kjeden.  
- Slå opp funksjonsnavn + `fil:linje` via `.symtab/.line`.

---

## 8) Shell/CLI – brukeropplevelse

```
dbg attach <pid>
dbg regs
dbg where               # fil:linje + et par source-linjer (hvis tilgjengelig)
dbg bp add <addr|func|file:line>
dbg bp rm <id>
dbg bp ls
dbg cont
dbg step [N]
dbg next [N]
dbg finish
dbg bt
dbg vars [--scope locals|args|globals] [--max-bytes N]
```

**Tips**
- `Ctrl-C` i shell: sett `ctx.debug_async_break = True` for å stoppe ved neste instruksjon.
- Vis midlertidige breakpoints i `bp ls` med markering (f.eks. `temp`).

---

## 9) Assembler/kompilator‑koblinger

- **Assembler**
  - Legg til mnemonic/opkode for `BRK` (+ evt. `BRK imm8`).
  - Støtt `file/line`‑direktiv eller generér `.line` fra kompilatoren.

- **C‑makro**
  - `#define BREAK() __asm__ volatile("BRK")` når inline asm/pseudo‑op finnes.
  - Alternativt en intrinsic eller en pseudo‑instruksjon i HSX‑frontenden.

- **Byggflagg**
  - `-g` aktiverer utslipp av `.symtab`, `.line`, `.frame` i `hxe`.

---

## 10) Feilhåndtering og hjørnetilfeller

- **Branches:** `step` kjører nøyaktig én instruksjon uansett tatt/ikke tatt.  
- **Kall:** `next` håndteres via temp‑BP på retur‑PC.  
- **Optimisert kode:** variabler kan være «pruned»; i V1 antar vi -O0‑stil eller enkel optimizer.  
- **Selvmodifiserende kode:** ikke støttet i V1.  
- **Manglende metadata:** `dbg vars` og `file:line` degraderer elegant (viser kun adresser/registre).

---

## 11) Ytelse og sikkerhet

- **Overhead** uten debugging er minimal: kun én rask guard i løkken for `bp_table/single_step/async`.  
- **Sikkerhet:** Clamp lesing av minne i `dbg vars` (maks bytes / tilgangssjekk).  
- **Samtidighet:** Hvis flere PIDs/tråder, beskytt `bp_table` og `ctx` med låser eller per‑PID‑aktivering.

---

## 12) Milepæler

### Fase 1
- [ ] `BRK` i ISA + VM trap
- [ ] `dbg attach/regs/cont/step`
- [ ] Breakpoints via tabell (`dbg bp add <addr>`)
- [ ] Async break fra shell

### Fase 2
- [ ] `next`/`finish` (midlertidige breakpoints)
- [ ] `dbg bt` (FP‑unwinding)

### Fase 3
- [ ] `.line` + `.symtab` i `hxe` → `fil:linje` i `dbg where/bt`
- [ ] `.frame` → `dbg vars` (args/locals/globals)

### Fase 4 (opsjon)
- [ ] Watchpoints (`mem_read/mem_write` hooks)
- [ ] Patching‑breakpoints (INT3‑stil)
- [ ] Remote stub (GDB RSP) / editor‑integrasjon

---

## 13) Eksempel: data‑ og kontrollflyt

### 13.1 Pseudo: `next`
```python
def dbg_next(pid, n=1):
    for _ in range(n):
        pc = ctx.pc
        op = fetch(pc)
        if is_call(op):
            ret_pc = pc_after_call(pc, op)
            bp_id = dbg.bp_add(pid, ret_pc, temp=True)
            dbg.cont(pid)
            # når vi stopper, temp‑BP er (auto)slettet
        else:
            dbg.step(pid, 1)
```

### 13.2 Pseudo: backtrace
```python
def dbg_bt(pid, max_frames=64):
    frames = []
    fp = ctx.fp
    pc = ctx.pc
    while len(frames) < max_frames and valid_fp(fp):
        name, file, line = lookup_symbol_line(pc)
        frames.append({"pc": pc, "fp": fp, "func": name, "file": file, "line": line})
        ret, prev_fp = read_ret_prevfp(fp)
        pc = ret
        fp = prev_fp
    return frames
```

### 13.3 Pseudo: variabeloppslag
```python
def dbg_vars(pid, scope="locals"):
    func = lookup_function(ctx.pc)
    fr = frame_info(func)
    out = []
    for v in fr[scope]:
        loc = v["loc"]
        if "stack_off" in loc:
            addr = ctx.fp + loc["stack_off"]
            val  = mem_read(addr, sizeof(loc["type"]))
        elif "reg" in loc:
            val  = ctx.regs[loc["reg"]]
        elif "addr" in loc:
            val  = mem_read(loc["addr"], sizeof(loc["type"]))
        out.append((v["name"], format_value(val, loc["type"])))

    return out
```

---

## 14) Testplan (kort)

- **Unit**: BRK‑semantikk, `bp_table`‑oppslag, `single_step`‑stopp, kall/retur‑beregning.  
- **Integrasjon**: `dbg next` over funksjonskall; `finish` tilbake til kallsted; `bt` over dypt call‑tre.  
- **Metadata**: `dbg where` korrekt for flere filer; `dbg vars` for args/locals/globals.  
- **Robusthet**: async break; manglende metadata; utenfor‑range FP.

---

## 15) Videre arbeid

- DWARF‑kompatibel eksport (full eller subset) for interoperabilitet.  
- GDB Remote Serial Protocol for ekstern klient (VS Code, CLion).  
- Symbol‑server for delte biblioteker/hxo.  
- Visual stepping og source‑visning i HSX‑shell eller editor‑plugin.

---

**Oppsummert:** Start med `BRK` + tabell‑breakpoints i VM og `dbg cont/step`. Bygg deretter `next/finish` med midlertidige BP‑er, og legg til `.line/.frame` i `hxe` for `where/vars/bt`. Dette gir en trygg, inkrementell vei til en brukbar debugger uten tunge avhengigheter.

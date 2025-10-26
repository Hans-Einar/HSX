# Implementation Playbook — HSX

> Track implementation tasks per module. Follow the structure: shared references → system modules → toolchain → toolkit. Each section mirrors `(5)/implementation` planning docs and `(6)/test` plans.

## Shared
- `shared/abi_syscalls.md`
  - [ ] Finalize module/function ID table; add UART/CAN/FRAM/etc. once design freezes.
- `shared/executive_protocol.md`
  - [ ] Keep event schema/ack/rate-limit notes aligned with `docs/executive_protocol.md`.
- `shared/resource_budgets.md`
  - [ ] Populate measured data once C port sizing available; enforce budgets in implementation.
- `shared/persistence_layout.md`
  - [ ] Document wear-leveling/rollback specifics for FRAM.
- `shared/security.md`
  - [ ] Fill policy table (auth levels, transport ACLs) when defined.

## System
### MiniVM (`system/MiniVM.md`)
- [ ] Integrate shared syscall header; track workspace-pointer acceptance tests (DR-2.1a).
- [ ] Implement BRK/event payload hooks matching event schema.
- [ ] Update `(6)/system/MiniVM_tests.md` with fixtures.

### Executive (`system/Executive.md`)
- [ ] Implement PID locks + `session.open/keepalive` per DR-8.1.
- [ ] Build event streamer with ACK/back-pressure handling.
- [ ] Expose `EXEC_GET_VERSION`; sync with shared header.
- [ ] Mirror tasks in `(6)/system/Executive_tests.md`.

### Mailbox (`system/Mailbox.md`)
- [ ] Define library API (status codes, configs) ready for extraction.
- [ ] Finalize resource tuning knobs; align tests in `(6)/system/Mailbox_tests.md`.

### ValCmd (`system/ValCmd.md`)
- [ ] Document persistence hook integration; tests in `(6)/system/ValCmd_tests.md`.

### Provisioning (`system/Provisioning.md`)
- [ ] Detail CAN/SD chunking protocol; update tests accordingly.

### HAL (`system/HAL.md`)
- [ ] Flesh out per-domain syscall tables (UART/CAN/FRAM/FS/GPIO/Timers/Timebase).
- [ ] Create HAL mocks in `(6)/mocks/hal/` for tests.

## Toolchain
### MVASM (`toolchain/mvasm.md`)
- [ ] Wire shared syscall header parsing into assembler.
- [ ] Expand listing/JSON output spec for debugger.

### hsx-llc (`toolchain/hsx-llc.md`)
- [ ] Add instrumentation hooks for register pressure metrics.

### Linker (`toolchain/linker.md`)
- [ ] Implement manifest embedding per `docs/hxe_format.md`.
- [ ] Add compatibility checks for version/caps.

### Formats (`toolchain/formats/`)
- `hxo.md`: [ ] Document object layout details.
- `hxe.md`: [ ] Sync with global spec as changes land.
- `listing.md`: [ ] Define listing/sidecar schema for debugger.

## Toolkit
### Shell (`toolkit/HSXshell.md`)
- [ ] Update CLI to use session/event APIs; write tests in `(6)/toolkit/Shell_tests.md`.

### Disassembler (`toolkit/disassembler.md`)
- [ ] Implement sidecar ingestion + filtering; tests in `(6)/toolkit/disassembler_tests.md`.

### Debugger (`toolkit/debugger.md`)
- [ ] Build `hsxdbg` core (session manager, event bus, state cache, CLI/TUI adapters); align with `(6)/toolkit/debugger_tests.md`.
- [ ] Extend CLI/TUI test suites (`python/tests/test_host_vm_cli.py`, debugger pipelines) to cover event drop handling, resynchronisation via `since_seq`, and concurrent observer vs owner sessions.

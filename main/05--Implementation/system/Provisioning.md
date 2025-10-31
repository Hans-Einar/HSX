# Provisioning & Persistence Implementation Plan

## Scope
- Provisioning flows (CAN/SD/host load) and FRAM persistence services (DR-1.1, DR-5.3, DG-5.3).
- SVC module `prov` (ID TBD) for image status/load/abort queries.
- Integration with value persistence (`val.persist`) and provisioning manifests.

## Preconditions
- Toolchain emits `.hxe` headers + manifests per `shared/formats/hxe.md`.
- FRAM layout defined (`shared/persistence_layout.md`).
- Mailbox/value subsystems available for status + calibration sync.

## Postconditions
- Provisioning module can validate, load, and report status for HXE payloads.
- FRAM writes/reads follow DR-5.3 (CRC, rollback) and emit events for tooling.
- CLI/automation can query provisioning state via SVC/RPC.

## Public Interfaces (proposed)
| Func | ID | R1 | R2 | R3 | Returns | Notes |
|------|----|----|----|----|---------|-------|
| `PROV_INFO` | `0x1700` | pid | out_ptr | max_len | `status` | Returns manifest/status JSON.
| `PROV_LOAD` | `0x1701` | source_ptr | flags | – | `status` | Initiates load from CAN/SD/host; flags choose source.
| `PROV_ABORT` | `0x1702` | pid | reason | – | `status` | Aborts in-progress transfer.
| `PROV_FMAP` | `0x1703` | key | out_ptr | – | `status` | Returns FRAM slot metadata.

## Implementation Notes
- Executive retains control loop; module describes library boundaries for future extraction.
- Log state transitions (`load_start`, `chunk_ok`, `crc_fail`, `complete`) for event stream.
- Reuse mailbox for progress updates (`svc:prov.status`).
- Security: once `docs/security.md` defined, enforce auth on load/abort commands.

## Playbook
- [ ] Define manifest schema (link to `toolchain/formats/hxe.md`).
- [ ] Document CAN/SD chunking protocol, retries, error handling.
- [ ] Outline rollback strategy when FRAM writes fail mid-update.

## Tests
- See `(6)/system/Provisioning_tests.md` for provisioning + persistence suites.

## Commit Log
- _Pending_.

## Traceability
- **DR:** DR-1.1, DR-3.1, DR-5.1, DR-5.3.
- **DG:** DG-1.2, DG-3.1, DG-5.3, DG-7.3.
- **DO:** DO-relay (future remote provisioning UI).

# Value & Command Implementation Plan

## Scope
- Value registry (module 0x07) managing OID tables, metadata, persistence hooks (DR-7.1, DR-7.3, DG-7.1–7.4).
- Command registry (module 0x08) with zero-arg invocation, auth tokens, async mailbox returns (DR-7.1, DG-7.2).
- Event + transport bindings (mailbox, CAN, UART) feeding toolkit watch panels (DR-8.1, DG-8.1).

## Preconditions
- Shared ABI definitions for modules 0x07/0x08 present in `shared/abi_syscalls.md`.
- Persistence layout defined (`shared/persistence_layout.md`).
- Mailbox subsystem available for subscriptions/async responses.

## Postconditions
- Library exposes deterministic APIs for value/command operations with f16 payload handling.
- Security policy enforced (auth levels, PIN tokens) as per DR-7.1.
- Subscriptions emit events consumable by tooling/CLI.

## Public Interfaces
### Value (module 0x07)
| Func | ID | R1 | R2 | R3 | R4 | Returns | Notes |
|------|----|----|----|----|----|---------|-------|
| `VAL_REGISTER` | `0x0700` | group_id | value_id | flags | desc_ptr | `status`, `oid` | Flags include RO/Persist/Sticky/Pin/Bool. |
| `VAL_LOOKUP` | `0x0701` | group_id | value_id | – | – | `status`, `oid` | No-create lookup. |
| `VAL_GET` | `0x0702` | oid | – | – | – | `f16` in R0 low 16 bits | Enforce auth level; returns `ENOENT`. |
| `VAL_SET` | `0x0703` | oid | f16 (R2 low 16 bits) | flags | – | `status` | Applies epsilon/rate limit. |
| `VAL_LIST` | `0x0704` | group_filter | out_ptr | max_items | – | `count` | 0xFF -> all groups. |
| `VAL_SUB` | `0x0705` | oid | mailbox_ptr | flags | – | `status` | Registers mailbox for change events. |
| `VAL_PERSIST` | `0x0706` | oid | mode | – | – | `status` | Mode 0=volatile,1=load,2=load+save. |

### Command (module 0x08)
| Func | ID | R1 | R2 | R3 | R4 | Returns | Notes |
|------|----|----|----|----|----|---------|-------|
| `CMD_REGISTER` | `0x0800` | group_id | value_id | flags | desc_ptr | `status`, `oid` | Flags include PIN, async allowed. |
| `CMD_LOOKUP` | `0x0801` | group_id | value_id | – | – | `status`, `oid` | – |
| `CMD_CALL` | `0x0802` | oid | token_ptr | flags | – | `status` | Synchronous invocation. |
| `CMD_CALL_ASYNC` | `0x0803` | oid | token_ptr | mailbox_ptr | – | `status` | Posts `(oid,rc)` to mailbox. |
| `CMD_HELP` | `0x0804` | oid | out_ptr | max_len | – | `status` | Writes descriptor/help text.

## Implementation Notes
- Maintain compact entry tables (value + command) with string dedupe; align with `(3.4)val_cmd.md` data structures.
- Enforce auth levels and tokens; log attempts for future security doc.
- Hook persistence writes into provisioning/FRAM layout.
- Ensure event payloads include `oid`, `f16`/`rc` for watcher/CLI consumption.

## Playbook
- [ ] Define shared enums/structs (entries, descriptors) for Python/C.
- [ ] Document transport bindings (mailbox frame format, CAN opcodes) in formats docs.
- [ ] Outline persistence interaction with FRAM layout.

## Tests
- Refer to `(6)/system/ValCmd_tests.md` for registry/security/persistence suites.

## Commit Log
- _Pending_.

## Traceability
- **DR:** DR-3.1, DR-5.3, DR-6.1, DR-7.1, DR-7.3, DR-8.1.
- **DG:** DG-3.1, DG-3.3, DG-7.1–7.4, DG-8.1.
- **DO:** DO-7.a (bulk ops).

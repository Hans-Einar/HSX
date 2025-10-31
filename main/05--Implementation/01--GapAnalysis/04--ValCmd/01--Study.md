# Gap Analysis: ValCmd

## 1. Scope Recap

_Brief synopsis of the design document and links back to the design specification._

**Design Reference:** [04.04--ValCmd.md](../../../04--Design/04.04--ValCmd.md)

**Summary:**  
The Value & Command Layer design specifies an executive-owned service providing dynamic parameter management and control dispatch. It serves as the central telemetry and control interface for HSX applications. Key design principles include:

- **Executive-owned storage** - all registry data resides in executive heap, not HXE application memory
- **Transparent HXE access** - operator-overloaded `Value` structs provide transparent SVC-based access
- **Compact storage** - 8-byte value entries, mix-in descriptor pattern for metadata
- **Deterministic addressing** - `(group_id, value_id)` tuples forming unique 16-bit OIDs
- **PID-based isolation** - each HXE app can only access values/commands it owns
- **Declarative registration** - HXE v2 `.value`/`.cmd` sections preprocessed before VM execution
- **Transport agnostic** - delegates to mailbox for notifications, FRAM for persistence
- **Direct protocol handling** - executive responds to CAN/UART requests without VM involvement
- **Resource bounded** - statically configured registry sizes per platform

---

## 2. Current Implementation

_What already exists today that satisfies the design intent._

**Code Paths:**
- **None** - No value/command subsystem implementation exists
- VM returns `HSX_ERR_ENOSYS` for module 0x07 (VALUE) and 0x08 (COMMAND) SVC calls
- Legacy `SLEEP_MS` trap on module 0x07 exists but deprecated (line 1150 in `host_vm.py`)

**Tests:**
- **None** - No tests for value/command subsystem

**Tools:**
- **None** - No shell commands for value/command manipulation (`val.list`, `val.get`, `val.set`, `cmd.call`)

**Documentation:**
- `docs/hsx_value_interface.md` - Specification document (in Norwegian) describing the value/command interface design
- `docs/abi_syscalls.md` - Documents modules 0x07 and 0x08 as "planned" with `HSX_ERR_ENOSYS` status
- Design documents: `main/04--Design/04.04--ValCmd.md` (380 lines), `main/03--Architecture/03.04--ValCmd.md`
- No header files: `include/hsx_value.h` and `include/hsx_command.h` referenced in design but not created

---

## 3. Missing or Partial Coverage

_Gaps that block full compliance with the design._

**Open Items:**
- **Complete subsystem missing:** The entire value/command subsystem specified in the 380-line design document is not implemented. This blocks:
  - All telemetry and control workflows for HSX applications
  - External monitoring via CAN/UART
  - Runtime parameter management
  - Calibration and persistence
  - Debugger watch panels for values
- **Data structures (4.2):** No implementation of value entries, command entries, group descriptors, or mix-in descriptor types (name, unit, range, persist)
- **Registry (4.3):** No value table, command table, or OID lookup mechanisms
- **VALUE SVC module 0x07 (5.1):** All functions return `ENOSYS`:
  - `VALUE_REGISTER` - register/update value with metadata
  - `VALUE_GET` - read f16 value by OID
  - `VALUE_SET` - write f16 value with notifications
  - `VALUE_SUB` - subscribe to value changes via mailbox
  - `VALUE_PERSIST` - toggle FRAM persistence
- **COMMAND SVC module 0x08 (5.1):** All functions return `ENOSYS`:
  - `CMD_REGISTER` - register zero-argument command
  - `CMD_CALL` - synchronous command invocation
  - `CMD_CALL_ASYNC` - asynchronous command with mailbox result
  - `CMD_HELP` - retrieve help text
- **PID-based isolation (4.4.2, 6):** No enforcement of owner_pid checks - design requires tasks can only access their own values/commands
- **Declarative registration (4.4.1):** No HXE v2 `.value`/`.cmd` section parsing or preprocessing
- **String tables (4.2.6):** No deduplicated string storage for names, units, help text
- **Epsilon/rate limiting (4.4.2):** No change threshold or notification rate limiting
- **Subscription management (4.4.3):** No mailbox-based notification delivery on value changes
- **Persistence integration (4.4.4):** No FRAM write/load for persisted values with debounce
- **CAN binding (4.4.6):** No OID-to-CAN frame mapping for GET/SET/PUB/CALL operations
- **Shell/CLI integration (4.4.7):** No `val.list`, `val.get`, `val.set`, `cmd.list`, `cmd.call` commands
- **Executive RPC commands (5.3):** No value/command enumeration or manipulation via executive protocol
- **Event emission (5.2):** No `value_changed`, `value_registered`, `cmd_invoked`, `cmd_completed` events
- **C header files:** Missing `include/hsx_value.h` and `include/hsx_command.h` referenced in design
- **Operator overload wrappers (5.4):** No C `Value` struct with transparent SVC access
- **Auth level enforcement (6):** No security checks for restricted values/commands

**Deferred Features:**
- **Array/matrix support (6, 9):** Design mentions DO-7.b for future array values but explicitly defers
- **Observer mode for external access:** Design mentions CAN/UART can bypass PID checks but unclear how this integrates
- **Advanced descriptor types:** Only core descriptors specified; extensibility exists but no additional types defined

**Documentation Gaps:**
- C API examples missing - no sample HXE code showing Value wrapper usage
- No `.sym` file integration for value symbol lookup in debugger
- Missing resource budget allocation specifics (registry sizes per platform)
- No examples of HXE v2 `.value`/`.cmd` section format

---

## 4. Next Actions

_Ordered steps to close the gaps._

**Priority Actions:**

**Phase 1: Core Data Structures and Registry**
1. **Create C header files** - Define `include/hsx_value.h` and `include/hsx_command.h` with data structures per section 4.2
2. **Implement compact value entry** - 8-byte `hsx_val_entry` structure with group_id, value_id, flags, auth_level, owner_pid, last_f16, desc_head
3. **Implement compact command entry** - Similar structure for commands with handler references
4. **Implement descriptor types** - Group, Name, Unit, Range, Persist descriptors with mix-in pattern per sections 4.2.2-4.2.4
5. **String table management** - Deduplicated null-terminated string storage per section 4.2.6
6. **Registry initialization** - Fixed-size value/command tables with OID-based lookup per section 4.3

**Phase 2: Python VALUE SVC Module (0x07)**
7. **VALUE_REGISTER** - Implement registration with PID capture, table allocation, descriptor chain building per section 4.4.1
8. **VALUE_GET** - Implement read with PID verification and auth_level checks per section 4.4.2
9. **VALUE_SET** - Implement write with epsilon threshold, rate limiting, notification dispatch per section 4.4.2
10. **VALUE_SUB** - Implement mailbox subscription registration per section 4.4.3
11. **VALUE_PERSIST** - Implement persistence toggle and FRAM integration per section 4.4.4

**Phase 3: Python COMMAND SVC Module (0x08)**
12. **CMD_REGISTER** - Implement command registration with PID capture per section 4.4.1
13. **CMD_CALL** - Implement synchronous command invocation with auth checks per section 4.4.5
14. **CMD_CALL_ASYNC** - Implement asynchronous invocation with mailbox result posting
15. **CMD_HELP** - Implement help text retrieval from descriptors

**Phase 4: Executive Integration**
16. **Event emission** - Emit `value_changed`, `value_registered`, `cmd_invoked`, `cmd_completed` events per section 5.2
17. **Executive RPC commands** - Implement `val.list`, `val.get`, `val.set`, `cmd.list`, `cmd.call` per section 5.3
18. **Resource tracking** - Monitor table occupancy and string table usage against budgets

**Phase 5: HXE v2 Declarative Registration**
19. **Section parser** - Parse `.value` and `.cmd` sections from HXE header per section 4.4.1
20. **Metadata preprocessing** - Register all values/commands before VM execution per section 1.1
21. **Descriptor building** - Construct descriptor chains from section metadata

**Phase 6: Persistence and Notifications**
22. **FRAM integration** - Implement load-on-boot and debounced writes per section 4.4.4
23. **Mailbox notifications** - Deliver value change notifications to subscribers per section 4.4.3
24. **Change detection** - Implement epsilon threshold and rate_limit enforcement per section 4.4.2

**Phase 7: Transport Bindings**
25. **CAN framing** - Implement OID-to-CAN mapping for GET/SET/PUB/CALL/RET operations per section 4.4.6
26. **Shell/CLI integration** - Implement numeric and named value access per section 4.4.7
27. **UART commands** - Enable external value/command access without PID checks

**Phase 8: C Application Interface**
28. **Value wrapper struct** - Implement C `Value` type with operator overloads per section 5.4
29. **Transparent SVC access** - Overloaded cast/assignment operators invoke VALUE_GET/SET SVCs
30. **Example HXE apps** - Create sample applications demonstrating value/command usage

**Phase 9: Advanced Features**
31. **Debugger integration** - Value watch panels, symbol lookup in `.sym` files
32. **Auth token validation** - Implement Pin flag enforcement and auth_level checks per section 6
33. **PID cleanup** - Automatically clear values/commands when task terminates per section 6
34. **C port** - Implement value/command subsystem in C for MCU deployment

**Cross-References:**
- Design Requirements: DR-1.3, DR-3.1, DR-5.3, DR-6.1, DR-7.1, DR-7.3, DR-8.1
- Design Goals: DG-1.4, DG-6.1, DG-6.2, DG-7.1, DG-7.2, DG-7.3, DG-7.4, DG-8.1, DG-8.2
- Related: HXE v2 format (needs `.value`/`.cmd` section definitions), Executive event streaming, Mailbox subsystem, FRAM persistence
- Test specification: `main/06--Test/system/ValCmd_tests.md` (if created)

---

**Last Updated:** 2025-10-31  
**Status:** Not Started (Complete subsystem missing - no implementation exists)

# HSX ABI Syscall Table (Draft)

Sources:
- [main/00--Context/00--Context.md](../main/00--Context/00--Context.md)
- [main/01--Mandate/01--Mandate.md](../main/01--Mandate/01--Mandate.md)
- [main/02--Study/02--Study.md](../main/02--Study/02--Study.md)
- [main/03--Architecture/03.02--Executive.md](../main/03--Architecture/03.02--Executive.md)
- [main/03--Architecture/03.04--ValCmd.md](../main/03--Architecture/03.04--ValCmd.md)
- [docs/hsx_value_interface.md](hsx_value_interface.md)
- `platforms/python/host_vm.py`

## Calling convention

- `SVC mod, fn` traps into the executive. `mod` selects a subsystem, `fn` selects the function within that subsystem.
- `R0` carries the return value. Some calls (for example `TASK_EXIT`) pass input arguments through `R0` before the handler overwrites it on return.
- `R1`..`R5` carry positional arguments as documented below. Registers above `R5` are caller saved.
- Unknown module or function pairs set `R0 = HSX_ERR_ENOSYS` (0xFFFF_FF01). Fatal VM faults raise the other `HSX_ERR_*` codes defined in `platforms/python/host_vm.py`.
- Mailbox calls return status codes defined in `include/hsx_mailbox.h`. Success is `HSX_MBX_STATUS_OK` (0), non-blocking polls return `HSX_MBX_STATUS_NO_DATA`, descriptor pool exhaustion returns `HSX_MBX_STATUS_NO_DESCRIPTOR` (0x0005), and blocking receives that expire now return `HSX_MBX_STATUS_TIMEOUT` (0x0007).
- All return values are 32 bit. The low 16 bits carry f16 payloads where noted.

## VM ISA notes

- The Python MiniVM exposes dedicated shift instructions `LSL`, `LSR`, and `ASR` (opcodes `0x31`-`0x33`). Shift amounts are taken modulo 32; `ASR` preserves the sign bit on right shifts. Shifts update Z/N based on the result, set C to the last bit shifted out (when the amount is non-zero), and always clear V.
- `ADC` and `SBC` (opcodes `0x34`/`0x35`) use the carry flag as carry-in/no-borrow markers, updating all PSW bits (Z/C/N/V) on completion.
- `DIV` (opcode `0x13`) raises `HSX_ERR_DIV_ZERO` (`0xFFFF_FF05`) and halts the VM when the divisor is zero; otherwise it performs signed 32-bit division truncated toward zero.

## Module map

| ID | Module | Implementation status | Notes |
|----|--------|-----------------------|-------|
| 0x00 | Core instrumentation | Implemented (Python) | Exposes the MiniVM step counter for coarse timing. |
| 0x01 | Task control and stdio | Implemented (Python) | Exit trap plus raw UART write. |
| 0x02 | CAN transport | Implemented (Python) | Transmit stub used by tests and logging. |
| 0x04 | Virtual filesystem | Implemented (Python) | Backed by `FSStub`; routes stdout and stderr to mailboxes when configured. |
| 0x05 | Mailbox subsystem | Implemented (Python + shared header) | Contract shared with C via `include/hsx_mailbox.h`. |
| 0x06 | Executive control | Implemented (Python) | Executive-level services (e.g., sleep). Apps don't explicitly yield—context switching happens automatically on blocking operations. |
| 0x07 | Value service | Planned | Specified in [docs/hsx_value_interface.md](hsx_value_interface.md); not yet exposed by the Python VM. |
| 0x08 | Command service | Planned | Specified in [docs/hsx_value_interface.md](hsx_value_interface.md). |
| 0x0E | Developer libm | Optional | Enabled with `--dev-libm`; supplies sin, cos, exp helpers for testing. |

## Module 0x00 - Core instrumentation

| Fn | Mnemonic | R1 | R2 | R3 | R4 | R5 | R0 on return | Status | Notes |
|----|----------|----|----|----|----|----|--------------|--------|-------|
| 0x00 | CORE_GET_STEPS | - | - | - | - | - | Total instructions executed since boot | Implemented | Mirrors `MiniVM.steps` for coarse profiling. |

## Module 0x01 - Task control and stdio

| Fn | Mnemonic | R1 | R2 | R3 | R4 | R5 | R0 on return | Status | Notes |
|----|----------|----|----|----|----|----|--------------|--------|-------|
| 0x00 | TASK_EXIT | - | - | - | - | - | Not returned; VM stops | Implemented | Caller places the exit code in R0 on entry; handler logs and halts (`platforms/python/host_vm.py:1118`). |
| 0x01 | UART_WRITE | buf_ptr | length | - | - | - | Bytes written | Implemented | Writes UTF-8 bytes to host logging, returns the byte count (`platforms/python/host_vm.py:1122`). |

## Module 0x02 - CAN transport

| Fn | Mnemonic | R1 | R2 | R3 | R4 | R5 | R0 on return | Status | Notes |
|----|----------|----|----|----|----|----|--------------|--------|-------|
| 0x00 | CAN_TX | can_id (11 bit) | payload_ptr | length (0..8) | - | - | 0 on success | Implemented | Logs the frame and returns zero (`platforms/python/host_vm.py:1129`). |

## Module 0x04 - Virtual filesystem

| Fn | Mnemonic | R1 | R2 | R3 | R4 | R5 | R0 on return | Status | Notes |
|----|----------|----|----|----|----|----|--------------|--------|-------|
| 0x00 | FS_OPEN | path_ptr | flags | - | - | - | File descriptor or -1 | Implemented | Paths are C strings; flags passed through to `FSStub` (`platforms/python/host_vm.py:1183`). |
| 0x01 | FS_READ | fd | dst_ptr | length | - | - | Bytes read | Implemented | Copies into VM memory; zero bytes at EOF (`platforms/python/host_vm.py:1187`). |
| 0x02 | FS_WRITE | fd | src_ptr | length | - | - | Bytes written | Implemented | Routes stdout and stderr via mailbox handles when configured (`platforms/python/host_vm.py:1192`). |
| 0x03 | FS_CLOSE | fd | - | - | - | - | 0 or -1 | Implemented | Closes descriptor (`platforms/python/host_vm.py:1235`). |
| 0x0A | FS_LISTDIR | path_ptr | dst_ptr | max_len | - | - | Bytes written | Implemented | Writes newline separated listing (`platforms/python/host_vm.py:1239`). |
| 0x0B | FS_DELETE | path_ptr | - | - | - | - | 0 or -1 | Implemented | Removes file (`platforms/python/host_vm.py:1244`). |
| 0x0C | FS_RENAME | old_path_ptr | new_path_ptr | - | - | - | 0 or -1 | Implemented | Simple rename guard (`platforms/python/host_vm.py:1248`). |
| 0x0D | FS_MKDIR | path_ptr | - | - | - | - | 0 or -1 | Implemented | Stubbed to success (`platforms/python/host_vm.py:1251`). |

## Module 0x05 - Mailbox subsystem

| Fn | Mnemonic | R1 | R2 | R3 | R4 | R5 | R0 on return | Status | Notes |
|----|----------|----|----|----|----|----|--------------|--------|-------|
| 0x00 | MAILBOX_OPEN | target_ptr | flags | - | - | - | Status; R1 = handle | Implemented | Flags use `HSX_MBX_MODE_*`. Empty target selects the PID namespace (`include/hsx_mailbox.h`, `platforms/python/host_vm.py:1341`). |
| 0x01 | MAILBOX_BIND | target_ptr | capacity | mode_mask | - | - | Status; R1 = descriptor_id | Implemented | Capacity 0 uses the default ring (`platforms/python/host_vm.py:1347`). |
| 0x02 | MAILBOX_SEND | handle | payload_ptr | length | flags | channel | Status; R1 = bytes sent | Implemented | Non blocking; returns `HSX_MBX_STATUS_WOULDBLOCK` if the ring is full (`platforms/python/host_vm.py:1354`). |
| 0x03 | MAILBOX_RECV | handle | buffer_ptr | max_len | timeout | info_ptr | Status; R1 = bytes, R2 = flags, R3 = channel, R4 = src_pid | Implemented | Python handler honours finite/infinite timeouts, populates the optional info struct, and returns `HSX_MBX_STATUS_TIMEOUT` when waits expire (`platforms/python/host_vm.py:2330`). |
| 0x04 | MAILBOX_PEEK | handle | - | - | - | - | Status; R1 = depth, R2 = bytes_used, R3 = next_len | Implemented | Provides ring statistics (`platforms/python/host_vm.py:1377`). |
| 0x05 | MAILBOX_TAP | handle | enable (0 or 1) | - | - | - | Status | Implemented | Toggles tap copy (`platforms/python/host_vm.py:1384`). |
| 0x06 | MAILBOX_CLOSE | handle | - | - | - | - | Status | Implemented | Releases handle (`platforms/python/host_vm.py:1335`). |

## Module 0x06 - Executive control

| Fn | Mnemonic | R1 | R2 | R3 | R4 | R5 | R0 on return | Status | Notes |
|----|----------|----|----|----|----|----|--------------|--------|-------|
| 0x00 | EXEC_SLEEP_MS | - | - | - | - | - | 0 | Implemented | Caller supplies the sleep duration in R0 on entry; handler schedules wake-up (`platforms/python/host_vm.py:1177`). |

This module provides executive-level services that don't fit naturally in other modules. Applications should not need to be aware of scheduling details—context switching happens automatically when tasks block on mailbox operations or sleep.

## Module 0x07 - Value service (planned)

Planned per [docs/hsx_value_interface.md](hsx_value_interface.md). Calls currently receive `HSX_ERR_ENOSYS` in the Python VM.

| Fn | Mnemonic | R1 | R2 | R3 | R4 | R5 | Expected R0 | Notes |
|----|----------|----|----|----|----|----|-------------|-------|
| 0x00 | VAL_REGISTER | group_id | value_id | flags | desc_ptr | - | OID on success | Registers or updates a value entry; descriptor points to `hsx_val_desc`. |
| 0x01 | VAL_LOOKUP | group_id | value_id | - | - | - | OID or -1 | Returns existing mapping without creating it. |
| 0x02 | VAL_GET | oid | - | - | - | - | f16 value (low 16 bits) | Reads the cached f16 payload. |
| 0x03 | VAL_SET | oid | f16 payload | - | - | - | 0 or errno | Caller supplies the new f16 in the low 16 bits of R2. |
| 0x04 | VAL_LIST | group_filter | out_ptr | max_items | - | - | Count written | Emits `(oid,f16)` pairs; `group_filter = 0xFF` lists all. |
| 0x05 | VAL_META | oid | out_ptr | - | - | - | 0 or errno | Writes metadata record for the value. |
| 0x06 | VAL_SUB | oid | mailbox_ptr | - | - | - | 0 or errno | Subscribes a mailbox to on-change notifications. |
| 0x07 | VAL_PERSIST | oid | mode | - | - | - | 0 or errno | Configures FRAM binding (0 = volatile, 1 = load, 2 = load+save). |

## Module 0x08 - Command service (planned)

Planned per [docs/hsx_value_interface.md](hsx_value_interface.md). Calls currently receive `HSX_ERR_ENOSYS` in the Python VM.

| Fn | Mnemonic | R1 | R2 | R3 | R4 | R5 | Expected R0 | Notes |
|----|----------|----|----|----|----|----|-------------|-------|
| 0x00 | CMD_REGISTER | group_id | value_id | flags | desc_ptr | - | OID on success | Registers a zero argument command; descriptor carries names and auth level. |
| 0x01 | CMD_LOOKUP | group_id | value_id | - | - | - | OID or -1 | Resolves command without creating it. |
| 0x02 | CMD_CALL | oid | token_ptr | - | - | - | 0 or errno | Synchronous command execution (`token_ptr = 0` when no auth token is needed). |
| 0x03 | CMD_CALL_ASYNC | oid | token_ptr | mailbox_ptr | - | - | 0 or errno | Posts `(oid, rc)` to the mailbox when complete. |
| 0x04 | CMD_HELP | oid | out_ptr | - | - | - | 0 or errno | Writes help text or security policy summary. |

## Module 0x0E - Developer libm (optional)

| Fn | Mnemonic | R1 | R2 | R3 | R4 | R5 | R0 on return | Status | Notes |
|----|----------|----|----|----|----|----|--------------|--------|-------|
| 0x00 | LIBM_SIN_F16 | f16 argument | - | - | - | - | f16 result | Optional | Enabled with `--dev-libm`; converts the low 16 bits of R1 to f32, computes `sin`, writes the f16 result back into the low 16 bits of R0 (`platforms/python/host_vm.py:1136`). |
| 0x01 | LIBM_COS_F16 | f16 argument | - | - | - | - | f16 result | Optional | Same pattern using `cos`. |
| 0x02 | LIBM_EXP_F16 | f16 argument | - | - | - | - | f16 result | Optional | Same pattern using `exp`. |

## Open issues

- Complete the rollout by updating all payloads/tooling to issue executive control traps through module 0x06, then remove the legacy module 0x07 alias once the value and command services are available ([main/03--Architecture/03.04--ValCmd.md](../main/03--Architecture/03.04--ValCmd.md)).
- Define a canonical "module version" query (candidate: `EXEC_GET_VERSION`, module 0x06) so payloads can negotiate required capabilities with the host executive. The call should accept a module ID in `R1` and return a structured version/feature bitmap in `R0`/`R1`.
- Implement the value and command services as specified in [docs/hsx_value_interface.md](hsx_value_interface.md), wiring persistence and mailbox bindings through the executive.

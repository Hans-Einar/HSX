# MiniVM Implementation Plan

## DR/DG Alignment
- DR-2.1 / DR-2.1a / DG-2.1–2.2: Workspace-pointer register swaps remain O(1) with measurable microbench acceptance criteria.
- DR-2.3 / DG-2.3: ABI (argument registers, spill rules) honoured across Python and future C port.
- DR-8.1 / DG-4.2 / DG-5.2: Debug traps emit structured events (	race_step, debug_break) for the executive stream.

## Implementation Notes
- Maintain shared register-bank allocator used by executive; surface instrumentation to confirm O(1) context switch latency (refactorNotes: workspace-pointer remediation).
- Ensure SVC table pulls module/function IDs from forthcoming shared header (ties into DR-2.5 once header lands).
- Emit debug_stop / mailbox_wait events via emit_event, mirroring the event schema in docs/executive_protocol.md.
- Provide helper to capture stack frames (pc/sp/reg_base) for the debugger; align with unctionality/#1_TUI_DEBUGGER requirements.

## Playbook (Implementation)
- [ ] Integrate shared syscall header once generated (module IDs, EXEC_GET_VERSION).
- [ ] Finalise microbench harness proving constant-time workspace swaps (tie into DR-2.1a acceptance).
- [ ] Wire BRK/SVC event payloads to match protocol schema (seq, ts, pid, type, data).
- [ ] Document any deviations/opcode additions in docs/abi_syscalls.md and update refactor notes.

## Commit Log
- _Pending_: log commit hashes + summary here as implementation proceeds.

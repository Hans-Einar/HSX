# HSX Shell Implementation Plan

## DR/DG Alignment
- DR-8.1 / DG-8.1: Shell must interoperate with debugger session/event RPCs.
- DR-6.1 / DG-6.4: Shell listen/stdio commands respect mailbox semantics and reserved channels.
- DR-7.1 / DG-7.4: Value/command commands honour numeric addressing + security policies.

## Implementation Notes
- Update python/shell_client.py to call new session APIs (attach/detach vs hsxdbg).
- Ensure mailbox listen paths handle event categories (trace, scheduler) with filtering/back-pressure messaging.
- Keep JSON mode output stable; add version flag to detect feature availability.
- Reference refactorNotes entry for CLI modernization + event stream alignment.

## PS Command Output Format
The `ps` command displays information about loaded HXE applications:

**Output columns:**
- `PID`: Process ID
- `APP_NAME`: Application name from HXE header (with instance suffix if multiple instances allowed)
- `STATE`: Task state (running, ready, waiting_mbx, paused, etc.)
- `FILEPATH`: Source path (file path or CAN master node details like `CAN:node_id:channel`)

**Example output:**
```
PID  APP_NAME              STATE      FILEPATH
1    motor_controller_#0   running    /opt/hsx/apps/motor.hxe
2    motor_controller_#1   ready      /opt/hsx/apps/motor.hxe
3    sensor_reader         waiting    CAN:0x42:1
```

**Implementation details:**
- App names with instance suffixes (`_#0`, `_#1`) indicate multiple instances of the same application.
- Filepath shows the load source: absolute path for file loads, or `CAN:<node_id>:<channel>` for CAN-loaded apps.
- Executive maintains app_name and filepath in TaskRecord for each loaded task.

## Playbook (Implementation)
- [ ] Wire shell attach/detach to PID lock aware RPCs.
- [ ] Add commands for session.open/events.subscribe diagnostics.
- [ ] Document fallback paths for legacy servers (no event stream).
- [ ] Update ps command to display app_name and filepath columns.
- [ ] Handle instance naming in shell output formatting.

## Commit Log
- _Pending_: record shell changes + DR references as commits land.

# Gap Analysis: CLI Debugger

## 1. Scope Recap

_Brief synopsis of the design document and links back to the design specification._

**Design Reference:** [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md)

**Summary:**  
The CLI Debugger design specifies a command-line interface for debugging HSX applications. It comprises:

- **Debugger Protocol** - Session management, event streaming, and runtime control between debugger clients and executive
- **CLI Frontend** - Interactive REPL and scriptable JSON commands for automation
- **Session Isolation** - PID locking to prevent conflicting debugger operations
- **Event-Driven Architecture** - Real-time state updates without polling
- **Protocol Versioning** - Capability negotiation for graceful degradation

**Dependencies:**
- Built on `hsxdbg` core package (see [06--Toolkit](../06--Toolkit/01--Study.md))
- Requires executive debugger RPC APIs (see [02--Executive](../02--Executive/01--Study.md))
- Requires toolchain symbol metadata (see [05--Toolchain](../05--Toolchain/01--Study.md))

---

## 2. Current Implementation

_What already exists today that satisfies the design intent._

**Code Paths:**
- **Shell Client:** `python/shell_client.py` (1,574 lines) - provides basic REPL but not formal debugger
  - Basic step/resume/pause commands
  - Executive command execution (ps, load, clock, etc.)
  - Mailbox listening and stdio streaming
  - Basic JSON output mode
  - Tab completion (command-level, not symbol-aware)
  - Session history (not persistent)
- **No dedicated CLI debugger implementation** - debugger commands mixed with shell commands

**Tests:**
- `python/tests/test_debugger_basic.py` (98 lines) - Basic debugger function tests
- **Minimal coverage** - no protocol tests, no session management tests, no event streaming tests

**Tools:**
- `python/shell_client.py` - Standalone shell CLI with basic debug commands

**Documentation:**
- `docs/executive_protocol.md` - Executive RPC protocol (incomplete for debugger)
- Design documents: `main/04--Design/04.09--Debugger.md`
- Implementation notes: `main/05--Implementation/toolkit/debugger.md`, `debugger_implementation.md`

---

## 3. Missing or Partial Coverage

_Gaps that block full compliance with the design._

**Open Items:**
- **Structured debugger protocol (5):** Design specifies complete session management, event streaming, and control protocol. Shell client has basic commands but no formal protocol implementation.
- **Session management (5.1):** No `session.open`/`close` with capability negotiation, heartbeats, or PID locking
- **Event streaming (5.2):** No event subscription, no async event delivery, no back-pressure handling
- **Breakpoint management (5.3):** No `set_breakpoint`, `clear_breakpoint`, `list_breakpoints` commands
- **Stack reconstruction (5.4):** No `stack.backtrace` with frame unwinding and symbol resolution
- **Watch expressions (5.5):** No watch variable management or update notifications
- **Memory inspection (5.6):** No formatted memory dumps or region queries
- **Disassembly (5.7):** No instruction disassembly with symbol annotations
- **Comprehensive JSON output (6.2):** Design specifies machine-readable output for CI/CD. Shell has basic JSON but not comprehensive for all debugger operations.
- **Context-aware completion (6.3):** Design specifies tab completion for commands, symbols, addresses. Shell has basic completion but not debugger-aware.
- **Persistent history (6.4):** Design specifies history across sessions. Shell has session history but not persistent.
- **Protocol error handling (7):** Missing reconnection logic, protocol mismatch handling, session conflict messaging

**Deferred Features:**
- **Reverse debugging:** Recording and replay of execution
- **Watchpoints:** Data breakpoints on memory/register changes
- **Conditional breakpoints:** Breakpoints with expressions

**Documentation Gaps:**
- No user guide for CLI debugger commands and workflows
- No examples of JSON automation scripts for CI/CD
- Protocol specification incomplete in `executive_protocol.md`

---

## 4. Next Actions

_Ordered steps to close the gaps._

**Priority Actions:**

**Phase 1: CLI Framework (requires hsxdbg core from 06--Toolkit Phase 1-3)**
1. **Refactor shell_client** - Separate shell commands from debugger commands into distinct modules
2. **Create CLI debugger module** - New `hsx-dbg` command-line tool built on `hsxdbg` core
3. **Command parser** - Implement REPL using `prompt_toolkit` with command parsing and validation
4. **JSON output mode** - Structured JSON output for all commands with `--json` flag

**Phase 2: Session Management Commands**
5. **Attach/detach commands** - `attach <pid>`, `detach`, `observer <pid>` implementing session protocol 5.1
6. **Session info commands** - `session info`, `session list` showing active sessions and locks
7. **Keepalive handling** - Automatic keepalive messages per heartbeat interval

**Phase 3: Breakpoint Management**
8. **Set breakpoints** - `break <addr/symbol>`, `break <file>:<line>` per section 5.3
9. **Clear breakpoints** - `delete <bp_id>`, `clear <addr/symbol>`
10. **List breakpoints** - `info breakpoints` showing all breakpoints with hit counts
11. **Enable/disable** - `enable <bp_id>`, `disable <bp_id>` without deletion

**Phase 4: Inspection Commands**
12. **Stack commands** - `backtrace`, `frame <n>`, `up`, `down` per section 5.4
13. **Watch commands** - `watch <var>`, `unwatch <var>`, `list watches` per section 5.5
14. **Memory commands** - `x/<fmt> <addr>`, `dump <start> <end>` per section 5.6
15. **Disassembly commands** - `disasm <addr/symbol>`, `disasm /s` (with source) per section 5.7

**Phase 5: Advanced Features**
16. **Context-aware completion** - Tab completion for symbols, addresses, registers using symbol files
17. **Persistent history** - Save command history to `~/.hsx_history` across sessions
18. **Scripting support** - Execute command files with `-x <script>` flag
19. **Error handling** - Protocol error recovery, reconnection logic per section 7

**Phase 6: Testing and Documentation**
20. **Expand test coverage** - Protocol tests, session management tests, command parsing tests
21. **Integration tests** - Full debugging workflows (attach, set breakpoints, step, inspect, detach)
22. **User guide** - Comprehensive CLI debugger command reference with examples
23. **Automation examples** - Sample JSON scripts for CI/CD integration

**Cross-References:**
- Design Requirements: DR-8.1, DG-8.1, DG-8.2, DG-8.3
- Dependencies: `hsxdbg` core package [06--Toolkit](../06--Toolkit/01--Study.md) Phases 1-3
- Executive debugger APIs [02--Executive](../02--Executive/01--Study.md) Phase 4
- Toolchain symbol files [05--Toolchain](../05--Toolchain/01--Study.md) Phase 3

---

**Last Updated:** 2025-10-31  
**Status:** Minimal (Basic commands in shell_client, formal CLI debugger not implemented)

# Gap Analysis: Toolkit

## 1. Scope Recap

_Brief synopsis of the design document and links back to the design specification._

**Design Reference:** [04.06--Toolkit.md](../../../04--Design/04.06--Toolkit.md)

**Summary:**  
The Toolkit design specifies user-facing interfaces to the HSX runtime, coordinating all operations through executive RPC. It comprises:

- **Process Manager** (`hsx_manager.py`) - lifecycle coordinator for MiniVM, Executive, and Shell components
- **Debugger Core** (`hsxdbg` package) - shared functionality including transport, session management, event bus, state cache, and command layer
- **CLI Debugger** - interactive REPL and scriptable JSON commands for automation
- **TUI Debugger** - Textual-based visual debugger (see [04.10--TUI_Debugger.md](../../../04--Design/04.10--TUI_Debugger.md))
- **VS Code Integration** - Debug Adapter Protocol support (see [04.11--vscode_debugger.md](../../../04--Design/04.11--vscode_debugger.md))
- **Cross-platform packaging** - distribution for Windows, macOS, and Linux

**Related Specifications:**
- [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md) - Debugger protocol and CLI implementation
- [04.10--TUI_Debugger.md](../../../04--Design/04.10--TUI_Debugger.md) - TUI debugger specification
- [04.11--vscode_debugger.md](../../../04--Design/04.11--vscode_debugger.md) - VS Code debugger integration

---

## 2. Current Implementation

_What already exists today that satisfies the design intent._

**Code Paths:**
- **Process Manager:** `python/hsx_manager.py` (362 lines)
  - Interactive command prompt with help system
  - Component lifecycle management (start/stop/restart for vm/exec/shell)
  - Status monitoring for all components
  - Load command forwarding to executive
  - Graceful shutdown with timeout handling
  - Cross-platform terminal detection and spawning
- **Shell Client:** `python/shell_client.py` (1,574 lines)
  - Interactive REPL connecting to executive RPC
  - Executive command execution (ps, load, clock, step, etc.)
  - Mailbox listening and stdio streaming
  - JSON output mode for automation
  - Tab completion and command history
- **Visual Monitor:** `python/blinkenlights.py` (451 lines)
  - Real-time visual monitoring of mailbox activity
  - Not in design spec but provides observability
- **Debugger Core Package:** **Not implemented** - `hsxdbg` package does not exist
  - No transport layer module
  - No session manager module
  - No event bus module
  - No state cache module
  - No command layer module
- **CLI Debugger:** **Minimal implementation** in shell_client.py
  - Basic step/resume/pause commands exist
  - No dedicated debugger mode or structured protocol
  - No breakpoint management
  - No stack reconstruction
  - No watch expressions
  - No JSON output for automation
- **TUI Debugger:** **Not implemented** - no Textual-based visual debugger
- **VS Code Integration:** **Not implemented** - no Debug Adapter Protocol support

**Tests:**
- `python/tests/test_shell_client.py` (123 lines) - Shell client unit tests
- `python/tests/test_debugger_basic.py` (98 lines) - Basic debugger function tests
- **Total test coverage:** 221 lines across 2 test files (minimal)

**Tools:**
- `python/hsx_manager.py` - Standalone manager CLI
- `python/shell_client.py` - Standalone shell CLI with basic debug commands
- `python/blinkenlights.py` - Visual monitoring tool

**Documentation:**
- `docs/executive_protocol.md` - Executive RPC protocol specification
- Design documents: `main/04--Design/04.06--Toolkit.md`, `04.09--Debugger.md`, `04.10--TUI_Debugger.md`, `04.11--vscode_debugger.md`
- Architecture: `main/03--Architecture/03.05--Toolkit.md` (focuses on shell/debugger concept)
- Implementation notes: `main/05--Implementation/toolkit/debugger.md`, `debugger_implementation.md`

---

## 3. Missing or Partial Coverage

_Gaps that block full compliance with the design._

**Open Items:**

**Manager (6.1-6.3):**
- **Logging system (6.3):** Design specifies capturing component stdout/stderr to log files. Not implemented - output goes to console only.
- **Configuration file (6.3):** Design specifies config file support for default ports and paths. Not implemented - uses hardcoded defaults.
- **Health checks (6.3):** Design mentions periodic verification of component health. Not implemented - no automatic health monitoring.
- **Automated restart (6.3):** Design mentions detecting crashes and restarting components. Not implemented - manual restart only.

**Debugger Core Package (4.2.1, 5):**
- **Complete `hsxdbg` package missing:** Design specifies comprehensive Python module with 5 major components. Package does not exist.
  - **Transport layer (`hsxdbg.transport`):** JSON-over-TCP RPC with connection management, request/response handling, reconnection logic
  - **Session manager (`hsxdbg.session`):** Connection lifecycle, protocol negotiation, PID attachments, session state
  - **Event bus (`hsxdbg.events`):** Async dispatcher for event streaming with bounded queues
  - **State cache (`hsxdbg.cache`):** Register/memory/stack/watch/mailbox caching to minimize RPC round-trips
  - **Command layer (`hsxdbg.commands`):** Typed command helpers (`step`, `resume`, `set_breakpoint`, `read_memory`)

**CLI Debugger:** See dedicated study [09--Debugger](../09--Debugger/01--Study.md)

**TUI Debugger:** See dedicated study [10--TUI_Debugger](../10--TUI_Debugger/01--Study.md)

**VS Code Integration:** See dedicated study [11--vscode_debugger](../11--vscode_debugger/01--Study.md)

**Executive Integration:**
- **Debugger RPC APIs missing:** Design assumes executive implements session/event/debugger RPCs. Executive gap analysis shows these are not implemented (see 02--Executive study).
- **Symbol loading:** Design assumes executive loads .sym files. Not implemented in executive.
- **Event emission:** Design requires executive to emit structured events. Event streaming infrastructure missing in executive.

**Deferred Features:**
- **Remote debugging relay (DO-relay):** TCP relay for debugging remote/embedded targets
- **Multi-session support:** Concurrent debugging of multiple PIDs
- **Manager clustering:** Coordinating multiple manager instances

**Documentation Gaps:**
- Executive protocol specification incomplete - debugger RPCs not fully documented in `executive_protocol.md`
- No packaging/distribution instructions for cross-platform installers
- No examples of manager configuration files

---

## 4. Next Actions

_Ordered steps to close the gaps._

**Priority Actions:**

**Phase 1: Debugger Core Infrastructure (coordinates with Executive Phase 4)**
1. **Create `hsxdbg` package structure** - Initialize Python package with proper module organization
2. **Implement transport layer** - JSON-over-TCP RPC client with connection management, timeout handling, reconnection logic
3. **Implement session manager** - Connection lifecycle, capability negotiation per section 5.1, session state tracking
4. **Implement command layer** - Typed helpers for debugger operations (`step`, `resume`, `read_memory`, etc.)
5. **Protocol specification** - Formalize JSON schemas for debugger RPC messages per section 5

**Phase 2: Event Streaming (coordinates with Executive Phase 4)**
6. **Implement event bus** - Async event dispatcher with bounded queues, subscriber management
7. **Event protocol** - Define event schemas for `trace_step`, `debug_break`, `mailbox_*`, `scheduler`, `watch_update`, `stdout/stderr`
8. **Back-pressure handling** - Queue overflow detection, slow-down requests per section 5.2.3
9. **Event filtering** - Selective subscription by event type and PID

**Phase 3: State Cache**
10. **Implement cache module** - Mirror registers, memory ranges, call stacks, watches, mailbox descriptors
11. **Cache invalidation** - Update cache on events, invalidate on control operations
12. **Cache query API** - Efficient local queries without RPC round-trips

**Phase 4: Manager Enhancements**
13. **Logging system** - Capture component stdout/stderr to log files with rotation
14. **Configuration file** - YAML/TOML config for ports, paths, component options
15. **Health checks** - Periodic component health verification with alerts
16. **Automated restart** - Crash detection and automatic component restart

**Phase 5: Testing and Documentation**
17. **Expand test coverage** - Unit tests for debugger core modules (transport, session, events, cache, commands)
18. **Integration tests** - Manager lifecycle tests, debugger core integration tests
19. **User guide** - Manager commands and configuration documentation
20. **Packaging** - Cross-platform installers for Windows, macOS, Linux

**Cross-References:**
- Design Requirements: DR-1.3, DR-3.1, DR-8.1
- Design Goals: DG-1.4, DG-8.1, DG-8.2, DG-8.3
- Related: Executive debugger APIs (session, events, stack, symbols, breakpoints) - see 02--Executive Phase 4
- Dependencies: Executive must implement debugger RPC APIs before full debugger functionality possible
- Toolchain symbol generation (.sym files) - see 05--Toolchain Phase 3
- **Debugger frontends:** CLI debugger [09--Debugger](../09--Debugger/01--Study.md), TUI [10--TUI_Debugger](../10--TUI_Debugger/01--Study.md), VS Code [11--vscode_debugger](../11--vscode_debugger/01--Study.md)

---

**Last Updated:** 2025-10-31  
**Status:** Partially Implemented (Manager functional, `hsxdbg` core package missing, debugger frontends in separate studies)

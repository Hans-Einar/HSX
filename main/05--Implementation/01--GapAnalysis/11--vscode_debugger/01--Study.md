# Gap Analysis: VS Code Debugger

## 1. Scope Recap

_Brief synopsis of the design document and links back to the design specification._

**Design Reference:** [04.11--vscode_debugger.md](../../../04--Design/04.11--vscode_debugger.md)

**Summary:**  
The VS Code Debugger design specifies Debug Adapter Protocol integration for IDE-native debugging. It comprises:

- **Debug Adapter Protocol (DAP)** - Protocol translation between DAP and HSX executive RPC
- **VS Code Extension** - Debug configuration UI and adapter lifecycle management
- **Source-Level Debugging** - Breakpoints, stepping, variable inspection at source line granularity
- **Symbol Loader** - Maps between source lines and instruction addresses using .sym files
- **Cross-Platform Support** - Windows, macOS, Linux development environments

**Dependencies:**
- Built on `hsxdbg` core package (see [06--Toolkit](../06--Toolkit/01--Study.md))
- Requires executive debugger RPC APIs (see [02--Executive](../02--Executive/01--Study.md))
- Requires toolchain .sym files with source line mapping (see [05--Toolchain](../05--Toolchain/01--Study.md))

---

## 2. Current Implementation

_What already exists today that satisfies the design intent._

**Code Paths:**
- **No VS Code integration** - Complete DAP adapter and extension missing

**Tests:**
- **No DAP tests** - No test coverage

**Tools:**
- None

**Documentation:**
- Design documents: `main/04--Design/04.11--vscode_debugger.md`
- Implementation notes: `main/05--Implementation/toolchain/vscode_debugger.md`

---

## 3. Missing or Partial Coverage

_Gaps that block full compliance with the design._

**Open Items:**
- **Complete DAP adapter missing:** Design specifies Debug Adapter Protocol implementation. Not implemented.
- **Debug adapter process (5):** No `hsx-dap.py` Python process implementing DAP server
- **Protocol messages (5.1):** No DAP request/response handling:
  - No `initialize` capability negotiation
  - No `launch`/`attach` session management
  - No `setBreakpoints` source-level breakpoint mapping
  - No `continue`/`next`/`stepIn`/`stepOut` execution control
  - No `pause` interrupt support
  - No `stackTrace` with source locations
  - No `scopes`/`variables` inspection
  - No `evaluate` expression evaluation
  - No `disconnect` session cleanup
- **Symbol loader (5.3):** No .sym file reader for source ↔ address mapping
- **Executive client (5.4):** No HSX executive RPC protocol integration
- **VS Code extension (6):** No extension package:
  - No `package.json` with debugger contribution
  - No launch configuration UI (`launch.json` templates)
  - No adapter process spawning and lifecycle
  - No debugging commands in VS Code command palette
- **Source-level abstraction (5.2):** No mapping between instruction-level and source-level operations
- **Breakpoint synchronization:** No translation between IDE and executive breakpoints
- **Variable inspection:** No register/memory display in VS Code variables view

**Deferred Features:**
- **Attach to running process:** Currently only `launch` mode planned
- **Remote debugging:** Attach to HSX runtime on different machine
- **Data breakpoints:** Watchpoints in VS Code UI

**Documentation Gaps:**
- No user guide for VS Code debugging setup and workflows
- No examples of `launch.json` configurations
- No troubleshooting guide for common DAP issues

---

## 4. Next Actions

_Ordered steps to close the gaps._

**Priority Actions:**

**Phase 1: DAP Adapter Foundation (requires hsxdbg core from 06--Toolkit Phase 1-3)**
1. **Create DAP adapter module** - New `hsx-dap.py` implementing Debug Adapter Protocol server
2. **DAP base class** - Abstract base implementing stdio/TCP communication per DAP spec
3. **Executive client integration** - Use `hsxdbg` core for HSX executive RPC connection
4. **Symbol loader** - Read .sym files and build source line → address mappings

**Phase 2: Core DAP Requests**
5. **Initialize request** - Capability negotiation (breakpoints, stepping, variables)
6. **Launch request** - Start debug session with HXE path, spawn executive if needed
7. **SetBreakpoints request** - Map source file:line to addresses, set executive breakpoints
8. **Execution control** - Implement `continue`, `next`, `stepIn`, `stepOut`, `pause` requests
9. **Disconnect request** - Clean up session and close connections

**Phase 3: Inspection Requests**
10. **StackTrace request** - Retrieve call stack from executive, map addresses to source locations
11. **Scopes request** - Enumerate variable scopes (registers, locals, globals)
12. **Variables request** - Retrieve register/memory values formatted for VS Code
13. **Evaluate request** - Support watch expressions and hover queries

**Phase 4: Event Handling**
14. **DAP events** - Translate executive events to DAP events:
  - `debug_break` → `stopped` event
  - `trace_step` → `stopped` event (step complete)
  - `stdout/stderr` → `output` event
15. **Source mapping** - Convert instruction addresses in events to source locations
16. **Thread management** - Map HSX PIDs to DAP thread IDs

**Phase 5: VS Code Extension**
17. **Extension scaffold** - Create VS Code extension project with TypeScript
18. **Package.json** - Define debugger contribution and activation events
19. **Launch configuration** - Provide `launch.json` templates for HXE debugging
20. **Adapter lifecycle** - Spawn and manage `hsx-dap.py` process
21. **Debug commands** - Add VS Code commands for HSX-specific operations

**Phase 6: Testing and Polish**
22. **DAP protocol tests** - Validate request/response handling against DAP spec
23. **End-to-end tests** - Full debugging workflows in VS Code with mock executive
24. **Error handling** - Clear error messages for common failure modes
25. **Performance** - Optimize symbol lookups and event processing for responsiveness

**Phase 7: Documentation and Distribution**
26. **User guide** - VS Code debugging tutorial with screenshots
27. **Launch.json examples** - Sample configurations for common scenarios
28. **Extension packaging** - VSIX bundle for VS Code marketplace distribution
29. **Troubleshooting guide** - Common issues and solutions

**Cross-References:**
- Design Requirements: DR-8.1, DG-8.1, DG-8.3
- Dependencies: `hsxdbg` core package [06--Toolkit](../06--Toolkit/01--Study.md) Phases 1-3
- Executive debugger APIs [02--Executive](../02--Executive/01--Study.md) Phase 4
- Toolchain .sym files [05--Toolchain](../05--Toolchain/01--Study.md) Phase 3
- DAP Specification: https://microsoft.github.io/debug-adapter-protocol/

---

**Last Updated:** 2025-10-31  
**Status:** Not Started (Complete DAP adapter and VS Code extension missing)

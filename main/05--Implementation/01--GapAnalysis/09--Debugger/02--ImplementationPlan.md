# CLI Debugger Implementation Plan

## Planned Implementation Order (Grand Plan)

1. Phase 1 - Python CLI debugger core built on the executive RPC layer.
2. Phase 2 - Event and trace integration once executive streaming is available.
3. Phase 3 - Advanced debugger features (breakpoints, watch, scripting).
4. Phase 4 - Documentation, UX polish, and regression coverage.
5. Phase 5 - C integration and packaging (deferred).
6. Phase 6 - Extended distribution targets (deferred).
7. Phase 7 - Disassembly remediation and VS Code parity.
8. Phase 8 - Breakpoint & connection resiliency.

## Sprint Scope

Deliver the Python-first work in Phases 1 through 4 this sprint. Keep the Phase 5 and 6 C/distribution items out of scope and log discoveries for the deferred backlog.

## Overview

This implementation plan addresses the gaps identified in the CLI Debugger Study document ([01--Study.md](./01--Study.md)). The plan is organized chronologically with clear dependencies tracked in [DependencyTree.md](../DependencyTree.md).

**Design Reference:** [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md)

**Note:** Basic shell commands exist in `shell_client.py`, but formal CLI debugger with structured protocol is missing. This plan builds a dedicated `hsx-dbg` command-line debugger.

---
# CLI Debugger Implementation Plan

## Overview

This implementation plan addresses the gaps identified in the CLI Debugger Study document ([01--Study.md](./01--Study.md)). The plan is organized chronologically with clear dependencies tracked in [DependencyTree.md](../DependencyTree.md).

**Design Reference:** [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md)

**Note:** Basic shell commands exist in `shell_client.py`, but formal CLI debugger with structured protocol is missing. This plan builds a dedicated `hsx-dbg` command-line debugger.

---

## Phase 1: CLI Framework

### 1.1 Refactor shell_client

**Priority:** MEDIUM  
**Dependencies:** Toolkit Phase 1-3 (hsxdbg core package)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Separate shell commands from debugger commands. Prepare for dedicated CLI debugger tool.

**Todo:**
- [ ] Review `python/shell_client.py` (1,574 lines)
- [ ] Identify shell-specific vs debugger-specific commands
- [ ] Extract debugger command logic into separate module
- [ ] Keep shell_client for general executive interaction
- [ ] Document separation rationale

---

### 1.2 Create CLI Debugger Module

**Priority:** HIGH  
**Dependencies:** 1.1 (Refactoring), Toolkit Phase 1-3 (hsxdbg core)  
**Estimated Effort:** 3-4 days

**Rationale:**  
New dedicated `hsx-dbg` command-line tool built on `hsxdbg` core package (from Toolkit module).

**Todo:**
- [x] Create `python/hsx_dbg.py` as main entry point
- [x] Integrate with `hsxdbg` core package
- [x] Implement basic REPL loop
- [x] Add command-line argument parsing (--host, --port, --json, etc.)
- [x] Add logging and error handling
- [x] Create CLI debugger tests
- [x] Document CLI debugger usage

---

### 1.3 Command Parser

**Priority:** HIGH  
**Dependencies:** 1.2 (CLI module)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Implement REPL using `prompt_toolkit` with command parsing and validation. Design specifies structured command interface.

**Todo:**
- [x] Install `prompt_toolkit` dependency
- [x] Implement command parser with subcommands
- [x] Add command validation and help system
- [x] Implement command history
- [x] Add multiline command support
- [x] Implement command aliases
- [x] Add parser tests
- [x] Document command syntax

---

### 1.4 JSON Output Mode

**Priority:** MEDIUM  
**Dependencies:** 1.2 (CLI module), 1.3 (Parser)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies machine-readable output for CI/CD (section 6.2). Enables automation and scripting.

**Todo:**
- [x] Add `--json` flag to CLI arguments
- [x] Implement JSON formatter for all command outputs
- [x] Ensure consistent JSON schema across commands
- [x] Add error reporting in JSON format
- [x] Add JSON output tests
- [x] Document JSON output format

---

## Phase 2: Session Management Commands

### 2.1 Attach/Detach Commands

**Priority:** HIGH  
**Dependencies:** Executive Phase 1.1 (Session management), Toolkit Phase 1-3  
**Estimated Effort:** 3-4 days

**Rationale:**  
Implement session attach/detach commands per protocol 5.1. The current executive exposes a global attach (no pid argument); observer mode remains a future enhancement once PID-level locks are available.

**Todo:**
- [x] Implement `attach` command (wraps current executive attach semantics)
- [x] Implement `detach` command (release global lock)
- [ ] Implement `observer <pid>` command (read-only session)
- [x] Handle session conflicts (PID already locked)
- [x] Add session state tracking (status/ps/info)
- [x] Add attach/detach tests
- [x] Document session commands (help topics, README)

---

### 2.2 Session Info Commands

**Priority:** MEDIUM  
**Dependencies:** 2.1 (Attach/detach)  
**Estimated Effort:** 1-2 days

**Rationale:**  
`session info`, `session list` commands show active sessions and locks. Helps manage multi-user scenarios.

**Todo:**
- [x] Implement `session info` command (current session details)
- [x] Implement `session list` command (all active sessions)
- [x] Display session capabilities
- [x] Show PID locks and owners
- [x] Add session info tests
- [x] Document session info commands

---

### 2.3 Keepalive Handling

**Priority:** LOW  
**Dependencies:** 2.1 (Attach/detach)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Automatic keepalive messages per heartbeat interval. Prevents session timeout.

**Todo:**
- [x] Implement automatic keepalive timer
- [x] Send keepalive messages at configured interval
- [x] Handle keepalive failures (reconnect or error)
- [x] Add keepalive configuration options
- [x] Add keepalive tests
- [x] Document keepalive behavior

---

## Phase 3: Breakpoint Management

### 3.1 Set Breakpoints

**Priority:** HIGH  
**Dependencies:** Executive Phase 1.3 (Breakpoint management), Toolchain Phase 3 (Symbol files)  
**Estimated Effort:** 3-4 days

**Rationale:**  
`break <addr/symbol>`, `break <file>:<line>` commands per section 5.3. Essential debugger functionality.

**Todo:**
- [x] Implement `break <address>` command (numeric address)
- [x] Implement `break <symbol>` command (function name)
- [x] Implement `break <file>:<line>` command (source location)
- [x] Resolve symbols using .sym files
- [x] Map source lines to addresses
- [x] Handle breakpoint set confirmation
- [x] Add breakpoint set tests
- [x] Document breakpoint syntax

---

### 3.2 Clear Breakpoints

**Priority:** HIGH  
**Dependencies:** 3.1 (Set breakpoints)  
**Estimated Effort:** 1-2 days

**Rationale:**  
`delete <bp_id>`, `clear <addr/symbol>` commands remove breakpoints.

**Todo:**
- [x] Implement `delete <bp_id>` command (by ID)
- [x] Implement `clear <addr/symbol>` command (by location)
- [x] Implement `clear` command (all breakpoints)
- [x] Handle breakpoint removal confirmation
- [x] Add clear breakpoint tests
- [x] Document clear commands

---

### 3.3 List Breakpoints

**Priority:** MEDIUM  
**Dependencies:** 3.1 (Set breakpoints)  
**Estimated Effort:** 1-2 days

**Rationale:**  
`info breakpoints` command shows all breakpoints with hit counts.

**Todo:**
- [x] Implement `info breakpoints` command
- [x] Display breakpoint ID, location, type, enabled status (mark disabled entries)
- [x] Show hit counts if available
- [x] Format output as table
- [x] Add JSON output for `info breakpoints`
- [x] Add list breakpoint tests
- [x] Document info breakpoints command

---

### 3.4 Enable/Disable Breakpoints

**Priority:** LOW  
**Dependencies:** 3.1 (Set breakpoints)  
**Estimated Effort:** 1 day

**Rationale:**  
`enable <bp_id>`, `disable <bp_id>` commands toggle breakpoints without deletion.

**Todo:**
- [x] Implement `enable <bp_id>` command (CLI-managed reapply)
- [x] Implement `disable <bp_id>` command (CLI-managed removal)
- [x] Update breakpoint state in executive
- [x] Add enable/disable tests
- [x] Document enable/disable commands

---

## Phase 4: Inspection Commands

### 4.1 Stack Commands

**Priority:** HIGH  
**Dependencies:** Executive Phase 1.5 (Stack reconstruction), Toolchain Phase 3 (Symbols)  
**Estimated Effort:** 3-4 days

**Rationale:**  
`backtrace`, `frame <n>`, `up`, `down` commands per section 5.4. Essential for understanding program state.

**Todo:**
- [x] Implement `backtrace` command (show call stack)
- [x] Implement `frame <n>` command (select frame)
- [x] Implement `up` command (move to caller frame)
- [x] Implement `down` command (move to callee frame)
- [x] Display frame info with source locations
- [x] Map addresses to function names using symbols
- [x] Add stack command tests
- [x] Document stack commands

---

### 4.2 Watch Commands

**Priority:** MEDIUM  
**Dependencies:** Executive Phase 2.3 (Watch expressions)  
**Estimated Effort:** 2-3 days

**Rationale:**  
`watch <var>`, `unwatch <var>`, `list watches` commands per section 5.5. Monitor variable changes.

**Todo:**
- [x] Implement `watch <variable>` command
- [x] Implement `watch <address>` command
- [x] Implement `unwatch <watch_id>` command
- [x] Implement `list watches` command
- [x] Display watch values and change notifications
- [x] Add watch command tests
- [x] Document watch commands

---

### 4.3 Memory Commands

**Priority:** MEDIUM  
**Dependencies:** Executive (Memory inspection APIs)  
**Estimated Effort:** 2-3 days

**Rationale:**  
`x/<fmt> <addr>`, `dump <start> <end>` commands per section 5.6. Inspect memory contents.

**Todo:**
- [x] Implement `x/<format> <address>` command (examine memory)
- [x] Support format specifiers (x=hex, d=decimal, i=instruction, s=string)
- [x] Implement `dump <start> <end>` command (hex dump)
- [x] Add ASCII preview for dumps
- [x] Add memory command tests
- [x] Document memory commands

---

### 4.4 Disassembly Commands

**Priority:** MEDIUM  
**Dependencies:** Executive Phase 1.6 (Disassembly API), Toolchain Phase 3 (Symbols)  
**Estimated Effort:** 2-3 days

**Rationale:**  
`disasm <addr/symbol>`, `disasm /s` commands per section 5.7. View assembly instructions with symbols.

**Todo:**
- [x] Implement `disasm <address>` command (disassemble at address)
- [x] Implement `disasm <symbol>` command (disassemble function)
- [x] Implement `disasm /s` flag (show source lines)
- [x] Annotate instructions with symbol names
- [x] Highlight current PC
- [x] Add disassembly command tests
- [x] Document disassembly commands

---

## Phase 5: Advanced Features

### 5.1 Context-Aware Completion

**Priority:** LOW  
**Dependencies:** Toolchain Phase 3 (Symbol files)  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies tab completion for commands, symbols, addresses, registers using symbol files (section 6.3).

**Todo:**
- [x] Implement command name completion
- [x] Implement symbol name completion (functions, variables)
- [x] Implement register name completion
- [x] Implement file path completion
- [x] Load symbols from .sym files
- [x] Integrate with prompt_toolkit completion API
- [x] Add completion tests
- [x] Document completion behavior

---

### 5.2 Persistent History

**Priority:** LOW  
**Dependencies:** 1.3 (Command parser)  
**Estimated Effort:** 1 day

**Rationale:**  
Design specifies history across sessions (section 6.4). Save to `~/.hsx_history`.

**Todo:**
- [x] Implement history save to `~/.hsx_history`
- [x] Implement history load on startup
- [x] Limit history size (configurable)
- [x] Add history search (Ctrl+R)
- [x] Add history tests
- [x] Document history file location

---

### 5.3 Scripting Support

**Priority:** LOW  
**Dependencies:** 1.3 (Command parser)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Execute command files with `-x <script>` flag. Enables automated debugging workflows.

**Todo:**
- [x] Add `-x <script>` command-line flag
- [x] Implement script file execution (read and execute commands)
- [x] Support comments in script files
- [x] Add error handling for script errors
- [x] Add scripting tests
- [x] Document script file format

---

### 5.4 Error Handling

**Priority:** MEDIUM  
**Dependencies:** Phase 2 (Session management)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Protocol error recovery, reconnection logic per section 7. Robust error handling.

**Todo:**
- [x] Implement connection loss detection
- [x] Add automatic reconnection with backoff
- [x] Handle protocol version mismatches gracefully
- [x] Display clear error messages for user
- [x] Add error recovery tests
- [x] Document error handling behavior

---

## Phase 6: Testing and Documentation

### 6.1 Expand Test Coverage

**Priority:** MEDIUM  
**Dependencies:** Phases 1-5 complete  
**Estimated Effort:** 1 week

**Rationale:**  
Protocol tests, session management tests, command parsing tests ensure quality.

**Todo:**
- [ ] Add protocol message tests
- [ ] Add session management tests (attach, detach, conflicts)
- [ ] Add command parser tests (valid/invalid syntax)
- [ ] Add integration tests (full debugging workflows)
- [ ] Measure test coverage (target >80%)
- [ ] Add tests to CI pipeline
- [ ] Document test architecture

---

### 6.2 Integration Tests

**Priority:** MEDIUM  
**Dependencies:** 6.1 (Test coverage)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Full debugging workflows: attach, set breakpoints, step, inspect, detach.

**Todo:**
- [ ] Create end-to-end test scenarios
- [ ] Test attach to running task
- [ ] Test breakpoint workflow (set, hit, continue)
- [ ] Test stepping workflow (step, next, finish)
- [ ] Test inspection workflow (registers, stack, memory)
- [ ] Test error scenarios (connection loss, invalid commands)
- [ ] Document integration test suite

---

### 6.3 User Guide

**Priority:** HIGH  
**Dependencies:** Phases 1-5 complete  
**Estimated Effort:** 3-4 days

**Rationale:**  
Comprehensive CLI debugger command reference with examples. Essential for users.

**Todo:**
- [ ] Write user guide in `docs/cli_debugger.md`
- [ ] Document all commands with syntax and examples
- [ ] Add common debugging workflows
- [ ] Include troubleshooting section
- [ ] Add keyboard shortcuts reference
- [ ] Provide quick start tutorial
- [ ] Review and refine documentation

---

### 6.4 Automation Examples

**Priority:** LOW  
**Dependencies:** 5.3 (Scripting support), 1.4 (JSON output)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Sample JSON scripts for CI/CD integration. Shows automation capabilities.

**Todo:**
- [ ] Create sample automation scripts
- [ ] Example: automated test run with breakpoint validation
- [ ] Example: memory dump automation
- [ ] Example: regression test script
- [ ] Document automation patterns
- [ ] Add scripts to repository

---

## Phase 7: Disassembly Remediation & VS Code Parity

**Priority:** HIGH  
**Dependencies:** Phase 4 (disassembly CLI), Executive Phase 1.6 (Disassembly API), Toolchain Phase 3 (.sym metadata), VS Code adapter Phase 2.6  
**Estimated Effort:** 5-7 days

**Rationale:**  
Design §5.5.7 in [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md#L459) and the HXE format spec (`docs/hxe_format.md`) require the executive to return real MVASM instructions with symbol/source annotations. Current output shows all-zero words in the VS Code disassembly panel (`hsx-dap-debug.log` sample), meaning the adapter cannot render mnemonics or operands. Root causes: the executive decodes from the task RAM mirror instead of the immutable code image (`python/execd.py:2099-2199`), `_format_disassembly` drops operand strings, and the RPC surface still exposes the legacy `cmd:"disasm"`/`mode:"cached"` contract rather than the documented `disasm.read` around-PC behavior. This phase restores spec compliance and keeps the VS Code extension in lockstep with the CLI tooling.

### 7.1 Executive Instruction Source & Annotation

**Priority:** HIGH  
**Dependencies:** Executive VM controller (`platforms/python/host_vm.py`), symbol loader  
**Estimated Effort:** 2 days

**Todo:**
- [x] Document the current mismatch (code lives in `MiniVM.code`, `disasm_read` reads `vm.read_mem`) and capture reproduction steps in `main/05--Implementation/01--GapAnalysis/09--Debugger/03--ImplementationNotes.md`.
- [x] Introduce a safe way to fetch instruction bytes (e.g., `MiniVM.read_code` or copying the HXE code section into the task snapshot) so `disasm_read` always decodes from the executable image, not mutable RAM.
- [x] Ensure symbol and source annotations are preserved when switching buffers (`symbol_lookup_addr/line` already provide metadata; keep offsets so labels render only at function entries).
- [x] Update caching/invalidation so cached disassembly is keyed on code bytes + pid; expire caches automatically on reload/unload.
- [x] Extend `python/tests/test_executive_sessions.py::test_disasm_read_basic` (and add new tests) to assert the byte stream mirrors the .sym metadata and that BRK/JMP opcodes round-trip.

### 7.2 VS Code Adapter & Tree View Formatting

**Priority:** HIGH  
**Dependencies:** Phase 2.6 (DAP backend reuse)  
**Estimated Effort:** 1-2 days

**Todo:**
- [x] Update `HSXDebugAdapter._format_disassembly` to consume operand *strings* as emitted by `disasm_util.format_operands` (fallback to list join when structured operands are added later) so mnemonics render as `LDI R1 <- 0x5`.
- [x] Ensure location metadata uses the canonical `{directory, file}` pairs coming from the executive rather than only `line.file` strings.
- [x] Expand adapter unit tests to cover operand rendering, symbol labels, and source click-through (e.g., add fixtures under `python/tests/test_hsx_dap_disassembly.py`).
- [x] Refresh the VS Code tree view copy/highlight logic so the PC-highlight icon only appears when the decoded address matches `referenceAddress`, and ensure copy-to-clipboard paths include operands and `; file:line` annotations.

### 7.3 Protocol Alignment & Client UX

**Priority:** MEDIUM  
**Dependencies:** Executive RPC layer, DAP transport  
**Estimated Effort:** 1-2 days

**Todo:**
- [x] Add the documented `cmd:"disasm.read"` entry point alongside the legacy `disasm` command; honor `mode:"around_pc"` (split `count` before/after the PC) and `mode:"from_addr"` semantics from the design.
- [x] Have the adapter request `mode:"around_pc"` + `addr: current_pc` by default to reduce bespoke window math in the extension, but keep backward-compatible behavior when running against older executives.
- [x] Update CLI (`hsx-dbg`) and VS Code docs to mention the new capability negotiation flag so other clients can detect when disassembly is unavailable.
- [x] Extend RPC tests (e.g., `python/tests/test_executive_sessions.py`) to cover the new request shape, cached/on-demand paths, and error handling when code bytes cannot be read.

### 7.4 Documentation & Telemetry

**Priority:** MEDIUM  
**Dependencies:** Completion of 7.1-7.3  
**Estimated Effort:** 1 day

**Todo:**
- [x] Update `docs/hsx_dbg_usage.md` (disassembly section) and `docs/hxe_format.md` (code/rodata handling) to reflect the fixed pipeline and any new flags.
- [x] Add troubleshooting notes to `main/04--Design/04.11--vscode_debugger.md` describing how the adapter surfaces disassembly errors in the Run/Debug view.
- [x] Instrument the adapter with debug logs summarizing opcode/operand counts (sampling) so regressions surface quickly in `hsx-dap-debug.log`.
- [x] Capture verification steps (CLI disasm, VS Code panel screenshot references) in Implementation Notes for traceability.

---

## Phase 8: Breakpoint & Connection Resiliency

**Priority:** HIGH  
**Dependencies:** Phase 3 (breakpoint/variable plumbing), Phase 7 (disassembly parity), vscode-hsx extension  
**Estimated Effort:** 5 days

**Rationale:**  
Evaluation/pause commands currently wedge when the tracked PID disappears (`unknown pid` loops), the VS Code UI doesn’t show breakpoints added via the CLI/executive, and instruction breakpoints can’t be set from the disassembly view. This phase hardens the adapter/backend so breakpoint state stays in sync regardless of where breakpoints originate, disassembly always refreshes on stops, and PID loss produces clear UX instead of endless reconnects.

### 8.1 PID Loss & Reconnect UX

**Todo:**
- [x] Detect `unknown pid` errors after reconnect, re-run `ps`, and either update `current_pid` or surface a fatal “target exited” message.
- [x] Emit telemetry + VS Code notifications when a PID disappears so users know to relaunch.
- [x] Extend the hsx_dap harness with a backend stub that simulates PID loss mid-session to cover the new logic.

### 8.2 Instruction Breakpoints & Disassembly Refresh

**Todo:**
- [x] Implement `setInstructionBreakpoints` to allow breakpoints directly from the disassembly tree (reusing `DebuggerBackend` APIs).
- [ ] Auto-refresh disassembly on every `stopped` event (breakpoint hits included) and ensure requests always send a non-zero `instructionCount`.
- [x] Add harness tests verifying instruction breakpoints hit and the disassembly panel populates after breakpoint stops.

### 8.3 Breakpoint Synchronization

**Todo:**
- [ ] Subscribe to executive breakpoint events (or poll) so VS Code reflects breakpoints created outside the adapter (CLI/executive UI).
- [ ] Reconcile local vs remote breakpoint sets after reconnect, removing stale entries and surfacing newly added ones.
- [ ] Document mixed breakpoint workflows and add telemetry when external breakpoints are synced.

---

## Definition of Done (DoD)

This implementation is considered complete when all of the following criteria are met:

### Phase 1 Completion
- [ ] CLI framework functional with command parser
- [ ] `hsx-dbg` command-line tool works
- [ ] JSON output mode available
- [ ] All Phase 1 tests pass

### Phase 2 Completion
- [ ] Session management commands functional (attach, detach, observer)
- [ ] Session info commands working
- [ ] Keepalive handling operational
- [ ] All Phase 2 tests pass

### Phase 3 Completion
- [ ] Breakpoint management functional (set, clear, list, enable/disable)
- [ ] Symbol resolution working
- [ ] Source line mapping functional
- [ ] All Phase 3 tests pass

### Phase 4 Completion
- [ ] Stack inspection commands working (backtrace, frame, up, down)
- [ ] Watch commands functional
- [ ] Memory inspection commands working
- [ ] Disassembly commands functional
- [ ] All Phase 4 tests pass

### Phase 5 Completion
- [ ] Context-aware completion working
- [ ] Persistent history functional
- [ ] Scripting support operational
- [ ] Error handling robust
- [ ] All Phase 5 tests pass

### Phase 6 Completion
- [ ] Test coverage >80% for CLI debugger
- [ ] Integration tests pass
- [ ] User guide complete and reviewed
- [ ] Automation examples provided
- [ ] All Phase 6 tests pass

### Phase 7 Completion
- [ ] Executive disassembly decodes from the immutable code image and matches `.sym` metadata
- [ ] `disasm.read`/`around_pc` RPC exposed and covered by regression tests
- [ ] VS Code adapter renders mnemonics + operands with correct source hyperlinks
- [ ] CLI/VS Code docs updated with new troubleshooting notes
- [ ] `hsx-dap-debug.log` shows decoded instructions (no all-zero fallbacks)

### Overall Quality Criteria
- [ ] CLI debugger functional for all common workflows
- [ ] Integration with hsxdbg core package verified
- [ ] Integration with Executive debugger APIs verified
- [ ] Symbol file loading works with Toolchain .sym files
- [ ] CI pipeline green
- [ ] Code follows project style guidelines
- [ ] All documentation reviewed and approved

### Traceability
- [ ] All design requirements tracked to implementation
- [ ] All gaps from Study document addressed
- [ ] DependencyTree.md updated with completion status

---

## Cross-References

**Design Documents:**
- [04.09--Debugger.md](../../../04--Design/04.09--Debugger.md) - CLI Debugger Design

**Gap Analysis:**
- [01--Study.md](./01--Study.md) - Gap Analysis Study

**Dependencies:**
- [DependencyTree.md](../DependencyTree.md) - Cross-module dependency tracking
- [06--Toolkit](../06--Toolkit/01--Study.md) - hsxdbg core package (Phases 1-3)
- [02--Executive](../02--Executive/01--Study.md) - Debugger APIs (Phase 1-2)
- [05--Toolchain](../05--Toolchain/01--Study.md) - Symbol files (Phase 3)

**Documentation:**
- `docs/executive_protocol.md` - Executive RPC protocol
- `docs/cli_debugger.md` - CLI debugger user guide (to be created)

---

**Last Updated:** 2025-10-31  
**Status:** Initial Plan  
**Owner:** Debugger Implementation Team

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
- [ ] Create `python/hsx_dbg.py` as main entry point
- [ ] Integrate with `hsxdbg` core package
- [ ] Implement basic REPL loop
- [ ] Add command-line argument parsing (--host, --port, --json, etc.)
- [ ] Add logging and error handling
- [ ] Create CLI debugger tests
- [ ] Document CLI debugger usage

---

### 1.3 Command Parser

**Priority:** HIGH  
**Dependencies:** 1.2 (CLI module)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Implement REPL using `prompt_toolkit` with command parsing and validation. Design specifies structured command interface.

**Todo:**
- [ ] Install `prompt_toolkit` dependency
- [ ] Implement command parser with subcommands
- [ ] Add command validation and help system
- [ ] Implement command history
- [ ] Add multiline command support
- [ ] Implement command aliases
- [ ] Add parser tests
- [ ] Document command syntax

---

### 1.4 JSON Output Mode

**Priority:** MEDIUM  
**Dependencies:** 1.2 (CLI module), 1.3 (Parser)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Design specifies machine-readable output for CI/CD (section 6.2). Enables automation and scripting.

**Todo:**
- [ ] Add `--json` flag to CLI arguments
- [ ] Implement JSON formatter for all command outputs
- [ ] Ensure consistent JSON schema across commands
- [ ] Add error reporting in JSON format
- [ ] Add JSON output tests
- [ ] Document JSON output format

---

## Phase 2: Session Management Commands

### 2.1 Attach/Detach Commands

**Priority:** HIGH  
**Dependencies:** Executive Phase 1.1 (Session management), Toolkit Phase 1-3  
**Estimated Effort:** 3-4 days

**Rationale:**  
Implement `attach <pid>`, `detach`, `observer <pid>` commands per session protocol 5.1. Core debugger functionality.

**Todo:**
- [ ] Implement `attach <pid>` command (exclusive session)
- [ ] Implement `detach` command (release PID lock)
- [ ] Implement `observer <pid>` command (read-only session)
- [ ] Handle session conflicts (PID already locked)
- [ ] Add session state tracking
- [ ] Add attach/detach tests
- [ ] Document session commands

---

### 2.2 Session Info Commands

**Priority:** MEDIUM  
**Dependencies:** 2.1 (Attach/detach)  
**Estimated Effort:** 1-2 days

**Rationale:**  
`session info`, `session list` commands show active sessions and locks. Helps manage multi-user scenarios.

**Todo:**
- [ ] Implement `session info` command (current session details)
- [ ] Implement `session list` command (all active sessions)
- [ ] Display session capabilities
- [ ] Show PID locks and owners
- [ ] Add session info tests
- [ ] Document session info commands

---

### 2.3 Keepalive Handling

**Priority:** LOW  
**Dependencies:** 2.1 (Attach/detach)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Automatic keepalive messages per heartbeat interval. Prevents session timeout.

**Todo:**
- [ ] Implement automatic keepalive timer
- [ ] Send keepalive messages at configured interval
- [ ] Handle keepalive failures (reconnect or error)
- [ ] Add keepalive configuration options
- [ ] Add keepalive tests
- [ ] Document keepalive behavior

---

## Phase 3: Breakpoint Management

### 3.1 Set Breakpoints

**Priority:** HIGH  
**Dependencies:** Executive Phase 1.3 (Breakpoint management), Toolchain Phase 3 (Symbol files)  
**Estimated Effort:** 3-4 days

**Rationale:**  
`break <addr/symbol>`, `break <file>:<line>` commands per section 5.3. Essential debugger functionality.

**Todo:**
- [ ] Implement `break <address>` command (numeric address)
- [ ] Implement `break <symbol>` command (function name)
- [ ] Implement `break <file>:<line>` command (source location)
- [ ] Resolve symbols using .sym files
- [ ] Map source lines to addresses
- [ ] Handle breakpoint set confirmation
- [ ] Add breakpoint set tests
- [ ] Document breakpoint syntax

---

### 3.2 Clear Breakpoints

**Priority:** HIGH  
**Dependencies:** 3.1 (Set breakpoints)  
**Estimated Effort:** 1-2 days

**Rationale:**  
`delete <bp_id>`, `clear <addr/symbol>` commands remove breakpoints.

**Todo:**
- [ ] Implement `delete <bp_id>` command (by ID)
- [ ] Implement `clear <addr/symbol>` command (by location)
- [ ] Implement `clear` command (all breakpoints)
- [ ] Handle breakpoint removal confirmation
- [ ] Add clear breakpoint tests
- [ ] Document clear commands

---

### 3.3 List Breakpoints

**Priority:** MEDIUM  
**Dependencies:** 3.1 (Set breakpoints)  
**Estimated Effort:** 1-2 days

**Rationale:**  
`info breakpoints` command shows all breakpoints with hit counts.

**Todo:**
- [ ] Implement `info breakpoints` command
- [ ] Display breakpoint ID, location, type, enabled status
- [ ] Show hit counts if available
- [ ] Format output as table
- [ ] Add JSON output for `info breakpoints`
- [ ] Add list breakpoint tests
- [ ] Document info breakpoints command

---

### 3.4 Enable/Disable Breakpoints

**Priority:** LOW  
**Dependencies:** 3.1 (Set breakpoints)  
**Estimated Effort:** 1 day

**Rationale:**  
`enable <bp_id>`, `disable <bp_id>` commands toggle breakpoints without deletion.

**Todo:**
- [ ] Implement `enable <bp_id>` command
- [ ] Implement `disable <bp_id>` command
- [ ] Update breakpoint state in executive
- [ ] Add enable/disable tests
- [ ] Document enable/disable commands

---

## Phase 4: Inspection Commands

### 4.1 Stack Commands

**Priority:** HIGH  
**Dependencies:** Executive Phase 1.5 (Stack reconstruction), Toolchain Phase 3 (Symbols)  
**Estimated Effort:** 3-4 days

**Rationale:**  
`backtrace`, `frame <n>`, `up`, `down` commands per section 5.4. Essential for understanding program state.

**Todo:**
- [ ] Implement `backtrace` command (show call stack)
- [ ] Implement `frame <n>` command (select frame)
- [ ] Implement `up` command (move to caller frame)
- [ ] Implement `down` command (move to callee frame)
- [ ] Display frame info with source locations
- [ ] Map addresses to function names using symbols
- [ ] Add stack command tests
- [ ] Document stack commands

---

### 4.2 Watch Commands

**Priority:** MEDIUM  
**Dependencies:** Executive Phase 2.3 (Watch expressions)  
**Estimated Effort:** 2-3 days

**Rationale:**  
`watch <var>`, `unwatch <var>`, `list watches` commands per section 5.5. Monitor variable changes.

**Todo:**
- [ ] Implement `watch <variable>` command
- [ ] Implement `watch <address>` command
- [ ] Implement `unwatch <watch_id>` command
- [ ] Implement `list watches` command
- [ ] Display watch values and change notifications
- [ ] Add watch command tests
- [ ] Document watch commands

---

### 4.3 Memory Commands

**Priority:** MEDIUM  
**Dependencies:** Executive (Memory inspection APIs)  
**Estimated Effort:** 2-3 days

**Rationale:**  
`x/<fmt> <addr>`, `dump <start> <end>` commands per section 5.6. Inspect memory contents.

**Todo:**
- [ ] Implement `x/<format> <address>` command (examine memory)
- [ ] Support format specifiers (x=hex, d=decimal, i=instruction, s=string)
- [ ] Implement `dump <start> <end>` command (hex dump)
- [ ] Add ASCII preview for dumps
- [ ] Add memory command tests
- [ ] Document memory commands

---

### 4.4 Disassembly Commands

**Priority:** MEDIUM  
**Dependencies:** Executive Phase 1.6 (Disassembly API), Toolchain Phase 3 (Symbols)  
**Estimated Effort:** 2-3 days

**Rationale:**  
`disasm <addr/symbol>`, `disasm /s` commands per section 5.7. View assembly instructions with symbols.

**Todo:**
- [ ] Implement `disasm <address>` command (disassemble at address)
- [ ] Implement `disasm <symbol>` command (disassemble function)
- [ ] Implement `disasm /s` flag (show source lines)
- [ ] Annotate instructions with symbol names
- [ ] Highlight current PC
- [ ] Add disassembly command tests
- [ ] Document disassembly commands

---

## Phase 5: Advanced Features

### 5.1 Context-Aware Completion

**Priority:** LOW  
**Dependencies:** Toolchain Phase 3 (Symbol files)  
**Estimated Effort:** 1 week

**Rationale:**  
Design specifies tab completion for commands, symbols, addresses, registers using symbol files (section 6.3).

**Todo:**
- [ ] Implement command name completion
- [ ] Implement symbol name completion (functions, variables)
- [ ] Implement register name completion
- [ ] Implement file path completion
- [ ] Load symbols from .sym files
- [ ] Integrate with prompt_toolkit completion API
- [ ] Add completion tests
- [ ] Document completion behavior

---

### 5.2 Persistent History

**Priority:** LOW  
**Dependencies:** 1.3 (Command parser)  
**Estimated Effort:** 1 day

**Rationale:**  
Design specifies history across sessions (section 6.4). Save to `~/.hsx_history`.

**Todo:**
- [ ] Implement history save to `~/.hsx_history`
- [ ] Implement history load on startup
- [ ] Limit history size (configurable)
- [ ] Add history search (Ctrl+R)
- [ ] Add history tests
- [ ] Document history file location

---

### 5.3 Scripting Support

**Priority:** LOW  
**Dependencies:** 1.3 (Command parser)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Execute command files with `-x <script>` flag. Enables automated debugging workflows.

**Todo:**
- [ ] Add `-x <script>` command-line flag
- [ ] Implement script file execution (read and execute commands)
- [ ] Support comments in script files
- [ ] Add error handling for script errors
- [ ] Add scripting tests
- [ ] Document script file format

---

### 5.4 Error Handling

**Priority:** MEDIUM  
**Dependencies:** Phase 2 (Session management)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Protocol error recovery, reconnection logic per section 7. Robust error handling.

**Todo:**
- [ ] Implement connection loss detection
- [ ] Add automatic reconnection with backoff
- [ ] Handle protocol version mismatches gracefully
- [ ] Display clear error messages for user
- [ ] Add error recovery tests
- [ ] Document error handling behavior

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

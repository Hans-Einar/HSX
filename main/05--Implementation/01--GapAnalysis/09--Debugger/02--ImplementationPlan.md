# CLI Debugger Implementation Plan

## Planned Implementation Order (Grand Plan)

1. Phase 1 - Python CLI debugger core built on the executive RPC layer.
2. Phase 2 - Event and trace integration once executive streaming is available.
3. Phase 3 - Advanced debugger features (breakpoints, watch, scripting).
4. Phase 4 - Documentation, UX polish, and regression coverage.
5. Phase 5 - C integration and packaging (deferred).
6. Phase 6 - Extended distribution targets (deferred).

## Sprint Scope

Deliver the Python-first work in Phases 1 through 4 this sprint. Keep the Phase 5 and 6 C/distribution items out of scope and log discoveries for the deferred backlog.

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
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.09--Debugger](../../../04--Design/04.09--Debugger.md)
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
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.09--Debugger](../../../04--Design/04.09--Debugger.md)
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
### 1.4 Task Metadata

**Priority:** LOW  
**Dependencies:** Executive Phase 3.3 (app naming)  
**Estimated Effort:** 1 day

**Rationale:**  
Executive now surfaces app names and metadata counts; CLI debugger should display these to help users distinguish instances and know when declarative resources exist.

**Todo:**
> Reference: [Implementation Notes](../02--Executive/03--ImplementationNotes.md) | [Design 04.09--Debugger.md](../../../04--Design/04.09--Debugger.md)
- [ ] Show `app_name`/instance suffixes in task listings
- [ ] Display metadata count (values/commands/mailboxes) when present
- [ ] Gate feature behind capability flag until executive Phase 3.3 merges
- [ ] Update CLI help/docs to mention the new columns
- [ ] Add regression tests once executive metadata summary is stable

> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.09--Debugger](../../../04--Design/04.09--Debugger.md)
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
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.09--Debugger](../../../04--Design/04.09--Debugger.md)
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
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.09--Debugger](../../../04--Design/04.09--Debugger.md)
- [ ] Implement `attach <pid>` command (exclusive session)
- [ ] Implement `detach` command (release PID lock)
- [ ] Implement `observer <pid>` command (read-only session)
- [ ] Handle session conflicts (PID already locked)
- [ ] Add session state tracking
- [ ] Add attach/detach tests
- [ ] Document session commands

---

### 2.2 Session Info Commands
### 1.3 Task Metadata

**Priority:** LOW  
**Dependencies:** Executive Phase 3.3 (app naming)  
**Estimated Effort:** 1 day

**Rationale:**  
Executive now surfaces app names and metadata counts; CLI debugger should display these to help users distinguish instances and know when declarative resources exist.

**Todo:**
> Reference: [Implementation Notes](../02--Executive/03--ImplementationNotes.md) | [Design 04.09--Debugger.md](../../../04--Design/04.09--Debugger.md)
- [ ] Show `app_name`/instance suffixes in task listings
- [ ] Display metadata count (values/commands/mailboxes) when present
- [ ] Gate feature behind capability flag until executive Phase 3.3 merges
- [ ] Update CLI help/docs to mention the new columns
- [ ] Add regression tests once executive metadata summary is stable


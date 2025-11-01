# VS Code Debugger Implementation Plan

## Planned Implementation Order (Grand Plan)

1. Phase 1 - Python Debug Adapter Protocol (DAP) foundation leveraging CLI/TUI services.
2. Phase 2 - Feature parity with CLI/TUI debuggers (breakpoints, tasks, mailboxes).
3. Phase 3 - VS Code UI polish (views, commands, launch configurations).
4. Phase 4 - Documentation, samples, and regression automation.
5. Phase 5 - Marketplace packaging and release automation.
6. Phase 6 - C/native integrations (deferred until Python flows are complete).

## Sprint Scope

Focus on the Python adapter and VS Code experience in Phases 1 through 5. Keep Phase 6 native/C extensions out of scope for this sprint and log emerging requirements for the deferred backlog.

## Overview

This implementation plan addresses the gaps identified in the VS Code Debugger Study document ([01--Study.md](./01--Study.md)). The plan is organized chronologically with clear dependencies tracked in [DependencyTree.md](../DependencyTree.md).

**Design Reference:** [04.11--vscode_debugger.md](../../../04--Design/04.11--vscode_debugger.md)

**Note:** Complete DAP adapter and VS Code extension are missing. This plan builds IDE-native debugging with Debug Adapter Protocol.

---

## Phase 1: DAP Adapter Foundation

### 1.1 Create DAP Adapter Module

**Priority:** HIGH  
**Dependencies:** Toolkit Phase 1-3 (hsxdbg core package)  
**Estimated Effort:** 3-4 days

**Rationale:**  
New `hsx-dap.py` implementing Debug Adapter Protocol server. Foundation for IDE integration.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Create `python/hsx_dap.py` as main DAP server
- [ ] Study DAP specification (https://microsoft.github.io/debug-adapter-protocol/)
- [ ] Integrate with `hsxdbg` core package
- [ ] Add command-line argument parsing
- [ ] Add logging configuration
- [ ] Create DAP adapter tests
- [ ] Document DAP adapter architecture

---

### 1.2 DAP Base Class

**Priority:** HIGH  
**Dependencies:** 1.1 (DAP module)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Abstract base implementing stdio/TCP communication per DAP spec. Protocol communication layer.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement DAP base class with protocol handling
- [ ] Implement stdio communication (standard DAP mode)
- [ ] Implement message framing (Content-Length headers)
- [ ] Implement JSON-RPC request/response handling
- [ ] Add message validation
- [ ] Add protocol tests
- [ ] Document protocol implementation

---

### 1.3 Executive Client Integration

**Priority:** HIGH  
**Dependencies:** 1.1 (DAP module), Toolkit Phase 1-3  
**Estimated Effort:** 2-3 days

**Rationale:**  
Use `hsxdbg` core for HSX executive RPC connection. Bridge between DAP and executive.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Integrate hsxdbg core connection
- [ ] Implement session management (attach to executive)
- [ ] Subscribe to executive events
- [ ] Map executive events to DAP events
- [ ] Handle connection lifecycle
- [ ] Add integration tests
- [ ] Document executive integration

---

### 1.4 Symbol Loader

**Priority:** HIGH  
**Dependencies:** Toolchain Phase 3 (.sym files)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Read .sym files and build source line → address mappings. Essential for source-level debugging.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement .sym file parser
- [ ] Build source file → address map
- [ ] Build address → source file map
- [ ] Implement symbol name lookup
- [ ] Handle missing .sym files gracefully
- [ ] Add symbol loader tests
- [ ] Document symbol file format expectations

---

## Phase 2: Core DAP Requests

### 2.1 Initialize Request

**Priority:** HIGH  
**Dependencies:** 1.2 (DAP base)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Capability negotiation (breakpoints, stepping, variables). First DAP handshake.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement `initialize` request handler
- [ ] Declare supported capabilities (supportsConfigurationDoneRequest, etc.)
- [ ] Return capability response
- [ ] Add initialize tests
- [ ] Document capabilities

---

### 2.2 Launch Request

**Priority:** HIGH  
**Dependencies:** 2.1 (Initialize), 1.3 (Executive client)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Start debug session with HXE path, spawn executive if needed. Begin debugging workflow.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement `launch` request handler
- [ ] Parse launch configuration (hxePath, execHost, execPort)
- [ ] Connect to executive using hsxdbg core
- [ ] Load HXE into executive
- [ ] Load .sym file for source mapping
- [ ] Send `initialized` event when ready
- [ ] Add launch tests
- [ ] Document launch configuration

---

### 2.3 SetBreakpoints Request

**Priority:** HIGH  
**Dependencies:** 2.2 (Launch), 1.4 (Symbol loader), Executive Phase 1.3  
**Estimated Effort:** 3-4 days

**Rationale:**  
Map source file:line to addresses, set executive breakpoints. Core debugging feature.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement `setBreakpoints` request handler
- [ ] Map source locations to instruction addresses using .sym
- [ ] Set breakpoints in executive at resolved addresses
- [ ] Return verified breakpoint locations
- [ ] Handle unresolved breakpoints (e.g., optimized out)
- [ ] Add breakpoint synchronization tests
- [ ] Document breakpoint mapping

---

### 2.4 Execution Control

**Priority:** HIGH  
**Dependencies:** 2.2 (Launch)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Implement `continue`, `next`, `stepIn`, `stepOut`, `pause` requests. Stepping and execution control.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement `continue` request (resume execution)
- [ ] Implement `next` request (step over)
- [ ] Implement `stepIn` request (step into)
- [ ] Implement `stepOut` request (step out of function)
- [ ] Implement `pause` request (interrupt execution)
- [ ] Send `stopped` event when execution pauses
- [ ] Add execution control tests
- [ ] Document execution control behavior

---

### 2.5 Disconnect Request

**Priority:** MEDIUM  
**Dependencies:** 2.2 (Launch)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Clean up session and close connections. Proper session termination.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement `disconnect` request handler
- [ ] Close executive connection
- [ ] Clean up resources
- [ ] Send `terminated` event
- [ ] Add disconnect tests
- [ ] Document disconnect behavior

---

## Phase 3: Inspection Requests

### 3.1 StackTrace Request

**Priority:** HIGH  
**Dependencies:** 2.2 (Launch), Executive Phase 1.5 (Stack reconstruction)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Retrieve call stack from executive, map addresses to source locations. Essential debugging feature.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement `stackTrace` request handler
- [ ] Fetch stack frames from executive
- [ ] Map frame addresses to source locations using .sym
- [ ] Return stack trace with source file:line
- [ ] Handle frames without source info
- [ ] Add stack trace tests
- [ ] Document stack trace mapping

---

### 3.2 Scopes Request

**Priority:** MEDIUM  
**Dependencies:** 3.1 (StackTrace)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Enumerate variable scopes (registers, locals, globals). Variable inspection hierarchy.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement `scopes` request handler
- [ ] Define "Registers" scope
- [ ] Define "Locals" scope (if available)
- [ ] Define "Globals" scope (if available)
- [ ] Return scope references
- [ ] Add scopes tests
- [ ] Document scope definitions

---

### 3.3 Variables Request

**Priority:** HIGH  
**Dependencies:** 3.2 (Scopes)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Retrieve register/memory values formatted for VS Code. Display program state.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement `variables` request handler
- [ ] Fetch register values from executive
- [ ] Format values for VS Code display
- [ ] Support different value formats (hex, decimal, binary)
- [ ] Handle memory reads for variable inspection
- [ ] Add variables tests
- [ ] Document variable formatting

---

### 3.4 Evaluate Request

**Priority:** MEDIUM  
**Dependencies:** 3.3 (Variables), Executive Phase 2.3 (Watch expressions)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Support watch expressions and hover queries. Interactive expression evaluation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement `evaluate` request handler
- [ ] Support register name evaluation (e.g., "r0")
- [ ] Support address evaluation (e.g., "@0x1000")
- [ ] Support symbol evaluation (if available)
- [ ] Return formatted results
- [ ] Add evaluate tests
- [ ] Document evaluate syntax

---

## Phase 4: Event Handling

### 4.1 DAP Events

**Priority:** HIGH  
**Dependencies:** 2.2 (Launch), 1.3 (Executive client)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Translate executive events to DAP events. Event-driven debugging.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Map debug_break event → `stopped` event (reason: breakpoint)
- [ ] Map trace_step event → `stopped` event (reason: step)
- [ ] Map stdout/stderr events → `output` event
- [ ] Map task_state events → `stopped` or `continued` events
- [ ] Add event filtering (don't send every trace_step)
- [ ] Add event tests
- [ ] Document event mapping

---

### 4.2 Source Mapping

**Priority:** HIGH  
**Dependencies:** 4.1 (DAP events), 1.4 (Symbol loader)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Convert instruction addresses in events to source locations. Source-level event notifications.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Map addresses to source locations for stopped events
- [ ] Include source file and line in stopped events
- [ ] Handle addresses without source mapping
- [ ] Add source mapping tests
- [ ] Document source mapping behavior

---

### 4.3 Thread Management

**Priority:** MEDIUM  
**Dependencies:** 4.1 (DAP events)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Map HSX PIDs to DAP thread IDs. Multi-task debugging support.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement PID → thread ID mapping
- [ ] Send `thread` event when tasks start/stop
- [ ] Implement `threads` request handler
- [ ] Return thread list with names
- [ ] Add thread management tests
- [ ] Document thread mapping

---

## Phase 5: VS Code Extension

### 5.1 Extension Scaffold

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 2-3 days

**Rationale:**  
Create VS Code extension project with TypeScript. Extension foundation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Create VS Code extension directory structure
- [ ] Initialize TypeScript project
- [ ] Add VS Code extension dependencies
- [ ] Create extension entry point (extension.ts)
- [ ] Set up build system (webpack/esbuild)
- [ ] Add extension tests
- [ ] Document extension structure

---

### 5.2 Package.json

**Priority:** HIGH  
**Dependencies:** 5.1 (Extension scaffold)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Define debugger contribution and activation events. Extension manifest.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Create package.json with extension metadata
- [ ] Define debugger type ("hsx")
- [ ] Register debug configuration provider
- [ ] Define activation events
- [ ] Specify extension dependencies
- [ ] Add icons and branding
- [ ] Document package.json structure

---

### 5.3 Launch Configuration

**Priority:** HIGH  
**Dependencies:** 5.2 (Package.json)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Provide `launch.json` templates for HXE debugging. User configuration interface.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Create launch configuration provider
- [ ] Define launch configuration schema
- [ ] Provide initial launch.json template
- [ ] Add configuration snippets
- [ ] Validate user configurations
- [ ] Add configuration tests
- [ ] Document configuration options

---

### 5.4 Adapter Lifecycle

**Priority:** HIGH  
**Dependencies:** 5.3 (Launch config), Phase 1-2 (DAP adapter)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Spawn and manage `hsx-dap.py` process. Adapter process management.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Implement debug adapter descriptor factory
- [ ] Spawn hsx-dap.py process with stdio communication
- [ ] Pass configuration to adapter
- [ ] Handle adapter process lifecycle
- [ ] Clean up on session end
- [ ] Add lifecycle tests
- [ ] Document adapter spawning

---

### 5.5 Debug Commands

**Priority:** LOW  
**Dependencies:** 5.1 (Extension scaffold)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Add VS Code commands for HSX-specific operations. Extended functionality.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Add command: "HSX: Load HXE File"
- [ ] Add command: "HSX: Connect to Executive"
- [ ] Add command: "HSX: Show Symbol Information"
- [ ] Register commands in package.json
- [ ] Implement command handlers
- [ ] Add command tests
- [ ] Document available commands

---

## Phase 6: Testing and Polish

### 6.1 DAP Protocol Tests

**Priority:** HIGH  
**Dependencies:** Phases 1-4 complete  
**Estimated Effort:** 1 week

**Rationale:**  
Validate request/response handling against DAP spec. Ensure protocol compliance.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Add protocol message validation tests
- [ ] Test all DAP request handlers
- [ ] Test all DAP event emissions
- [ ] Test error conditions
- [ ] Validate against DAP specification
- [ ] Measure test coverage (target >80%)
- [ ] Document test approach

---

### 6.2 End-to-End Tests

**Priority:** HIGH  
**Dependencies:** 6.1 (Protocol tests), Phase 5 (Extension)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Full debugging workflows in VS Code with mock executive. Integration testing.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Create end-to-end test scenarios
- [ ] Test launch workflow
- [ ] Test breakpoint workflow
- [ ] Test stepping workflow
- [ ] Test variable inspection
- [ ] Test with real VS Code instance
- [ ] Add E2E tests to CI
- [ ] Document E2E test suite

---

### 6.3 Error Handling

**Priority:** MEDIUM  
**Dependencies:** Phase 1-5 complete  
**Estimated Effort:** 2-3 days

**Rationale:**  
Clear error messages for common failure modes. User-friendly errors.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Handle missing .sym files (clear error message)
- [ ] Handle executive connection failures
- [ ] Handle HXE load failures
- [ ] Handle breakpoint set failures
- [ ] Display errors in VS Code UI
- [ ] Add error handling tests
- [ ] Document common errors

---

### 6.4 Performance

**Priority:** MEDIUM  
**Dependencies:** Phase 1-5 complete  
**Estimated Effort:** 2-3 days

**Rationale:**  
Optimize symbol lookups and event processing for responsiveness. Good user experience.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Profile adapter performance
- [ ] Optimize symbol lookup (caching, indexing)
- [ ] Optimize event processing
- [ ] Reduce latency in stepping operations
- [ ] Benchmark performance
- [ ] Add performance tests
- [ ] Document performance characteristics

---

## Phase 7: Documentation and Distribution

### 7.1 User Guide

**Priority:** HIGH  
**Dependencies:** Phases 1-6 complete  
**Estimated Effort:** 2-3 days

**Rationale:**  
VS Code debugging tutorial with screenshots. User documentation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Write user guide in `docs/vscode_debugger.md`
- [ ] Add installation instructions
- [ ] Document launch.json configuration
- [ ] Provide debugging tutorial with screenshots
- [ ] Add troubleshooting section
- [ ] Include keyboard shortcuts reference
- [ ] Review and refine documentation

---

### 7.2 Launch.json Examples

**Priority:** MEDIUM  
**Dependencies:** 7.1 (User guide)  
**Estimated Effort:** 1 day

**Rationale:**  
Sample configurations for common scenarios. Help users get started.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Create example: local debugging
- [ ] Create example: remote executive
- [ ] Create example: attach to running task
- [ ] Add examples to documentation
- [ ] Include comments explaining options

---

### 7.3 Extension Packaging

**Priority:** MEDIUM  
**Dependencies:** Phase 5 (Extension complete)  
**Estimated Effort:** 1-2 days

**Rationale:**  
VSIX bundle for VS Code marketplace distribution. Distribution package.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Package extension as VSIX
- [ ] Test VSIX installation
- [ ] Create README for marketplace
- [ ] Add changelog
- [ ] Prepare for marketplace submission
- [ ] Document packaging process

---

### 7.4 Troubleshooting Guide

**Priority:** LOW  
**Dependencies:** 7.1 (User guide)  
**Estimated Effort:** 1 day

**Rationale:**  
Common issues and solutions. Support documentation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.02--Executive](../../../04--Design/04.02--Executive.md)
- [ ] Document common DAP adapter issues
- [ ] Document executive connection issues
- [ ] Document symbol file issues
- [ ] Provide solutions and workarounds
- [ ] Add FAQ section
- [ ] Include debug logging instructions

---

## Definition of Done (DoD)

This implementation is considered complete when all of the following criteria are met:

### Phase 1 Completion
- [ ] DAP adapter module functional
- [ ] DAP base class with protocol handling working
- [ ] Executive client integration operational
- [ ] Symbol loader reading .sym files
- [ ] All Phase 1 tests pass

### Phase 2 Completion
- [ ] Initialize request working
- [ ] Launch request functional (connect, load HXE, load symbols)
- [ ] SetBreakpoints request mapping source to addresses
- [ ] Execution control working (continue, next, stepIn, stepOut, pause)
- [ ] Disconnect request cleaning up properly
- [ ] All Phase 2 tests pass

### Phase 3 Completion
- [ ] StackTrace request retrieving and mapping stack
- [ ] Scopes request enumerating variable scopes
- [ ] Variables request displaying register/memory values
- [ ] Evaluate request supporting expressions
- [ ] All Phase 3 tests pass

### Phase 4 Completion
- [ ] DAP events mapping from executive events
- [ ] Source mapping converting addresses to source locations
- [ ] Thread management mapping PIDs to threads
- [ ] All Phase 4 tests pass

### Phase 5 Completion
- [ ] VS Code extension scaffold complete
- [ ] Package.json defining debugger contribution
- [ ] Launch configuration templates provided
- [ ] Adapter lifecycle management working
- [ ] Debug commands implemented
- [ ] All Phase 5 tests pass

### Phase 6 Completion
- [ ] DAP protocol tests >80% coverage
- [ ] End-to-end tests passing
- [ ] Error handling robust and user-friendly
- [ ] Performance acceptable (responsive debugging)
- [ ] All Phase 6 tests pass

### Phase 7 Completion
- [ ] User guide complete with screenshots
- [ ] Launch.json examples provided
- [ ] Extension packaged as VSIX
- [ ] Troubleshooting guide available
- [ ] All Phase 7 tests pass

### Overall Quality Criteria
- [ ] VS Code debugger functional for all common workflows
- [ ] DAP specification compliance verified
- [ ] Integration with hsxdbg core package verified
- [ ] Integration with Executive debugger APIs verified
- [ ] Symbol file loading working with Toolchain .sym files
- [ ] Extension installable and working in VS Code
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
- [04.11--vscode_debugger.md](../../../04--Design/04.11--vscode_debugger.md) - VS Code Debugger Design

**Gap Analysis:**
- [01--Study.md](./01--Study.md) - Gap Analysis Study

**Dependencies:**
- [DependencyTree.md](../DependencyTree.md) - Cross-module dependency tracking
- [06--Toolkit](../06--Toolkit/01--Study.md) - hsxdbg core package (Phases 1-3)
- [02--Executive](../02--Executive/01--Study.md) - Debugger APIs (Phase 1-2)
- [05--Toolchain](../05--Toolchain/01--Study.md) - .sym files (Phase 3)

**Documentation:**
- `docs/vscode_debugger.md` - VS Code debugger user guide (to be created)
- DAP Specification: https://microsoft.github.io/debug-adapter-protocol/
- VS Code Extension API: https://code.visualstudio.com/api

---

**Last Updated:** 2025-10-31  
**Status:** Initial Plan  
**Owner:** VS Code Debugger Implementation Team

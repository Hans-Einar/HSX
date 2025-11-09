# TUI Debugger Implementation Plan

## Planned Implementation Order (Grand Plan)

1. Phase 1 - Foundation work after the CLI debugger stabilizes (shared services, layout).
2. Phase 2 - Core TUI views for tasks, registers, breakpoints, and mailboxes.
3. Phase 3 - Live update plumbing using executive event streaming.
4. Phase 4 - UX polish, documentation, and regression coverage.
5. Phase 5 - Packaging and distribution planning (deferred until Python flows settle).

## Sprint Scope

Deliver the Python-focused work in Phases 1 through 4. Keep Phase 5 packaging (and any future native ports) out of scope for this sprint while capturing discoveries for later scheduling.

## Overview

This implementation plan addresses the gaps identified in the TUI Debugger Study document ([01--Study.md](./01--Study.md)). The plan is organized chronologically with clear dependencies tracked in [DependencyTree.md](../DependencyTree.md).

**Design Reference:** [04.10--TUI_Debugger.md](../../../04--Design/04.10--TUI_Debugger.md)

**Note:** Complete TUI is missing. This plan builds a full-screen terminal debugger using Textual framework.

---

## Phase 1: TUI Framework Setup

### 1.1 Install Textual Dependency

**Priority:** HIGH  
**Dependencies:** None  
**Estimated Effort:** 1 day

**Rationale:**  
Design specifies Textual framework for TUI (section 4.1). Modern Python TUI with asyncio integration.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Add `textual >= 0.58.0` to project requirements
- [ ] Verify Textual installation and compatibility
- [ ] Review Textual documentation and examples
- [ ] Document Textual version requirements

---

### 1.2 Create TUI Application Module

**Priority:** HIGH  
**Dependencies:** 1.1 (Textual dependency), Toolkit Phase 1-3 (hsxdbg core)  
**Estimated Effort:** 2-3 days

**Rationale:**  
New `hsx-tui` command-line tool built on `hsxdbg` core package. Foundation for TUI debugger.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create `python/hsx_tui.py` as main entry point
- [ ] Integrate with `hsxdbg` core package
- [ ] Add command-line argument parsing (--host, --port, etc.)
- [ ] Add logging configuration
- [ ] Create basic app skeleton
- [ ] Add TUI app tests
- [ ] Document TUI app usage

---

### 1.3 Application Shell

**Priority:** HIGH  
**Dependencies:** 1.2 (TUI module)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Main Textual app class with layout management and event routing (section 4.3.1). Core TUI architecture.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create main Textual App class
- [ ] Implement layout management system
- [ ] Implement event routing between components
- [ ] Add app lifecycle handlers (on_mount, on_unmount)
- [ ] Implement panel focus management
- [ ] Add app shell tests
- [ ] Document app architecture

---

### 1.4 Connection Manager

**Priority:** HIGH  
**Dependencies:** 1.3 (App shell), Toolkit Phase 1-3  
**Estimated Effort:** 2-3 days

**Rationale:**  
Integrate debugger core session and event subscription. Connects TUI to executive.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Integrate hsxdbg core connection
- [ ] Implement session management (attach/detach)
- [ ] Subscribe to debugger events
- [ ] Implement event dispatch to panels
- [ ] Handle connection loss and reconnection
- [ ] Add connection manager tests
- [ ] Document connection management

---

## Phase 2: Core Panel Implementation

### 2.0 Task List Metadata

**Priority:** MEDIUM  
**Dependencies:** Executive Phase 3.3 (app naming), CLI Debugger Phase 1.x
**Estimated Effort:** 2 days

**Rationale:**  
Mirror CLI capabilities by displaying app names and metadata presence in the TUI task list so users can quickly identify instances and declarative resources.

**Todo:**
> Reference: [Implementation Notes](../02--Executive/03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger.md](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Show app instance names in task list panel
- [ ] Provide metadata badges (values/commands/mailboxes) when counts > 0
- [ ] Add tooltip/details view for metadata summary
- [ ] Update layout to accommodate metadata columns without overcrowding
- [ ] Add tests once executive metadata summary stabilises and CLI behaviour anchors expectations

### 2.1 Registers Panel

**Priority:** HIGH  
**Dependencies:** 1.3 (App shell)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Display R0-R15, PC, SP, PSW with change highlighting. Essential debugger view.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create Registers widget (Textual Widget subclass)
- [ ] Display general-purpose registers (R0-R15)
- [ ] Display special registers (PC, SP, PSW)
- [ ] Implement register value formatting (hex, decimal)
- [ ] Add change highlighting (different color for modified registers)
- [ ] Update on trace_step events
- [ ] Add registers panel tests
- [ ] Document registers panel

---

### 2.2 Disassembly Panel

**Priority:** HIGH  
**Dependencies:** 1.3 (App shell), Executive Phase 1.6 (Disassembly API)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Show instructions around PC with symbols and breakpoint markers. Core debugging view.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create Disassembly widget
- [ ] Fetch instructions from executive disassembly API
- [ ] Display opcodes with address and mnemonic
- [ ] Highlight current PC instruction
- [ ] Show breakpoint markers (●)
- [ ] Annotate with symbol names
- [ ] Implement scrolling (follow PC or manual)
- [ ] Add disassembly panel tests
- [ ] Document disassembly panel

---

### 2.3 Console Panel

**Priority:** HIGH  
**Dependencies:** 1.3 (App shell)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Stdout/stderr output and command input field. User interaction and output display.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create Console widget (scrollable text area)
- [ ] Display stdout/stderr streams
- [ ] Implement command input field
- [ ] Add command history (up/down arrows)
- [ ] Execute commands through hsxdbg core
- [ ] Display command results
- [ ] Add console panel tests
- [ ] Document console panel

---

### 2.4 Status Bar

**Priority:** MEDIUM  
**Dependencies:** 1.3 (App shell)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Connection info, PID, execution state, runtime counters. System status at a glance.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create Status widget (footer bar)
- [ ] Display connection status (connected/disconnected)
- [ ] Display current PID
- [ ] Display execution state (running/paused/stopped)
- [ ] Display instruction counter
- [ ] Display clock rate
- [ ] Update on state changes
- [ ] Add status bar tests
- [ ] Document status bar

---

## Phase 3: Advanced Panels

### 3.1 Trace Panel

**Priority:** MEDIUM  
**Dependencies:** 1.3 (App shell)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Scrollable execution history with PC, opcode, flags. Historical view of execution.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create Trace widget (scrollable table)
- [ ] Display trace records (seq, PC, opcode, flags)
- [ ] Implement auto-scroll to bottom
- [ ] Add manual scrolling support
- [ ] Limit buffer size (configurable)
- [ ] Format trace data for display
- [ ] Add trace panel tests
- [ ] Document trace panel

---

### 3.2 Stack Panel

**Priority:** MEDIUM  
**Dependencies:** 1.3 (App shell), Executive Phase 1.5 (Stack reconstruction)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Call stack frames with symbol names. Navigate call hierarchy.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create Stack widget (list view)
- [ ] Fetch stack frames from executive
- [ ] Display frame index, function name, address
- [ ] Show source file and line if available
- [ ] Implement frame selection (highlight)
- [ ] Update on debug_break events
- [ ] Add stack panel tests
- [ ] Document stack panel

---

### 3.3 Memory Inspector

**Priority:** MEDIUM  
**Dependencies:** 1.3 (App shell)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Hex dump with ASCII preview and navigation. Low-level memory inspection.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create Memory widget (hex dump view)
- [ ] Display memory address, hex values, ASCII
- [ ] Implement scrolling and navigation (PgUp/PgDn)
- [ ] Add address jump (type address to navigate)
- [ ] Highlight changed bytes
- [ ] Fetch memory from executive
- [ ] Add memory panel tests
- [ ] Document memory panel

---

### 3.4 Watch List

**Priority:** MEDIUM  
**Dependencies:** 1.3 (App shell), Executive Phase 2.3 (Watch expressions)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Variables and expressions with real-time value updates. Monitor key values.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create Watch widget (list view)
- [ ] Display watch expression and current value
- [ ] Add/remove watches interactively
- [ ] Update values on events
- [ ] Highlight changed values
- [ ] Support address and symbol watches
- [ ] Add watch panel tests
- [ ] Document watch panel

---

### 3.5 Mailbox Panel

**Priority:** LOW  
**Dependencies:** 1.3 (App shell)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Descriptor activity and recent messages. Monitor IPC activity.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create Mailbox widget (table view)
- [ ] Display descriptor list (target, capacity, mode)
- [ ] Show recent messages (sender, size, seq)
- [ ] Update on mailbox events
- [ ] Implement message inspection (detail view)
- [ ] Add mailbox panel tests
- [ ] Document mailbox panel

---

## Phase 4: Event Integration

### 4.1 Event Handlers

**Priority:** HIGH  
**Dependencies:** 1.4 (Connection manager), Phase 2 & 3 (Panels)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Subscribe to debugger core events (trace_step, debug_break, etc.). Drive panel updates.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Subscribe to trace_step events
- [ ] Subscribe to debug_break events
- [ ] Subscribe to task_state events
- [ ] Subscribe to register_changed events
- [ ] Subscribe to memory_changed events
- [ ] Subscribe to stdout/stderr events
- [ ] Route events to appropriate panels
- [ ] Add event handler tests
- [ ] Document event handling

---

### 4.2 Panel Updates

**Priority:** HIGH  
**Dependencies:** 4.1 (Event handlers)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Transform events into panel update messages with throttling. Ensure responsive UI (<200ms latency).

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Implement event-to-update transformation
- [ ] Add update throttling (limit refresh rate)
- [ ] Queue updates for batch processing
- [ ] Implement panel refresh methods
- [ ] Optimize update performance
- [ ] Add panel update tests
- [ ] Document update mechanism

---

### 4.3 Change Highlighting

**Priority:** MEDIUM  
**Dependencies:** 4.2 (Panel updates)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Visual indicators for register/memory changes. Helps user track state changes.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Track previous values for comparison
- [ ] Highlight changed registers (color/style)
- [ ] Highlight changed memory bytes
- [ ] Add fade-out animation for highlights
- [ ] Make highlighting configurable
- [ ] Add highlighting tests
- [ ] Document highlighting behavior

---

## Phase 5: Keyboard Navigation

### 5.1 Global Shortcuts

**Priority:** HIGH  
**Dependencies:** 1.3 (App shell)  
**Estimated Effort:** 2-3 days

**Rationale:**  
F5 (continue), F10 (step over), F11 (step in), F9 (toggle breakpoint). Standard debugger shortcuts.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Implement F5 (continue execution)
- [ ] Implement F10 (step over)
- [ ] Implement F11 (step into)
- [ ] Implement Shift+F11 (step out)
- [ ] Implement F9 (toggle breakpoint at PC)
- [ ] Implement Ctrl+C (pause execution)
- [ ] Add global shortcut tests
- [ ] Document keyboard shortcuts

---

### 5.2 Panel Navigation

**Priority:** MEDIUM  
**Dependencies:** 1.3 (App shell)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Tab/Shift+Tab to switch focus between panels. Navigate between views.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Implement Tab (focus next panel)
- [ ] Implement Shift+Tab (focus previous panel)
- [ ] Highlight focused panel (border color)
- [ ] Implement panel focus cycling
- [ ] Add panel navigation tests
- [ ] Document navigation keys

---

### 5.3 Scrolling

**Priority:** MEDIUM  
**Dependencies:** Phase 2 & 3 (Scrollable panels)  
**Estimated Effort:** 1-2 days

**Rationale:**  
Arrow keys, PgUp/PgDn for scrollable panels. Navigate panel contents.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Implement Up/Down arrow scrolling
- [ ] Implement PgUp/PgDn page scrolling
- [ ] Implement Home/End navigation
- [ ] Add mouse wheel support (optional)
- [ ] Add scrolling tests
- [ ] Document scrolling keys

---

### 5.4 Command Mode

**Priority:** MEDIUM  
**Dependencies:** 2.3 (Console panel)  
**Estimated Effort:** 1 day

**Rationale:**  
`:` to enter command input in console panel. Vi-style command entry.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Implement `:` key to focus console input
- [ ] Implement Esc to return to normal mode
- [ ] Add command mode indicator
- [ ] Add command mode tests
- [ ] Document command mode

---

## Phase 6: Layout and Themes

### 6.1 Default Layout

**Priority:** HIGH  
**Dependencies:** Phase 2 & 3 (All panels)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Implement standard layout from section 5.1. Organized panel arrangement.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Design default layout (panel positions and sizes)
- [ ] Implement layout composition
- [ ] Left column: registers, stack
- [ ] Center: disassembly, trace
- [ ] Right: watches, memory
- [ ] Bottom: console
- [ ] Top: status bar
- [ ] Add layout tests
- [ ] Document layout structure

---

### 6.2 Responsive Resizing

**Priority:** MEDIUM  
**Dependencies:** 6.1 (Default layout)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Dynamic panel sizing based on terminal dimensions. Adapt to different screen sizes.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Implement responsive grid layout
- [ ] Handle terminal resize events
- [ ] Adjust panel sizes proportionally
- [ ] Implement minimum panel sizes
- [ ] Hide panels if terminal too small
- [ ] Add resize tests
- [ ] Document responsive behavior

---

### 6.3 Theme Support

**Priority:** LOW  
**Dependencies:** 1.3 (App shell)  
**Estimated Effort:** 2-3 days

**Rationale:**  
Dark and light color schemes. User preference support.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Define dark theme (default)
- [ ] Define light theme
- [ ] Implement theme switching
- [ ] Apply themes to all panels
- [ ] Add theme configuration option
- [ ] Add theme tests
- [ ] Document themes

---

## Phase 7: Testing and Documentation

### 7.1 Widget Tests

**Priority:** MEDIUM  
**Dependencies:** Phase 2 & 3 (Panels)  
**Estimated Effort:** 1 week

**Rationale:**  
Unit tests for individual panel components. Ensure widget quality.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Add registers panel widget tests
- [ ] Add disassembly panel widget tests
- [ ] Add console panel widget tests
- [ ] Add status bar widget tests
- [ ] Add trace panel widget tests
- [ ] Add stack panel widget tests
- [ ] Add memory panel widget tests
- [ ] Add watch panel widget tests
- [ ] Measure widget test coverage (target >80%)

---

### 7.2 Integration Tests

**Priority:** MEDIUM  
**Dependencies:** 7.1 (Widget tests)  
**Estimated Effort:** 3-4 days

**Rationale:**  
Full TUI debugging workflows with mock events. End-to-end testing.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Create integration test scenarios
- [ ] Test TUI startup and connection
- [ ] Test stepping workflow with panel updates
- [ ] Test breakpoint workflow
- [ ] Test event handling and panel synchronization
- [ ] Test keyboard navigation
- [ ] Add integration tests to CI
- [ ] Document integration test suite

---

### 7.3 User Guide

**Priority:** HIGH  
**Dependencies:** Phases 1-6 complete  
**Estimated Effort:** 2-3 days

**Rationale:**  
Comprehensive TUI keyboard shortcuts and panel descriptions. User documentation.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Write user guide in `docs/tui_debugger.md`
- [ ] Document all keyboard shortcuts
- [ ] Describe each panel and its purpose
- [ ] Add navigation guide
- [ ] Include troubleshooting section
- [ ] Provide quick start tutorial
- [ ] Review and refine documentation

---

### 7.4 Screenshots

**Priority:** LOW  
**Dependencies:** 7.3 (User guide)  
**Estimated Effort:** 1 day

**Rationale:**  
Visual examples of TUI in action. Help users understand interface.

**Todo:**
> Reference: [Implementation Notes](03--ImplementationNotes.md) | [Design 04.10--TUI_Debugger](../../../04--Design/04.10--TUI_Debugger.md)
- [ ] Capture screenshots of TUI
- [ ] Show default layout
- [ ] Show different panel views
- [ ] Show keyboard shortcuts in action
- [ ] Add screenshots to documentation
- [ ] Add animated GIFs of workflows

---

## Definition of Done (DoD)

This implementation is considered complete when all of the following criteria are met:

### Phase 1 Completion
- [ ] Textual framework integrated
- [ ] TUI application module functional
- [ ] Application shell with layout management working
- [ ] Connection manager operational
- [ ] All Phase 1 tests pass

### Phase 2 Completion
- [ ] Registers panel displaying values
- [ ] Disassembly panel showing instructions
- [ ] Console panel with input/output functional
- [ ] Status bar displaying system info
- [ ] All Phase 2 tests pass

### Phase 3 Completion
- [ ] Trace panel showing execution history
- [ ] Stack panel displaying call frames
- [ ] Memory inspector showing hex dump
- [ ] Watch list tracking expressions
- [ ] Mailbox panel showing IPC activity
- [ ] All Phase 3 tests pass

### Phase 4 Completion
- [ ] Event handlers subscribed and routing events
- [ ] Panel updates responsive (<200ms latency)
- [ ] Change highlighting working
- [ ] All Phase 4 tests pass

### Phase 5 Completion
- [ ] Global keyboard shortcuts functional (F5, F10, F11, F9)
- [ ] Panel navigation working (Tab, Shift+Tab)
- [ ] Scrolling operational in all panels
- [ ] Command mode functional
- [ ] All Phase 5 tests pass

### Phase 6 Completion
- [ ] Default layout implemented
- [ ] Responsive resizing working
- [ ] Theme support functional (dark/light)
- [ ] All Phase 6 tests pass

### Phase 7 Completion
- [ ] Widget tests >80% coverage
- [ ] Integration tests passing
- [ ] User guide complete with screenshots
- [ ] All Phase 7 tests pass

### Overall Quality Criteria
- [ ] TUI debugger functional for all common workflows
- [ ] Integration with hsxdbg core package verified
- [ ] Integration with Executive debugger APIs verified
- [ ] Performance acceptable (UI responsive under load)
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
- [04.10--TUI_Debugger.md](../../../04--Design/04.10--TUI_Debugger.md) - TUI Debugger Design

**Gap Analysis:**
- [01--Study.md](./01--Study.md) - Gap Analysis Study

**Dependencies:**
- [DependencyTree.md](../DependencyTree.md) - Cross-module dependency tracking
- [06--Toolkit](../06--Toolkit/01--Study.md) - hsxdbg core package (Phases 1-3)
- [02--Executive](../02--Executive/01--Study.md) - Debugger APIs (Phase 1-2)
- [05--Toolchain](../05--Toolchain/01--Study.md) - Symbol files (Phase 3)

**Documentation:**
- `docs/tui_debugger.md` - TUI debugger user guide (to be created)
- Textual Documentation: https://textual.textualize.io/

---

**Last Updated:** 2025-10-31  
**Status:** Initial Plan  
**Owner:** TUI Debugger Implementation Team

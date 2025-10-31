# Gap Analysis: TUI Debugger

## 1. Scope Recap

_Brief synopsis of the design document and links back to the design specification._

**Design Reference:** [04.10--TUI_Debugger.md](../../../04--Design/04.10--TUI_Debugger.md)

**Summary:**  
The TUI Debugger design specifies a full-screen terminal interface for HSX debugging. It comprises:

- **Textual Framework** - Modern Python TUI framework with asyncio integration
- **Modular Panel Layout** - Registers, disassembly, trace, stack, memory, watches, mailbox, console
- **Event-Driven Updates** - Real-time panel updates triggered by debugger core events (<200ms latency)
- **Keyboard-First Navigation** - All functionality accessible via keyboard shortcuts
- **Responsive Layout** - Dynamic panel resizing based on terminal dimensions

**Dependencies:**
- Built on `hsxdbg` core package (see [06--Toolkit](../06--Toolkit/01--Study.md))
- Requires executive debugger RPC APIs (see [02--Executive](../02--Executive/01--Study.md))
- Requires toolchain symbol metadata (see [05--Toolchain](../05--Toolchain/01--Study.md))

---

## 2. Current Implementation

_What already exists today that satisfies the design intent._

**Code Paths:**
- **No TUI debugger implementation** - Complete TUI is missing

**Tests:**
- **No TUI tests** - No test coverage

**Tools:**
- `python/blinkenlights.py` (451 lines) - Visual monitor for mailbox activity (not a debugger, but demonstrates real-time visualization concept)

**Documentation:**
- Design documents: `main/04--Design/04.10--TUI_Debugger.md`

---

## 3. Missing or Partial Coverage

_Gaps that block full compliance with the design._

**Open Items:**
- **Complete TUI missing:** Design specifies Textual-based visual debugger with multiple panels. Not implemented.
- **Application shell (4.3.1):** No main application class managing layout, event routing, lifecycle
- **Panel components (4.3.2):** No panel widgets implemented:
  - No registers panel (R0-R15, PC, SP, PSW display)
  - No disassembly panel (instructions around PC with symbols, breakpoints)
  - No trace panel (scrollable execution history)
  - No stack panel (call stack with frame pointers)
  - No memory inspector (hex dump with ASCII preview)
  - No watch list (variables and expressions)
  - No mailbox panel (descriptor activity, messages)
  - No console panel (stdout/stderr, command input)
  - No status bar (connection info, PID, state, counters)
- **Event handlers (4.3.3):** No event subscription or panel update logic
- **Layout system (5):** No default or custom layout implementation
- **Keyboard shortcuts (7):** No global shortcuts for navigation, stepping, breakpoint toggle
- **Theme support (6):** No color schemes or visual customization
- **Connection management:** No debugger core session integration

**Deferred Features:**
- **Advanced TUI features (DO-8.a):** Enhanced visualizations, custom layouts, scripting in TUI
- **Multi-PID views:** Simultaneous debugging of multiple processes
- **Split-screen layouts:** User-configurable panel arrangements
- **Mouse support:** Optional mouse interaction for panel resizing and navigation

**Documentation Gaps:**
- No user guide for TUI keyboard shortcuts and navigation
- No examples of custom layouts or themes

---

## 4. Next Actions

_Ordered steps to close the gaps._

**Priority Actions:**

**Phase 1: TUI Framework Setup (requires hsxdbg core from 06--Toolkit Phase 1-3)**
1. **Install Textual dependency** - Add `textual >= 0.58.0` to project requirements
2. **Create TUI application module** - New `hsx-tui` command-line tool built on `hsxdbg` core
3. **Application shell** - Main Textual app class with layout management and event routing
4. **Connection manager** - Integrate debugger core session and event subscription

**Phase 2: Core Panel Implementation**
5. **Registers panel** - Display R0-R15, PC, SP, PSW with change highlighting
6. **Disassembly panel** - Show instructions around PC with symbols and breakpoint markers
7. **Console panel** - Stdout/stderr output and command input field
8. **Status bar** - Connection info, PID, execution state, runtime counters

**Phase 3: Advanced Panels**
9. **Trace panel** - Scrollable execution history with PC, opcode, flags
10. **Stack panel** - Call stack frames with symbol names
11. **Memory inspector** - Hex dump with ASCII preview and navigation
12. **Watch list** - Variables and expressions with real-time value updates
13. **Mailbox panel** - Descriptor activity and recent messages

**Phase 4: Event Integration**
14. **Event handlers** - Subscribe to debugger core events (trace_step, debug_break, etc.)
15. **Panel updates** - Transform events into panel update messages with throttling
16. **Change highlighting** - Visual indicators for register/memory changes

**Phase 5: Keyboard Navigation**
17. **Global shortcuts** - F5 (continue), F10 (step over), F11 (step in), F9 (toggle breakpoint)
18. **Panel navigation** - Tab/Shift+Tab to switch focus between panels
19. **Scrolling** - Arrow keys, PgUp/PgDn for scrollable panels
20. **Command mode** - : to enter command input in console panel

**Phase 6: Layout and Themes**
21. **Default layout** - Implement standard layout from section 5.1
22. **Responsive resizing** - Dynamic panel sizing based on terminal dimensions
23. **Theme support** - Dark and light color schemes

**Phase 7: Testing and Documentation**
24. **Widget tests** - Unit tests for individual panel components
25. **Integration tests** - Full TUI debugging workflows with mock events
26. **User guide** - Comprehensive TUI keyboard shortcuts and panel descriptions
27. **Screenshots** - Visual examples of TUI in action

**Cross-References:**
- Design Requirements: DR-8.1, DG-8.1, DG-8.2, DG-8.3
- Dependencies: `hsxdbg` core package [06--Toolkit](../06--Toolkit/01--Study.md) Phases 1-3
- Executive debugger APIs [02--Executive](../02--Executive/01--Study.md) Phase 4
- Toolchain symbol files [05--Toolchain](../05--Toolchain/01--Study.md) Phase 3

---

**Last Updated:** 2025-10-31  
**Status:** Not Started (Complete TUI missing)

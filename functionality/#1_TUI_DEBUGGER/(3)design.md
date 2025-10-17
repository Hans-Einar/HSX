# Feature Design — HSX Debugger Toolkit & TUI

> Detailed specification for the agreed solution. Update as the design playbook (D1–D6) progresses.

## Overview
- Feature ID: `#1_TUI_DEBUGGER`
- Design status: `not started`
- Last updated: `2025-10-16`
- Related docs: `(1)functionality.md`, `(2)study.md`

## Architecture & Components
- **Debugger core:** shared session/transport/event layer consumed by CLI (`dbg`), scripting API, and TUI.
- **CLI (`dbg`):** command-line entry point building atop the core; supports scripted and interactive usage.
- **TUI frontend:** implemented using the selected framework (textual/prompt_toolkit/etc.), composing modular panels (registers/stack/memory/watch/trace).
- **Executive/VM updates:** mailbox/event channel, trace instrumentation, stack/memory hooks, BRK/virtual breakpoint support.

## Detailed Design Tasks

### D1 Evaluate TUI frameworks (`not started`)
- <!-- populate once D1 tasks complete -->

### D2 Draft debugger-core architecture (`not started`)
- <!-- populate once D2 tasks complete -->

### D3 Prototype executive signalling channel (`not started`)
- <!-- populate once D3 tasks complete -->

### D4 Audit VM/executive for stack/memory support (`not started`)
- <!-- populate once D4 tasks complete -->

### D5 Define MCU `dbg.hsx` relay (`not started`)
- <!-- populate once D5 tasks complete -->

### D6 Prepare design documentation (`not started`)
- <!-- populate once D6 tasks complete -->

## Compatibility & Migration Considerations
- To be detailed once architecture decisions are final.

## Testing Strategy
- To be specified during the design phase (unit, integration, manual validation).

## Documentation Updates
- Identify required documentation changes (CLI/TUI help, architecture notes) during design.

## Risks & Mitigations
- Record risks and proposed mitigations as design decisions are made.

## Sign-off
- Approved by: `<pending>`
- Date: `<pending>`

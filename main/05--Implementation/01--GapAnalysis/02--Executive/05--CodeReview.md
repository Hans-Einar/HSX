# Code Review – Executive (02--Executive)

## Scope
Reviewed the Python executive implementation through Phase 2.6 (sessions, events, breakpoints, symbol/stack APIs, memory regions, watches, task-state streaming, `trace_step.changed_regs`). Cross-checked behaviour against `02--ImplementationPlan.md`, the accompanying implementation notes, and the executive design spec (`04.02--Executive.md`).

## Findings

- **Gap vs. plan (“config flag” still missing)** – `python/execd.py:156`  
  The Phase 2.6 checklist calls for making register-diff tracking optional (“config flag”). The current code only exposes a private attribute (`ExecutiveState.trace_track_changed_regs`) that tests can toggle but clients cannot. Please add a user-facing control (e.g., negotiated session capability or CLI flag) so downstream tools can disable `changed_regs` if the extra payload is unwanted.

- **Spec compliance improvement** – `python/execd.py:1654`  
  `changed_regs` always includes `"PC"` because the Program Counter changes on every step. That matches the literal register diff, but the design intent was to highlight meaningful state deltas for debugger UIs. Consider suppressing `"PC"` (and possibly unchanged `"PSW"`) unless an instruction explicitly modifies them, or document the behaviour so consumers know to filter out the noise.

- **Overall alignment**  
  Session lifecycle, event streaming/back-pressure, breakpoint handling, symbol/stack/disasm helpers, memory regions, watch expressions, task-state reasons, and protocol/help documentation all match the design sections that were implemented. Recent task-state and `changed_regs` docs (`docs/executive_protocol.md`, `help/events.txt`) are in sync with the emitted payloads.

## Recommendations
1. Expose a proper configuration surface for enabling/disabling register diff tracking (e.g., a `session.open` capability or `config` command) and propagate the setting into `_handle_trace_step_event`.
2. Either filter redundant `"PC"`/`"PSW"` entries from `changed_regs` or clearly document the semantics so debugger authors can make an informed decision.

Addressing these items keeps the executive features consistent with the plan and avoids surprising downstream tooling.

## Update
- 2025-11-03: Added `trace config changed-regs <on|off>` control path (see `python/execd.py:156/3170`, `python/shell_client.py:1507`) and filtered the implicit PC diff so `changed_regs` only reports meaningful register updates. Documentation/help were updated accordingly.

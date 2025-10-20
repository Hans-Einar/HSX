# Refactor Context — Core Functionality Alignment

## Snapshot
- **Subsystem(s):** `python/execd.py` executive daemon, MiniVM backend (`platforms/python/host_vm.py`), debugger tooling (`functionality/#1_TUI_DEBUGGER`), HSX documentation set (`docs/hsx_spec-v2.md`, `docs/executive_protocol.md`), milestone roadmap.
- **Motivation:** The current runtime/executive behaviour has drifted from the documented architecture in `hsx_spec-v2.md` and the expectations captured for the debugger feature. We need to align the core infrastructure before pushing deeper on tooling so that milestone sequencing (notably Milestone 5 and the upcoming debugger milestone) reflects reality.
- **Drivers:** 
  - Gap analysis captured in `functionality/#1_TUI_DEBUGGER/main_code_implementation_gaps.md`.
  - Requirements and study material for the debugger (`functionality/#1_TUI_DEBUGGER/(3)requirements.md`, `(2)study.md`).
  - Strategic decision to bring Milestone 9 (Debugger & Tooling) forward immediately after Milestone 5.
  - Observed divergence between `MILESTONES.md` commitments and the in-tree implementation.

## Current Behaviour
- `python/execd.py` exposes the documented RPC commands (attach/step/clock/etc.) but lacks session-scoped control, persistent event feeds, and breakpoint mediation. Event payloads are logged and discarded rather than streamed to clients.
- MiniVM’s debug hooks (`platforms/python/host_vm.py`) can emit `debug_stop` events and honour temporary breakpoints internally, yet execd does not surface them; breakpoint lists live only in the VM process.
- Toolchain symbols and metadata remain optional; the executive keeps only transient state (task table, log deque) with no persistent store for symbols, trace history, or breakpoint archives.
- Documentation (`docs/hsx_spec-v2.md`, `docs/executive_protocol.md`) describes richer behaviour (capability negotiation, watcher feeds, run-to-PC operations) than is currently implemented.
- Milestone tracking indicates completion up to Milestone 5, but the implemented features do not fully satisfy the documented acceptance criteria or the needs identified for the debugger milestone.

## Observed Problems
- **Session management gaps:** No PID-scoped session objects or capability negotiation, preventing safe multi-client usage and blocking debugger requirements (ref. gaps §1).
- **Breakpoint mediation absent:** Execd lacks APIs to add/remove/list breakpoints or to propagate `debug_stop` notifications, forcing front-ends to poll or talk to the VM directly (ref. gaps §2; requirements F-4, S-1).
- **No event/signalling channel:** Clients cannot subscribe to scheduler/mailbox/trace updates; execd discards VM events after logging (ref. gaps §3; requirements F-6).
- **Run-to-PC / multi-break control missing:** There is no facility to arm the executive with program-counter breakpoints for hands-off stepping; debugger would have to single-step and compare PCs locally, which is inefficient for both host and MCU targets.
- **Documentation drift:** Milestone descriptions and HSX spec reference features (data stores, configuration hooks, mailbox-driven signalling) that are absent or partially implemented, making it hard to validate current progress.
- **Process visibility loss:** Without a consolidated requirements baseline (new `(3)requirements.md`) and refactor tracking, it is difficult to measure how far Milestone 5 actually progressed and what remains before tooling layers can depend on it.

## Constraints & Assumptions
- Maintain compatibility with existing RPC protocol version 1 while extending execd; legacy shell clients must continue to work during the refactor.
- Proposed breakpoint and event handling should live inside execd so lightweight debugger shims (including potential MCU-side tooling) can reuse the same control surface.
- Refactor must keep MiniVM single-task semantics intact; scheduler/executive responsibilities remain separated per existing implementation constraints.
- Documentation in `docs/hsx_spec-v2.md` will be treated as source-of-truth; any intentional deviations uncovered during refactor should be captured and fed back into both the spec and milestone plan.
- Milestone ordering will be updated to position the debugger (current Milestone 9) immediately after Milestone 5, so refactor outcomes should support that sequencing.

## Additional Notes
- This refactor package seeds the structured SDP workflow (`refactor/#01_CoreFunctionality`) so subsequent objectives, analysis, and design documents can be populated as gaps are closed.
- Follow-up tasks will include defining concrete objectives for restoring Milestone 5 scope, specifying required execd enhancements (event stream, breakpoint registry, run-to-PC), and updating `MILESTONES.md`/`agents.md` to reflect the revised roadmap.*** End Patch

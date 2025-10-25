# Disassembler Implementation Plan

## DR/DG Alignment
- DR-3.1 / DG-3.3: Consume linker symbol/line metadata for UI panels.
- DR-8.1 / DG-8.1: Provide CLI/TUI friendly disassembly views integrated with event stream.

## Implementation Notes
- Build parser for listing/debug sidecar produced by linker; surface per-PC metadata in hsxdbg state cache.
- Support numeric + named symbols (DG-7.4) in output.
- Provide JSON output for automation/test harnesses.

## Playbook
- [ ] Implement sidecar ingestion library shared by CLI/TUI.
- [ ] Add filters (per module, per PID) to reduce noise.
- [ ] Integrate with watch list to highlight tracked addresses.

## Commit Log
- _Pending_.

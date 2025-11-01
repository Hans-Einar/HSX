# Code Review – MiniVM (01--VM)

## Scope
Reviewed the Python reference MiniVM implementation against the current plan (`02--ImplementationPlan.md`) and design contract (`04.01--VM.md`). Focused on the recently delivered Phase 1 work (shift ops, PSW flags, ADC/SBC, DIV, trace support, streaming loader).

## Findings

- **Bug / Spec drift** – `platforms/python/host_vm.py:1010`  
  Shift instructions set `overflow=None` when the shift amount is zero, which preserves the previous `V` flag. The design doc and MVASM notes state that shifts must always clear `V`. Please update the shift handlers so they explicitly clear `V` (e.g., pass `overflow=False` even for zero shifts) to match the spec.

- **Documentation stale** – `docs/abi_syscalls.md:23`  
  The shift operation blurb still says “Results update the zero flag pending the broader PSW implementation work.” The VM now updates Z/N/C/V, so this text should be refreshed (and ideally call out the new carry semantics) to keep the ABI documentation authoritative.

- **General consistency**  
  Other reviewed items (ADC/SBC opcodes, DIV error handling, trace API snapshots, streaming loader) line up with the design tables in `04.01--VM.md` and the plan deliverables. No functional gaps observed there.

## Recommendations
1. Patch `host_vm.py` so every shift explicitly clears `V`, even for shift-by-zero cases, and add a regression asserting that behaviour.
2. Refresh `docs/abi_syscalls.md` (and any related ISA notes) to describe the final PSW semantics for the new instructions.

Once those issues are addressed, Phase 1 stays fully in sync with the published design.

## Update
- 2025-11-03: Cleared shift-overflow drift by forcing `set_flags(... overflow=False)` in `platforms/python/host_vm.py:1008` and refreshed `docs/abi_syscalls.md` to document full PSW behaviour.

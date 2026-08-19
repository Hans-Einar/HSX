# DBG-ST-003 — Inspection, Resources, Lifecycle, and Execution Semantics

- Status: ACTIVE STUDY
- DesignAnalysis: `DBG-DA-001`
- Iteration: `DBG-IT-001-002`
- Owning issue: #38

## Question and scope

Which model best satisfies symbol/source/address/inspection fidelity, multi-client
breakpoint/watch ownership, explicit target lifecycle, and distinct instruction/source
stepping semantics across `DBG-R-005..DBG-R-006` and `DBG-R-014..DBG-R-025`?

## Required evidence

- current `python/hsx_dbg/symbols.py`, backend/resource/stack helpers, debugger/DAP handlers,
  executive debug semantics, and relevant tests/fixtures;
- legacy HSX/debugger design evidence and cross-track `HSX-ST-001` dependency;
- `DBG-ST-001`, `DBG-CR-001`, and `DBG-GAP-001`.

## Required analysis

- define address/source identity and stop-snapshot inspection contracts;
- define breakpoint/watch desired-vs-actual state, owner/provenance, and reconciliation;
- define attach, launch, detach/disconnect, terminate/kill semantics;
- define instruction, source-into, source-over, and source-out algorithms and stop reasons;
- separate Debugger-owned contracts from missing HSX runtime contracts;
- state responsibilities/non-responsibilities, alternatives, risks, and proposed contracts.

## Non-goals

No product edits, no frontend presentation design, no invented HSX architecture contract, and
no implementation authorization.

## Findings

To be completed by the assigned Study worker.

# DBG-ST-005 — Legacy Reuse, Adapt, Replace, and Regression-Oracle Audit

- Status: ACTIVE STUDY
- DesignAnalysis: `DBG-DA-001`
- Iteration: `DBG-IT-001-002`
- Owning issue: #38

## Question and scope

Which current debugger components and behaviors should be reused, adapted/extracted,
replaced, or retired without allowing legacy module boundaries to dictate the target
architecture?

## Required evidence

- `python/hsx_dbg/backend.py`, `session.py`, and `symbols.py`;
- `python/executive_session.py`;
- `python/hsx_dap/__init__.py` and DAP wrappers;
- Python debugger tests/fixtures;
- `vscode-hsx/src/extension.ts`, package/runtime launcher, tests, and custom views;
- signed `DBG-RF-001` regression oracle and all `DBG-F-001..DBG-F-026` findings.

## Required analysis

- component-by-component reuse/adapt/replace/retire decision with evidence;
- useful semantics/API/data types worth preserving independent of file layout;
- risks and prerequisite regression tests for every move/replacement;
- compatibility mechanisms with explicit retain/remove conditions;
- migration ordering that keeps the legacy debugger runnable as an oracle;
- gaps where evidence is insufficient for a confident decision.

## Non-goals

No product edits, no final architecture decision, no optimistic parity claim, and no
implementation authorization.

## Findings

To be completed by the assigned Study worker.

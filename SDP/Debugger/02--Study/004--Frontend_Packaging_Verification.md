# DBG-ST-004 — Frontend, Packaging, and Production Verification Architecture

- Status: ACTIVE STUDY
- DesignAnalysis: `DBG-DA-001`
- Iteration: `DBG-IT-001-002`
- Owning issue: #38

## Question and scope

Which thin DAP, CLI, VS Code presentation, runtime-package, compatibility, and production
verification boundaries best satisfy `DBG-R-001..DBG-R-003`, `DBG-R-026..DBG-R-036`?

## Required evidence

- current DAP wrapper/adapter, `python/hsx_dap/`, CLI debugger, `vscode-hsx/src/extension.ts`,
  extension manifest/scripts/tests, DAP tests/fixtures, and `DBG-RF-001` oracle;
- packaging and cross-platform behavior from current code/docs;
- `DBG-ST-001`, `DBG-CR-001`, and `DBG-GAP-001`.

## Required analysis

- define thin frontend ports and DAP serialization/capability responsibilities;
- separate standard DAP UX from optional HSX-specific VS Code views;
- compare version-coherent runtime packaging options;
- define compatibility registry and removal conditions;
- define production-path Windows/Linux verification layers and release oracle;
- state responsibilities/non-responsibilities, alternatives, risks, and proposed contracts.

## Non-goals

No product edits, no debugger-core policy in frontend modules, no package build, and no
implementation authorization.

## Findings

To be completed by the assigned Study worker.

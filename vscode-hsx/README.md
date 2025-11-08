# HSX VS Code Debugger (Preview)

This extension wires the HSX Debug Adapter (`python/hsx_dap`) into the VS Code
debugger UI so you can attach to an executive instance and inspect stacks,
registers, and watches from within the IDE.

## Status

- Supports launch/attach, pause/continue, single-step, stack traces, registers,
  watch display, and console output.
- Relies on the Python `hsx_dap` module that lives in this repository. The
  extension's debug adapter wrapper (`debugAdapter/hsx-dap.py`) simply ensures
  the repo root is on `sys.path` and invokes `python.hsx_dap.main()`.
- Additional features (hover evaluation, memory read/write, breakpoint source
  mapping) will land in upcoming iterations.

## Usage

1. Install VS Code and ensure `python3` is available on your PATH (or set the
   `PYTHON`/`HSX_PYTHON` environment variables).
2. From this repository root run `code vscode-hsx`.
3. Press <kbd>F5</kbd> (run extension) or package the extension normally. The
   contributed debug type is `hsx`.
4. Add a debug configuration similar to:

```jsonc
{
  "type": "hsx",
  "name": "HSX Launch",
  "request": "launch",
  "pid": 1,
  "host": "127.0.0.1",
  "port": 9998
}
```

5. Start the HSX manager/executive, then launch the configuration. The adapter
   will lock the requested PID, stream events, and surface stacks/registers in
   VS Code.

## Repository Layout

```
vscode-hsx/
├── package.json       # Extension manifest (contributes `hsx` debugger)
├── README.md          # This file
├── src/extension.js   # Activation logic + debug adapter factory
└── debugAdapter/
    └── hsx-dap.py     # Wrapper that launches python.hsx_dap.main()
```

The actual DAP implementation lives under `python/hsx_dap`. Keeping the adapter
logic in Python allows us to reuse `hsxdbg` (transport/session/cache) directly.

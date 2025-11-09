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

1. Install VS Code and ensure `python3` (or your preferred interpreter) is
   available on your PATH. You can point the extension at a custom interpreter
   with the `pythonPath` launch option or via the `PYTHON`/`HSX_PYTHON`
   environment variables.
2. From this repository root run `code vscode-hsx` and execute `npm install`
   (installs the TypeScript toolchain for the extension).
3. Use `npm run compile` to build `dist/extension.js` or `npm run watch` to
   rebuild automatically while developing the extension.
4. Press <kbd>F5</kbd> to launch an “Extension Development Host” session or run
   `npm run package` (requires `vsce`) to produce a `.vsix` you can install
   elsewhere. The contributed debug type is `hsx`.
5. Add a debug configuration similar to:

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

6. Start the HSX manager/executive, then launch the configuration. The adapter
   will lock the requested PID, stream events, and surface stacks/registers in
   VS Code.

### Launch options

Every `hsx` configuration understands the following properties:

| Property     | Description                                                                 |
|--------------|-----------------------------------------------------------------------------|
| `pid`        | Required. Executive PID to lock via `session.open`.                         |
| `host`       | Executive host (defaults to `127.0.0.1`).                                   |
| `port`       | Executive port (defaults to `9998`).                                        |
| `symPath`    | Optional path to a `.sym` file hint (forwarded to the Python adapter).      |
| `pythonPath` | Interpreter used to launch `hsx-dap.py`.                                    |
| `logLevel`   | Adapter log verbosity (`CRITICAL`, `ERROR`, `WARNING`, `INFO`, `DEBUG`).    |
| `adapterArgs`| Extra command-line switches appended after `hsx-dap.py`.                    |
| `env`        | Additional environment variables merged into the adapter process.           |

The extension registers a snippet named **“HSX: Attach PID”** that seeds a
configuration with the most common fields.

## Repository Layout

```
vscode-hsx/
├── package.json       # Extension manifest + npm scripts
├── README.md          # This file
├── src/extension.ts   # Activation logic + debug adapter factory (TypeScript)
├── dist/extension.js  # Compiled JavaScript consumed by VS Code
└── debugAdapter/
    └── hsx-dap.py     # Wrapper that launches python.hsx_dap.main()
```

The actual DAP implementation lives under `python/hsx_dap`. Keeping the adapter
logic in Python allows us to reuse `hsxdbg` (transport/session/cache) directly.

# HSX Shell Demo

This demo builds a simple shell task that runs inside the HSX Python VM. The shell lists available payload `.hxe`
images and launches the first entry via the new exec syscall shim.

## Build

```bash
make
```

This compiles `shell.mvasm` into `build/shell.hxe` and builds each payload under `payloads/*/` into
`build/payloads/<name>/main.hxe`.

## Run

```bash
make run
```

The `run` target launches the VM with `shell.hxe`, pointing `--exec-root` at the built payload directory.

## Files

- `shell.mvasm` – hand-written assembly for the shell task (UART + SVC usage).
- `payloads/` – sample programs compiled to `.hxe` that the shell can launch.
- `Makefile` – orchestrates both the shell build and the payload toolchain steps.


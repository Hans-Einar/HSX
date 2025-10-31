# Simple Direct Build Example

This example demonstrates the simplest use case: building a single C source file directly.

## Files

- `main.c` - Simple C program that returns 42

## Build Command

```bash
python3 ../../../python/hsx-cc-build.py --debug main.c -o hello.hxe
```

## What Happens

1. **Compilation**: `main.c` → `main.ll` (LLVM IR with debug info)
2. **Lowering**: `main.ll` → `main.asm` + `main.dbg` (MVASM + debug metadata)
3. **Assembly**: `main.asm` → `main.hxo` (Object file)
4. **Linking**: `main.hxo` → `hello.hxe` + `hello.sym` (Executable + symbols)
5. **Metadata**: Generate `sources.json` for debugger path resolution

## Output Files

After building, check `build/debug/`:
```
build/debug/
├── hello.hxe        # Executable
├── hello.sym        # Symbol file with line numbers
├── sources.json     # Source path mappings
├── main.ll          # LLVM IR (intermediate)
├── main.asm         # MVASM (intermediate)
├── main.dbg         # Debug info (intermediate)
└── main.hxo         # Object file (intermediate)
```

## Verifying the Build

Check that debug artifacts were created:
```bash
ls -lh build/debug/
cat build/debug/sources.json
```

## Alternative: Release Build

For a release build without debug info:
```bash
python3 ../../../python/hsx-cc-build.py main.c -o hello.hxe -b build/release
```

This produces only `build/release/hello.hxe` with optimizations enabled.

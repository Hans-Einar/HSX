# Multi-File Project Example

This example demonstrates building a project with multiple source files, showing how `hsx-cc-build.py` handles separate compilation and linking.

## Files

- `main.c` - Main program that calls functions from other modules
- `math.c` - Mathematical operations (add, multiply)
- `utils.c` - Utility functions (print_result)

## Build Command

```bash
python3 ../../../python/hsx-cc-build.py --debug main.c math.c utils.c -o calculator.hxe
```

## What Happens

For each source file:
1. Compile to LLVM IR with debug info
2. Lower to MVASM with line mappings
3. Assemble to HXO object file

Then:
4. Link all HXO files into single HXE executable
5. Merge debug info from all compilation units
6. Generate unified symbol file
7. Create sources.json with all source files

## Output Structure

```
build/debug/
├── calculator.hxe    # Final executable
├── calculator.sym    # Merged symbol table
├── sources.json      # All source file mappings
├── main.ll/.asm/.hxo/.dbg
├── math.ll/.asm/.hxo/.dbg
└── utils.ll/.asm/.hxo/.dbg
```

## Key Features Demonstrated

1. **Separate Compilation**: Each .c file compiled independently
2. **Cross-Module Calls**: Functions from different files call each other
3. **Debug Info Merging**: Symbol table includes all functions from all files
4. **Source Tracking**: sources.json maps all source files for debugger

## Verifying Cross-Module Linking

Check the symbol file to see functions from all modules:
```bash
cat build/debug/calculator.sym
```

You should see symbols for:
- `main` (from main.c)
- `add`, `multiply` (from math.c)
- `print_result`, `get_last_result` (from utils.c)

## Build Variants

**Release build** (optimized, no debug info):
```bash
python3 ../../../python/hsx-cc-build.py main.c math.c utils.c -o calculator.hxe -b build/release
```

**Verbose build** (see each compilation step):
```bash
python3 ../../../python/hsx-cc-build.py --debug -v main.c math.c utils.c -o calculator.hxe
```

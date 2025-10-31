# hsx-cc-build.py Examples

This directory contains example projects demonstrating different ways to use `hsx-cc-build.py`, the unified build orchestrator for the HSX toolchain.

## Examples

### 1. simple-direct-build/
Basic single-file C program built directly without a Makefile.

**Usage:**
```bash
cd simple-direct-build
python3 ../../python/hsx-cc-build.py --debug main.c -o hello.hxe
```

**What it demonstrates:**
- Direct source file compilation
- Debug build with all artifacts (.hxe, .sym, sources.json)
- Single-command workflow

### 2. multi-file-project/
Multi-file C project with separate compilation units.

**Usage:**
```bash
cd multi-file-project
python3 ../../python/hsx-cc-build.py --debug main.c math.c utils.c -o calculator.hxe
```

**What it demonstrates:**
- Multiple source file compilation
- Separate compilation and linking
- Cross-module function calls

### 3. makefile-project/
Project with a Makefile using hsx-cc-build.py for orchestration.

**Usage:**
```bash
cd makefile-project
python3 ../../python/hsx-cc-build.py --debug -C .
```

**What it demonstrates:**
- Makefile integration mode
- Complex build rules
- Incremental builds

### 4. custom-build-dirs/
Example showing custom build directory configuration.

**Usage:**
```bash
cd custom-build-dirs
python3 ../../python/hsx-cc-build.py --debug main.c -b output/debug -o app.hxe
```

**What it demonstrates:**
- Custom build directory placement
- Build artifact organization
- Release vs debug builds

## General Usage Patterns

### Debug Build (Recommended for Development)
```bash
hsx-cc-build.py --debug <sources> -o output.hxe
```

Generates:
- `build/debug/output.hxe` - Executable
- `build/debug/output.sym` - Symbol file for debugger
- `build/debug/sources.json` - Source path mappings
- `build/debug/*.dbg` - Intermediate debug info

### Release Build
```bash
hsx-cc-build.py <sources> -o output.hxe -b build/release
```

### Makefile Integration
```bash
hsx-cc-build.py --debug -C /path/to/project
```

Invokes `make debug` and generates debug metadata automatically.

### Verbose Output (for Debugging Builds)
```bash
hsx-cc-build.py --debug -v <sources>
```

Shows detailed command execution and pipeline stages.

## Requirements

- Python 3.9+
- clang (for C compilation)
- HSX toolchain components (hsx-llc.py, asm.py, hld.py)

## Troubleshooting

**Tool not found errors:**
- Ensure `python/` directory contains toolchain scripts
- Check that clang is installed: `clang --version`

**Build failures:**
- Use `-v` flag for verbose output
- Check that all source files exist
- Verify include paths for headers

**Missing debug symbols:**
- Ensure `--debug` flag is used
- Check that `.sym` file is generated alongside `.hxe`
- Verify `sources.json` exists in build directory

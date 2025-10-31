# hsx-cc-build.py Implementation

## Overview

`hsx-cc-build.py` is the unified build orchestrator for the HSX toolchain. It provides a single entry point for compiling C/C++ source code to HSX executables (`.hxe`), automating the multi-stage pipeline and ensuring proper debug metadata generation.

## DR/DG Alignment

- **DR-2.1a / DG-3.2:** Orchestrates LLVM-based lowering with proper compilation flags
- **DR-3.1 / DG-3.1, DG-3.3:** Ensures complete debug metadata generation (.sym, .dbg, sources.json)
- **DR-2.2 / DR-2.3:** Preserves ABI compliance through consistent flag passing
- **DG-3.5:** Automates debug-friendly artifact generation for tooling consumption

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    hsx-cc-build.py                           │
│                  (Build Orchestrator)                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │ Command Line │────────▶│ Argument     │                 │
│  │ Interface    │         │ Parser       │                 │
│  └──────────────┘         └──────┬───────┘                 │
│                                   │                          │
│                                   ▼                          │
│                          ┌─────────────────┐                │
│                          │  HSXBuilder     │                │
│                          │  - Config Mgmt  │                │
│                          │  - Tool Finding │                │
│                          │  - Pipeline Ctl │                │
│                          └────────┬────────┘                │
│                                   │                          │
│         ┌─────────────────────────┼─────────────────────┐   │
│         ▼                         ▼                     ▼   │
│  ┌─────────────┐          ┌──────────────┐     ┌──────────┐│
│  │ Make Mode   │          │ Direct Mode  │     │ Metadata ││
│  │ - make call │          │ - clang      │     │ Generator││
│  │ - target    │          │ - hsx-llc    │     │ - sources││
│  └─────────────┘          │ - asm.py     │     │   .json  ││
│                            │ - hld.py     │     └──────────┘│
│                            └──────────────┘                  │
└─────────────────────────────────────────────────────────────┘
         │                          │                  │
         ▼                          ▼                  ▼
  ┌────────────┐           ┌──────────────┐    ┌──────────────┐
  │   make     │           │  Toolchain   │    │  Debug Files │
  │   target   │           │  Components  │    │  - .sym      │
  └────────────┘           │  - hsx-llc   │    │  - .dbg      │
                           │  - asm.py    │    │  - sources   │
                           │  - hld.py    │    └──────────────┘
                           └──────────────┘
```

### Class Structure

#### HSXBuilder

The main orchestrator class that manages the build process.

**Attributes:**
- `args`: Parsed command-line arguments
- `verbose`: Boolean flag for detailed logging
- `project_root`: Path to the project root directory
- `build_dir`: Path to the build output directory

**Key Methods:**

##### `__init__(self, args)`
Initializes the builder with command-line arguments, determines working directory, and sets up build paths.

**Responsibilities:**
- Change to specified directory if `-C` flag provided
- Determine build directory based on `--build-dir` or `--debug` flags
- Create build directory structure
- Log configuration in verbose mode

##### `find_tool(self, tool: str) -> Path`
Locates toolchain components in the project or system PATH.

**Search Order:**
1. Project `python/` directory
2. System PATH via `shutil.which()`
3. Raise `HSXBuildError` if not found

**Rationale:** Ensures local development versions take precedence over system-installed tools.

##### `build_with_make(self)`
Executes Makefile-based builds.

**Process:**
1. Determine target (`debug` or `all`) based on `--debug` flag
2. Construct make command with optional `-j` parallelism
3. Verify Makefile exists in project root
4. Execute make and capture output
5. Post-process for debug builds (generate sources.json)

##### `compile_c_to_ll(self, c_file: Path) -> Path`
Compiles C source to LLVM IR.

**Debug Flags (when --debug):**
- `-g`: Generate DWARF debug information
- `-O0`: Disable optimizations for accurate debugging
- `-fdebug-prefix-map=$(PROJECT_ROOT)=.`: Make paths relative for portability

**Output:** `.ll` file in build directory

##### `lower_ll_to_asm(self, ll_file: Path) -> tuple[Path, Optional[Path]]`
Lowers LLVM IR to MVASM using `hsx-llc.py`.

**Process:**
1. Invoke `hsx-llc.py` with LLVM IR input
2. Generate `.asm` output
3. If `--debug`: Generate `.dbg` sidecar with `--emit-debug` flag

**Output:** 
- `.asm` file (MVASM source)
- `.dbg` file (debug metadata, optional)

##### `assemble_to_hxo(self, asm_file: Path) -> Path`
Assembles MVASM to HXO object file using `asm.py`.

**Output:** `.hxo` object file

##### `link_to_hxe(self, hxo_files: List[Path], dbg_files: List[Path]) -> Path`
Links HXO files to HXE executable using `hld.py`.

**Process:**
1. Collect all `.hxo` inputs
2. Determine output name (from `--output` or default `app.hxe`)
3. Construct linker command with `--app-name`
4. If debug: Add `--debug-info` with `.dbg` files and `--emit-sym` for symbol file

**Output:**
- `.hxe` executable
- `.sym` symbol file (debug builds only)

##### `generate_sources_json(self, source_files: List[Path])`
Creates source file mapping for debugger path resolution.

**JSON Structure:**
```json
{
  "version": 1,
  "project_root": "/absolute/path/to/project",
  "build_time": "2025-10-31T09:00:00Z",
  "sources": [
    {
      "file": "main.c",
      "path": "/absolute/path/to/project/main.c",
      "relative": "./main.c"
    }
  ],
  "include_paths": [
    "/absolute/path/to/project/include"
  ]
}
```

**Purpose:** Enables debugger to resolve relative source paths from `.sym` file to actual file locations.

##### `build_direct(self, source_files: List[Path])`
Builds source files directly without make.

**Pipeline for each source:**
1. C → LLVM IR (clang)
2. LLVM IR → MVASM (hsx-llc.py)
3. MVASM → HXO (asm.py)

**Final steps:**
4. Link all HXO → HXE (hld.py)
5. Generate sources.json (debug builds)

##### `build(self) -> int`
Main entry point that dispatches to appropriate build mode.

**Logic:**
```
if args.sources or args.no_make:
    build_direct()
else:
    build_with_make()
    if args.debug:
        generate_sources_json()
```

**Returns:** Exit code (0 for success, non-zero for failure)

## Build Modes

### 1. Makefile Integration Mode

**Command:**
```bash
hsx-cc-build.py --debug -C /path/to/project
```

**Process:**
1. Change directory to project root
2. Invoke `make debug` (or `make all` for release)
3. Post-process: scan for source files and generate `sources.json`
4. All intermediate artifacts are controlled by Makefile rules

**Use Cases:**
- Multi-module projects with complex dependencies
- Projects with custom build rules (code generation, asset processing)
- Integration with existing build systems

**Advantages:**
- Respects existing Makefile incremental build logic
- Supports parallel compilation via make's built-in `-j` flag
- Maintains compatibility with custom build steps

### 2. Direct Source Mode

**Command:**
```bash
hsx-cc-build.py --debug main.c utils.c -o myapp.hxe
```

**Process:**
1. For each source file:
   - Compile C → LLVM IR with debug flags
   - Lower LLVM IR → MVASM with debug info
   - Assemble MVASM → HXO
2. Link all HXO files → HXE with symbol file
3. Generate sources.json

**Use Cases:**
- Quick prototyping and iteration
- Single-file programs
- Build script integration without Makefile
- Continuous integration pipelines

**Advantages:**
- No Makefile required
- Simple command-line interface
- Explicit control over compilation flags
- Direct visibility into pipeline stages

## Debug Metadata Generation

The script ensures complete debug metadata generation through coordinated flag passing:

### Compilation Stage (clang)
```bash
# $(PROJECT_ROOT) represents the project root path, e.g., /home/user/project
clang -g -O0 -fdebug-prefix-map=$(PROJECT_ROOT)=. source.c -S -emit-llvm -o source.ll
```

**Flags:**
- `-g`: Embed DWARF debug info in LLVM IR (DILocation, DISubprogram, DIFile nodes)
- `-O0`: Disable optimizations to preserve source-level structure
- `-fdebug-prefix-map`: Replace absolute paths with relative paths for portability

### Lowering Stage (hsx-llc.py)
```bash
hsx-llc.py source.ll -o source.asm --emit-debug source.dbg
```

**Output:**
- `.asm`: MVASM source with register assignments
- `.dbg`: JSON file with:
  - Function definitions (name, file, start line)
  - LLVM instruction → MVASM line mappings
  - Source file references

### Linking Stage (hld.py)
```bash
hld.py source.hxo -o app.hxe --app-name myapp --debug-info source.dbg --emit-sym app.sym
```

**Output:**
- `.hxe`: Executable with embedded debug section table
- `.sym`: JSON symbol file with:
  - Function addresses and sizes
  - Instruction-level line mappings (PC → source file:line)
  - Symbol table (labels → addresses)
  - Memory region layout

### Metadata File (sources.json)
Generated after successful build:
```bash
# Internal call by HSXBuilder.generate_sources_json()
```

**Output:**
- `sources.json`: Path resolution map for debugger

## Command-Line Interface

### Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `sources` | positional | [] | Source files to build (direct mode) |
| `-C, --directory` | path | cwd | Change to directory before building |
| `-b, --build-dir` | path | `build` or `build/debug` | Build output directory |
| `--debug` | flag | false | Enable debug build with symbols |
| `-o, --output` | string | `app.hxe` | Output executable name |
| `--app-name` | string | derived from output | Application name for HXE header |
| `--no-make` | flag | false | Skip make, build files directly |
| `-j, --jobs` | int | auto | Parallel jobs for make |
| `-v, --verbose` | flag | false | Verbose output |
| `-h, --help` | flag | - | Show help message |

### Examples

**Debug build using Makefile:**
```bash
hsx-cc-build.py --debug -C /path/to/project
```

**Release build with custom output directory:**
```bash
hsx-cc-build.py -C /path/to/project -b build/release
```

**Direct build with multiple sources:**
```bash
hsx-cc-build.py --debug main.c src/utils.c src/math.c -o calculator.hxe
```

**Parallel build with 8 jobs:**
```bash
hsx-cc-build.py --debug -C /path/to/project -j 8
```

**Verbose output for debugging:**
```bash
hsx-cc-build.py --debug -v main.c -o test.hxe
```

## Error Handling

### Exception Hierarchy

```
Exception
└── HSXBuildError
    ├── Tool not found
    ├── Command execution failure
    ├── No Makefile found
    └── No source files discovered
```

### Error Propagation

The script uses a fail-fast approach with detailed error reporting:

```python
def run_command(self, cmd: List[str]) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(cmd)}", file=sys.stderr)
        if e.stdout:
            print("STDOUT:", e.stdout, file=sys.stderr)
        if e.stderr:
            print("STDERR:", e.stderr, file=sys.stderr)
        raise HSXBuildError(f"Command failed: {' '.join(cmd)}")
```

**Error Context Provided:**
- Failed command with full arguments
- Standard output (if any)
- Standard error (if any)
- Stack trace (in verbose mode)

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Build error (compilation, linking, etc.) |
| 130 | User interrupt (Ctrl+C) |

## Integration Points

### Makefile Integration

Projects can invoke `hsx-cc-build.py` from Makefiles for simplified debug builds:

```makefile
# Makefile
PROJECT_ROOT := $(shell pwd)

.PHONY: debug release

debug:
    python3 python/hsx-cc-build.py --debug -C $(PROJECT_ROOT)

release:
    python3 python/hsx-cc-build.py -C $(PROJECT_ROOT) -b build/release
```

### CI/CD Integration

Example GitHub Actions workflow:

```yaml
- name: Build HSX Debug Build
  run: |
    python3 python/hsx-cc-build.py --debug -C . -j 4

- name: Upload Debug Artifacts
  uses: actions/upload-artifact@v3
  with:
    name: debug-build
    path: |
      build/debug/*.hxe
      build/debug/*.sym
      build/debug/sources.json
```

### IDE Integration

VS Code tasks.json example:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "HSX Debug Build",
      "type": "shell",
      "command": "python3",
      "args": [
        "${workspaceFolder}/python/hsx-cc-build.py",
        "--debug",
        "-C",
        "${workspaceFolder}",
        "-v"
      ],
      "group": {
        "kind": "build",
        "isDefault": true
      }
    }
  ]
}
```

## Design Decisions

### 1. Tool Discovery Strategy

**Decision:** Search `python/` directory before system PATH.

**Rationale:**
- Ensures developers use project-local toolchain versions
- Avoids version mismatches between system and project tools
- Simplifies development setup (no system installation required)

### 2. Default Build Directories

**Decision:** Use `build/` for release, `build/debug/` for debug builds.

**Rationale:**
- Clear separation between build types
- Matches common conventions (CMake, Ninja)
- Simplifies `.gitignore` patterns
- Easy to clean specific build types

### 3. Verbose Mode Behavior

**Decision:** Log each pipeline stage and command execution.

**Rationale:**
- Aids debugging of build failures
- Provides transparency into toolchain invocations
- Helps users understand the build process
- Minimal performance overhead

### 4. Debug-by-Default Philosophy

**Decision:** All debug artifacts generated atomically when `--debug` flag is set.

**Rationale:**
- Ensures debugger always has complete information
- Prevents partial debug info due to manual steps
- Simplifies debug workflow (single flag instead of multiple options)
- Matches expectations from other toolchains (gcc -g, clang -g)

### 5. Make Integration vs. Direct Build

**Decision:** Support both modes with automatic detection.

**Rationale:**
- Respects existing project structures (Makefile-based)
- Provides escape hatch for simple use cases (direct build)
- Enables gradual migration from manual scripts
- Reduces friction for new users (no Makefile required for simple programs)

## Future Enhancements

### Planned Features

1. **Incremental Build Support (Direct Mode):**
   - Track source file modification times
   - Skip recompilation of unchanged files
   - Maintain dependency graph

2. **Configuration Files:**
   - Support `.hsx-build.json` for project-level defaults
   - Define include paths, compilation flags, metadata
   - Enable per-project customization without command-line flags

3. **Cross-Compilation:**
   - Support multiple target architectures
   - Platform-specific toolchain selection
   - ABI variant handling

4. **Build Caching:**
   - Cache compiled objects across builds
   - Content-addressable storage (like ccache)
   - Shared cache for CI environments

5. **Dependency Management:**
   - Automatic detection of `#include` dependencies
   - External library linking
   - Package manager integration

## Testing Strategy

### Unit Tests

Test individual HSXBuilder methods in isolation:

```python
def test_compile_c_to_ll_debug_flags():
    """Verify debug flags are passed to clang"""
    args = argparse.Namespace(debug=True, verbose=False, directory=None, build_dir=None)
    builder = HSXBuilder(args)
    # Mock subprocess.run and verify -g, -O0, -fdebug-prefix-map in call
    
def test_find_tool_precedence():
    """Verify local tools are found before system tools"""
    args = argparse.Namespace(debug=False, verbose=False, directory=None, build_dir=None)
    builder = HSXBuilder(args)
    tool_path = builder.find_tool('hsx-llc.py')
    assert 'python/' in str(tool_path)
```

### Integration Tests

Test complete build pipelines:

```python
def test_debug_build_direct_mode(tmp_path):
    """Verify debug build generates all artifacts"""
    source = tmp_path / "main.c"
    source.write_text("int main() { return 0; }")
    
    args = parse_args(['--debug', str(source), '-o', 'test.hxe'])
    builder = HSXBuilder(args)
    exit_code = builder.build()
    
    assert exit_code == 0
    assert (builder.build_dir / 'test.hxe').exists()
    assert (builder.build_dir / 'test.sym').exists()
    assert (builder.build_dir / 'sources.json').exists()
```

### Regression Tests

Ensure behavior consistency across updates:

```bash
# Test suite in tests/toolchain/test_hsx_cc_build.py
pytest tests/toolchain/test_hsx_cc_build.py -v
```

## Troubleshooting

### Common Issues

**"Tool not found: hsx-llc.py"**
- Ensure `python/hsx-llc.py` exists in project
- Check PATH includes toolchain location
- Use `--verbose` to see search locations

**"No Makefile found in project root"**
- Use `--no-make` flag for direct builds
- Verify current directory with `-C`
- Provide source files explicitly

**"Build failed" with no output**
- Use `--verbose` flag for detailed logs
- Check individual tool invocations
- Verify input file existence

**Missing debug symbols**
- Ensure `--debug` flag is set
- Verify clang supports `-g` flag
- Check `.dbg` files are generated
- Inspect linker command for `--emit-sym`

## Implementation Notes

- Script requires Python 3.9+ (compatible with project requirements)
- Depends on `clang` being available in PATH
- All paths use `pathlib.Path` for cross-platform compatibility
- Subprocess invocations use `check=True` for fail-fast behavior
- JSON files use 2-space indentation for readability

## Playbook

- [x] Implement main orchestration logic (HSXBuilder class)
- [x] Add Makefile integration mode
- [x] Add direct source file mode
- [x] Implement debug metadata generation
- [x] Add sources.json generation
- [x] Create comprehensive CLI with argparse
- [x] Add verbose logging
- [x] Implement error handling and propagation
- [ ] Add unit tests for HSXBuilder methods
- [ ] Add integration tests for build modes
- [ ] Create example projects in examples/
- [ ] Add build caching support (future)
- [ ] Add configuration file support (future)

## Commit Log

- 2025-10-31: Initial implementation with Makefile and direct modes
- 2025-10-31: Added debug metadata generation (sources.json, .sym, .dbg)
- 2025-10-31: Documentation created in 04.05--Toolchain.md and this file

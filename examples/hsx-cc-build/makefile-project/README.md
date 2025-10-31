# Makefile Project Example

This example shows how to integrate `hsx-cc-build.py` with a traditional Makefile-based build system.

## Files

- `Makefile` - Build configuration with debug/release targets
- `main.c` - Main program
- `module1.c`, `module2.c` - Separate modules

## Build Commands

### Using Make Targets

```bash
# Debug build
make debug

# Release build
make release

# Custom build with verbose output
make custom-build

# Clean
make clean
```

### Direct hsx-cc-build.py Invocation

```bash
# Let hsx-cc-build.py call make for you
python3 ../../../python/hsx-cc-build.py --debug -C .
```

This will:
1. Change to project directory
2. Invoke `make debug`
3. Post-process to generate `sources.json`

## Makefile Integration Patterns

### Pattern 1: Makefile Calls hsx-cc-build.py

The Makefile invokes `hsx-cc-build.py` as part of build targets:

```makefile
debug:
    $(PYTHON) $(HSX_CC_BUILD) --debug $(SOURCES) -o $(OUTPUT)
```

**Advantages:**
- Fine control over build parameters
- Easy to add custom flags per target
- Integrates with other make rules

### Pattern 2: hsx-cc-build.py Calls Make

Use `hsx-cc-build.py -C .` to invoke the Makefile:

```bash
python3 ../../../python/hsx-cc-build.py --debug -C .
```

**Advantages:**
- Leverages existing Makefile incremental build logic
- Automatic sources.json generation
- Consistent debug artifact handling

## Output Structure

After `make debug`:
```
build/debug/
├── myapp.hxe
├── myapp.sym
├── sources.json
└── (intermediate files)
```

After `make release`:
```
build/release/
├── myapp.hxe
└── (intermediate files, no debug info)
```

## Advanced Usage

### Parallel Builds

Add `-j` flag in Makefile:
```makefile
debug:
    $(PYTHON) $(HSX_CC_BUILD) --debug -j 4 $(SOURCES) -o $(OUTPUT)
```

### Custom Build Directories

```makefile
debug:
    $(PYTHON) $(HSX_CC_BUILD) --debug $(SOURCES) -o $(OUTPUT) -b custom/debug
```

### Application Name

```makefile
release:
    $(PYTHON) $(HSX_CC_BUILD) $(SOURCES) -o $(OUTPUT) --app-name "MyApp"
```

## When to Use Each Pattern

**Use Makefile → hsx-cc-build.py when:**
- You need custom build configurations
- Project has multiple output targets
- You want fine-grained control

**Use hsx-cc-build.py → Make when:**
- You have an existing complex Makefile
- You want automatic debug metadata generation
- You prefer the hsx-cc-build.py interface

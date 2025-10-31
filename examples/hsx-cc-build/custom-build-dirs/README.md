# Custom Build Directories Example

This example demonstrates how to organize build outputs using custom directory structures.

## Files

- `main.c` - Simple C program

## Build Commands

### Debug Build in Custom Directory

```bash
python3 ../../../python/hsx-cc-build.py --debug main.c -b output/debug -o app.hxe
```

Creates:
```
output/debug/
├── app.hxe
├── app.sym
├── sources.json
└── (intermediates)
```

### Release Build in Custom Directory

```bash
python3 ../../../python/hsx-cc-build.py main.c -b output/release -o app.hxe
```

Creates:
```
output/release/
├── app.hxe
└── (intermediates, no debug)
```

### Multiple Build Configurations

Build both debug and release versions:

```bash
# Debug with symbols
python3 ../../../python/hsx-cc-build.py --debug main.c -b builds/debug -o app_debug.hxe

# Release optimized
python3 ../../../python/hsx-cc-build.py main.c -b builds/release -o app_release.hxe

# Profile build (with debug but optimizations)
python3 ../../../python/hsx-cc-build.py --debug main.c -b builds/profile -o app_profile.hxe
```

Result:
```
builds/
├── debug/
│   ├── app_debug.hxe
│   ├── app_debug.sym
│   └── sources.json
├── release/
│   └── app_release.hxe
└── profile/
    ├── app_profile.hxe
    ├── app_profile.sym
    └── sources.json
```

## Use Cases

### 1. Separate Debug and Release Builds

Keep debug and release artifacts separate:
```bash
# Debug for development
hsx-cc-build.py --debug main.c -b dist/debug

# Release for deployment
hsx-cc-build.py main.c -b dist/release
```

### 2. Per-Platform Builds

Organize by target platform:
```bash
# Desktop build
hsx-cc-build.py --debug main.c -b build/desktop -o app.hxe

# Embedded build (future)
hsx-cc-build.py main.c -b build/embedded -o app.hxe
```

### 3. Temporary/Experimental Builds

Use throwaway directories:
```bash
# Experiment with a change
hsx-cc-build.py --debug main.c -b /tmp/test-build -o test.hxe
```

### 4. CI/CD Build Organization

Organize artifacts by build number:
```bash
BUILD_NUM=123
hsx-cc-build.py --debug main.c -b artifacts/build-$BUILD_NUM -o app.hxe
```

## Default Behavior

Without `-b` flag:
- Release builds → `build/`
- Debug builds → `build/debug/`

With `-b` flag:
- Uses specified directory regardless of debug/release

## Best Practices

1. **Use descriptive paths**: `build/debug`, `build/release`, not `build/1`, `build/2`
2. **Keep debug and release separate**: Prevents confusion and accidental deployment of debug builds
3. **Add to .gitignore**: `build/`, `output/`, `dist/`, `artifacts/`
4. **Clean old builds**: Remove old artifacts before release builds

## Cleanup

Remove all custom build directories:
```bash
rm -rf output/ builds/ dist/
```

Or selectively:
```bash
rm -rf output/debug/  # Keep release
rm -rf builds/profile/  # Keep debug and release
```

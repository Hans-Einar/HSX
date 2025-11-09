# Portable Debug Build Workflow

This guide explains how to produce portable debug artefacts with the HSX
toolchain. It consolidates the prefix-map, `.dbg`, `.sym`, and `sources.json`
capabilities so that source paths remain valid when builds are moved between
machines or executed inside CI sandboxes.

## 1. Recommended Workflow

1. **Invoke the unified builder** in debug mode:

   ```bash
   python python/hsx-cc-build.py --debug main.c src/util.c -o demo.hxe
   ```

2. The builder automatically:
   - Applies `-fdebug-prefix-map=<project_root>=.` to every Clang invocation.
   - Emits `.dbg` files during LLVM → MVASM lowering.
   - Produces `.sym` when linking (`hld.py --emit-sym`).
   - Generates `build/debug/sources.json` containing absolute/relative paths plus
     the prefix map used during the build.

3. Copy the entire `build/debug/` directory to the target machine together with
   the `.hxe` artefact.

4. Consumers (executive, debugger, tools) load `sources.json` via
   `python/source_map.py` to resolve original sources, even if the build now
   lives at a different root.

## 2. Makefile Integration

`hsx-cc-build.py --debug` exposes the computed mapping through environment
variables:

```makefile
DEBUG_PREFIX_MAP ?= $(HSX_DEBUG_PREFIX_MAP)

debug: export CFLAGS += -g -O0 -fdebug-prefix-map=$(DEBUG_PREFIX_MAP)
debug:
	python python/hsx-cc-build.py --debug -C $(PWD) --no-make \
	    src/main.c src/driver.c -o firmware.hxe
```

Notes:
- When the builder spawns subcommands it sets both `HSX_DEBUG_PREFIX_MAP` and
  `DEBUG_PREFIX_MAP`. Custom Makefile recipes should reference one of them.
- The debug target above reuses the builder for linking; `--no-make` prevents a
  recursive `make` invocation.

## 3. Custom Build Scripts

For bespoke workflows that orchestrate the toolchain manually:

1. Export a prefix map before invoking Clang:

   ```python
   env = os.environ.copy()
   env.setdefault("HSX_DEBUG_PREFIX_MAP", f"{project_root.resolve()=}.")
   env.setdefault("DEBUG_PREFIX_MAP", env["HSX_DEBUG_PREFIX_MAP"])
   clang_cmd = [
       "clang", "-g", "-O0",
       f"-fdebug-prefix-map={env['HSX_DEBUG_PREFIX_MAP']}",
       "-S", "-emit-llvm", str(source), "-o", str(ir)
   ]
   subprocess.run(clang_cmd, env=env, check=True)
   ```

2. After linking, generate `sources.json` using the builder utility:

   ```python
   from python.hsx_cc_build import HSXBuilder

  _builder = HSXBuilder(argparse.Namespace(
       debug=True, sources=[], directory=None,
       build_dir=str(build_dir), clean=False,
       verbose=False, no_make=True, output=None,
       app_name=None, jobs=None,
   ))
   builder.generate_sources_json(collected_sources)
   ```

## 4. Debug Artefacts

| File | Description |
| --- | --- |
| `*.hxe` | Executable image |
| `*.sym` | Link-time symbol file (addresses, instructions, memory regions) |
| `*.dbg` | Per-unit MVASM debug metadata |
| `sources.json` | Source map with prefix-map information |

## 5. Troubleshooting & Pitfalls

| Issue | Resolution |
| --- | --- |
| Missing `sources.json` | Ensure `--debug` is supplied. The builder only emits `sources.json` for debug builds. |
| Prefix map absent in downstream scripts | Propagate `HSX_DEBUG_PREFIX_MAP` / `DEBUG_PREFIX_MAP` to any custom Clang invocations. |
| Symbols lack file paths | Confirm `--emit-debug` was passed during lowering and `.dbg` files are handed to the linker (`--debug-info`). |
| Relocated build cannot find sources | Use `python/source_map.py.SourceMap` with `search_roots` pointing to the new project location. |
| CI build fails due to missing Clang | Skip make mode or install Clang; the builder checks availability via `shutil.which`. |

## 6. Quick Tutorial

1. **Clone** the repository and enter the project root.
2. **Run** `python python/hsx-cc-build.py --debug examples/tests/hello.c -o hello.hxe`.
3. **Inspect artefacts** under `build/debug/`:
   - `hello.hxe` (executable)
   - `hello.sym` (symbols)
   - `hello.dbg` (debug metadata)
   - `sources.json` (source map)
4. **Simulate relocation** by copying `build/debug/` elsewhere and running:

   ```python
   from python.source_map import SourceMap
   smap = SourceMap.from_file("build/debug/sources.json")
   print(smap.resolve("examples/tests/hello.c", search_roots=["/new/location"]))
   ```

5. The resolved path points to the relocated source tree thanks to the prefix
   map in the JSON file.

Keeping these steps in place ensures debugger sessions always locate the correct
sources, regardless of where the build runs or which machine consumes the
artefacts.

# sources.json Format

Debug builds produced by `hsx-cc-build.py --debug` generate
`build/debug/sources.json`. This file helps the debugger resolve source files
after the build tree moves or when paths were remapped using
`-fdebug-prefix-map`.

```json
{
  "version": 1,
  "project_root": "/absolute/path/to/project",
  "build_time": "1970-01-01T00:00:00Z",
  "prefix_map": "/absolute/path/to/project=.",
  "sources": [
    {
      "file": "src/main.c",
      "path": "/absolute/path/to/project/src/main.c",
      "relative": "./src/main.c"
    }
  ],
  "include_paths": [
    "/absolute/path/to/project/include",
    "/usr/local/include/hsx"
  ]
}
```

## Fields

| Field | Description |
| --- | --- |
| `version` | Schema version (currently `1`). |
| `project_root` | Absolute path to the project root at build time. |
| `build_time` | UTC timestamp in ISO 8601 format derived from `SOURCE_DATE_EPOCH` (defaults to `1970-01-01T00:00:00Z`). |
| `prefix_map` | Optional prefix-map value applied to the build (present for debug builds). |
| `sources` | Array of source descriptors (see below). |
| `include_paths` | Array of include directories that existed during the build. |

### Source Descriptor

Each entry in `sources` contains:

| Field | Description |
| --- | --- |
| `file` | Project-relative path (using `/` separators) when the source lives under `project_root`; otherwise the absolute path. |
| `path` | Absolute path to the source file at build time. |
| `relative` | Debugger-friendly relative path (prefixed with `./`) when the file lives under the project root; otherwise the absolute path. |

### Generation Rules

- All entries are de-duplicated and sorted by relative path.
- Files residing in the build directory (e.g. generated sources) are skipped.
- The builder exports the prefix map in both `HSX_DEBUG_PREFIX_MAP` and `DEBUG_PREFIX_MAP`, allowing custom build steps to consume the same mapping.
- Deterministic builds honour [`SOURCE_DATE_EPOCH`](https://reproducible-builds.org/docs/source-date-epoch/); when unset the timestamp falls back to `1970-01-01T00:00:00Z`.
- Consumers can load and resolve entries using `python/source_map.py`, which
  applies the recorded prefix map and searches alternate project roots when
  necessary.

### Resolution Algorithm

`SourceMap.resolve()` performs the following steps:

1. Normalises the requested path and collects candidate keys (raw, without `./`,
   project-root absolute, and prefix-map rewrites).
2. Looks up matching source entries and, for each, tries the recorded absolute
   path (`path`). If it exists, it is returned immediately.
3. For each entry, combines the relative descriptor (`file` or `relative`) with
   the project root, optional search roots supplied by the caller, and the
   current working directory. The first existing file or symlink is returned.
4. When no candidates exist, a `FileNotFoundError` is raised with the original
   request path for diagnostics.

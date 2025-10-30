# HXE Format (Implementation Notes)

Reference spec: docs/hxe_format.md.

## Summary
- 64-byte header (magic HSXE, version, flags, entry, code_len, ro_len, bss_size, req_caps, CRC32, app_name).
- `app_name` field (32 bytes at offset 0x20): null-terminated ASCII application name (max 31 chars).
- `flags` field bit 1: allow_multiple_instances flag controls instance naming.
- Sections: code, rodata, optional manifest (length-prefixed JSON/TOML) carrying provisioning metadata.
- CRC covers header (0x00-0x1F, excluding app_name), code, rodata.
- Capability flags and manifest content drive provisioning/persistence modules.

## Multiple Instance Handling
- Loader extracts app_name from header at offset 0x20.
- If `allow_multiple_instances` flag (bit 1 in flags) is set and app_name already exists, executive appends `_#0`, `_#1`, etc.
- If flag not set and app_name exists, loader returns `EEXIST`.
- Instance names displayed in ps command output with suffixes.

## Implementation Tasks
- Linker (hld.py) writes header with app_name field + CRC + manifest as per spec.
- Linker accepts `--app-name` and `--allow-multiple-instances` command-line options.
- Loader validates version/CRC, extracts app_name, checks for conflicts, and exposes manifest to provisioning layer.
- Executive maintains app_name and filepath in TaskRecord for ps command.
- Tests (see (6)/toolchain/linker_tests.md) must cover header validation, manifest parsing, CRC failures, app name conflicts, and instance naming.

## Traceability
- **DR:** DR-3.1, DR-5.3.
- **DG:** DG-3.1, DG-3.5, DG-5.3.

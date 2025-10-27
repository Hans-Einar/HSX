# HXE Format (Implementation Notes)

Reference spec: docs/hxe_format.md.

## Summary
- 32-byte header (magic HSXE, version, flags, entry, code_len, ro_len, bss_size, req_caps, CRC32).
- Sections: code, rodata, optional manifest (length-prefixed JSON/TOML) carrying provisioning metadata.
- CRC covers header (0x00–0x17), code, rodata.
- Capability flags and manifest content drive provisioning/persistence modules.

## Implementation Tasks
- Linker (hld.py) writes header + CRC + manifest as per spec.
- Loader validates version/CRC and exposes manifest to provisioning layer.
- Tests (see (6)/toolchain/linker_tests.md) must cover header validation, manifest parsing, CRC failures.

## Traceability
- **DR:** DR-3.1, DR-5.3.
- **DG:** DG-3.1, DG-3.5, DG-5.3.

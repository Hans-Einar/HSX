# HSX Packaging Checklist

> SDP Reference: 2025-10 Main Run (Design Playbook #11)

## Scope
- Capture required artefacts for `make package` / `make release` so SDK drops remain reproducible.
- Define metadata sidecars (JSON listings, manifests) that tooling expects alongside `.hxe` binaries.
- Ensure the documentation bundle includes all SDP-tagged specs touched this run.

## Artefacts
1. **Binaries**
   - Compiled `.hxe` samples from `examples/tests/test_*` (release flavour).
   - Optional `.hxo` intermediates for debugging.
2. **Metadata**
   - `asm.py --dump-json` outputs for each `.hxe` (placed next to binaries).
   - Linker summaries (entry address, sizes) captured from `hld.py -v` and stored as `<name>.linkinfo.json`.
   - Provisioning manifests (embedded or sidecar JSON) per `docs/hxe_format.md` when applicable.
3. **Documentation**
   - SDP-tagged specs (`docs/MVASM_SPEC.md`, `docs/asm.md`, `docs/hsx_llc.md`, `docs/hld.md`, `docs/hxe_format.md`, `docs/security.md`).
   - Release notes (`docs/toolchain.md` version history).
4. **Tooling**
   - `python/`, `platforms/python/`, shell/debugger scripts, and their dependency manifests.

## Process
1. Run `make release` (invokes `tests` + `package`).
2. After packaging, verify contents:
   - No `examples/**/build` directories inside the archive.
   - All `.json` listings present for `.hxe` payloads.
   - `docs/` folder contains the SDP-tagged files listed above.
3. Optional: sign the resulting ZIP (`dist/<PACKAGE>-<timestamp>.zip`) using the team’s signing workflow.
4. Publish artefacts to the internal drop location with checksum metadata.

## Automation Hooks
- Add a future CI step that inspects the ZIP for required files and fails if listings/manifests are missing.
- Consider generating a top-level `MANIFEST.json` summarising included binaries, their entry points, and hash values for downstream tooling.

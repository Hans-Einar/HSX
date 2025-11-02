# Executive Implementation Notes

Use this file to record progress per session.

## Template

```
## YYYY-MM-DD - Name/Initials (Session N)

### Focus
- Task(s) tackled: ...
- Dependencies touched: ...

### Status
- TODO / IN PROGRESS / DONE / BLOCKED

### Details
- Summary of code changes / key decisions.
- Tests run (commands + result).
- Follow-up actions / hand-off notes.
```

Start new sections chronologically. Keep notes concise but actionable so the next agent can resume quickly.

## 2025-11-05 - Codex (Session 1)

### Focus
- Task(s) tackled: Phase 2.4 planning for `.mailbox` metadata emission across the toolchain (llvm→mvasm→hxo/hxe).
- Dependencies touched: Reviewed design doc 04.05--Toolchain.md, current `hsx-llc.py`, `asm.py`, and `hld.py`.

### Status
- DONE

### Details
- Current state: toolchain lacks any metadata handling; neither `hsx-llc`, `asm.py`, nor `hld.py` recognise `.value/.cmd/.mailbox` directives. Phase 2 will therefore introduce the entire metadata path.
- Proposed approach:
  - **MVASM directive syntax:** allow JSON payloads to minimise bespoke parsing. e.g. `.mailbox {"target":"app:telemetry","capacity":128,"mode_mask":"FANOUT|RDWR","owner_pid":2,"bindings":[{"pid":2,"flags":"STDOUT"}]}`.
  - **hsx-llc:** capture `#pragma hsx_mailbox(...)` and emit the directive with a normalised JSON object (mode strings expanded to constants).
  - **asm.py:** detect `.mailbox` lines, parse the trailing JSON via `json.loads`, validate required keys, and append structured entries to the HXO metadata blob (storing verbatim JSON for string tables when we add values/commands).
  - **hld.py:** merge mailbox metadata arrays from all HXO inputs, deduplicate identical targets, and write a consolidated JSON payload into the HXE `.mailbox` section, aligning with the loader’s expectations (version=1 object with `"mailboxes": [...]`).
- Planned tests:
  1. Unit tests around assembler parsing (valid + malformed JSON, option combinations).
  2. Linker integration test: two HXO inputs each contributing mailboxes should merge cleanly and produce a single `.mailbox` section.
  3. End-to-end build sample (C pragma → hsx-cc-build) asserting resulting HXE metadata matches loader schema and that `platforms/python/host_vm.py` pre-creates the mailboxes.
- Follow-up actions / hand-off notes:
  - Track implementation in Session 2 (below); additional work remains for pragma extraction in `hsx-llc` and value/command metadata.

## 2025-11-05 - Codex (Session 2)

### Focus
- Task(s) tackled: Implement Phase 2.4 `.mailbox` metadata pipeline (assembler directives → HXO → linker → HXE) plus documentation/tests.
- Dependencies touched: `python/asm.py`, `python/hld.py`, `python/tests/test_vm_stream_loader.py`, `python/tests/test_linker*.py`, `docs/MVASM_SPEC.md`.

### Status
- DONE

### Details
- Summary of code changes / key decisions:
  - Added JSON-based `.mailbox` directive handling in `asm.py`, captured metadata in `LAST_METADATA`, and emitted it in `.hxo` objects.
  - Reworked the linker to produce HXE v2 images in-place (header v0x0002, metadata table, CRC) and merge mailbox metadata across modules.
  - Updated streaming loader tests to build real HXE images through the toolchain, ensuring `VMController` pre-creates declared mailboxes, and documented the directive in MVASM spec.
- Tests run (commands + result):
  - `C:/appz/miniconda/envs/py312/python.exe -m pytest python/tests/test_vm_stream_loader.py python/tests/test_linker.py python/tests/test_linker_dupdef.py python/tests/test_import_unresolved.py`
  - `C:/appz/miniconda/envs/py312/python.exe -m pytest python/tests/test_asm_sections.py python/tests/test_vm_exit.py`
- Follow-up actions / hand-off notes:
  - Extend `hsx-llc` to emit `.mailbox` directives from pragmas and mirror this work for `.value`/`.cmd` sections in subsequent phases.

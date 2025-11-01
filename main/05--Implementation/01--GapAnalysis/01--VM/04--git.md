# Git Log — VM Shift Opcode Work

> File name: `(4)git.md`. Use this log to capture branch, commits, and PR status for the VM implementation gap analysis.

## Branch
- Name: `implementation/VM`
- Created on: `2025-11-01`
- Owner: VM implementation team (Codex support)
- Based on commit: `9f6422b0d9c489127657b4a32344551ec65efec3`

## Commit Log
| Date | Commit hash | Message | Author | Notes |
| --- | --- | --- | --- | --- |
| 2025-11-01 | 369908abfc54ed0b3a98e361759c242e62c7d6b4 | Shift Support | Hans Einar | Adds LSL/LSR/ASR opcodes, documentation updates, and regression test `python/tests/test_vm_shift_ops.py`. ✔ `python -m pytest python/tests/test_vm_shift_ops.py` |
| 2025-11-01 | e20d92cdae354701ad9e38d4dfea690718567ae1 | MiniVM PSW flags | Hans Einar | Implements full Z/C/N/V handling across ADD/SUB/CMP/MUL/logic/shift ops, documents PSW semantics, and adds `python/tests/test_vm_psw_flags.py`. ✔ `python -m pytest python/tests` |
| 2025-11-01 | 7f7cc5b7696d3c149ffae2b903a119e65ad7110e | Carry-aware arithmetic | Hans Einar | Adds ADC/SBC opcodes (VM + assembler/disassembler), updates docs, and extends PSW tests. ✔ `python -m pytest python/tests` |
| 2025-11-01 | 9e8b9c7054734151461cf7778d5a12f435a14eb5 | Integer DIV support | Hans Einar | Implements signed DIV with zero-trap handling, updates docs, and adds `python/tests/test_vm_div.py`. ✔ `python -m pytest python/tests` |
| 2025-11-01 | 0caa12fc66d4601322a21c20d9215dc40093d575 | Trace API snapshot | Hans Einar | Adds VM trace accessors/events, updates gap notes, and adds `python/tests/test_vm_trace_api.py`. ✔ `python -m pytest python/tests` |
| 2025-11-01 | a1e640be6a26fa97a1bd83ec4f3f61d61dfd81cd | Streaming loader | Hans Einar | Implements VM streaming load APIs and tests (`python/tests/test_vm_stream_loader.py`). ✔ `python -m pytest python/tests` |

## Pull Request
- PR URL / ID: _TBD_
- Status: _TBD_
- Reviewers: _TBD_
- Merge date: _TBD_
- Notes: _Add review outcomes or follow-up items once a PR exists._

## Additional Notes
- Update this file whenever new commits land or PR state changes.
- Link CI runs, code reviews, or related issues as the implementation progresses.

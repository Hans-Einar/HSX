# `dbg.resolver-inspection/1.9` — exact CALL semantic proof conformance

Status: **STEERING REFROZEN / CANDIDATE ONLY / INDEPENDENT REVIEW PENDING**

Steering authority: issue #38 comment `5380763854`.
Clarification authority: issue #38 comment `5380862432`.
Parent candidate interface: `dbg.resolver-inspection/1.8`.
Portable authority: accepted `HSX-D-002` / `HSX-ST-007` resume-vs-call-site semantics.
Toolchain evidence: `docs/MVASM_SPEC.md`, `python/opcodes.py`, `python/disassemble.py`, `python/tests/test_opcode_table.py`.

## Problem

The pre-1.9 candidate correctly refused to publish `call_site_pc` without portable CALL evidence,
but then used `resume_pc` as the next caller `UnwindFrame.pc`. Accepted HSX evidence explicitly
identifies direct return/resume-PC caller lookup as legacy/degraded behavior. A caller frame may
therefore be assigned source/location/unwind rows for the instruction after CALL rather than the
suspended CALL instruction.

The debugger must either prove the checked candidate is CALL or stop continuation. It may not
silently substitute `resume_pc` as equivalent caller-frame PC.

## Existing exact evidence

No artifact wire/schema change is needed:

- `ArchitectureDescriptor.instruction_encoding` selects a versioned instruction encoding;
- `InstructionRecord` carries exact `address`, `byte_size` and optional exact `encoded_word`;
- MVASM defines opcode values as the stable public mapping in canonical `python/opcodes.py`;
- assembler/disassembler/VM opcode coverage is already checked against that one table;
- fixed32 decoder extracts the primary opcode as `(encoded_word >> 24) & 0xff`;
- canonical fixed32 CALL opcode is `0x24`;
- canonical fixed32 primary opcode values form a closed set defined by `opcodes.OPCODE_LIST`.

## Minimal semantic-proof boundary

RF-004 adds one small debugger-core module whose sole responsibility is classification required
for call-site proof. It is not a general disassembler and owns no artifact parsing, stack walk,
frontend formatting, runtime I/O or run-control policy.

For exact `instruction_encoding == "hsx.fixed32/1"`:

1. input is one exact `InstructionRecord` already resolved at the checked candidate address;
2. the candidate CALL-site record must have `byte_size == 4`; otherwise
   `CORRUPT / instruction_encoding_contract`;
3. `encoded_word is None` yields `UNAVAILABLE / instruction_semantics_unavailable`;
4. primary opcode is `(encoded_word >> 24) & 0xff`;
5. opcode `0x24` is proven CALL;
6. another opcode in the canonical closed fixed32 opcode set is proven non-CALL;
7. a primary opcode byte outside the canonical set is
   `CORRUPT / instruction_encoding_contract` and is not normalized to non-CALL;
8. any other instruction encoding yields `UNSUPPORTED / instruction_encoding_unsupported`.

The pure debugger package may carry a frozen self-contained set of canonical fixed32 primary
opcode byte values plus the CALL constant. This is a versioned semantic projection, not a
runtime dependency on the build toolchain. Conformance tests must assert:

- exact set equality with `{opcode for _, opcode in opcodes.OPCODE_LIST}`;
- exact CALL equality with `opcodes.OPCODES["CALL"] == 0x24`;
- primary-opcode extraction matches the existing disassembler's top-byte decode.

## StackService rule

`call_site_adjustment` remains a row-owned checked address operation.

After caller resume PC is recovered:

- perform the checked adjustment without wrap;
- require one exact `InstructionRecord` at the candidate;
- proven CALL -> publish `call_site_pc=candidate` and use that candidate as the next caller
  `UnwindFrame.pc`;
- proven canonical non-CALL -> terminate `CORRUPT / call_site_not_call` with the existing
  trustworthy prefix preserved under 1.6;
- unknown fixed32 primary opcode -> terminate `CORRUPT / instruction_encoding_contract`;
- missing encoded semantic evidence -> terminate `UNAVAILABLE / instruction_semantics_unavailable`;
  with an existing prefix this is represented as `PARTIAL`, never as fabricated continuation;
- unsupported encoding -> terminate `UNSUPPORTED / instruction_encoding_unsupported` while
  preserving the prefix;
- metadata/index contract failures remain `CORRUPT`;
- call-site semantic failure terminates before caller-SP/frame-base/GPR recovery is attempted;
- `resume_pc` remains retained separately and is never replaced by the call-site address.

No caller frame is created from resume PC when call-site proof did not succeed.

## Non-changes

This refreeze does not:

- add or alter `InstructionRecord` fields;
- change canonical artifact component bytes/digests;
- add a general ISA/disassembly API;
- change HSX-D-002 or the VM/toolchain opcode contract;
- import Executive, VM, DAP/CLI, VS Code or frontend policy into debugger-core;
- authorize RF-005..009.

## Candidate/review gate

Implementation and tests stay on `master/rf004-v13-candidate`. Promotion requires fresh
independent exact-head review of the complete 1.3..1.9 interface chain, followed by the normal
Slice005 and Slice006 product review/verification/sign-off sequence.
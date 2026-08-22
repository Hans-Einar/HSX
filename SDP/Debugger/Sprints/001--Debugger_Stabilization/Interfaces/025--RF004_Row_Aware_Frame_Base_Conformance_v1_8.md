# `dbg.resolver-inspection/1.8` — row-aware current-frame frame-base conformance

Status: **STEERING REFROZEN / CANDIDATE ONLY / INDEPENDENT REVIEW PENDING**

Steering authority: issue #38 comment `5380568339`.
Parent candidate interface: `dbg.resolver-inspection/1.7`.
Portable authority: accepted `HSX-D-002` / `HSX-ST-007` current-profile PC-row semantics.

## Problem

The pre-1.8 candidate derived the top-frame `frame_base` from snapshot R7 whenever the selected ABI was `hsx.abi.llc-r7-word32/1`. That is too broad. In the frozen current profile, R7 is the established current frame pointer only after `MOV R7,R15` has executed and before `POP R7` executes. At function entry before `PUSH R7`, at `MOV R7,R15` before execution, and at `RET` after `POP R7`, current R7 is caller-state evidence rather than the current frame base.

`frame_base` is authoritative recovered-frame evidence used by location recipes. It must therefore be tied to the exact selected PC row rather than inferred from the ABI name alone.

## Normative delta

No public DTO field, opcode, recipe schema, portable HSX contract, runtime API or frontend API is added.

For `hsx.abi.llc-r7-word32/1`:

1. StackService still seeds top-frame PC, SP, architecture-order GPRs and PSW from exactly one read of the exact `InspectionContext` snapshot.
2. StackService must select and validate the exact applicable `UnwindRow` before it may derive the current top-frame `frame_base`.
3. Only an exact `boundary=ORDINARY` row admits snapshot R7 as current frame-base evidence. R7 must be available, exact-width and validate as a typed address in the descriptor's SP/data space. Then and only then `UnwindFrame.frame_base` may equal that address.
4. `ENTRY`, `EPILOGUE`, `TERMINAL` and `UNSUPPORTED` rows do not infer current frame base from R7. `frame_base=None` is the conservative result absent a later explicitly frozen current-frame-base seam.
5. An unavailable or invalid R7 on an `ORDINARY` top frame leaves `frame_base=None` and records a typed diagnostic. There is no wrap, mask, SP substitution, live re-read or fallback.
6. This top-frame rule is independent of caller-frame recovery. A caller frame receives `frame_base` only from the exact applicable `caller_frame_base_rule` or admitted SAME semantics. A recovered caller R7 value is not automatically reinterpreted as caller frame base.
7. `LocationEvaluator` and the `frame_base` recipe opcode consume only the selected `UnwindFrame.frame_base`; `None` remains explicit unavailable evidence.
8. Row selection remains artifact-driven over exact image/ABI/function/PC ranges. Debug time opcode-pattern inference is forbidden.

## Current-profile phase matrix

The accepted portable profile must be demonstrated with explicit rows:

| Phase | Boundary | CFA | caller PC | caller SP | caller R7 | top `frame_base` |
|---|---|---|---|---|---|---|
| function entry, before `PUSH R7` | `ENTRY` | `SP+4` | `[CFA-4]` | `CFA` | `SAME` | unavailable |
| after push, at `MOV R7,R15` before execution | `ENTRY` | `SP+8` | `[CFA-4]` | `CFA` | `[CFA-8]` | unavailable |
| stable body/local release before `POP R7` | `ORDINARY` | `R7+8` | `[CFA-4]` | `CFA` | `[CFA-8]` | exact snapshot R7 if valid |
| at `RET`, after `POP R7` | `EPILOGUE` | `SP+4` | `[CFA-4]` | `CFA` | `SAME` | unavailable |
| top-level entry/return | `TERMINAL` | exact row CFA | no fabricated caller | no fabricated caller | no fabricated caller | unavailable |

The matrix also requires an `ORDINARY` negative case with R7 unavailable or invalid: no current frame base is published.

## Candidate/review gate

This delta may be implemented and tested only on `master/rf004-v13-candidate` during the temporary no-5.6-review window. It is not signed and must not be promoted to `codex/dbg-rf-004` until a fresh independent exact-head interface review plus normal Slice005/006 review, verification and Master sign-off are restored.

# DBG-RF-010 — RF-004 Exact CALL-Site Evidence Fence

- Status: **ACTIVE CORRECTIVE CHILD / IMPLEMENTATION CANDIDATE**
- `corrective_child_of: DBG-RF-004`
- Origin: `DBG-CR-002` -> `DBG-GAP-002`
- Finding: `DBG-F-027` (Medium)
- Issue: #55
- Frozen review baseline: `514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`

## Objective

Close one exact-evidence conformance defect in Slice005 without changing the frozen public interface.

`StackService._checked_call_site()` must prove that the resolved `InstructionRecord` returned for the checked candidate actually names that exact candidate before `prove_call()` may authorize continuation.

## Owned scope

- `python/hsx_debugger/stack.py` exact call-site record fence;
- dedicated RF-010 adversarial test(s);
- SDP evidence for this corrective child.

## Required behavior

For a checked call-site candidate `C`:

1. `index.instruction_at(C)` must resolve exactly one `InstructionRecord`;
2. that record must satisfy `record.address == C` exactly, including address space and unsigned value;
3. mismatch terminates `CORRUPT` with diagnostic code `call_site_index_contract`;
4. any already-proven frame prefix is preserved under `dbg.resolver-inspection/1.6`;
5. no caller SP, caller frame-base or caller GPR recovery occurs after the mismatch;
6. exact-address CALL, non-CALL, missing evidence, unknown opcode and unsupported encoding retain their frozen 1.9 semantics.

## Non-responsibilities

- no new CALL decoder or opcode contract;
- no artifact-index redesign;
- no Slice006 or InspectionService change;
- no Executive/VM/AVR/frontend change;
- no interface refreeze;
- no RF-005..009 work.

## Verification

Focused tests must prove:

- wrong-address valid CALL record -> `CORRUPT / call_site_index_contract`;
- trustworthy prefix length remains one in the current fixture;
- only the caller-PC recovery read occurs before rejection; no later caller-state reads;
- existing exact CALL/non-CALL/missing/unknown/unsupported cases remain unchanged.

## Review/sign-off

This corrective child is not complete merely because tests pass. It requires a fresh independent exact-head review, formal verification evidence, and Master sign-off before the RF-004 promotion/reconstruction sequence may consume it.

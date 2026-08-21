# DBG-CF-001-005-002 — `dbg.resolver-inspection/1.2` Recovered-Frame Conformance

- Status: **CONTRACT PASS / TRACE-CORRECTED CANDIDATE / REVIEW 032 PENDING**
- Authority: issue #38 comment `5370574104`
- Interface: `dbg.resolver-inspection/1.2`
- Scope: UnwindFrame recovered GPR/PSW evidence and explicit LocationEvaluator consumption
- HSX portable contract delta: none
- SnapshotReadPort delta: none

## Exact public delta

Only UnwindFrame adds:

- `recovered_registers: RegisterSet`
- `recovered_psw: RegisterValue`

All version-1.1 fields, methods, Enum members and ownership boundaries remain unchanged.

## Required positive fixtures

| ID | Construction | Required observation |
|---|---|---|
| `RF-EV-001` | Top frame from exact all-declared InspectionContext snapshot | GPR RegisterSet is exactly architecture.register_order; pc/sp and PSW come from that same snapshot. |
| `RF-EV-002` | Snapshot omits/cannot prove one GPR or PSW | Exact entry is retained with available=false/value=None; no guess or omission. |
| `RF-EV-003` | Caller row has exact GPR SAME | Corresponding younger evidence is copied exactly, including unavailable state. |
| `RF-EV-004` | Caller row has validated GPR EXPRESSION | Exact-width evaluated result becomes that caller GPR evidence. |
| `RF-EV-005` | Accepted HSX schema/profile explicitly admits PSW caller-state rule and row has PSW SAME or valid unsigned PSW EXPRESSION | recovered_psw is available with exact width/value. |
| `RF-EV-006` | LocationEvaluator receives a selected top/non-top UnwindFrame | RecipeEvaluationContext is constructed only from explicit frame plus existing binding/index/architecture/ABI arguments. |
| `RF-EV-007` | Non-top `reg_value` / `special_value PSW` | Evaluator uses frame.recovered_registers/recovered_psw and performs no current-register read. |
| `RF-EV-008` | Repeating one exact unwind | Every frame's recovered evidence/order/availability is deterministic and equal. |

## Required negative/unavailable fixtures

| ID | Construction | Required outcome |
|---|---|---|
| `RF-EV-101` | Architecture GPR missing, duplicated, reordered, wrong-width or extra PC/SP/PSW in recovered_registers | CORRUPT; no frame publication. |
| `RF-EV-102` | recovered_psw wrong ID/width or inconsistent available/value | CORRUPT. |
| `RF-EV-103` | Caller GPR has no rule, UNDEFINED/UNAVAILABLE/OPTIMIZED_OUT, or failed rule | Explicit unavailable entry. |
| `RF-EV-104` | Younger caller-clobbered GPR is available but caller row has no exact SAME/expression evidence | Caller entry is unavailable; never copied. |
| `RF-EV-105` | Non-top PSW has no exact accepted rule/evidence | recovered_psw unavailable and `special_value PSW` returns UNAVAILABLE. |
| `RF-EV-106` | register_rules names PC/SP, an unknown register, duplicate register, or invalid PSW expression result | CORRUPT. |
| `RF-EV-107` | frame.context differs from LocationEvaluator context/binding evidence | Reject before opcode/read. |
| `RF-EV-108` | Implementation tries hidden cache, global side channel, fixed-R7/ABI default, current-register fallback or frame-aware SnapshotReadPort extension | Non-conformant. |

## Recovery authority

This fixture does not invent saved/clobbered semantics. Available caller evidence arises only
from the applicable accepted unwind row's explicit EXPRESSION/SAME rule. Missing rules are
unavailable. If an accepted HSX recipe cannot express whether a required GPR/PSW is recoverable,
implementation stops for Steering/HSX rather than adding a Debugger default.

## Gates

Review `DBG-RVW-001-005-031` passed contract content but returned REWORK trace-only. Fresh
`DBG-RVW-001-005-032` reviews the unchanged `1.2` semantics plus corrected current trace. Product review
identity `DBG-RVW-001-005-011` remains reserved for a later post-refreeze Slice-007 product
head. No Slice-007 worker restarts before interface-review PASS.

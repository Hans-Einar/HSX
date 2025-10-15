# HSX Mailbox Mid‑Implementation Review (October 2024)

## 1. Purpose & Inputs
This report consolidates:
- The current blocker notes in `mailbox_difficulties.md`.
- GPT Pro’s structured review across the mailbox spec, runtime, shell tooling, and tests (prompt dated Oct 2024).
- Progress captured in `mailbox_update_implementation.md` to highlight what is complete, incomplete, or off-track.

It is meant to checkpoint the engineering effort before resuming runtime work or updating the implementation plan.

---

## 2. Progress Snapshot vs Original Plan
| Area (from `mailbox_update_implementation.md`) | Status Update | Notes |
| --- | --- | --- |
| Shell visibility / filters | ✅ Completed | `python/shell_client.py`, `help/mbox.txt`, and tests updated; filters surface `app:`/`shared:` descriptors as intended. |
| Documentation (spec, help) | ⚠️ Partially done | `docs/hsx_spec-v2.md` mentions namespaces and filters, but needs authoritative ABI + timeout tables and scheduling terminology refresh. |
| Regression coverage | ⚠️ Partial | Manager + shell client unit tests exist; **no SVC-level integration tests yet**. Demo still fails end-to-end. |
| Runtime fixes (SVC bind/open/recv) | ❌ Blocked | Namespace lookup works manager-side, but SVC RECV path corrupts context; producer/consumer demo stalls. |
| Demo README / evidence | ⚠️ Not updated | Baseline captured; no post-fix transcript due to runtime instability. |

---

## 3. Key Findings (Severity Ordered)
### Blockers
1. **SVC MAILBOX_RECV ABI mismatch**  
   - Shim vs spec disagreement on where the optional info pointer lives (register vs stack).  
   - VM never writes back metadata; demo interprets garbage.
2. **Context restore after mailbox wait corrupts PC**  
   - After `_complete_mailbox_wait`, tasks resume at `pc_out_of_range`, implying PC/SP/flags are restored incorrectly.  
   - Demo crashes after a few receives; instrumentation missing.
3. **Scheduler “step vs cycle” ambiguity**  
   - Current “step” executes multiple guest instructions before rotating.  
   - Needs redesign to enforce “one step = one instruction” for determinism and debugging.

### High
4. **Timeout semantics undocumented / inconsistently handled**  
   - Shim uses sentinel `-1`; VM expects 16-bit values.  
   - No single place defines POLL/FINITE/INFINITE behaviour.
5. **No SVC integration tests**  
   - Existing tests exercise the manager only; trapping from guest code is unverified.

### Medium
6. **Documentation drift**  
   - Spec still talks about “cycles” and lacks concrete ABI tables.  
   - Namespace rules scattered across several files.
7. **Demo evidence missing**  
   - README / runbook not reflecting current CLI steps or limitations.

### Low
8. **`app:` namespace parity tests** absent at SVC level.  
9. **Help docs lack upcoming clock/step semantics** once scheduler changes land.

---

## 4. Namespace Audit (Doc Intent vs Implementation)
| Namespace | Documented Intent | Observed Behaviour | Gaps |
| --- | --- | --- | --- |
| `pid:` | Private per PID channels; created at spawn. | Manager creates `pid:<pid>` + stdio; handles stay per PID. | Need SVC testcase to prove blocking semantics. |
| `svc:` | Executive services with optional `@pid`. | Works within manager; shell filters show remote stdio. | SVC path still unstable (same RECV issues). |
| `app:` | Global by default; `@pid` scopes. | Manager reuses descriptors across PIDs (verified manually). | Missing automated SVC tests + doc clarity. |
| `shared:` | Global fanout-capable namespace. | Manager tests cover fanout/policies. | No SVC tests; doc should note policy expectation. |

---

## 5. Runtime & VM Pain Points
1. **MAILBOX_RECV argument marshalling:** optional pointer must be read from `[SP + 12]` (6th argument). Shim currently loads from registers.  
2. **SVC completion instrumentation lacking:** need before/after dumps in `_svc_mailbox_controller` and `_complete_mailbox_wait`.  
3. **Scheduler rotation:** must run exactly one instruction per task; current code uses “cycles” field causing multi-instruction bursts.  
4. **Timeout handling:** unify constants (`HSX_MBX_TIMEOUT_POLL`, finite ticks, `HSX_MBX_TIMEOUT_INFINITE`) across header/spec/shim.  
5. **Demo harness:** absence of deterministic stepping makes diagnosing mailbox waits painful.

---

## 6. Documentation & Terminology Gaps
- **Spec v2:** needs step-based scheduler definition, mailbox ABI tables, timeout semantics, and consolidated namespace section.  
- **Header (`hsx_mailbox.h`):** add per-call comment table for register/stack usage.  
- **Help docs:** once scheduling changes land, update CLI help (`clock step`, `mbox` examples referencing `@pid` and `shared:`).  
- **Plan docs (`mailbox_update_implementation.md`):** should note runtime blockers and deferred tasks explicitly.

---

## 7. Recommended Actions (Dependency Ordered)
### Phase 0 – Unblock SVC path
1. Document MAILBOX_* ABI in spec + header; lock argument order.  
2. Patch `hsx_mailbox.mvasm` to push overflow args correctly; remove sentinel hacks; ensure `hsx_mailbox_recv_basic` honours new ABI.  
3. Instrument VM SVC entry/exit; fix PC/SP restore until stable.  
4. Create minimal SVC integration test (producer sends, consumer recv with info struct, verify resume state).

### Phase 1 – Scheduler Simplification
5. Redefine VM “step” as one instruction; rotate one step per runnable PID.  
6. Expose `clock step N` and `clock step N -p PID` in RPC + shell for deterministic debugging.  
7. Update docs/spec/help to drop “cycles” and explain stepping model.

### Phase 2 – Validation & Docs
8. Add SVC regression tests for `app:`/`shared:` (bind/open/fanout, timeout variants).  
9. Refresh documentation (spec, README, help) with consolidated namespace guidance and new CLI usage.

### Phase 3 – Demo & Evidence
10. Update demo README with run instructions using new scheduler.  
11. Capture post-fix transcripts (`mbox`, `mailbox_snapshot`, producer/consumer output).

---

## 8. Suggested Updates to `mailbox_update_implementation.md`
- Mark Main Task 6/7 (runtime fixes) as blocked with the diagnosed ABI/scheduler issues.  
- Add explicit todo items for VM instrumentation, scheduler rewrite, and integration tests.  
- Insert doc action items (ABI tables, timeout semantics, step terminology).  
- Note that README/test artefacts remain pending due to runtime instability.

---

## 9. Forward Plan
Before resuming code changes:
1. Align team on the ABI & scheduler redesign (shared understanding across spec/header/runtime).  
2. Implement Phase 0 tasks (shim fixes + instrumentation) and prove stability with a small SVC test.  
3. Only then update `mailbox_update_implementation.md` to reflect the new sequencing and responsible owners.

This report, alongside GPT Pro’s recommendations, should guide the next revision of the implementation plan.

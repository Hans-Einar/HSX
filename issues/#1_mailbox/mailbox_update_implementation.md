# HSX Mailbox Shared Namespace Implementation Plan

Updated with findings from `mailbox_update (1).md`: runtime support for `app:`/`shared:` descriptors already exists in `python/mailbox.py`; the critical gaps are shell visibility, documentation, regression coverage **and the still-missing runtime plumbing that lets the demo share a mailbox in practice**. Tasks below now reflect both the work already finished and the outstanding pieces needed to make `examples/demos/mailbox` actually run end-to-end.

## Main Task 1 — Confirm Runtime Behaviour & Demo Baseline
- [x] Drive the `examples/demos/mailbox` producer/consumer through the Python executive while tracing `mailbox_bind/open/send/recv` to capture the descriptor IDs and demonstrate that both PIDs share the same `app:procon` descriptor (`mailbox_baseline.md`).
- [x] Record current `mailbox_snapshot` output (JSON) to use as “before” evidence that `app:` descriptors are missing from the shell view despite existing in the manager.
- [x] Save a short transcript showing producer stdin → consumer stdout to anchor expected behaviour after tooling fixes.

## Main Task 2 — Fix Shell `mbox` Visibility & Filters
- [x] Update `python/shell_client.py` `mbox` handler to consume the full `descriptor_snapshot()` output (no namespace filtering) and present namespace/owner/queue metrics for `pid`, `svc`, `app`, and `shared`.
- [x] Expose optional filters: `mbox all`, `mbox pid <n>`, `mbox app`, `mbox shared` to make large outputs manageable.
- [x] Ensure RPC payloads (`mailbox_snapshot`) pass through namespace data unchanged; adjust any server-side filtering in `platforms/python/host_vm.py` if needed.
- [x] Refresh `help/mbox.txt` (or equivalent) with examples showing `app:` and `shared:` usage plus filter syntax.

## Main Task 3 — Documentation Alignment
- [x] Update `docs/hsx_spec-v2.md` (and related design notes) to clarify that `app:<name>` without `@pid` is global in the current Python executive, while `app:<name>@<pid>` scopes to a specific owner.
- [x] Document `shared:<name>` semantics as always-global, and call out that the host executive is authoritative for namespace handling today.
- [ ] Add a README snippet under `examples/demos/mailbox/` describing how to drive the demo via shell commands (`send`, `listen`, `mbox`, filters).

## Main Task 4 — Regression Coverage
- [x] Add/extend unit tests in `python/tests/test_mailbox_manager.py` to cover two-PID interaction on `app:` and `shared:` targets, asserting descriptor reuse and message delivery.
- [x] Introduce shell-client level tests (or golden JSON fixtures) ensuring `mbox` renders all namespaces and respects filters.
- [ ] Optionally add an integration smoke test that runs the producer/consumer demo via the VM and asserts stdout contains the relayed message.

## Main Task 5 — Verification & Sign-off
- [ ] Re-run the demo end-to-end; capture `mbox` output showing `Namespace=app` (or `shared`) with non-zero depth/bytes once traffic flows.
- [ ] Verify filters (`mbox shared`, `mbox pid <n>`, etc.) return expected subsets.
- [ ] Summarize changes (tooling, docs, tests) and attach evidence/logs for review.

---

---

## Main Task 6 — Stabilize MAILBOX SVC Path (Phase 0 blockers) [done]
- [x] **Document ABI**: Update `include/hsx_mailbox.h` and `docs/hsx_spec-v2.md` with definitive register/stack tables for every `MAILBOX_*` call (especially `MAILBOX_RECV` optional info-out pointer and timeout semantics).
- [x] **Patch assembly shim** `examples/lib/hsx_mailbox.mvasm` to push overflow arguments per the documented ABI; remove sentinel timeout hacks; ensure both `hsx_mailbox_recv` and `hsx_mailbox_recv_basic` follow the same contract.
- [x] **Instrument VM SVC handler**: Add temporary tracing in `platforms/python/host_vm.py` (`_svc_mailbox_controller`, `_complete_mailbox_wait`) to capture register frames before trap, after trap, and after wake so corrupted PC/SP can be diagnosed.
- [x] **Fix context restore**: Ensure the resume path wakes blocked tasks with valid `pc`, `sp`, `flags`, and status registers (validated via the new SVC runtime test).
- [x] **Add minimal SVC integration test** (Python): boot two tasks via the VM, perform `MAILBOX_RECV(INFINITE)`/`MAILBOX_SEND`, and assert the consumer resumes with correct status/length + descriptor reuse.

## Main Task 7 — VM Scheduler & Stepping Simplification (Phase 1) [active]
- [x] Redefine a VM “step” as exactly one guest instruction; update the executive loop to run one step per runnable PID in strict round-robin order.
- [x] Expose new shell/RPC controls: `clock step <N>` (global round-trips) and `clock step <N> -p <pid>` (single task stepping).
- [x] Update accounting fields (`accounted_cycles` → `accounted_steps`, etc.) and refresh documentation/help text to drop “cycles”.
- [x] Extend automated tests to cover deterministic stepping (e.g., load three tasks, run `clock step 6`, assert each advanced two instructions).

## Main Task 8 — Regression Coverage & Namespace Parity (Phase 2)
- [x] Add SVC-level tests for `app:` and `shared:` namespaces covering bind/open across multiple PIDs, fanout policies, and timeout behaviours.
- [x] Ensure `MAILBOX_BIND/OPEN/SEND/RECV` via traps reuse descriptors and return meaningful status codes (no silent `INTERNAL_ERROR`).
- [x] Capture fixtures verifying that the optional info pointer receives `{length, flags, channel, src_pid, status}` as documented.

## Main Task 9 — Documentation & Help Refresh
- [x] Consolidate namespace guidance, timeout semantics, and new stepping model in `docs/hsx_spec-v2.md`; include an explicit ABI appendix for the mailbox module.
- [x] Update shell help (`help/mbox.txt`, new `help/clock.txt`) to cover filters, `@pid` stdio access, `shared:` examples, and the new stepping CLI.
- [x] Add or refresh `examples/demos/mailbox/README.md` with accurate run/step instructions once the runtime is stable.

## Main Task 10 — Demo Sign-off & Artefacts (Phase 3)
- [x] Re-run the producer/consumer demo end-to-end under the new scheduler; record `mbox` snapshots showing `app:procon` activity and consumer output (`mailbox_baseline.md`, section D).
- [x] Update `mailbox_baseline.md` (or add a “post-fix” section) with successful transcripts, traces, and any diagnostic notes gathered while fixing the runtime.
- [x] Compile a final verification bundle summarising tooling, runtime, and documentation changes for review/merge (`mailbox_verification_report.md`).

# RF-004 Routing-C Aggregate Execution Result

Status: **PASS WITH KNOWN BASELINES**

Role: read-only TESTER execution evidence. This record does not sign or complete `DBG-RF-010`, `DBG-RF-011`, or parent `DBG-RF-004`.

## Authority

- Parent: `DBG-RF-004`
- Origin review: `DBG-RVW-001-005-037`
- Review remediation: `DBG-CR-002` -> `DBG-GAP-002`
- Corrective children: `DBG-RF-010`, `DBG-RF-011`
- Bounded Low rework: `DBG-F-029`
- Coordination: issue #54
- Tester report: issue #54 comment `5381602329`
- Exact product/test head executed: `045f1cf58beaf393680e1f4118cfa76de65220b2`
- Branch tested: `master/rf004-routing-c-remediation`
- Frozen reviewed candidate remained: `master/rf004-v13-candidate@514f7f1cdf8420ccaf6ae84d14b20e4d13931cdc`
- Draft PR #50 remained: `codex/dbg-rf-004@46169516058aadf0e691a5981e29da4954b7444f`

## Environment

- Python: `C:\Users\hanse\miniconda3\python.exe`
- Python 3.11.5
- pytest 8.4.2
- win32
- `PYTHONPATH=python`
- `PYTHONDONTWRITEBYTECODE=1`

## Results

### Focused Routing-C remediation

All focused commands passed with no failure, error, skip, or xfail:

- `DBG-F-027` / RF-010 exact call-site fence: **2 passed**
- `DBG-F-028` / RF-011 explicit factory dependencies: **5 passed**
- candidate guards including closed `DBG-F-029`: **5 passed, zero XFAIL**
- CALL/instruction semantic matrix: **12 passed**
- Stack/dependency contracts: **19 passed**
- Inspection/service precedence: **19 passed**
- Recipe/metadata: **32 passed**

The focused evidence confirms:

1. wrong-address resolved CALL metadata is `CORRUPT / call_site_index_contract`, preserves only the trustworthy top-frame prefix, and performs no saved-R7/post-proof caller-state read;
2. exact-address CALL evidence still succeeds;
3. omission of either composition dependency independently, or both, fails at the ordinary Python call boundary;
4. explicit dependency injection is retained unchanged;
5. the LocationRow diagnostic test is an ordinary PASS and no P002 xfail remains.

### Stress / concurrency

- 20/20 iterations PASS
- 22 tests per iteration
- aggregate: **440 passed**
- no failure/error/skip/xfail

### Signed regression signals

- RF-004 signed oracle: **159 passed, 3 skipped**, no failure/error
- RF-002/RF-003 first-wave signal: **81 passed**, no failure/error
- complete debugger-core aggregate: **403 passed, 3 skipped, zero XFAIL**, no failure/error

### Broad Python baseline

Full `python/tests` result:

- **937 passed**
- **5 skipped**
- **0 xfailed**
- **2 failed**

The only failures are the accepted historical baselines:

1. `python/tests/test_hsx_dbg_commands.py::test_break_add_symbol_line` — ignored/generated demo `main.sym` absent;
2. `python/tests/test_shell_client.py::test_pretty_dmesg_assigns_session_numbers` — optional-tabulate formatting baseline.

No new Routing-C regression was observed.

## Scope and integrity

- exact local/remote remediation HEAD matched the instructed head;
- frozen candidate ref remained unchanged;
- PR #50 branch ref remained unchanged;
- protected product paths remained unchanged: no Executive/session/runtime adapter, VM/platform, AVR, DAP/CLI/VS Code/frontend, or RF-005..009 product implementation;
- fresh temporary checkout ended clean;
- no tracked mutation was made by the tester;
- tester made only the required result comment.

Mechanical tester classification: `ROUTING_C_EXECUTION_PASS_WITH_KNOWN_BASELINES`.

## Next gate

All three findings from `DBG-RVW-001-005-037` now have implementation and execution evidence on the remediation chain, but the corrective children are not signed. Append current-state traceability above this tested product/test head, prove no product/test diff after `045f1cf58beaf393680e1f4118cfa76de65220b2`, and obtain a **fresh independent exact-head review**.

The reviewer/worker that changed `DBG-F-029` is not independent for the changed head and may not approve it.

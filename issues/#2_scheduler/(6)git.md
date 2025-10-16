# Git Log — Scheduler Register-Window Remediation

> File name: `(6)git.md`. Capture branch, commits, and PR status for this issue.

## Branch
- Name: `Issue_#2_scheduler`
- Created on: `2025-02-14`
- Owner: Runtime/Executive team (Codex assisting)
- Based on commit: `115ed60f74a5451898b5e60736deb5c3d70e3ea3`

## Commit Log
| Date | Commit hash | Message | Author | Notes |
| --- | --- | --- | --- | --- |
| 2025-10-15 | 11cba7276a357c9090d875cfcc8c9044d84bb80b | scheduler: scaffold task memory allocators and log progress. | Hans Einar | Introduced allocator scaffolding and updated issue docs (T1 design).
| 2025-10-15 | 9d5d596ff5e3e6bbe3417f29efe293b3846b32d9 | T1 checkboxes for register/stack allocation | Hans Einar | Filled in git log, adjusted playbook, and refined allocator scaffolding.
| 2025-10-15 | f9dad8f2663307562f139bcaed27ced3dc9d9c01 | platforms/python/host_vm.py allocates per-task register banks and stack slices... | Hans Einar | Completed T1 work, verified snapshot/restore & two-task smoke test, moved playbook to T2.
| 2025-10-16 | dc8592e6c516f4c00ce89bdb0c7a28e6707ca5c2 | Introduced RegisterFile wrapper for MiniVM | Hans Einar | MiniVM now accesses register windows via memory; context save/restore updated.
| 2025-10-16 | 035f438bdae771de2b562f92c98ad449c432ba40 | MiniVM register window integration tests | Hans Einar | Ran targeted unit tests and marked T2 complete in the playbook.
| 2025-10-16 | bef1cbe766bca171249243464d00baeafaed6fc6 | Completed T2 test coverage | Hans Einar | Recorded unit tests and updated playbook; ready to start scheduler contract work (T3).
| 2025-10-16 | 3dace2120038eb9b2aff6de48932982faac90157 | Progressed T3 allocator reuse | Hans Einar | `_store_active_state` now reuses task memory allocations; task metadata stays in sync.
| 2025-10-16 | c15e2c1567bd6a61ba9b99dc87a235282f5b0880 | Added scheduler instrumentation | Hans Einar | Controller now tracks step/rotate/block/wake events and exposes stats/trace (CLI exposure pending).
| 2025-10-16 | a5c978be2b5d2752efdfedd440948cc12223ba6a | Finished T3 scheduler work | Hans Einar | CLI `sched` command reports scheduler counters/trace; tests rerun successfully.
| 2025-10-16 | 959499f2a853c4ef56fc5ddd2fec024362725453 | Added register isolation & stack guard tests | Hans Einar | New unit tests cover register window isolation and stack overflow handling.
| 2025-10-16 | 358ba171a38100e5dbca1a2a6fad626d4862587f | Extended sched CLI tests and playbook | Hans Einar | Added sched payload/pretty-print coverage; documented test runs in T4 plan.
| 2025-10-16 | b062b8007f34808a039f03a90559de40c00b5e85 | Added scheduler stats integration test | Hans Einar | `python/tests/test_scheduler_stats.py` verifies counters/trace exposure.
| 2025-10-16 | f31fe6d4fbee4596b9f1aa4fede4e36f743b87bf | Documentation/help updates | Hans Einar | Spec now documents scheduler instrumentation; CLI help covers `sched stats`; captured evidence logged.

## Pull Request
- PR URL / ID: _TBD_
- Status: _open / merged / closed_
- Reviewers: _TBD_
- Merge date: _TBD_
- Notes: _Summary of review feedback and outcomes_

## Additional Notes
- Link CI runs, review threads, or related branches as work progresses.
- Record revert or follow-up commits if they affect this issue.
- Update this document whenever a new commit is made or PR state changes.

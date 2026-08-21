# HSX issue-comment role protocol

Status: **ACTIVE COORDINATION CONVENTION**

Use the first line of cross-agent GitHub issue comments as:

```text
HSX | <SENDER> -> <RECIPIENT> | <short subject>
```

Canonical role names:

- `STEERING`
- `MASTER`
- `TESTER`
- `REVIEWER`
- `VERIFIER`

Examples:

```text
HSX | STEERING -> MASTER | RF-004 refreeze decision
HSX | MASTER -> TESTER | Run v1.3 feasibility at exact head
HSX | TESTER -> MASTER | v1.3 feasibility PASS
HSX | MASTER -> REVIEWER | Review exact corrective head
HSX | REVIEWER -> MASTER | Exact-head review REWORK
HSX | MASTER -> STEERING | RF-004 parent decision package
```

Rules:

1. The sender is the role that owns the comment contents, not merely the account posting it.
2. The recipient is the role expected to act next.
3. A comment that is durable evidence but requires no action may target `MASTER` or `STEERING` as the next gate owner.
4. Execution-only TESTER instructions must state whether repository mutation is forbidden. When marked READ-ONLY, TESTER must not edit, format, commit, push, amend, merge, rebase, or auto-fix repository files.
5. TESTER responses must include exact HEAD, exact commands, exit codes/results, pre/post `git status --porcelain`, and any generated files.
6. Cross-role comments should reference the exact issue/comment/commit they consume when known.
7. This convention is coordination metadata only; SDP IDs, exact-head sign-offs, Reviews and Verifications remain the authoritative engineering records.

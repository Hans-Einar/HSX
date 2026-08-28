# RF-004 v1.3 TESTER response template

Use this exact first-line role tag in issue #38:

```text
HSX | TESTER -> MASTER | RF-004 v1.3 read-only feasibility result
```

Required body:

```text
Exact requested HEAD: <sha>
Exact tested HEAD: <sha>
Remote branch head observed: <sha>

Pre-test git status --porcelain:
<output or CLEAN>

Commands executed:
1. <exact command>
   exit: <code>
   result: <summary>
...

Semantic probe:
- current-profile R7 dereference result: <type/signedness/width/value>
- register_rules key: <value>
- current pre-patch validator classification: <code>
- hypothetical to_register parser classification: <code>
- register fallback calls observed: <count>

Post-test git status --porcelain:
<output or CLEAN>

git diff --exit-code: PASS/FAIL
Tracked repository mutation caused by test execution: NO/YES

Conclusion: PASS / FAIL / BLOCKED

Failures/raw relevant traceback:
<none or exact output>
```

TESTER must not propose or implement a fix in this response.

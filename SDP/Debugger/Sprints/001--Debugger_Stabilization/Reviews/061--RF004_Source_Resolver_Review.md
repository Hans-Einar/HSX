# DBG-RVW-001-005-004 — RF-004 SourceResolver Review

- Status: **REWORK**
- Findings: **0 Blocking / 0 High / 1 Medium / 0 Low**
- Reviewed product head: `c0f975c4a278cecd89e19d332ca5601b074a115e`
- Coordination head: `54196e271dbc83b99bbf9f02286f45e8491a1fb5`

## Finding

On Windows, `_join_locator` passes a valid inner drive-looking logical-ID segment such as
`src/C:/unit.c` through `os.path.join`. Host drive semantics can collapse that full logical-ID
join to `<root>/src/unit.c`, resolving bytes at a locator that was never the exact joined ID.
This violates explicit-root plus full-logical-ID policy. The correction is private to Slice004:
treat every logical-ID segment literally so inner drive-looking segments cannot reset/collapse
the explicit root, and add the Windows regression.

## Evidence

- Focused SourceResolver/SourceMap: `29 passed, 3 skipped`.
- RF004 oracle: `16 passed, 1 skipped`; broad debugger: `279 passed, 3 skipped`.
- Skips are Windows case-distinct inapplicability and WinError1314 symlink degradation only.
- Ambiguity, immutability, Black/compile/import, `186` exports, signatures/schema/Enum identity,
  strict trace, exact scope, ancestry/connectivity/clean live remote otherwise PASS.

No edits were made. Verification004 and Slice005 remain stopped. Fresh corrective review036 is
reserved for the corrected product head.

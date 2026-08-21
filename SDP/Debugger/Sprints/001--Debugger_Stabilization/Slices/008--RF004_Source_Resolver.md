# DBG-SL-001-005-004 — RF-004 Exact Source Resolver

- Status: **IMPLEMENTED / INDEPENDENT REVIEW004 PENDING**
- Product head: `c0f975c4a278cecd89e19d332ca5601b074a115e`
- Parent: `DBG-RF-004`
- Iteration: `DBG-IT-001-005`
- Depends on signed: `DBG-SL-001-005-001..003`, `DBG-SL-001-005-007`
- Review: `DBG-RVW-001-005-004`
- Verification: `DBG-VER-001-005-004`

## Goal and why now

Implement exact case-preserving, content-verified SourceRef-to-local-locator resolution,
separate from the artifact index and any frontend navigation policy.

## Owned files

- `python/hsx_debugger/sources.py`
- relevant additive exports in `python/hsx_debugger/__init__.py`
- `python/tests/test_hsx_debugger_sources.py`

`python/source_map.py`, artifact modules and all runtime/frontend files are read-only.

## Required behavior

- validate frozen logical-ID NFC/separator/control/dot/absolute/drive/UNC rules;
- accept only explicit exact overrides, prefix mappings and ordered search roots as locator
  policy;
- preserve original SourceRef identity through relocation and symlink resolution;
- verify exact candidate byte length and SHA-256 before `RESOLVED`;
- return missing, ambiguous, content-mismatch and case-collision outcomes with all candidates;
- enforce exact override/no-fallthrough then case-collision/ambiguity/single-candidate content
  precedence; one content match among multiple locators remains ambiguous;
- adapt classified SourceMap prefix/relocation/symlink behavior without using its first-match
  fallback as target semantics;
- never globally lowercase/casefold identity or perform basename guessing.

## Invariants and non-goals

- local locators are excluded from SourceRef/bundle identity and canonical digests;
- filesystem case behavior may discover candidates but never changes logical identity;
- no symbol parsing, target reads, UI navigation, workspace heuristics or current-directory
  fallback unless the directory is an explicit search root;
- no DAP/CLI/VS Code, Executive/VM/AVR or RF-005..009 work.

## Traceability

`DBG-R-024..DBG-R-025`, `DBG-R-028`, `DBG-R-034..DBG-R-036`;
`DBG-F-020`; `DBG-D-004`, `DBG-D-009`; `HSX-D-002`;
interface `dbg.resolver-inspection/1.2`.

## Verification and completion signal

Test exact current root, explicit relocation/prefix, explicit override, symlink, missing,
digest/length mismatch, duplicate basename, case-collision and case-distinct files. Include
portable invalid logical IDs and ensure no CWD/basename/lowercase guess. Run legacy SourceMap
tests unchanged. Close only after exact-head review, formal verification and Master sign-off.

## Worker evidence

- Focused SourceResolver + unchanged SourceMap: `29 passed, 3 skipped`.
- Skips: case-distinct host behavior inapplicable on case-insensitive Windows; new and unchanged
  legacy symlink cases both exact WinError1314 privilege degradation.
- Compile/import/exports/exact resolve signature/Black: PASS.
- Exact three-file scope, diff check and clean Git state: PASS.
- Broad regression intentionally deferred to review/verification.

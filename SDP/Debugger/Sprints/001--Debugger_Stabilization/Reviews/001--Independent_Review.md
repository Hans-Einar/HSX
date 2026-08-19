# DBG-RVW-001-001-001 — Independent Review

- Status: PASS
- Review date: 2026-08-19
- Reviewed implementation head:
  `208063e344b767f82790ce579eba6327e2cdd0ce`
- Implementation base:
  `e5a50ab45acdcb515ccd3602ce99487bd668cdfd`
- Branch: `codex/dbg-rf-001`
- Slice: `DBG-SL-001-001-001`
- Refactor: `DBG-RF-001`

## Review boundary

The review compared the complete exact diff from the implementation base to the reviewed
implementation head against the frozen `DBG-RF-001` and `DBG-SL-001-001-001` contracts.
It evaluated `DBG-F-001..DBG-F-003`, `DBG-R-001`, `DBG-R-002`, `DBG-R-032`, and the initial
evidence obligations for `DBG-R-033` and `DBG-R-036`.

No product fix or structural debugger work was performed by the reviewer.

## Result

**PASS — no Blocking, High, or Medium findings.**

No Low findings were recorded. The implementation is ready for the separate formal
`DBG-VER-001-001-001` pass. This review is not verification and is not Master sign-off.

## Contract assessment

- `DBG-F-001` / `DBG-R-001`: raw bootstrap and adapter diagnostics in the production path
  now go to stderr or configured logging. The reviewed adapter path retains stdout solely
  for `DAPProtocol` framed writes.
- `DBG-F-002` / `DBG-R-002`: the dispatcher writes and flushes the successful initialize
  response before it emits `initialized`; the production-wrapper black-box test observes
  that exact wire order.
- `DBG-F-003` / `DBG-R-032`: subprocess coverage starts
  `vscode-hsx/debugAdapter/hsx-dap.py`, the same path selected by
  `HSXAdapterFactory` in `vscode-hsx/src/extension.ts`, and exercises both `launch` and
  `attach`.
- `DBG-R-033`: the targeted product-path evidence passed on Windows. Linux execution remains
  an explicit residual obligation under `DBG-RF-009`; no Linux PASS is claimed here.
- `DBG-R-036`: the strict byte parser and production-wrapper scenarios provide the intended
  initial regression oracle before structural replacement.

The small constructor change to `python/tests/dap_stubs.py` is necessary and within the frozen
directly related fixture allowance. `DebuggerSession.connect()` supplies additional named
constructor arguments (`client_name`, `keepalive_enabled`, and `keepalive_interval`) to the
configured backend factory; accepting and ignoring those fields keeps the capturing test
backend compatible with the real production-wrapper connection path without changing
product behavior.

## Evidence rerun by reviewer

Platform: Windows (`win32`), Python 3.11.5, pytest 8.4.2.

1. `c:/Users/hanse/miniconda3/python.exe -m pytest python/tests/test_hsx_dap_cli.py python/tests/test_hsx_dap_harness.py python/tests/test_hsx_dbg_backend.py -q`
   — PASS, `36 passed in 0.33s`.
2. `c:/Users/hanse/miniconda3/python.exe -m pytest python/tests/test_hsx_dap_cli.py -vv`
   — PASS, `3 passed`; explicit production-wrapper `launch` and `attach` cases passed and
   the non-DAP preamble negative test passed.
3. Ten consecutive runs of
   `c:/Users/hanse/miniconda3/python.exe -m pytest python/tests/test_hsx_dap_cli.py -q`
   — PASS, all ten runs reported `3 passed`; no cleanup hang or intermittent subprocess
   failure was observed.
4. Direct negative controls against `_assert_only_framed_messages` using a valid frame with
   injected preamble and trailing raw bytes — PASS, `2/2 rejected`.
5. `c:/Users/hanse/miniconda3/python.exe -m pytest python/tests -q`
   — nonzero, `534 passed, 2 skipped, 2 failed`.
6. `git diff --check
   e5a50ab45acdcb515ccd3602ce99487bd668cdfd..208063e344b767f82790ce579eba6327e2cdd0ce`
   — PASS, no output.

## Broad-suite failure classification

The two broad-suite failures are not caused by this Slice:

- `test_break_add_symbol_line` requires the ignored generated artifact
  `examples/demos/build/debug/longrun/main.sym`. It is absent from both reviewed Git trees,
  and no demo/build or owning test file changed in the Slice diff.
- `test_pretty_dmesg_assigns_session_numbers` exercises untouched shell pretty-print code.
  In this environment the installed optional `tabulate` path renders the session number as
  a table cell, while the assertion expects fallback text containing `session=1`. Neither
  `python/shell_client.py` nor `python/tests/test_shell_client.py` changed in the Slice.

They remain residual repository-suite evidence for later ownership; they do not justify an
out-of-scope product change in `DBG-RF-001`.

## Residuals and next gate

- Formal `DBG-VER-001-001-001` evidence has not yet been recorded.
- Master exact-head sign-off has not occurred.
- Linux product-wrapper evidence remains assigned to `DBG-RF-009` as allowed by the frozen
  Slice contract.
- `DBG-DA-001` and structural `DBG-RF-002..DBG-RF-009` product work remain blocked until
  verification and Master exact-head sign-off complete `DBG-RF-001`.

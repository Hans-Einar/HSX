# Debugger Verification

Verification records for debugger Refactors live here.

Each product-code Refactor must record evidence against an exact commit/head and the
requirements/design IDs it verifies. At minimum record:

- test/build commands and results;
- black-box/product-path scenarios where relevant;
- platform(s) used;
- regression/golden fixtures used;
- independent review ID/result;
- residual risks or explicit none;
- exact commit SHA accepted by Master sign-off.

`DBG-RF-001` reserves `DBG-VER-001-001-001`. Its evidence record is created only after
implementation and independent exact-head review; a planned relation is not verification.

Completed records:

- `DBG-VER-001-001-001.md` — Windows PASS for signed implementation head `208063e`.
- `DBG-RF-001--Master_Signoff.md` — Master exact-head reconciliation and completion decision.
- `DBG-VER-001-004-001.md` and `DBG-SL-001-004-001--Master_Signoff.md` — RF-002 Slice PASS
  and exact-head sign-off at `232e20a6…`.
- `DBG-VER-001-004-002.md` and `DBG-SL-001-004-002--Master_Signoff.md` — RF-003 Slice PASS
  and exact-head sign-off at `cf4d8a6…`.
- `DBG-VER-001-004-004.md` and `DBG-SL-001-004-001--Master_Signoff_v2.md` — corrected RF-002
  Slice PASS and exact-head sign-off at `a064020…`.
- `DBG-VER-001-004-003.md` — integration Slice PASS at `860a98a…`, sign-off pending.

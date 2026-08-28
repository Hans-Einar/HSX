# DBG-RVW-001-005-001 — RF-004 Legacy Oracle Review

- Status: **REWORK**
- Reviewed exact implementation head: `a9a22fc4750f22d774eade43810a499dd1992859`
- Implementation base: `9b9d48771923da213d17617ed4f72126cfaf1e17`
- Review mode: fresh independent, read-only
- Next review: `DBG-RVW-001-005-020`

## Findings

1. **High — wide-address target false without descriptor.** The oracle made `0x10020`
   unconditionally overflow rather than separating a narrow-descriptor failure from a valid
   wider unmasked address.
2. **Medium — source identity/filesystem outcomes conflated.** Case-collision was unconditional,
   and duplicate basename identity/unavailable/locator ambiguity were combined.
3. **Medium — BEST_EFFORT_LIVE diagnostic wrong.** It used `coherent_snapshot_unavailable`
   instead of frozen `portable_snapshot_evidence_unavailable`.
4. **Medium — symlink skip too broad.** Every OSError/NotImplementedError became Windows
   privilege skip instead of only WinError 1314, with unsupported symlink distinct.
5. **Medium — local/global golden not fully executable.** The test ignored the manifest's
   exact function-qualified local value.

No product or frozen-interface finding was reported.

## Independent evidence

- exact seven-file owned implementation diff and diff-check: PASS;
- new oracle: 14 passed, 1 WinError 1314 skip;
- symbol/source combined: 20 passed, 2 same-platform skips;
- focused backend/stack/location: 14 passed;
- hashseed 0/1: each 14 passed, 1 skip;
- clean coordination trace: three YAML files and 140-row Ledger PASS.

Symlink behavior is not verified/PASS on this host.

## Master disposition

REWORK accepted. A fresh bounded corrective worker owns the same seven Slice files only and
must split descriptor-dependent address outcomes, split source identity/locator outcomes, fix
the BEST_EFFORT diagnostic, narrow symlink skip classification and assert exact local/global
goldens. Fresh exact-head review is `DBG-RVW-001-005-020`.

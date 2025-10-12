# BACKLOG

Items we want to track, but which are not currently on the active TODO list:

- Add explicit CRC regression tests for asm.py/hld.py pipeline (verify header + data checksums).
- Expand floating-point coverage (f32<->f16 conversions, mixed-precision code paths).
- Document and design debugger tooling (breakpoints, single-step UX) as part of the upcoming milestone planning.
- Revisit retention policy for intermediate `.ll` files (decide whether to prune after `.mvasm`/`.hxe` generation).
- Implement `hsx-llc` lowering for integer `trunc`/`sext`/`zext` flows and dynamic-index GEPs, then bring back the corresponding pytest coverage.
- Evaluate documentation pipeline options (Doxygen theming vs Sphinx/MkDocs hybrid) before public hosting.
- Plan documentation publishing strategy (commit HTML artifacts vs. deploy via GitHub Pages).


# Standard Operating Procedure — Documentation & Iteration

## Purpose
- Ensure architecture/design documents stay aligned with implementation.
- Define touch-points between main docs, feature playbooks, and refactor packages.
- Provide iteration checklist so updates are applied consistently.

## Artefact Overview
- `main/(1)mandate.md`: project mandate; update when scope/goals change.
- `main/(2)study.md`: foundational research; revise when new investigations shift decisions.
- `main/(3)architecture/`: subsystem responsibilities and interfaces.
- `main/(4)design/`: implementation planning per subsystem.
- `functionality/#*/`: feature-specific docs (requirements, design, implementation playbook).
- `refactor/#*/`: refactor packages mirroring the same lifecycle.
- `docs/*.md`: canonical specs (hsx_spec-v2, executive_protocol, hsx_value_interface, etc.).

## Iteration Workflow
1. **Kickoff**
   - Confirm mandate/study remain valid; record any new assumptions or constraints.
   - Create/update feature or refactor package with requirements `(3)` before touching design.
2. **Architecture Review**
   - Identify affected subsystem views (for example `(3.2)executive.md`, `(3.4)val_cmd.md`).
   - Update responsibilities/interfaces if the change alters behaviour or boundaries.
   - Check off items in the architecture playbook once each view reflects the latest plan.
3. **Design Detailing**
   - For every subsystem touched, update the corresponding `(4.x)` design spec with data structures, algorithms, edge cases, and tests.
   - Reference study/architecture sections to maintain traceability.
   - Ensure design playbook items are ticked only after review.
4. **Implementation**
   - Follow the feature/refactor implementation playbook; keep docs current while coding.
   - Record tests and artefacts in DoD checklists.
5. **Verification & Sign-off**
   - Confirm architecture/design docs reflect final behaviour.
   - Update `docs/` specs if external APIs or formats changed.
   - Run through SOP checklist before closing feature/refactor.

## Change Control Checklist
- [ ] Mandate/study impacted?
- [ ] Relevant `(3.x)` architecture view updated?
- [ ] Relevant `(4.x)` design spec updated?
- [ ] Feature/refactor requirements & DoD synced?
- [ ] Docs under `docs/` refreshed (specs, interfaces)?
- [ ] Architecture/Design playbooks updated with status?
- [ ] Version control history references documentation changes?

## Review Cadence
- Hold architecture/design review when major subsystem changes are proposed.
- Perform monthly documentation audit: ensure playbook checkboxes match actual progress.
- Use SOP checklist during release preparation to avoid stale docs.

## Notes
- Keep documents concise; cross-link rather than duplicate content.
- When deprecating functionality, mark sections as deprecated and note follow-up actions.
- Encourage contributors to update docs incrementally within the same change set.

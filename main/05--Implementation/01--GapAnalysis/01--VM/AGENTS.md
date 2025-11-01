# VM Gap Analysis – Agent Guide

Welcome! This workspace tracks the execution of the VM implementation plan. Follow the steps below whenever you pick up this effort.

## 1. Get Oriented
- Read `README.md` in `../` for the gap-analysis framing.
- Skim `01--Study.md` for current findings and `02--ImplementationPlan.md` for the ordered backlog.
- Review `03--ImplementationNotes.md` (create it if missing) to see the most recent actions.

## 2. Working the Plan
- Always tackle items in the order defined by the implementation plan unless `DependencyTree.md` indicates a different prerequisite.
- Before touching code, capture the intended work (scope, files, tests) in the notes file under the matching plan section (e.g., **1.1 Shift Operations**).
- Keep changes incremental: prefer finishing or clearly parking one to-do item before starting the next.

## 3. Recording Progress
- Update `03--ImplementationNotes.md` as you finish each sub-step. Include:
  - Date (ISO format)
  - Your handle/initials
  - Summary of what you investigated/implemented
  - Status markers: TODO / IN PROGRESS / DONE / BLOCKED
  - Links or file paths to relevant patches/tests
- If you leave an item partially complete, document blockers or next steps so the next agent can resume smoothly.

## 4. Testing & Validation
- Run targeted unit/integration tests after each functional change. Note the commands and outcomes in the notes.
- If tests cannot run (time, environment, blockers), state why and list what must happen before closing the item.

## 5. Hand-off Workflow
1. Update `03--ImplementationNotes.md` with everything achieved during the session.
2. Stop editing once you are ready for a checkpoint; let the maintainer commit.
3. After the commit lands, create `04--Git.md` mirroring the format in `issues/#2_scheduler/06--Git.md` (link to commit hash, summary of changes, any follow-up todos).

## 6. Communication
- Use clear, actionable language in all docs.
- If you discover discrepancies between design and implementation, capture them both in the notes and (if substantial) raise an issue.

Stay consistent with these steps to keep the VM gap analysis traceable and easy to resume. Happy hacking!

# Feature Workflow Guide

Use this reference when adding new functionality or upgrading existing behaviour.  
Each feature request lives under `functionality/#<id>_<slug>/`.

---

## 0. Creating a New Feature Folder
1. Copy `functionality/#0_template/` → `functionality/#<id>_<slug>/`.
2. Keep numeric prefixes on all template files.
3. Capture stakeholder conversation in `(0)interview.md`; end with a clear requirements snapshot.
4. Fill out `(1)functionality.md` with the refined problem statement, use cases, and triggers.
5. Draft an initial study `(2)study.md` capturing the baseline behaviour and candidate approaches.
6. Summarise the agreed solution in `(3)design.md` before implementation begins.

---

## 1. Picking Up an Existing Feature (fresh context window)
1. Review `(4)dod.md` for the current status.
2. Skim `(1)functionality.md`, `(2)study.md`, `(3)design.md`, `(5)implementation.md`, and `(6)git.md` to understand scope and progress.
3. Check `functionality/INDEX.md` for a quick summary if needed.
4. Note the active subtask in `(5)implementation.md` before making changes.

---

## 2. Start of Each Work Session
1. Run `git status` from the repo root. Sync `(6)git.md` if commits are missing.
2. Confirm you are on the correct branch; record the branch name in `(6)git.md`.
3. Re-read the active items in `(5)implementation.md` and ensure their status reflects reality.

---

## 3. During the Work Session
1. Work only on the active subtask(s) in `(5)implementation.md`.
2. Update the playbook as you go: mark completed steps, add notes, record new discoveries.
3. Keep docs and code aligned (e.g., update `(3)design.md` if the solution changes).
4. Log test commands and results; link artefacts in `(4)dod.md` when they verify DoD items.

---

## 4. End of the Work Session
1. Summarise code/document changes (this becomes the suggested commit message).
2. Update `(5)implementation.md` statuses and leave handover notes.
3. List remaining “Next actions” at the bottom of the summary.
4. Stage and commit if appropriate.
5. Append new commits to `(6)git.md` (date, hash, message, notes).
6. Run `git status` to confirm a clean tree before stopping.

---

## 5. Additional Reminders
- Record every new file in git immediately, even if you commit later.
- Do not merge into `main` until the DoD checklist is complete (unless requested).
- Treat `(4)dod.md` as the authoritative status board.
- Keep `(5)implementation.md` as the living task list.
- Document blockers in both `(5)implementation.md` and your end-of-session summary.

By following these steps, feature development remains auditable and hand-offs stay smooth.

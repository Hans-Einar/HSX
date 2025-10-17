# Agent Workflow Guide

Use this checklist to stay consistent across sessions and handovers.  
When in doubt, consult `issues/#0_template/README.md` for template details.

---

## 0. Creating a New Issue Folder
1. Copy `issues/#0_template/` → `issues/#<id>_<slug>/`.
2. Rename each template file as-is (numeric prefixes intact).
3. Fill out `(1)issue.md` with the problem statement, context, and evidence.
4. Draft the initial review/remediation/DoD as soon as enough data is available.
5. Record the branch name in `(6)git.md` when the work branch is created.

---

## 1. Picking Up an Existing Issue (fresh context window)
1. Read the quick links in `(4)dod.md` to orient yourself.
2. Skim `(1)issue.md`, `(2)study.md`, `(3)remediation.md`, `(5)implementation.md`, and `(6)git.md` to understand current status.
3. Check `issues/INDEX.md` if you need a TL;DR before diving in.
4. Note the active task in `(5)implementation.md` and pending subtasks.

---

## 2. Start of Each Work Session
1. Run `git status` in the repo. If there are commits missing from `(6)git.md`, add them before making new edits.
2. Confirm you are on the correct branch (`git branch --show-current`) and update `(6)git.md` if the branch changed.
3. Re-read the active task in `(5)implementation.md` and ensure its status reflects reality (e.g., `active`).

---

## 3. During the Work Session
1. Work on the **active** task only. Follow the remaining unchecked bullets in `(5)implementation.md`.
2. Update the playbook as you make progress:
   - Mark substeps complete (`[x]`) with short notes/evidence.
   - Add any new substeps discovered.
3. Keep the code and docs in sync (e.g., adjust `(4)dod.md` if scope changes).
4. Run relevant tests/commands and record results.

---

## 4. End of the Work Session
1. Summarise the code/document changes (this text becomes the suggested commit message).
2. Update `(5)implementation.md` statuses and handover notes.
3. List remaining “Next actions” at the bottom of the summary so the next agent can resume quickly.
4. Stage and commit if appropriate (`git add ... && git commit -m "<message>"`).
5. Append the new commit to `(6)git.md` (date, hash, message, notes).
6. Run `git status` to ensure a clean tree before stopping.

---

## 5. Additional Reminders
- Every new file should be added to git immediately (`git add <file>`), even if the commit comes later.
- Do not push upstream until the DoD checklist is complete (unless stakeholders request otherwise).
- Keep `(4)dod.md` as the authoritative status board—tick items there once verified.
- Use `(5)implementation.md` as the living TODO list; treat it like a Kanban column for the active task.
- If you block on something, record the blocker in the playbook and the summary so the next agent can pick it up.

By following these steps, each handoff is smooth, and history stays auditable.

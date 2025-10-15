# Issue Documentation Template

This folder defines the standard document procedure (SDP) for tracking runtime issues.  
When a new issue is discovered, copy this directory as `issues/#<id>_<slug>/` (for example `issues/#2_scheduler/`).  
Each Markdown file keeps a numeric prefix `(1)`, `(2)`, … to preserve ordering in directory listings.

## Files

| File | Purpose |
| --- | --- |
| `(1)issue.md` | Canonical description of the problem. Captures context, evidence, impact, and acceptance signals. |
| `(2)review.md` | Technical assessment of how implementation diverges from expectations/spec. May suggest remediation directions. |
| `(3)remediation.md` | Detailed implementation plan based on the review. Breaks work into actionable tasks, dependencies, and verification steps. |
| `(4)dod.md` | “Definition of Done” summary: TL;DR, links to the other docs, and concrete task checklists that mark completion. |
| `(5)implementation.md` | Detailed, living playbook for executing remediation tasks; fine-grained checklist for agents. |
| `(6)git.md` | Git activity log for the issue: branch details, commit history, pull request references. |

## Usage Notes

1. Maintain the naming convention `issues/#<id>_<slug>/`. Increment `<id>` per issue; `<slug>` is a short descriptive tag.
2. Preserve the numeric filename prefixes `(1)…(6)` when copying. They keep files ordered chronologically.
3. Keep the templates intact in this folder. Copy (do not move) when starting a new issue.
4. Maintain `(5)implementation.md` as the fine-grained execution log for agents; update it continuously.
5. Update `(6)git.md` whenever a branch is created, commits are made, or a PR progresses (include commit hashes and notes).
6. When the issue is resolved, ensure all checkboxes in `(4)dod.md` are ticked and `(6)git.md` documents the final merge outcome.

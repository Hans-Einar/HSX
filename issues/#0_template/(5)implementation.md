# IMPLEMENTATION PLAYBOOK TEMPLATE

> File name: `(5)implementation.md` (retain the numeric prefix when copying).

> This document maintains a detailed, step-by-step task list so agents can pause/resume work seamlessly.

## Task Tracker
Link each section to the corresponding task ID in `(3)remediation.md` and checklist entries in `(4)dod.md`.

### T1 `<Title>` (`<status>`)
- [ ] Step 1 — `<description>`
  - Notes:
  - Artifacts:
- [ ] Step 2 — `<description>`

### T2 `<Title>` (`<status>`)
- [ ] Step 1 — `<description>`

_(add more sections as needed)_

> Recommended status labels: `not started`, `active`, `blocked`, `open`, `done`. Update the status in parentheses whenever the task progresses.

## Implementation Issues Log

> Track unexpected problems discovered while implementing the remediation plan. Duplicate the structure below for each issue (I1, I2, ...).

### I<id> `<short title>` (`<status>`)
- **Summary:** `<short description>`
- **Study findings:** `<root cause insights>`
- **Remediation:** `<planned fix>`
- **Implementation:**
  - Commits: `<hash or TBD>`
  - Tests: `<commands>`

_(add more issues as needed)_

## Context & Artifacts
- Source files / directories touched:
- Test suites to run:
- Commands / scripts used:

## Handover Notes
- Current status:
- Pending questions / blockers:
- Suggested next action when resuming:

Update this document continuously whenever progress is made or blocked, so the next agent has full context.

# Implementation Guidelines

- Use refactorNotes.md as the running implementation checklist. Each change should reference the relevant design doc section before coding.
- Split work into chronological branches per feature area (e.g., impl/event-stream, impl/pid-locks). Keep branches focused and merge sequentially after review.
- Before coding, review the corresponding design spec in main/(4)design/ and ensure docs/executive_protocol.md stays in sync with any protocol adjustments.
- Update playbook checkboxes and refactorNotes.md entries as milestones complete to maintain traceability.
- Include regression tests and protocol samples (event payloads, session flows) with each feature per the design specifications.
- Document deviations or discoveries directly in the design docs, appending implementation notes so future iterations remain aligned.


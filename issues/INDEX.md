# Issues Index

Brief summary of active and historical issues. Each entry links to its dedicated folder under `issues/`.

- [`#0_template/`](./#0_template/) — Standard document procedure templates for new issues. Copy this folder when starting a new investigation.
- [`#1_mailbox/`](./#1_mailbox/) — Mailbox namespace and stdio visibility fixes. TL;DR: align shell, docs, and tests with `app:/shared:` descriptors so producer/consumer demos work end-to-end.
- [`#2_scheduler/`](./#2_scheduler/) — Scheduler/context-switch divergence from spec. TL;DR: current VM copies registers and ignores base pointers; refactor to true register-window model with one-instruction steps and stack guards.

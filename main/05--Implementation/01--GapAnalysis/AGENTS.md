# Gap Analysis - Coordination Agent Guide

This directory orchestrates progress across all implementation tracks. Use this guide when working at the "grand plan" level.

## Documents
- `GrandImplementationPlan.md` - master schedule (python-first). Defines the order in which modules and phases should land.
- `GrandImplementationNotes.md` - (create/update) quick status snapshot per module.
- `DependencyTree.md` - historical dependency map; reference when sequencing work.

## How to Work Here
1. Review the grand plan to confirm current priorities (e.g., finish Executive Phase 1 before moving to Mailbox Phase 2).
2. Dive into the specific module folder (e.g., `01--VM`, `02--Executive`) and follow that module's `AGENTS.md` / `ImplementationNotes.md`.
3. After finishing work, update:
   - Module-specific notes/logs.
   - `GrandImplementationNotes.md` with a short summary of what changed.
   - `GrandImplementationPlan.md` only if priorities or sequencing need adjustment.

## General Rules
- Stay python-first; defer C ports until the plan explicitly calls for them.
- Keep documentation in sync (module plans, executive protocol, etc.).
- Use pytest for regression coverage and log commands/results.
- If pausing work, leave clear TODOs in both module notes and the grand notes.

Thanks for coordinating! This layer keeps the whole implementation effort aligned.

# Project Context — HSX Platform

> Snapshot of the overarching HSX initiative to orient contributors before diving into mandate, study, or design documents.

## Snapshot
- **Project name:** HSX Runtime & Tooling
- **Primary stakeholders:** Runtime/Tooling team, Firmware team, HSX leadership
- **Target hardware:** AVR128DA28-class MCUs and ARM Cortex‑M nodes hosting HSX apps
- **Current phase:** Milestone 5 wrap-up / debugger preparation
- **Key artefacts:** `MILESTONES.md`, `docs/hsx_spec-v2.md`, `docs/executive_protocol.md`

## Goals
- Deliver a modular HSX execution environment with VM, executive, shell, and debugger components that run consistently on desktop hosts and MCU targets.
- Keep one host firmware per CAN node while deploying domain-specific HSX apps that communicate via mailbox+HAL interfaces.
- Maintain alignment between implementation, documentation, and milestone roadmap.
- Support Python-first prototyping with a path to C-native components where necessary.

## Constraints & Assumptions
- Cross-platform tooling (Windows/macOS/Linux) with Python ≥3.11 as baseline.
- Preserve `.hxe` format, VM ISA, mailbox semantics, and protocol compatibility while iterating.
- Host executive runs natively on MCU/embedded targets without requiring an OS or shell inside the VM.
- Staged rollout via milestones; debugger tooling promoted immediately after Milestone 5.

## Open Questions / Notes
- Confirm long-term repository split between system code and tooling.
- Establish governance process for updating specs vs. implementation.
- Track how C porting efforts will interface with Python prototypes and embedded host builds.
- Define provisioning strategy for distributing HSX apps (CAN master vs. on-node storage) across product lines.

# Project Mandate — HSX Runtime & Tooling

## Purpose
Define the overarching goal, scope, and success signals for the HSX platform so all downstream documents and workstreams share a common mandate.

## Vision
- Deliver a portable HSX runtime capable of loading and executing self-contained “apps” on resource-constrained microcontrollers (e.g., AVR128DA28, ARM Cortex‑M) by pairing a lightweight MiniVM with a native host executive.
- Enable every HSX node to share the same host firmware while domain-specific behaviour ships as HSX apps that can be distributed (CAN/J1939, SD card, or host provisioning) without touching the host binary.
- Maintain developer ergonomics through Python-first tooling while charting a clear path to embedded firmware deployments.

## Scope
- **In scope:** HSX MiniVM, native host executive, mailbox subsystem, HAL bindings for MCU peripherals, shell client, debugger toolkit, documentation, packaging, and deployment flows for CAN node scenarios.
- **Out of scope (initially):** Running a general-purpose OS or shell inside the VM, non-HSX ISA targets, fully featured debugger on microcontrollers beyond lightweight shims, unrelated tooling.
- **Assumptions:** Host executive controls the VM (no in-VM control layer), apps communicate via mailboxes and HAL-backed services, VM remains single-task interpreter with context switching managed by the executive.

## Strategic Objectives
1. Align implementation with `hsx_spec-v2.md` so architecture and behaviour match documented expectations.
2. Complete milestone roadmap up through debugger/tooling integration with minimal divergence.
3. Maintain developer-friendly Python tooling while planning the migration path for performance-critical components to C.

## Success Metrics
- Milestones met with corresponding documentation/test evidence.
- Toolchain produces `.hxe` artefacts that run on both desktop prototypes and embedded hosts with identical behaviour.
- Apps interchange data through mailbox/HAL channels and can be provisioned dynamically (CAN/SD) without host firmware changes.
- Debugger attaches via executive, manages breakpoints, and streams events as specified.

## Governance & Stakeholders
- **Product owner:** HSX leadership team.
- **Technical leads:** Runtime/Tooling leads responsible for MiniVM, executive, and tooling.
- **Review cadence:** Mandate reviewed at major milestone boundaries; updates propagate through study and design docs.

## Dependencies
- Foundational docs (`docs/hsx_spec-v2.md`, `docs/executive_protocol.md`) remain authoritative and are kept in sync with implementation.
- Teams maintain feature playbooks (`functionality/…`) and refactor packages (`refactor/…`) aligned with this mandate.

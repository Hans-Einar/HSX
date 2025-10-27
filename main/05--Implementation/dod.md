# Definition of Done — Implementation Phase

| Module | DR Coverage | DG Alignment | Notes |
|--------|-------------|--------------|-------|
| MiniVM | DR-1.3, DR-2.1, DR-2.1a, DR-2.2, DR-2.3, DR-8.1 | DG-1.3–1.4, DG-2.1–2.4, DG-4.1–4.3, DG-5.4 | Ensure workspace-pointer acceptance microbench + debug events implemented. |
| Executive | DR-1.1, DR-1.2, DR-2.5, DR-3.1, DR-5.1–5.3, DR-6.1, DR-7.1, DR-8.1 | DG-1.2–1.4, DG-3.4–3.5, DG-5.1–5.4, DG-6.x, DG-7.x, DG-8.2 | Includes session/event streaming, PID locks, provisioning hooks. |
| HSX Shell | DR-6.1, DR-7.1, DR-8.1 | DG-6.4, DG-7.2, DG-8.1 | Shell commands must leverage new session/event APIs and respect mailbox/stdio policy. |
| MVASM | DR-2.3, DR-2.5, DR-3.1 | DG-3.1–3.5 | Emits deterministic .hxo; consumes shared syscall header; exports debug metadata. |
| hsx-llc | DR-2.1a, DR-2.2, DR-3.1 | DG-2.1–2.3, DG-3.2 | Register allocation instrumentation + lowering compliance. |
| Linker | DR-3.1, DR-5.3 | DG-3.1, DG-3.5, DG-7.3 | .hxe header contract + FRAM manifest bundling. |
| Disassembler | DR-3.1, DR-8.1 | DG-3.3, DG-8.1 | Consumes listing metadata for tooling panels. |
| Debugger (hsxdbg) | DR-8.1 | DG-8.1–8.3 | Session/event core, TUI, automation surfaces. |
| Provisioning | DR-1.1, DR-3.1, DR-5.3 | DG-1.2, DG-5.3, DG-7.3 | CAN/SD workflows + persistence. |
| Value/Command | DR-6.1, DR-7.1, DR-7.3 | DG-6.x, DG-7.x | Registry, security, persistence & transport bindings. |

All commits should cite relevant DR/GD IDs in messages and update this table once DoD per module is satisfied.

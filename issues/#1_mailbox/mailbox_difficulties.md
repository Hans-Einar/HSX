# HSX Mailbox Runtime Difficulties (October 2024)

## Current Situation
- The Python executive already understands the `app:`/`shared:` namespaces; descriptors are shared correctly inside the manager.
- The `examples/demos/mailbox` C producer/consumer now relies on the new `hsx_mailbox_recv_basic()` helper (uses the assembly shim to call SVC `MAILBOX_RECV` with timeout `HSX_MBX_TIMEOUT_INFINITE`).
- In practice the demo still stalls: producer stays blocked on stdin, consumer never sees traffic, and every end‑to‑end attempt ends with the VM reporting `pc_out_of_range` after a recv.

## Key Technical Challenges
- **SVC argument plumbing:** the assembly helper for `hsx_mailbox_recv()` still has mismatched expectations about where the optional recv‑info pointer lives (register vs stack). When the struct pointer is passed, the Python VM doesn’t write back the status/length fields, so the C side misinterprets buffer state.
- **`recv_basic` shortcut instability:** falling back to `hsx_mailbox_recv_basic()` removes the info pointer entirely, but now we rely on a sentinel timeout value (`-1` → `0xFFFF`). That keeps the assembler happy, yet the VM crashes once the task resumes, suggesting a deeper context/register restoration bug.
- **VM scheduling & state restore:** traces show `mailbox_wait` events landing, but the VM resumes the producer/consumer with corrupted program counters (`pc_out_of_range`). That points to `_complete_mailbox_wait` or the subsequent scheduler rotation writing stale PC/SP data back into the task context.
- **Lack of coverage for SVC path:** existing Python tests poke the manager directly; nothing exercises the full SVC entry/exit path with blocking timeouts. We’re debugging blind whenever the executive mishandles register frames.

## What’s Working
- Shell tooling (`mbox` filters, help text) and documentation updates are aligned.
- Python unit suites pass (`python/tests/test_mailbox_manager.py`, `python/tests/test_shell_client.py`).
- The manager happily reuses descriptor `app:procon` across PIDs; the issue sits squarely in the VM/SVC boundary.

## Suggested Next Steps
1. **Instrument `_svc_mailbox_controller` & `_complete_mailbox_wait`:** dump the VM register set before and after the wake‑up path to prove whether PC/SP are being restored.
2. **Stabilize the assembly shim:** either (a) rework `hsx_mailbox_recv` to load the info pointer from the stack slot the VM expects, or (b) expose a C‑only helper that bypasses the shim and uses the Python host RPC to receive data for the demo until the SVC path is proven.
3. **Add regression coverage:** a minimal integration test that boots two tasks via the SVC interface, binds `app:demo`, and checks for matching descriptor IDs + message flow.
4. **Pause feature churn and realign docs/tests:** before touching more runtime code, let’s catalogue what the documentation promises vs. what actually exists today.

For now the producer/consumer demo remains blocked until the SVC receive path is stable.

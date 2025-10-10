# Design Changes Log

## 2024-07-18 · Mailbox Fan-Out Semantics for STDIO
**Context**
- Request: support multiple tasks consuming the same mailbox stream (stdio fan-out, logging, pipeline observers).
- Constraints: preserve current single-consumer semantics unless explicitly opted-in; no extra retention beyond configured capacity; Python executive is reference implementation for now.

**Goals**
- Allow more than one subscriber to observe mailbox traffic without forcing `TAP`-style mirrors.
- Give producers control over backlog policy (drop-oldest vs wait-for-space) while respecting finite capacity.
- Surface message loss or blocking to callers so slow consumers can recover.

**Non-Goals**
- Persisting messages beyond the mailbox capacity.
- Retroactively delivering history to late subscribers (they start at the live head).
- Changing the HSXE format or existing SVC module numbering.

**Proposed Runtime Model**
1. Each mailbox keeps a monotonic 32-bit `seq_no` that increments per message alongside the circular buffer.
2. Subscriber state (per handle) stores `last_seq` (sequence ID most recently delivered) and `flags` (e.g. `HSX_MBXF_OVERRUN`).
3. `MAILBOX_RECV` in fan-out mode returns the next available message where `seq_no > last_seq`. If multiple messages queued, repeated `RECV` calls advance until caught up. When no new data exists, behavior matches current timeout/poll rules.
4. Mailbox capacity is unchanged. When the buffer is full:
   - **Drop-oldest policy (`MAILBOX_MODE_FANOUT_DROP`)**: advance the head slot even if some subscribers have not seen it. Their next `RECV` returns the new head and sets `HSX_MBXF_OVERRUN` to signal loss.
   - **Block-on-space policy (`MAILBOX_MODE_FANOUT_BLOCK`)**: new sends park the producer until every subscriber has advanced past the oldest slot (leverages existing wait/wake plumbing in the executive).
5. Producers select the policy through new mode bits at `MAILBOX_BIND`/`MAILBOX_OPEN`. Default remains the existing single-consumer queue (no fan-out flag set).
6. `MAILBOX_TAP` continues to mirror live frames without sequence tracking; taps do not delay eviction.

**API Additions (draft)**
- New mode flag `HSX_MBX_MODE_FANOUT` to opt into multi-reader behavior.
- Supplemental policy bits `HSX_MBX_MODE_FANOUT_DROP` (default for fan-out) and `HSX_MBX_MODE_FANOUT_BLOCK`.
- Message flag `HSX_MBXF_OVERRUN` returned via `MAILBOX_RECV` metadata when loss occurs.
- Optional query via `MAILBOX_PEEK` to expose `(tail_seq, head_seq, subscriber_count)` for diagnostics.

**Impact / Compatibility**
- Existing mailboxes continue operating as strict FIFO queues; no spec change unless the new mode bit is set.
- STDIO pipes (`svc:stdio.*`) can be reconfigured to `FANOUT_DROP` so multiple listeners observe stdout simultaneously.
- Python tests need new coverage for fan-out fan-in scenarios and send blocking.
- C executive must mirror the data structures once scheduler wait/wake integration lands.

**Next Steps**
1. Prototype sequence tracking and policies in the Python mailbox manager.
2. Extend shell listen/send commands with options to toggle fan-out policy per mailbox.
3. Once behavior stabilizes, update `docs/hsx_spec.md` and the SVC API reference with the finalized flags and semantics.
4. Write regression tests ensuring overruns and blocking propagate correct status codes.

---

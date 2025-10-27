# Executive Protocol Reference (Implementation Copy)

Primary source: docs/executive_protocol.md. This copy highlights implementation TODOs:

- Maintain JSON-over-TCP RPC commands (session.open/close/keepalive, events.subscribe/ack/unsubscribe).
- Event payload schema: {seq, ts, type, pid, data} with categories 	race_step, debug_break, scheduler, mailbox_send/recv, watch_update, stdout, stderr, warning.
- Back-pressure contract: bounded queue per session (max_events negotiated), drop-oldest warning, ACK handling, reconnect via since_seq.
- PID lock policy: single debugger per PID; passive listeners use pid_lock=null.
- Error modes: unsupported_category, session_required, heartbeat timeout, version mismatch.

Implementation docs must link here when describing event handling.

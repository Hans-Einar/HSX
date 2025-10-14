# Producer/Consumer Mailbox Demo

The *procon* example pairs two HSX tasks to demonstrate mailbox based
communication without relying on an external terminal window.

## Design goals

- Spawn the **consumer** task, bind a shared mailbox (`app:procon`), and stream
  any payload received on that mailbox to its own stdout.
- Spawn the **producer** task, read bytes from its stdin mailbox and forward
  them into the shared `app:procon` mailbox.
- Keep the topology entirely inside the executive so it works even when a
  dedicated terminal window cannot be spawned.
- Provide an escape hatch: typing `exit` (or sending it via stdin) causes the
  producer to terminate, which stops the demo cleanly.

## Message flow

```text
hsx shell stdin -> producer stdin -> app:procon -> consumer stdout -> hsx shell
```

1. The consumer binds the shared mailbox (`hsx_mailbox_bind`) before entering
   its receive loop.
2. The producer opens the same mailbox and blocks on stdin reads.
3. Whenever new input arrives, the producer trims trailing newlines, sends the
   payload into `app:procon`, and optionally stops when the payload equals
   `exit`.
4. The consumer receives each payload and echoes it to stdout, making messages
   visible back in the HSX manager console.

This pipeline guarantees that the demo survives environments where the tooling
cannot create an auxiliary operating-system terminal.

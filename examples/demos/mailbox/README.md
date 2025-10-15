# Mailbox Producer/Consumer Demo

This demo pairs two HSX tasks—a producer and a consumer—that exchange messages
over the shared mailbox `app:procon`. The workflow below mirrors the current
runtime (single-instruction scheduler, instruction-based stepping, namespace
filters) so the instructions double as a regression checklist for Main Task 9.

## Build the demo artefacts

```sh
cd examples/demos
make mailbox_producer mailbox_consumer
```

The build emits `build/mailbox/producer.hxe` and `build/mailbox/consumer.hxe`.

## Launch the VM + executive stack

```sh
PYTHONPATH=. python python/hsx_manager.py
```

At the `manager>` prompt:

1. `start all` – spawns the VM (`host_vm.py`), the executive daemon (`execd.py`),
   and an inline shell if no external terminal is available.
2. `status` – confirm both services are listening (`vm` on port 9999, `exec` on
   port 9998).

## Load the producer/consumer tasks

From the manager shell (or another shell via `shell`):

```sh
load examples/demos/build/mailbox/consumer.hxe
load examples/demos/build/mailbox/producer.hxe
ps
```

You should see two runnable PIDs. The consumer binds `app:procon`; the producer
waits on `svc:stdio.in@<producer_pid>` for input.

## Drive execution deterministically

- `clock status` – capture the initial state (auto loop stopped, totals zero).
- `clock step 20` – retire 20 instructions across both tasks (round-robin). Each
  `clock step` call advances both tasks by one instruction per rotation.
- `clock step 10 -p <producer_pid>` – advance only the producer if you want to
  single-step its stdin loop.

The manual counters (`manual_steps`, `manual_total_steps`) increment so you can
replay the same sequence later.

## Interact with the mailbox

- `listen <consumer_pid>` – stream the consumer’s stdout.
- `send <producer_pid> "hello world"` – deliver input to the producer; the
  payload is forwarded to the shared mailbox and echoed by the consumer.
- `send <producer_pid> exit` – exit the producer cleanly.

## Inspect descriptors

```sh
mbox shared          # confirm app:procon is visible with namespace=shared
mbox ns app owner 0  # host (PID 0) view of global app: mailboxes
mbox pid <producer_pid>
```

The shared mailbox reports fan-out and depth metrics. After sending data you
should see `depth=0` (consumer drained the queue).

## Tear down

`stop all` or simply exit the manager; it terminates the shell, executive, and
VM in reverse order.

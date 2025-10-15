# HSX Mailbox Runtime Baseline (pre-tooling updates)

Captured while running `platforms/python/host_vm.py --listen 4444 --svc-trace` and driving the `examples/demos/mailbox` artifacts with `python/shell_client.py`.

## A. Descriptor Snapshot

Initial snapshot after launching `consumer.hxe` and `producer.hxe` (no manual binding yet):

```json
{"status":"ok","descriptors":[
  {"descriptor_id":1,"namespace":1,"name":"stdio.in","owner_pid":1,"capacity":64,"bytes_used":0,"queue_depth":0,"head_seq":0,"next_seq":0,"mode_mask":3,"subscriber_count":1,"waiters":[],"taps":[]},
  {"descriptor_id":2,"namespace":1,"name":"stdio.out","owner_pid":1,"capacity":64,"bytes_used":0,"queue_depth":0,"head_seq":0,"next_seq":0,"mode_mask":3,"subscriber_count":2,"waiters":[],"taps":[]},
  {"descriptor_id":3,"namespace":1,"name":"stdio.err","owner_pid":1,"capacity":64,"bytes_used":0,"queue_depth":0,"head_seq":0,"next_seq":0,"mode_mask":3,"subscriber_count":2,"waiters":[],"taps":[]},
  {"descriptor_id":4,"namespace":0,"name":"pid:1","owner_pid":1,"capacity":64,"bytes_used":0,"queue_depth":0,"head_seq":0,"next_seq":0,"mode_mask":3,"subscriber_count":0,"waiters":[],"taps":[]},
  {"descriptor_id":5,"namespace":1,"name":"stdio.in","owner_pid":2,"capacity":64,"bytes_used":0,"queue_depth":0,"head_seq":0,"next_seq":0,"mode_mask":3,"subscriber_count":1,"waiters":[],"taps":[]},
  {"descriptor_id":6,"namespace":1,"name":"stdio.out","owner_pid":2,"capacity":64,"bytes_used":0,"queue_depth":0,"head_seq":0,"next_seq":0,"mode_mask":3,"subscriber_count":1,"waiters":[],"taps":[]},
  {"descriptor_id":7,"namespace":1,"name":"stdio.err","owner_pid":2,"capacity":64,"bytes_used":0,"queue_depth":0,"head_seq":0,"next_seq":0,"mode_mask":3,"subscriber_count":1,"waiters":[],"taps":[]},
  {"descriptor_id":8,"namespace":0,"name":"pid:2","owner_pid":2,"capacity":64,"bytes_used":0,"queue_depth":0,"head_seq":0,"next_seq":0,"mode_mask":3,"subscriber_count":0,"waiters":[],"taps":[]}
]}
```

`app:procon` is absent until we explicitly bind it.

## B. Manual `app:procon` Bind + Cross-PID Opens

```text
mailbox_bind(pid=0, target="app:procon", capacity=64, mode=3)
→ {'status': 'ok', 'mbx_status': 0, 'descriptor': 9, 'capacity': 64, 'mode': 3}
```

Opening the same target for each PID reuses descriptor `9`:

```text
mailbox_open(pid=1, target="app:procon") → handle 4, descriptor 9
mailbox_open(pid=2, target="app:procon") → handle 4, descriptor 9
```

Snapshot immediately after the two opens:

```json
{"descriptor_id":9,"namespace":2,"name":"procon","owner_pid":null,
 "capacity":64,"bytes_used":0,"queue_depth":0,"head_seq":0,"next_seq":0,
 "mode_mask":3,"subscriber_count":2,"waiters":[],"taps":[]}
```

CLI view (`mbox`) reflects the new descriptor:

```text
ID  Namespace  Owner  Depth  Bytes  Mode   Name
...
  9  app            -      0      0  0x0003  procon
```

## C. Message Round-Trip

Send from PID 2 (producer side handle 4) and receive from PID 1 (consumer handle 4):

```text
mailbox_send(pid=2, handle=4, data="hello from host")
→ {'status': 'ok', 'mbx_status': 0, 'length': 15, 'descriptor': 9}

mailbox_recv(pid=1, handle=4)
→ {'status': 'ok', 'mbx_status': 0, 'length': 15, 'flags': 0,
    'channel': 0, 'src_pid': 2, 'text': 'hello from host'}
```

After the recv, `mailbox_snapshot` shows `descriptor_id:9` with `queue_depth:0`, confirming the message queue drained and both processes used the shared descriptor.

These captures form the baseline evidence needed before modifying the shell tooling.

---

## D. Post-fix Verification (instruction-stepping scheduler)

Commands issued via `python/shell_client.py --host 127.0.0.1 --port 9998` with a fresh `host_vm.py --listen 9999` / `execd.py --listen 9998` pair:

```text
load examples/demos/build/mailbox/consumer.hxe   → pid 1
load examples/demos/build/mailbox/producer.hxe   → pid 2
clock step 200                                   # retire 200 instructions round-robin
listen 1 5
```

`listen` shows the consumer announcing its bind:

```json
{
  "messages": [
    {
      "channel": 0,
      "text": "mailbox consumer listening on app:procon",
      "target": "svc:stdio.out@1"
    }
  ],
  "status": "ok"
}
```

Injecting producer input and stepping forward:

```text
send 2 hello
clock step 40
listen 1 5
```

The consumer echoes the payload (truncated transcript):

```json
{
  "messages": [
    {
      "channel": 0,
      "text": "hello",
      "target": "svc:stdio.out@1"
    }
  ],
  "status": "ok"
}
```

A snapshot of the shared descriptor confirms the global binding:

```text
mbox ns app
    ID  Namespace  Owner  Depth  Bytes  Mode   Name
     9  app            -      0      0  0x0003  procon
```

Manual stepping statistics after the exchange:

```json
{
  "state": "stopped",
  "manual_steps": 3,
  "manual_total_steps": 50,
  "auto_steps": 0,
  "auto_total_steps": 0
}
```

These logs demonstrate the end-to-end producer/consumer flow under the strict
instruction scheduler, matching the updated documentation and shell tooling.

# Runtime Cache Query API

`python/hsxdbg/cache.py` exposes a shared `RuntimeCache` that mirrors task
state for debugger front-ends. Query helpers hide the caching logic and fall
back to RPC loaders only when necessary.

## Register API

```python
state = cache.get_registers(pid)
value = cache.query_registers(pid, "R0")
```

- `update_registers(pid, mapping)` – store snapshot (R0-R15 + PC/SP/PSW).
- `get_registers(pid)` – returns `RegisterState` or `None`.
- `query_registers(pid, name)` – returns scalar register value when cached.

`CommandClient.get_register_state()` keeps the cache populated by calling the
`dumpregs` RPC when the cache is empty or `refresh=True`.

## Memory API

- `cache_memory(pid, base, bytes)` – seed a block.
- `read_memory(pid, addr, length)` – exact slice when cached.
- `query_memory(pid, addr, length, fallback)` – fallback invoked with the
  unresolved address/length. Command client passes a lambda that issues the
  `peek` RPC and stores the result.

## Stack API

- `update_call_stack(pid, frames)` – convert the executive frame dicts into
  `StackFrame` objects.
- `get_call_stack(pid)` – returns cached frames (empty list if missing).
- `query_call_stack(pid, fallback)` – fallback returns the raw frame list (from
  the `stack` RPC). Command client handles `refresh` semantics for consumers.

## Watch API

- `update_watch(pid, record)` – stores/updates a `WatchValue` entry.
- `iter_watches(pid)` – returns cached watch values.
- `query_watches(pid, fallback)` – fallback returns the raw watch entries from
  the `watch list` RPC. Command client uses `list_watches(refresh=True)` to
  force a refresh.

## Mailbox API

`update_mailboxes(pid, descriptors)`/`list_mailboxes(pid)` store metadata for
`mailbox_*` commands. Event-driven invalidation happens via `CacheController`.

## Integration Summary

- `SessionManager` optionally instantiates an EventBus + `CacheController` to
  feed the cache with trace/watch/debug_break events.
- `CommandClient` invalidates caches on control operations (`step`, `pause`,
  `resume`) and provides high-level methods (`get_register_state`,
  `get_call_stack`, `list_watches`, `read_memory`) that automatically refresh
  the cache from the relevant RPC when stale.

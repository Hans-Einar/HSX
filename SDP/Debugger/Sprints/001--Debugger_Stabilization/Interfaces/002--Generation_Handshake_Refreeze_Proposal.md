# Controller/Gateway Generation Handshake — Refreeze Proposal

- Status: **BLOCKER / STEERING DECISION REQUIRED**
- Owning iteration: `DBG-IT-001-004`
- Frozen interface affected: `dbg.controller-gateway/1`
- Affected Slices: `DBG-SL-001-004-001`, `DBG-SL-001-004-002`,
  `DBG-SL-001-004-003`
- Accepted designs: `DBG-D-001`, `DBG-D-002`, `DBG-D-003`
- Discovery phase: parallel foundation workers, before any product commit
- Product WIP: recoverable local stash `efc91f2640647402bc92c69bde1c57685cfaa1f1`

## Blocking contradiction

The frozen interface says the legacy gateway increments debugger-local session/stream
generations when OPEN_SESSION/SUBSCRIBE succeeds. It also says every completion/health/event
must exact-match the controller model generation before mutation. The controller public port
has no generation-adoption command/notice.

Therefore:

1. controller emits OPEN_SESSION effect stamped generation `N`;
2. gateway opens the session and emits completion/health stamped `N+1`;
3. controller correctly rejects both as stale;
4. no frozen input can advance the controller to `N+1`;
5. SUBSCRIBE has the same contradiction for stream generation.

Using RF-002's internal pure `replace_generation` helper from outside the actor or auto-adopting
an arbitrary higher notice would violate single-writer authority and exact fencing. Keeping the
gateway stamp at `N` would violate the frozen gateway generation rule. Both fresh workers
stopped without staging/committing product changes.

## Alternatives

### A — Controller preallocates the next generation (recommended)

Refreeze as `dbg.controller-gateway/1.1`:

- On OPEN_SESSION acceptance, the controller atomically increments local session and
  capability generations, resets stream/target legacy continuity, invalidates epoch/old
  pending state, and emits the effect already stamped with the new generation.
- On SUBSCRIBE_EVENTS acceptance, the controller atomically increments stream generation and
  emits the effect with that generation.
- Gateway validates monotonic expected generation, adopts the effect stamp for its local
  transport instance and echoes the exact stamp on completion/health/events.
- Failure does not roll back generation. A retry of the same idempotent operation uses the same
  operation/stamp; a new open/subscribe command allocates another generation.
- Negotiated capability contents remain gateway evidence, but capability-generation identity
  is controller-owned.

Benefits: preserves one state writer, exact-match fencing, immutable envelopes and current
ports; adds no adoption envelope and no implicit higher-generation trust. This matches the
accepted Study intent that session generation belongs under controller authority.

### B — Origin-stamped completion plus explicit transition envelope

Gateway returns OPEN/SUBSCRIBE completion stamped `N` and a new frozen
`GenerationTransition {origin, next, cause}`. Controller validates origin then adopts next.

Trade-off: explicit two-phase handshake, but adds a new public notice/transition type and more
ordering/failure cases. It is sound but larger than needed for the foundation.

### C — Controller auto-adopts any higher generation (reject)

This is simple but destroys exact-generation fencing, permits stale/foreign notice takeover and
turns gateway callbacks into state authority. It conflicts with `DBG-D-001/D-003`.

### D — Gateway never increments generations (reject)

This cannot distinguish reopened sessions/streams and violates the accepted identity/lifetime
requirements.

## Recommended contract delta

Authorize Alternative A and make only these `dbg.controller-gateway/1.1` changes:

1. Generation allocation for OPEN_SESSION/SUBSCRIBE_EVENTS is controller-owned.
2. `GatewayEffect.generation` is the exact generation the gateway must use/echo.
3. Gateway validates monotonic effect generation but never invents a different stamp.
4. Controller transition to the new generation occurs atomically before effect dispatch and
   invalidates previous epoch/continuity.
5. Retry/new-operation rules above are frozen and negative-tested.
6. Legacy profile and every existing no-runtime/no-frontend/no-RF-004..009 guard remain.

No HSX target contract, `DBG-D-*` design meaning, Executive protocol or runtime implementation
change is requested. This is a shared interface handshake correction discovered before product
integration.

## Resume gate

Workers remain stopped and integration remains blocked until Steering authorizes/refuses a
refreeze in issue #38. On authorization, Master updates interface 001, Slice contracts,
CurrentIndex/Relations/Ledger/Handoff, restores only the recoverable owned-file WIP, and assigns
fresh worker passes against the corrected interface. Existing partial files receive no review,
verification or implementation authority.

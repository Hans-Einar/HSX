# Controller/Gateway Generation Handshake — Refreeze Proposal

- Status: **STEERING RESOLVED — TWO-PHASE v1.1 REFREEZE AUTHORIZED**
- Owning iteration: `DBG-IT-001-004`
- Frozen interface affected: `dbg.controller-gateway/1`
- Affected Slices: `DBG-SL-001-004-001`, `DBG-SL-001-004-002`,
  `DBG-SL-001-004-003`
- Accepted designs: `DBG-D-001`, `DBG-D-002`, `DBG-D-003`
- Discovery phase: parallel foundation workers, before any product commit
- Product WIP: recoverable local stash `efc91f2640647402bc92c69bde1c57685cfaa1f1`
- Steering decision: issue #38 comment `5357146230`
- Frozen successor: `003--Controller_Gateway_Envelope_Set_v1_1.md`

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

### A — Controller reserves then promotes the next generation (accepted/refined)

Steering refined Alternative A to reserve -> authoritative success -> promote. Controller
consumes a monotonic N+1 watermark and records the pending reservation before dispatch but
keeps legal old continuity active. Gateway validates/echoes the reserved stamp unchanged.
Only matching operation + reservation + exact stamp + authoritative resource-established
success promotes; failure/cancellation burns without promotion/rollback. See the frozen v1.1
successor for the complete semantics and fixtures.

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

## Accepted contract delta

Comment `5357146230` authorizes these `dbg.controller-gateway/1.1` changes:

1. Allocation watermark/reservation for OPEN/SUBSCRIBE is controller-owned.
2. Reservation does not change active continuity.
3. `GatewayEffect.generation` is the exact reserved generation gateway validates/echoes.
4. Only matching authoritative success promotes and retires superseded continuity.
5. Failure/cancellation burns; same-operation retry reuses; new operation allocates next.
6. Session and stream namespaces/parent fencing remain independent.
7. Legacy profile and every no-runtime/no-frontend/no-RF-004..009 guard remain.

No HSX target contract, `DBG-D-*` design meaning, Executive protocol or runtime implementation
change is requested. This is a shared interface handshake correction discovered before product
integration.

## Resume gate

Workers remain stopped and integration remains blocked until the new interface implementation
and required contract fixtures pass fresh independent `DBG-RVW-001-004-004`. Only then may
Master selectively restore candidate WIP and assign fresh worker passes. Existing partial files
receive no review, verification or implementation authority.

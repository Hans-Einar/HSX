# Portable Debug Runtime Architecture

- Status: ACCEPTED / FROZEN PORTABLE TARGET BASELINE
- Range: `HSX-A-001..HSX-A-005`
- Requirements: `HSX-R-001..HSX-R-036`
- Studies: `HSX-ST-001..HSX-ST-008`
- State: accepted target; semantic baseline `b57e368f77bb533b09397d633fc92565655e1668`; not implemented

Steering froze these architecture IDs in issue #47 comment `5356480919`. They describe
portable HSX evidence and authority, not Debugger UI/controller policy or AVR realization.

## Proposed architecture decisions

| ID | Boundary | Owns | Explicitly does not own |
|---|---|---|---|
| `HSX-A-001` | Runtime Identity and Lifecycle Authority | Executive/stream/session/target/PID/LoadedImage refs and generations; ArtifactRef; attachment leases; lifecycle commit/tombstone evidence | Debug-bundle identity/binding, Debugger disconnect defaults, UI naming, source-step algorithm, AVR storage/transport |
| `HSX-A-002` | Architecture, ABI, and Debug Artifact Description | Typed address spaces; serialization/alignment; reusable ImageDebugBundleRef and target-specific ImageDebugBinding; canonical serializer/golden vectors; source identity; ABI/unwind/location descriptors | Target lifecycle identity, local source locator/UI policy, implicit masks, one universal R7 recipe, target-specific AVR encoding choices outside profiles |
| `HSX-A-003` | Execution Evidence and Inspection Consistency | Ordered transitions, stable stops, inspection revisions/snapshots, exact step/bypass evidence, blocked-state capability | Debugger controller state machine, source into/over/out policy, fabricated timer completion |
| `HSX-A-004` | Event Continuity and Capability Profiles | Stream identity, canonical order, cursor/selection, ACK/gaps/resume, checkpoints/health and current/degraded profiles | Client callback/threading policy, DAP events, version guessing, silent loss |
| `HSX-A-005` | Remote Debug Resource Authority | Remote resource/owner/provenance identity, revisions/CAS, shared effective bindings, lifetime/tombstones/events and degraded limits | Debugger logical desired resources, snapshot Watch expressions, IDE presentation |

## Architectural dependency order

1. `HSX-A-001` identity/generations are consumed by every other boundary.
2. `HSX-A-002` image/address/ABI data and `HSX-A-001` target identity bind snapshots and
   resources.
3. `HSX-A-003` transition/snapshot evidence supplies causal state to `HSX-A-004` events and
   exact resource-hit evidence to `HSX-A-005`.
4. `HSX-A-004` carries continuity/gap evidence for lifecycle, transition and resource streams;
   it does not redefine their domain semantics.
5. `HSX-A-005` revisions/provenance are consumed by exact-step bypass and Debugger
   reconciliation.

## Cross-track ownership

| Concern | HSX owns | Debugger owns | AVR owns |
|---|---|---|---|
| Identity/lifecycle | Portable refs, generations, leases, authority and outcomes | Controller recovery policy and user-facing lifecycle intents/default selection | Target storage/boot/process realization and resource budgets |
| Addresses/ABI | Descriptor schemas, checked values, ABI/unwind/location contracts | Artifact/source services and presentation/handle mapping | Harvard/physical spaces and concrete native ABI profile implementation |
| Run/stop/snapshot | Runtime evidence, revisions, tokens and exact primitives | Serialized state reduction, stop epochs, inspection composition and source-step plans | On-target atomicity mechanism/timing |
| Events | Canonical event stream continuity and capabilities | Gateway consumption, ACK-after-apply and reconciliation policy | Transport implementation/limits |
| Resources | Remote identity/owner/revision/lifecycle evidence | Desired logical resources, multi-frontend policy and snapshot Watch | Hardware breakpoint/watch realization and limits |

## Architecture invariants

1. No reference is valid without its owning instance/target/image/stream generation.
2. PID, path, app name, CRC, endpoint and sequence integer are never sufficient identity alone.
3. Current, degraded and unsupported profiles are explicit capability records.
4. Domain mutation evidence is revisioned and conditionally addressable; stale operations fail.
5. Command receipt and completion, runtime state, transition cause and stable inspection stop
   remain separate evidence records.
6. Inspection consistency is immutable snapshot or revision-pinned validation; best-effort live
   reads cannot claim coherence.
7. Event delivery loss cannot rewrite canonical history or ACK state.
8. Remote resource observation cannot transfer ownership.
9. Legacy behavior is contained in named degraded profiles with tests and removal conditions.
10. Portable contracts do not select Debugger UI policy or AVR implementation strategy.
11. LoadedImageRef is target/load identity and never contains a bundle ref/digest; reusable
    bundle identity and target-specific binding are separate acyclic records.
12. Source logical identity preserves exact NFC case/content; local filesystem resolution is
    locator policy, not HSX identity.

## Profile architecture

The target current profile is `hsx.portable-debug-runtime/1`, composed from capabilities:

- `hsx.runtime.identity-generations/1`
- `hsx.lifecycle.authority-leases/1`
- `hsx.architecture.descriptor/1`
- `hsx.abi.descriptor/1`
- `hsx.debug.image-bundle/1`
- `hsx.debug.unwind-recipes/1`
- `hsx.debug.location-recipes/1`
- optional `hsx.debug.register-write/1`
- `hsx.execution.evidence/1`
- `hsx.inspection.snapshot/1`
- optional `hsx.blocked.snapshot/1`
- `hsx.event-stream.core/1`
- `hsx.event-stream.resume/1`
- `hsx.event-stream.health/1`
- `hsx.runtime-state.events/1`
- `hsx.debug-resource.events/1`
- `hsx.reconcile-baseline/1`
- `hsx.debug-resource.revisions/1`

The Python legacy evidence is exposed only as named degraded profiles, including
`hsx.python-debug-legacy/1`, `hsx.legacy-event-stream/1`, and
`hsx.legacy-debug-resources/1`. A client selects behavior from negotiated capabilities, never
by guessing a software version.

## Migration posture

The current Python implementation is the differential oracle. Contract fixtures first capture
its accepted behavior and known gaps. Implementations then add typed identity/revision fields
and capability profiles without changing Debugger policy. Legacy adapters remain available
until current-profile fixtures pass across Python and future native implementations. No
product migration is authorized by this architecture proposal.

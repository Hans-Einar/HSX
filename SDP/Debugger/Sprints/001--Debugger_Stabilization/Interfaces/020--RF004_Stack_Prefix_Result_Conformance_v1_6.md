# `dbg.resolver-inspection/1.6` — trustworthy stack-prefix result conformance

Status: **STEERING REFROZEN / CANDIDATE IMPLEMENTATION PENDING REVIEW**

Steering authority: issue #38 comment `5375603250`.
Parent projection: `dbg.resolver-inspection/1.5`.
Portable HSX baseline remains unchanged; this projection closes a representation defect against
accepted `HSX-D-002`.

## Conflict closed by 1.6

Portable unwind semantics require every already-proven frame to remain available as a
trustworthy immutable prefix when continuation terminates with an exact category such as
`UNSUPPORTED`, `CORRUPT`, or `STALE`. Generic `InspectionResult[T]` intentionally carries a
value only for `COMPLETE/PARTIAL`, so it cannot represent that combination without either
losing frames or lying about termination.

1.6 does **not** weaken generic `InspectionResult`.

## Dedicated stack sequence envelopes

```text
StackWalkResult {
  status: COMPLETE | PARTIAL | UNAVAILABLE | STALE |
          ARTIFACT_MISMATCH | UNSUPPORTED | CORRUPT,
  context: InspectionContext,
  frames: tuple[UnwindFrame, ...],
  diagnostics: tuple[Diagnostic, ...]
}

StackPageResult {
  status: same status subset,
  context: InspectionContext,
  page: FramePage,
  diagnostics: tuple[Diagnostic, ...]
}
```

`UNKNOWN_HANDLE` is invalid in either envelope.

### StackWalkResult invariants

- all frames have the exact result context and contiguous `frame_index = 0..N-1`;
- `COMPLETE` has at least one frame and no terminating diagnostic;
- `PARTIAL` has at least one frame and at least one terminating diagnostic;
- `UNAVAILABLE` has no frame and at least one diagnostic;
- `STALE`, `ARTIFACT_MISMATCH`, `UNSUPPORTED`, and `CORRUPT` have at least one diagnostic and
  may retain zero or more frames proven before termination;
- no result contains a frame whose CFA/PC/SP required evidence was not completed before the
  terminating condition;
- no status is rewritten merely to make a generic envelope accept a prefix.

### StackPageResult invariants

- `page.total_frames` equals the number of proven prefix frames from the exact underlying walk;
- pagination slices that prefix only; no theoretical/full-stack count is invented;
- every returned `FrameRecord.unwind` has the exact result context;
- `COMPLETE` has `page.total_frames >= 1` and no terminating diagnostic;
- `PARTIAL` has `page.total_frames >= 1` and a diagnostic;
- `UNAVAILABLE` has `page.total_frames == 0` and a diagnostic;
- the other terminating statuses preserve their diagnostics and may expose the page slice of
  any already-proven prefix;
- offset beyond the proven prefix returns an empty page while retaining the same status,
  total and terminating diagnostics.

## Service signatures

```text
StackService.unwind(...) -> StackWalkResult
EpochInspectionSession.stack(page: PageRequest) -> StackPageResult
```

Slice006 may intern handles for proven prefix frames while its exact epoch/session remains
active, regardless of why continuation terminated. Actual epoch invalidation still wins before
new handle allocation and makes existing handles stale. Re-resolving an interned frame performs
an exact repeated walk and may use the frame only if that repeated walk still proves the same
frame index before its termination.

## Non-changes

- no frontend/DAP IDs or presentation;
- no best-effort live reads;
- no fabricated caller continuation;
- no weakening of stop-epoch or handle invalidation;
- no Executive/VM/AVR change;
- no RF-005+ authorization.

Candidate implementation remains unpromoted until fresh independent exact-head review and
formal verification are available.

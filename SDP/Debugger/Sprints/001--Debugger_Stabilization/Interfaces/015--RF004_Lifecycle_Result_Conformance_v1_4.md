# `dbg.resolver-inspection/1.4` — lifecycle/control result conformance

Status: **STEERING REFROZEN / CANDIDATE ONLY / INDEPENDENT REVIEW PENDING**

Steering authority: issue #38 comment `5375130207`.
Parent interface: `dbg.resolver-inspection/1.3`.

## Normative delta

Generic `ResolutionResult[T]` and `InspectionResult[T]` remain recursively contract-safe immutable and MUST NOT contain lifecycle-bearing service/session objects.

The inspection factory therefore uses a dedicated control envelope:

```text
InspectionServiceCreateResult {
  status: ResolutionStatus,
  service: InspectionService | None,
  diagnostics: tuple[Diagnostic, ...]
}

InspectionService.create(...) -> InspectionServiceCreateResult
```

- `RESOLVED`: exactly one non-null service and no diagnostics.
- failure: `service=None` and at least one diagnostic.
- no ambiguous/candidate list semantics.

`InspectionOpenResult.session` remains its existing dedicated lifecycle envelope. `service` and `session` fields are explicit **opaque lifecycle/control references**: the envelope fields are immutable, while supported lifecycle operations may change the referenced control object's internal state. This exception is narrow and does not apply to generic result payloads, artifact/frame/value records, containers, or caller-defined mutable objects.

No portable HSX target/runtime contract, recipe schema, snapshot semantics, or frontend contract changes.

## Candidate rule

During the temporary no-5.6-review window this interface may be implemented/tested only on `master/rf004-v13-candidate`. It is not signed or promotable until a fresh independent exact-head interface review and normal Slice review/verification/sign-off are restored.

# `dbg.resolver-inspection/1.5` — exact symbol-id lookup conformance

Status: **STEERING REFROZEN / CANDIDATE QUERY IMPLEMENTATION DEFERRED / REVIEW PENDING**

Steering authority: issue #38 comment `5375145347`.
Parent interface: `dbg.resolver-inspection/1.4`.

## Normative delta

Add one exact immutable artifact-index query:

```text
DebugArtifactIndex.symbol_by_id(symbol_id: str) -> ResolutionResult[SymbolRecord]
```

- exact non-empty `symbol_id` only;
- one exact match => `RESOLVED`;
- zero => `UNAVAILABLE / symbol_id_unavailable`;
- duplicate identity => `CORRUPT / duplicate_symbol_identity`;
- no name, basename, casefold, function-id, declaration-order, or first-candidate fallback.

`SnapshotExpression.SymbolExpression` consumes only this query and remains valid only for address-bearing FUNCTION/LABEL records. `VariableExpression` uses the same exact symbol identity plus its frozen function/scope identity and LocationRow evaluation.

No artifact wire schema, component digest, portable HSX contract, runtime protocol, or frontend policy changes.

## Candidate note

The current candidate InspectionService consumes the public method and returns `artifact_index_contract` rather than reading a private `_symbols` collection if the method is absent. The previously signed Slice003 file remains untouched on the candidate branch until the additive method can be applied as a surgical diff and independently reviewed; test doubles exercise the 1.5 consumer seam meanwhile.

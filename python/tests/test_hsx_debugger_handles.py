from __future__ import annotations

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

from hsx_debugger import *
from hsx_debugger.handles import (
    DomainHandle,
    EpochHandleStore,
    HandleInternResult,
    HandleKind,
    ScopeKind,
)


ZERO = "0" * 64


def context(epoch_id="epoch", snapshot_token="snapshot"):
    artifact = ArtifactRef(
        "hsx.artifact-ref/1", "application/vnd.hsx.hxe", CanonicalUInt64(1),
        CanonicalUInt64(64), ContentDigest("sha256", ZERO)
    )
    target = TargetRef("target", ExecutiveInstanceRef("exec"), "opaque", 1, 7, 1)
    image = LoadedImageRef(
        "hsx.loaded-image-ref/1", target.executive, target, "image",
        CanonicalUInt64(1), artifact
    )
    generation = GenerationStamp("exec", 1, "opaque", 1, 1, 1, 7, EvidenceGrade.PORTABLE)
    stop = StopToken(target, image, "stop", 3)
    snapshot = InspectionSnapshotRef(
        target, image, stop, snapshot_token, 3, 4,
        frozenset({"registers", "memory", "disassembly"}),
        SnapshotStability.IMMUTABLE, EvidenceGrade.PORTABLE
    )
    return InspectionContext(
        target, image,
        EpochBinding(StopEpochId(epoch_id), generation, stop, snapshot, EvidenceGrade.PORTABLE)
    )


def test_intern_is_exact_idempotent_and_monotonic() -> None:
    ctx = context()
    store = EpochHandleStore.create(ctx)
    first = store.intern(HandleKind.FRAME, (0,))
    again = store.intern(HandleKind.FRAME, (0,))
    second = store.intern(HandleKind.FRAME, (1,))
    assert isinstance(first, HandleInternResult)
    assert first.status is InspectionStatus.COMPLETE
    assert first.handle == again.handle
    assert (first.handle.serial, second.handle.serial) == (1, 2)
    assert store.resolve(first.handle, HandleKind.FRAME).object_key == (0,)


def test_scope_and_variable_key_shapes_are_frozen() -> None:
    ctx = context()
    store = EpochHandleStore.create(ctx)
    frame = store.intern(HandleKind.FRAME, (0,)).handle
    scope = store.intern(HandleKind.SCOPE, (frame.serial, ScopeKind.LOCALS)).handle
    symbol = store.intern(HandleKind.VARIABLE, (scope.serial, "symbol", 4, "local.x")).handle
    register = store.intern(HandleKind.VARIABLE, (scope.serial, "register", 2, "R7")).handle
    assert store.resolve(scope, HandleKind.SCOPE).object_key == (frame.serial, ScopeKind.LOCALS)
    assert store.resolve(symbol, HandleKind.VARIABLE).object_key == (
        scope.serial, "symbol", 4, "local.x"
    )
    assert store.resolve(register, HandleKind.VARIABLE).object_key == (
        scope.serial, "register", 2, "R7"
    )


def test_bad_keys_are_corrupt_without_consuming_serial() -> None:
    ctx = context()
    store = EpochHandleStore.create(ctx)
    bad = store.intern(HandleKind.SCOPE, (0, ScopeKind.LOCALS))
    assert bad.status is InspectionStatus.CORRUPT
    assert bad.handle is None
    first = store.intern(HandleKind.FRAME, (0,))
    assert first.handle.serial == 1


def test_wrong_kind_and_unknown_serial_are_unknown_handle() -> None:
    ctx = context()
    store = EpochHandleStore.create(ctx)
    frame = store.intern(HandleKind.FRAME, (0,)).handle
    assert store.resolve(frame, HandleKind.SCOPE).status is InspectionStatus.UNKNOWN_HANDLE
    unknown = DomainHandle(ctx, HandleKind.FRAME, 999)
    assert store.resolve(unknown, HandleKind.FRAME).status is InspectionStatus.UNKNOWN_HANDLE


def test_foreign_context_is_unknown_even_with_same_epoch_spelling() -> None:
    ctx = context()
    other = context(epoch_id="epoch", snapshot_token="other")
    store = EpochHandleStore.create(ctx)
    foreign = DomainHandle(other, HandleKind.FRAME, 1)
    assert store.resolve(foreign, HandleKind.FRAME).status is InspectionStatus.UNKNOWN_HANDLE


def test_invalidate_is_terminal_and_idempotent() -> None:
    ctx = context()
    store = EpochHandleStore.create(ctx)
    frame = store.intern(HandleKind.FRAME, (0,)).handle
    first = store.invalidate("resume")
    second = store.invalidate("repeat")
    assert first.status is InvalidationStatus.INVALIDATED
    assert second.status is InvalidationStatus.ALREADY_STALE
    assert store.resolve(frame, HandleKind.FRAME).status is InspectionStatus.STALE
    stale = store.intern(HandleKind.FRAME, (1,))
    assert stale.status is InspectionStatus.STALE
    assert stale.handle is None


def test_concurrent_same_key_interns_one_serial() -> None:
    ctx = context()
    store = EpochHandleStore.create(ctx)
    with ThreadPoolExecutor(max_workers=8) as pool:
        handles = tuple(pool.map(lambda _: store.intern(HandleKind.FRAME, (7,)).handle, range(64)))
    assert {item.serial for item in handles} == {1}
    assert len(set(handles)) == 1


def test_concurrent_distinct_keys_get_unique_never_reused_serials() -> None:
    ctx = context()
    store = EpochHandleStore.create(ctx)
    with ThreadPoolExecutor(max_workers=8) as pool:
        handles = tuple(pool.map(lambda i: store.intern(HandleKind.FRAME, (i,)).handle, range(32)))
    assert len({item.serial for item in handles}) == 32
    assert sorted(item.serial for item in handles) == list(range(1, 33))

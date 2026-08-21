from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, replace
from enum import Enum
from pathlib import Path
import sys
from types import MemberDescriptorType, SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from hsx_debugger.addresses import ByteOrder, HsxAddress, HsxAddressRange, AddressSpaceId, Permission
from hsx_debugger.contracts import EvidenceGrade, GenerationStamp
from hsx_debugger.identity import (
    ArtifactRef,
    CanonicalUInt64,
    ContentDigest,
    EpochBinding,
    ExecutiveInstanceRef,
    ImageDebugBundleRef,
    InspectionContext,
    InspectionSnapshotRef,
    LoadedImageRef,
    SnapshotStability,
    SourceRef,
    StopEpochId,
    StopToken,
    TargetRef,
)
from hsx_debugger.metadata import (
    FunctionRecord,
    InstructionClassification,
    InstructionRecord,
    LexicalScopeRecord,
    MemoryRegion,
    SourceIdentityManifest,
    SourceIdentityRecord,
    SourceLocation,
    SymbolKind,
    SymbolRecord,
    TypeKind,
    TypeMember,
    TypeRecord,
)
from hsx_debugger.results import (
    ContextBindingResult,
    ContextBindingStatus,
    Diagnostic,
    DisassembledInstruction,
    DisassemblyBlock,
    EvaluatedValue,
    ExpressionKind,
    ExpressionValue,
    InspectionResult,
    InspectionStatus,
    MemoryBlock,
    MemorySegment,
    MemorySegmentStatus,
    ResolutionResult,
    ResolutionStatus,
    ValueAvailability,
    ValuePiece,
    ValuePieceStatus,
)
from hsx_debugger.snapshot import SnapshotReadPort, fence_snapshot_result, require_snapshot_read_set


ZERO = "0" * 64


def refs():
    artifact = ArtifactRef(
        "hsx.artifact-ref/1",
        "application/vnd.hsx.hxe",
        CanonicalUInt64(1),
        CanonicalUInt64(10),
        ContentDigest("sha256", ZERO),
    )
    target = TargetRef("target-ref", ExecutiveInstanceRef("exec"), "target", 1, 5, 1)
    image = LoadedImageRef(
        "hsx.loaded-image-ref/1", target.executive, target, "image", CanonicalUInt64(1), artifact
    )
    bundle = ImageDebugBundleRef(
        "hsx.image-debug-bundle-ref/1", artifact, "sha256", "1" * 64
    )
    source = SourceRef(bundle, "src/main.c", ContentDigest("sha256", "2" * 64), CanonicalUInt64(3))
    generation = GenerationStamp(
        executive_instance_id="exec",
        session_generation=1,
        target_id="target",
        target_generation=1,
        capability_generation=1,
        stream_generation=1,
        display_pid=5,
        evidence_grade=EvidenceGrade.PORTABLE,
    )
    stop = StopToken(target, image, "stop", 2)
    snapshot = InspectionSnapshotRef(
        target,
        image,
        stop,
        "snapshot",
        2,
        3,
        frozenset({"registers", "memory"}),
        SnapshotStability.REVISION_PINNED,
        EvidenceGrade.PORTABLE,
    )
    context = InspectionContext(
        target,
        image,
        EpochBinding(StopEpochId("epoch"), generation, stop, snapshot, EvidenceGrade.PORTABLE),
    )
    return source, context


def test_source_manifest_empty_golden_and_ordering_deep_immutability() -> None:
    empty = SourceIdentityManifest("hsx.source-identity-manifest/1", ())
    assert empty.canonical_digest() == "6caa23594d6f57fb795a2e73648f5c8ed9928a5e25798d3bb48545412ca164a0"
    a = SourceIdentityRecord("a.c", ContentDigest("sha256", ZERO), CanonicalUInt64(0))
    b = SourceIdentityRecord("b.c", ContentDigest("sha256", "1" * 64), CanonicalUInt64(1), "c")
    records = [a, b]
    manifest = SourceIdentityManifest("hsx.source-identity-manifest/1", records)
    records.append(a)
    assert manifest.records == (a, b)
    assert SourceIdentityManifest("hsx.source-identity-manifest/1", (b, a)).records == (a, b)
    with pytest.raises(ValueError, match="unique"):
        SourceIdentityManifest("hsx.source-identity-manifest/1", (a, a))
    with pytest.raises(FrozenInstanceError):
        manifest.schema = "x"  # type: ignore[misc]


def test_source_function_and_location_invariants() -> None:
    source, _ = refs()
    location = SourceLocation(source, 1, 2, 0)
    code = AddressSpaceId("code")
    function = FunctionRecord(
        "fn", "main", None, HsxAddressRange(HsxAddress(code, 0x20), 8), location
    )
    assert function.definition == location
    with pytest.raises(ValueError):
        SourceLocation(source, 0)
    with pytest.raises(ValueError, match="non-empty"):
        replace(function, range=HsxAddressRange(HsxAddress(code, 0), 0))


@pytest.mark.parametrize(
    "record",
    [
        SymbolRecord("f", "f", SymbolKind.FUNCTION, HsxAddress(AddressSpaceId("code"), 0), 4, "f", None, None, 0),
        SymbolRecord("l", "l", SymbolKind.LABEL, HsxAddress(AddressSpaceId("code"), 4), 0, "f", "scope", None, 1),
        SymbolRecord("g", "g", SymbolKind.GLOBAL, None, 4, None, None, "i32", 2),
        SymbolRecord("x", "x", SymbolKind.LOCAL, None, 4, "f", "scope", "i32", 3),
        SymbolRecord("c", "c", SymbolKind.CONSTANT, None, 4, None, None, "i32", 4),
    ],
)
def test_symbol_kind_valid_forms(record: SymbolRecord) -> None:
    assert record.address is not None if record.kind in {SymbolKind.FUNCTION, SymbolKind.LABEL} else record.address is None


def test_symbol_kind_rejects_sentinels_and_mismatched_function_scope_pairs() -> None:
    code = AddressSpaceId("code")
    with pytest.raises(ValueError, match="addressless"):
        SymbolRecord("g", "g", SymbolKind.GLOBAL, HsxAddress(code, 0), 4, None, None, None, 0)
    with pytest.raises(ValueError, match="function/scope"):
        SymbolRecord("c", "c", SymbolKind.CONSTANT, None, 4, "f", None, None, 0)
    with pytest.raises(ValueError, match="function/scope"):
        SymbolRecord("x", "x", SymbolKind.LOCAL, None, 4, "f", None, None, 0)
    with pytest.raises(ValueError, match="scoped"):
        SymbolRecord("l", "l", SymbolKind.LABEL, HsxAddress(code, 1), 0, None, "s", None, 0)


def test_type_kind_size_member_order_overlap_and_bounds_invariants() -> None:
    first = TypeMember("a", "u8", 0, 8)
    second = TypeMember("b", "u8", 8, 8)
    struct = TypeRecord("pair", "Pair", TypeKind.STRUCT, 16, ByteOrder.LITTLE, (first, second))
    union = TypeRecord("either", "Either", TypeKind.UNION, 8, ByteOrder.BIG, (first, replace(first, name="b")))
    assert struct.members == (first, second)
    assert len(union.members) == 2
    with pytest.raises(ValueError, match="only STRUCT/UNION"):
        TypeRecord("i", "int", TypeKind.INTEGER, 8, ByteOrder.LITTLE, (first,))
    assert replace(struct, members=(second, first)).members == (second, first)
    with pytest.raises(ValueError, match="overlap"):
        replace(struct, members=(first, TypeMember("b", "u8", 4, 8)))
    with pytest.raises(ValueError, match="exceeds"):
        replace(struct, members=(first, TypeMember("b", "u16", 8, 16)))


def test_scope_instruction_memory_record_invariants() -> None:
    source, _ = refs()
    code = AddressSpaceId("code")
    pc_range = HsxAddressRange(HsxAddress(code, 0x20), 8)
    scope = LexicalScopeRecord("scope", "fn", None, pc_range, 0)
    instruction = InstructionRecord(
        "insn", HsxAddress(code, 0x20), 2, 0xABCD, "fn", SourceLocation(source, 1), InstructionClassification.USER
    )
    region = MemoryRegion("text", ".text", "code", pc_range, frozenset({Permission.READ, Permission.EXECUTE}))
    assert scope.declaration_order == 0
    assert instruction.encoded_word == 0xABCD
    assert region.permissions == frozenset({Permission.READ, Permission.EXECUTE})
    with pytest.raises(ValueError, match="fit"):
        replace(instruction, encoded_word=1 << 16)
    with pytest.raises(ValueError, match="parent"):
        replace(scope, parent_scope_id="scope")
    assert replace(region, permissions=frozenset()).permissions == frozenset()
    with pytest.raises(TypeError, match="Permission"):
        replace(region, permissions=frozenset({"read"}))


def test_result_envelopes_enforce_status_cardinality_and_structured_diagnostics() -> None:
    diagnostic = Diagnostic("missing", "missing evidence", component="test", frame_index=0)
    assert ResolutionResult(ResolutionStatus.RESOLVED, None, (1,), ()).values == (1,)
    assert ResolutionResult(ResolutionStatus.AMBIGUOUS, None, (1, 2), (diagnostic,)).values == (1, 2)
    with pytest.raises(ValueError, match="one or more"):
        ResolutionResult(ResolutionStatus.RESOLVED, None, (), ())
    with pytest.raises(ValueError, match="at least two"):
        ResolutionResult(ResolutionStatus.AMBIGUOUS, None, (1,), ())
    _, context = refs()
    assert InspectionResult(InspectionStatus.COMPLETE, context, 1, ()).value == 1
    assert InspectionResult(InspectionStatus.PARTIAL, context, 1, (diagnostic,)).value == 1
    with pytest.raises(ValueError, match="no value"):
        InspectionResult(InspectionStatus.STALE, context, 1, (diagnostic,))
    with pytest.raises(ValueError, match="no context"):
        ContextBindingResult(ContextBindingStatus.STALE, context, (diagnostic,))


def test_generic_result_payloads_are_deeply_frozen_after_construction() -> None:
    _, context = refs()
    source = {"outer": [{"numbers": [1, 2], "labels": {"a", "b"}}]}
    inspection = InspectionResult(InspectionStatus.COMPLETE, context, source, ())
    resolution = ResolutionResult(ResolutionStatus.RESOLVED, None, [source], ())

    source["outer"][0]["numbers"].append(3)
    source["outer"][0]["labels"].add("c")
    source["new"] = []

    for payload in (inspection.value, resolution.values[0]):
        assert payload["outer"][0]["numbers"] == (1, 2)
        assert payload["outer"][0]["labels"] == frozenset({"a", "b"})
        assert "new" not in payload
        with pytest.raises(TypeError):
            payload["new"] = "mutation"  # type: ignore[index]


def test_generic_result_payloads_reject_mutable_duck_objects() -> None:
    _, context = refs()
    duck = SimpleNamespace(value=1)
    with pytest.raises(TypeError, match="immutable scalars"):
        InspectionResult(InspectionStatus.COMPLETE, context, duck, ())
    with pytest.raises(TypeError, match="immutable scalars"):
        ResolutionResult(ResolutionStatus.RESOLVED, None, (duck,), ())


def test_generic_results_reject_mutable_scalar_subclasses() -> None:
    _, context = refs()

    class MutableInt(int):
        pass

    class MutableStr(str):
        pass

    class MutableBytes(bytes):
        pass

    values = (MutableInt(1), MutableStr("text"), MutableBytes(b"bytes"))
    for value in values:
        value.mutable_state = []
        with pytest.raises(TypeError, match="immutable scalars"):
            InspectionResult(InspectionStatus.COMPLETE, context, value, ())
        with pytest.raises(TypeError, match="immutable scalars"):
            ResolutionResult(ResolutionStatus.RESOLVED, None, (value,), ())


def test_generic_results_reject_inherited_frozen_dataclasses_with_extra_state() -> None:
    _, context = refs()

    @dataclass(frozen=True)
    class FrozenDictBase:
        value: int

    class MutableDictChild(FrozenDictBase):
        def __init__(self, value: int) -> None:
            super().__init__(value)
            self.mutable_state = []

    @dataclass(frozen=True, slots=True)
    class FrozenSlotsBase:
        value: int

    class MutableSlotsChild(FrozenSlotsBase):
        __slots__ = ("mutable_state",)

        def __init__(self, value: int) -> None:
            super().__init__(value)
            object.__setattr__(self, "mutable_state", [])

    for value in (MutableDictChild(1), MutableSlotsChild(2)):
        with pytest.raises(TypeError, match="directly declared as a dataclass"):
            InspectionResult(InspectionStatus.COMPLETE, context, value, ())
        value.mutable_state.append("visible mutation")
        with pytest.raises(TypeError, match="directly declared as a dataclass"):
            ResolutionResult(ResolutionStatus.RESOLVED, None, (value,), ())


def test_generic_results_reject_undeclared_state_on_direct_frozen_dataclasses() -> None:
    _, context = refs()

    @dataclass(frozen=True)
    class DictPayload:
        value: int

    @dataclass(frozen=True)
    class SlotPayload:
        __slots__ = ("value", "mutable_state")

        value: int

    @dataclass(frozen=True)
    class MutableFieldPayload:
        values: list[int]

    dict_payload = DictPayload(1)
    object.__setattr__(dict_payload, "mutable_state", [])
    slot_payload = SlotPayload(2)
    object.__setattr__(slot_payload, "mutable_state", [])
    mutable_values = [3]

    with pytest.raises(TypeError, match="undeclared instance state"):
        InspectionResult(InspectionStatus.COMPLETE, context, dict_payload, ())
    with pytest.raises(TypeError, match="undeclared slots"):
        ResolutionResult(ResolutionStatus.RESOLVED, None, (slot_payload,), ())
    with pytest.raises(TypeError, match="deeply immutable"):
        InspectionResult(
            InspectionStatus.COMPLETE,
            context,
            MutableFieldPayload(mutable_values),
            (),
        )
    mutable_values.append(4)
    assert mutable_values == [3, 4]


def test_generic_results_reject_custom_attribute_access_concealment() -> None:
    _, context = refs()

    @dataclass(frozen=True)
    class HiddenExtraPayload:
        value: int

        def __getattribute__(self, name: str):
            if name == "__dict__":
                raw_state = object.__getattribute__(self, "__dict__")
                return {"value": raw_state["value"]}
            return object.__getattribute__(self, name)

    @dataclass(frozen=True)
    class ConcealingBase:
        values: list[int]

        def __getattribute__(self, name: str):
            if name == "values":
                return tuple(object.__getattribute__(self, name))
            return object.__getattribute__(self, name)

    @dataclass(frozen=True)
    class ConcealingDerived(ConcealingBase):
        label: str

    @dataclass(frozen=True, slots=True)
    class FallbackPayload:
        value: int

        def __getattr__(self, name: str):
            return (name,)

    hidden_extra = HiddenExtraPayload(1)
    object.__setattr__(hidden_extra, "mutable_state", [])
    hidden_values = [2]
    hidden_field = ConcealingDerived(hidden_values, "derived")

    assert "mutable_state" not in hidden_extra.__dict__
    assert hidden_field.values == (2,)
    assert object.__getattribute__(hidden_field, "values") is hidden_values

    for value in (hidden_extra, hidden_field, FallbackPayload(3)):
        with pytest.raises(TypeError, match="custom attribute access"):
            InspectionResult(InspectionStatus.COMPLETE, context, value, ())
        with pytest.raises(TypeError, match="custom attribute access"):
            ResolutionResult(ResolutionStatus.RESOLVED, None, (value,), ())

    hidden_values.append(4)
    object.__getattribute__(hidden_extra, "mutable_state").append("raw mutation")
    assert object.__getattribute__(hidden_field, "values") == [2, 4]
    assert object.__getattribute__(hidden_extra, "mutable_state") == ["raw mutation"]


def test_generic_results_reject_filtering_dict_descriptor_with_mutable_state() -> None:
    _, context = refs()

    @dataclass(frozen=True)
    class FilteringDictPayload:
        value: int

        @property
        def __dict__(self):
            return {"value": object.__getattribute__(self, "value")}

    payload = FilteringDictPayload(1)
    object.__setattr__(payload, "mutable_state", [])

    assert object.__getattribute__(payload, "__dict__") == {"value": 1}
    assert object.__getattribute__(payload, "mutable_state") == []
    for factory in (
        lambda: InspectionResult(InspectionStatus.COMPLETE, context, payload, ()),
        lambda: ResolutionResult(ResolutionStatus.RESOLVED, None, (payload,), ()),
    ):
        with pytest.raises(TypeError, match="__dict__ storage descriptor"):
            factory()


def test_generic_results_ignore_mutated_slots_metadata_and_find_real_storage() -> None:
    _, context = refs()

    class SlotBase:
        __slots__ = ("mutable_state",)

    @dataclass(frozen=True, slots=True)
    class SlotPayload(SlotBase):
        value: int

    class SlotEnum(Enum):
        __slots__ = ("mutable_state",)

        ITEM = 1

    payload = SlotPayload(2)
    object.__setattr__(payload, "mutable_state", [])
    object.__setattr__(SlotEnum.ITEM, "mutable_state", [])
    SlotBase.__slots__ = ()
    SlotEnum.__slots__ = ()

    for value in (payload, SlotEnum.ITEM):
        with pytest.raises(TypeError, match="undeclared member storage"):
            InspectionResult(InspectionStatus.COMPLETE, context, value, ())
        with pytest.raises(TypeError, match="undeclared member storage"):
            ResolutionResult(ResolutionStatus.RESOLVED, None, (value,), ())
        object.__getattribute__(value, "mutable_state").append("live mutation")
        assert object.__getattribute__(value, "mutable_state") == ["live mutation"]


@pytest.mark.parametrize("descriptor_action", ["delete", "replace"])
def test_generic_results_reject_concealed_removed_dataclass_member_descriptor(
    descriptor_action: str,
) -> None:
    _, context = refs()

    class SlotBase:
        __slots__ = ("mutable_state",)

    @dataclass(frozen=True, slots=True)
    class SlotPayload(SlotBase):
        value: int

    payload = SlotPayload(3)
    descriptor = type.__getattribute__(SlotBase, "__dict__")["mutable_state"]
    assert type(descriptor) is MemberDescriptorType
    MemberDescriptorType.__set__(descriptor, payload, [])
    SlotBase.__slots__ = ()
    if descriptor_action == "delete":
        del SlotBase.mutable_state
    else:
        SlotBase.mutable_state = property(lambda self: ())

    assert MemberDescriptorType.__get__(descriptor, payload, SlotPayload) == []
    with pytest.raises(TypeError, match="member storage layout"):
        InspectionResult(InspectionStatus.COMPLETE, context, payload, ())
    with pytest.raises(TypeError, match="member storage layout"):
        ResolutionResult(ResolutionStatus.RESOLVED, None, (payload,), ())


@pytest.mark.parametrize("descriptor_action", ["delete", "replace"])
def test_generic_results_reject_concealed_removed_enum_member_descriptor(
    descriptor_action: str,
) -> None:
    _, context = refs()

    class SlotEnum(Enum):
        __slots__ = ("mutable_state",)

        ITEM = 1

    descriptor = type.__getattribute__(SlotEnum, "__dict__")["mutable_state"]
    assert type(descriptor) is MemberDescriptorType
    MemberDescriptorType.__set__(descriptor, SlotEnum.ITEM, [])
    SlotEnum.__slots__ = ()
    if descriptor_action == "delete":
        del SlotEnum.mutable_state
    else:
        SlotEnum.mutable_state = property(lambda self: ())

    assert MemberDescriptorType.__get__(descriptor, SlotEnum.ITEM, SlotEnum) == []
    with pytest.raises(TypeError, match="member storage layout"):
        InspectionResult(InspectionStatus.COMPLETE, context, SlotEnum.ITEM, ())
    with pytest.raises(TypeError, match="member storage layout"):
        ResolutionResult(ResolutionStatus.RESOLVED, None, (SlotEnum.ITEM,), ())


def test_generic_results_inspect_raw_enum_value_behind_custom_access() -> None:
    _, context = refs()

    class ConcealingEnum(Enum):
        ITEM = [1]

        def __getattribute__(self, name: str):
            if name == "value":
                return tuple(object.__getattribute__(self, "_value_"))
            return object.__getattribute__(self, name)

    assert ConcealingEnum.ITEM.value == (1,)
    with pytest.raises(TypeError, match="exact immutable scalar"):
        InspectionResult(InspectionStatus.COMPLETE, context, ConcealingEnum.ITEM, ())
    with pytest.raises(TypeError, match="exact immutable scalar"):
        ResolutionResult(ResolutionStatus.RESOLVED, None, (ConcealingEnum.ITEM,), ())


def test_generic_results_accept_direct_deeply_frozen_dataclasses() -> None:
    _, context = refs()

    @dataclass(frozen=True, slots=True)
    class FrozenChild:
        value: int

    @dataclass(frozen=True)
    class FrozenPayload:
        name: str
        child: FrozenChild
        values: tuple[int, ...]
        tags: frozenset[str]

    @dataclass(frozen=True, slots=True)
    class FrozenBase:
        value: int

    @dataclass(frozen=True, slots=True)
    class FrozenDerived(FrozenBase):
        label: str

    class ScalarEnum(Enum):
        ITEM = "item"

    class StringEnum(str, Enum):
        ITEM = "item"

    payload = FrozenPayload("valid", FrozenChild(1), (2, 3), frozenset({"a", "b"}))
    derived = FrozenDerived(4, "derived")
    inspection = InspectionResult(InspectionStatus.COMPLETE, context, payload, ())
    resolution = ResolutionResult(
        ResolutionStatus.RESOLVED,
        None,
        (payload, derived, ScalarEnum.ITEM, StringEnum.ITEM),
        (),
    )

    assert inspection.value is payload
    assert resolution.values == (payload, derived, ScalarEnum.ITEM, StringEnum.ITEM)


def test_memory_and_value_records_preserve_missing_segments_and_partial_pieces() -> None:
    data = AddressSpaceId("data")
    complete = MemorySegment(0, 2, b"ab", MemorySegmentStatus.COMPLETE)
    missing = MemorySegment(2, 2, b"", MemorySegmentStatus.UNAVAILABLE)
    block = MemoryBlock(HsxAddress(data, 0), 4, [complete, missing])
    assert block.segments == (complete, missing)
    with pytest.raises(ValueError, match="gap-explicit"):
        MemoryBlock(HsxAddress(data, 0), 5, (complete, replace(missing, offset=3, requested_length=2)))
    available_piece = ValuePiece(0, 8, 0, b"\x01", ValuePieceStatus.AVAILABLE)
    unavailable_piece = ValuePiece(8, 8, 0, None, ValuePieceStatus.UNAVAILABLE, "not captured")
    evaluated = EvaluatedValue(
        "x", "x", "u16", "<partial>", None, 16, ValueAvailability.PARTIAL,
        (available_piece, unavailable_piece),
    )
    expression = ExpressionValue(
        ExpressionKind.VARIABLE, "x", "<partial>", None, 16, ValueAvailability.PARTIAL,
        (available_piece, unavailable_piece),
    )
    assert evaluated.raw_bytes is None and expression.pieces == evaluated.pieces
    with pytest.raises(ValueError, match="only a variable"):
        replace(expression, expression_kind=ExpressionKind.REGISTER)


def test_partial_pieces_require_ordered_exact_destination_bit_coverage() -> None:
    available_low = ValuePiece(0, 4, 0, b"\x01", ValuePieceStatus.AVAILABLE)
    unavailable_high = ValuePiece(8, 8, 0, None, ValuePieceStatus.UNAVAILABLE, "not captured")
    with pytest.raises(ValueError, match="cover every bit"):
        EvaluatedValue(
            "x", "x", "u16", "<partial>", None, 16, ValueAvailability.PARTIAL,
            (available_low, unavailable_high),
        )

    overlapping = ValuePiece(3, 5, 0, None, ValuePieceStatus.UNAVAILABLE, "not captured")
    with pytest.raises(ValueError, match="overlap"):
        EvaluatedValue(
            "x", "x", "u8", "<partial>", None, 8, ValueAvailability.PARTIAL,
            (available_low, overlapping),
        )

    out_of_range = ValuePiece(4, 5, 0, None, ValuePieceStatus.UNAVAILABLE, "not captured")
    with pytest.raises(ValueError, match="exceeds"):
        EvaluatedValue(
            "x", "x", "u8", "<partial>", None, 8, ValueAvailability.PARTIAL,
            (available_low, out_of_range),
        )

    trailing_gap = ValuePiece(4, 3, 0, None, ValuePieceStatus.UNAVAILABLE, "not captured")
    with pytest.raises(ValueError, match="cover every bit"):
        EvaluatedValue(
            "x", "x", "u8", "<partial>", None, 8, ValueAvailability.PARTIAL,
            (available_low, trailing_gap),
        )

    with pytest.raises(ValueError, match="ordered"):
        EvaluatedValue(
            "x", "x", "u8", "<partial>", None, 8, ValueAvailability.PARTIAL,
            (
                ValuePiece(4, 4, 0, None, ValuePieceStatus.UNAVAILABLE, "not captured"),
                available_low,
            ),
        )


def test_memory_inspection_status_matches_segment_evidence_bidirectionally() -> None:
    _, context = refs()
    data = AddressSpaceId("data")
    diagnostic = Diagnostic("memory_unavailable", "some bytes were not captured")
    unrelated = Diagnostic("note", "unrelated diagnostic")
    complete = MemoryBlock(
        HsxAddress(data, 0),
        4,
        (MemorySegment(0, 4, b"abcd", MemorySegmentStatus.COMPLETE),),
    )
    mixed = MemoryBlock(
        HsxAddress(data, 0),
        4,
        (
            MemorySegment(0, 2, b"ab", MemorySegmentStatus.COMPLETE),
            MemorySegment(2, 2, b"", MemorySegmentStatus.UNAVAILABLE),
        ),
    )
    unavailable = MemoryBlock(
        HsxAddress(data, 0),
        4,
        (MemorySegment(0, 4, b"", MemorySegmentStatus.UNAVAILABLE),),
    )

    assert InspectionResult(InspectionStatus.COMPLETE, context, complete, ()).value is complete
    assert InspectionResult(InspectionStatus.PARTIAL, context, mixed, (diagnostic,)).value is mixed
    with pytest.raises(ValueError, match="every segment complete"):
        InspectionResult(InspectionStatus.COMPLETE, context, mixed, ())
    with pytest.raises(ValueError, match="available and unavailable"):
        InspectionResult(InspectionStatus.PARTIAL, context, complete, (unrelated,))
    with pytest.raises(ValueError, match="available and unavailable"):
        InspectionResult(InspectionStatus.PARTIAL, context, unavailable, (diagnostic,))
    with pytest.raises(ValueError, match="no value"):
        InspectionResult(InspectionStatus.UNAVAILABLE, context, unavailable, (diagnostic,))
    assert InspectionResult(InspectionStatus.UNAVAILABLE, context, None, (diagnostic,)).value is None


def test_instruction_and_disassembly_records_enforce_order_and_exact_metadata_bytes() -> None:
    code = AddressSpaceId("code")
    insn = InstructionRecord(
        "i", HsxAddress(code, 0), 2, 0x1234, None, None, InstructionClassification.UNMAPPED
    )
    first = DisassembledInstruction(insn.address, b"\x12\x34", insn, "nop")
    second = DisassembledInstruction(HsxAddress(code, 2), b"\x00\x00", None, None)
    block = DisassemblyBlock(HsxAddress(code, 0), 2, (first, second))
    assert block.instructions == (first, second)
    with pytest.raises(ValueError, match="strictly ascending"):
        DisassemblyBlock(HsxAddress(code, 0), 2, (second, first))
    with pytest.raises(ValueError, match="byte_size"):
        replace(first, encoded=b"\x12")
    with pytest.raises(TypeError, match="InstructionRecord"):
        DisassembledInstruction(
            insn.address,
            b"\x12\x34",
            SimpleNamespace(address=insn.address, byte_size=2),
            "nop",
        )


def test_snapshot_port_is_protocol_only_and_fences_mixed_or_unsupported_context() -> None:
    _, context = refs()

    class Fixture:
        def read_registers(self, context, selection):
            raise NotImplementedError

        def read_memory(self, context, address, byte_length):
            raise NotImplementedError

        def read_disassembly(self, context, address, instruction_count):
            raise NotImplementedError

    assert isinstance(Fixture(), SnapshotReadPort)
    assert require_snapshot_read_set(context, "memory").status is InspectionStatus.COMPLETE
    assert require_snapshot_read_set(context, "stack").status is InspectionStatus.UNAVAILABLE
    with pytest.raises(ValueError, match="frozen"):
        require_snapshot_read_set(context, "live")
    exact = InspectionResult(InspectionStatus.COMPLETE, context, 1, ())
    assert fence_snapshot_result(context, exact) is exact
    other_snapshot = replace(context.epoch.snapshot, inspection_revision=4, snapshot_token="other")
    other_epoch = replace(context.epoch, snapshot=other_snapshot)
    other_context = replace(context, epoch=other_epoch)
    stale = fence_snapshot_result(context, InspectionResult(InspectionStatus.COMPLETE, other_context, 1, ()))
    assert stale.status is InspectionStatus.STALE
    assert stale.context == context and stale.value is None
    assert stale.diagnostics[0].code == "snapshot_context_stale"

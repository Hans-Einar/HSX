"""Exact immutable RF-004 identity, bundle, binding, and epoch values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re
import unicodedata
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from .addresses import ArchitectureDescriptor

from .contracts import EvidenceGrade, GenerationStamp, StopEpoch
from .results import (
    ContextBindingResult,
    ContextBindingStatus,
    Diagnostic,
    ResolutionResult,
    ResolutionStatus,
    _register_contract_enums,
)


_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_UINT64_MAX = (1 << 64) - 1
_READ_SETS = frozenset({"registers", "memory", "disassembly", "stack", "resources"})


def _require_nonempty(value: str, field_name: str, *, controls: bool = False) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    if controls and _CONTROL.search(value):
        raise ValueError(f"{field_name} contains a forbidden control character")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field_name} must contain Unicode scalar values") from exc


def _require_int(value: int, field_name: str, *, minimum: int = 0) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")


def _require_hex64(value: str, field_name: str) -> None:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be exactly 64 lowercase hexadecimal characters")


def _tuple(value: object, field_name: str) -> tuple:
    if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
        raise TypeError(f"{field_name} must be a tuple or list")
    return tuple(value)


def _canonical_string(value: str, field_name: str = "canonical string") -> str:
    _require_nonempty(value, field_name, controls=True)
    return unicodedata.normalize("NFC", value)


def _canonical_json_string(value: str) -> str:
    value = _canonical_string(value)
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _canonical_json_text(value: object) -> str:
    if isinstance(value, CanonicalUInt64):
        return _canonical_json_string(value.canonical())
    if isinstance(value, str):
        return _canonical_json_string(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise TypeError("canonical object keys must be strings")
            key = _canonical_string(raw_key, "canonical object key")
            if key in normalized:
                raise ValueError("canonical object keys collide after NFC normalization")
            normalized[key] = item
        return "{" + ",".join(
            f"{_canonical_json_string(key)}:{_canonical_json_text(normalized[key])}"
            for key in sorted(normalized)
        ) + "}"
    if isinstance(value, (tuple, list)):
        return "[" + ",".join(_canonical_json_text(item) for item in value) + "]"
    # Identity payload integers must already be schema-typed CanonicalUInt64 or emitted as
    # minimal decimal strings by their projection.  Null, floats, and numeric JSON tokens are
    # deliberately not accepted.
    raise TypeError(f"unsupported canonical identity value: {type(value).__name__}")


def canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    """Serialize one already schema-validated identity payload canonically."""

    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")
    return _canonical_json_text(payload).encode("utf-8")


def canonical_structured_digest(domain_tag: str, payload: Mapping[str, object]) -> str:
    """Return the frozen domain-separated SHA-256 digest."""

    tag = _canonical_string(domain_tag, "domain_tag").encode("utf-8")
    return hashlib.sha256(tag + b"\x00" + canonical_json_bytes(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class CanonicalUInt64:
    value: int

    def __post_init__(self) -> None:
        _require_int(self.value, "value")
        if self.value > _UINT64_MAX:
            raise ValueError("value must fit uint64")

    def canonical(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ExecutiveInstanceRef:
    value: str

    def __post_init__(self) -> None:
        _require_nonempty(self.value, "value", controls=True)


@dataclass(frozen=True, slots=True)
class TargetRef:
    canonical_ref: str
    executive: ExecutiveInstanceRef
    target_id: str
    target_generation: int
    display_pid: int
    pid_generation: int

    def __post_init__(self) -> None:
        _require_nonempty(self.canonical_ref, "canonical_ref", controls=True)
        if not isinstance(self.executive, ExecutiveInstanceRef):
            raise TypeError("executive must be ExecutiveInstanceRef")
        _require_nonempty(self.target_id, "target_id", controls=True)
        _require_int(self.target_generation, "target_generation", minimum=1)
        _require_int(self.display_pid, "display_pid")
        _require_int(self.pid_generation, "pid_generation", minimum=1)


@dataclass(frozen=True, slots=True)
class ContentDigest:
    algorithm: str
    value: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ValueError("algorithm must be 'sha256'")
        _require_hex64(self.value, "value")

    def canonical_payload(self) -> dict[str, str]:
        return {"algorithm": self.algorithm, "value": self.value}


@dataclass(frozen=True, slots=True)
class StructuredDigest:
    algorithm: str
    value: str

    def __post_init__(self) -> None:
        if self.algorithm != "sha256":
            raise ValueError("algorithm must be 'sha256'")
        _require_hex64(self.value, "value")

    def canonical_payload(self) -> dict[str, str]:
        return {"algorithm": self.algorithm, "value": self.value}


@dataclass(frozen=True, slots=True)
class DescriptorDigestRef:
    ref: str
    digest: str

    def __post_init__(self) -> None:
        _require_nonempty(self.ref, "ref", controls=True)
        _require_hex64(self.digest, "digest")

    def canonical_payload(self) -> dict[str, str]:
        return {"ref": self.ref, "digest": self.digest}


@dataclass(frozen=True, slots=True)
class ComponentDigestRef:
    schema: str
    canonical_component_digest: str

    def __post_init__(self) -> None:
        _require_nonempty(self.schema, "schema", controls=True)
        _require_hex64(self.canonical_component_digest, "canonical_component_digest")

    def canonical_payload(self) -> dict[str, str]:
        return {
            "schema": self.schema,
            "canonical_component_digest": self.canonical_component_digest,
        }


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    ref_schema: str
    media_type: str
    container_version: CanonicalUInt64
    byte_length: CanonicalUInt64
    content_digest: ContentDigest

    def __post_init__(self) -> None:
        if self.ref_schema != "hsx.artifact-ref/1":
            raise ValueError("ref_schema must be 'hsx.artifact-ref/1'")
        if self.media_type != "application/vnd.hsx.hxe":
            raise ValueError("media_type must be 'application/vnd.hsx.hxe'")
        if not isinstance(self.container_version, CanonicalUInt64):
            raise TypeError("container_version must be CanonicalUInt64")
        if self.container_version.value < 1:
            raise ValueError("container_version must be >= 1")
        if not isinstance(self.byte_length, CanonicalUInt64):
            raise TypeError("byte_length must be CanonicalUInt64")
        if not isinstance(self.content_digest, ContentDigest):
            raise TypeError("content_digest must be ContentDigest")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "ref_schema": self.ref_schema,
            "media_type": self.media_type,
            "container_version": self.container_version.canonical(),
            "byte_length": self.byte_length.canonical(),
            "content_digest": self.content_digest.canonical_payload(),
        }


@dataclass(frozen=True, slots=True)
class LoadedImageRef:
    ref_schema: str
    executive_instance_ref: ExecutiveInstanceRef
    target_ref: TargetRef
    loaded_image_id: str
    image_generation: CanonicalUInt64
    artifact_ref: ArtifactRef

    def __post_init__(self) -> None:
        if self.ref_schema != "hsx.loaded-image-ref/1":
            raise ValueError("ref_schema must be 'hsx.loaded-image-ref/1'")
        if not isinstance(self.executive_instance_ref, ExecutiveInstanceRef):
            raise TypeError("executive_instance_ref must be ExecutiveInstanceRef")
        if not isinstance(self.target_ref, TargetRef):
            raise TypeError("target_ref must be TargetRef")
        if self.executive_instance_ref != self.target_ref.executive:
            raise ValueError("executive_instance_ref must equal target_ref.executive")
        _require_nonempty(self.loaded_image_id, "loaded_image_id", controls=True)
        if not isinstance(self.image_generation, CanonicalUInt64):
            raise TypeError("image_generation must be CanonicalUInt64")
        if self.image_generation.value < 1:
            raise ValueError("image_generation must be >= 1")
        if not isinstance(self.artifact_ref, ArtifactRef):
            raise TypeError("artifact_ref must be ArtifactRef")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "ref_schema": self.ref_schema,
            "executive_instance_ref": self.executive_instance_ref.value,
            "target_ref": self.target_ref.canonical_ref,
            "loaded_image_id": self.loaded_image_id,
            "image_generation": self.image_generation.canonical(),
            "artifact_ref": self.artifact_ref.canonical_payload(),
        }


@dataclass(frozen=True, slots=True)
class ArchitectureDescriptorRef:
    ref: str
    digest: str

    def __post_init__(self) -> None:
        _require_nonempty(self.ref, "ref", controls=True)
        _require_hex64(self.digest, "digest")


@dataclass(frozen=True, slots=True)
class AbiDescriptorRef:
    ref: str
    digest: str

    def __post_init__(self) -> None:
        _require_nonempty(self.ref, "ref", controls=True)
        _require_hex64(self.digest, "digest")


@dataclass(frozen=True, slots=True)
class RecipeSchemaRef:
    schema: str
    digest: str

    def __post_init__(self) -> None:
        if self.schema not in {"hsx.unwind-recipe/1", "hsx.location-recipe/1"}:
            raise ValueError("schema must be a frozen unwind/location recipe schema")
        _require_hex64(self.digest, "digest")


@dataclass(frozen=True, slots=True)
class ImageDebugBundleIdentityPayload:
    bundle_schema: str
    artifact_ref: ArtifactRef
    architecture_descriptor: DescriptorDigestRef
    abi_descriptor: DescriptorDigestRef
    symbol_model: ComponentDigestRef
    unwind_recipe: ComponentDigestRef
    location_recipe: ComponentDigestRef
    source_identity_manifest_ref: StructuredDigest
    required_debug_capabilities: tuple[str, ...]
    interpretation_schema_versions: tuple[tuple[str, CanonicalUInt64], ...]

    def __post_init__(self) -> None:
        if self.bundle_schema != "hsx.image-debug-bundle/1":
            raise ValueError("bundle_schema must be 'hsx.image-debug-bundle/1'")
        if not isinstance(self.artifact_ref, ArtifactRef):
            raise TypeError("artifact_ref must be ArtifactRef")
        if not isinstance(self.architecture_descriptor, DescriptorDigestRef):
            raise TypeError("architecture_descriptor must be DescriptorDigestRef")
        if not isinstance(self.abi_descriptor, DescriptorDigestRef):
            raise TypeError("abi_descriptor must be DescriptorDigestRef")
        expected_components = (
            (self.symbol_model, "hsx.debug-component.symbol-model/1", "symbol_model"),
            (self.unwind_recipe, "hsx.unwind-recipe/1", "unwind_recipe"),
            (self.location_recipe, "hsx.location-recipe/1", "location_recipe"),
        )
        for value, schema, field_name in expected_components:
            if not isinstance(value, ComponentDigestRef):
                raise TypeError(f"{field_name} must be ComponentDigestRef")
            if value.schema != schema:
                raise ValueError(f"{field_name} must use schema {schema!r}")
        if not isinstance(self.source_identity_manifest_ref, StructuredDigest):
            raise TypeError("source_identity_manifest_ref must be StructuredDigest")
        capabilities = _tuple(self.required_debug_capabilities, "required_debug_capabilities")
        for capability in capabilities:
            _require_nonempty(capability, "required_debug_capability", controls=True)
        normalized_capabilities = [unicodedata.normalize("NFC", item) for item in capabilities]
        if len(set(normalized_capabilities)) != len(normalized_capabilities):
            raise ValueError("required_debug_capabilities must be NFC-unique")
        capabilities = tuple(sorted(capabilities, key=lambda item: unicodedata.normalize("NFC", item).encode("utf-8")))
        versions = _tuple(self.interpretation_schema_versions, "interpretation_schema_versions")
        normalized_keys: set[str] = set()
        checked_versions: list[tuple[str, CanonicalUInt64]] = []
        for entry in versions:
            if not isinstance(entry, (tuple, list)) or len(entry) != 2:
                raise TypeError("interpretation_schema_versions entries must be pairs")
            key, version = entry
            _require_nonempty(key, "interpretation schema", controls=True)
            normalized = unicodedata.normalize("NFC", key)
            if normalized in normalized_keys:
                raise ValueError("interpretation schema keys must be NFC-unique")
            normalized_keys.add(normalized)
            if not isinstance(version, CanonicalUInt64):
                raise TypeError("interpretation schema versions must be CanonicalUInt64")
            checked_versions.append((key, version))
        checked_versions.sort(key=lambda entry: unicodedata.normalize("NFC", entry[0]))
        object.__setattr__(self, "required_debug_capabilities", capabilities)
        object.__setattr__(self, "interpretation_schema_versions", tuple(checked_versions))

    def canonical_payload(self) -> dict[str, object]:
        return {
            "bundle_schema": self.bundle_schema,
            "artifact_ref": self.artifact_ref.canonical_payload(),
            "architecture_descriptor": self.architecture_descriptor.canonical_payload(),
            "abi_descriptor": self.abi_descriptor.canonical_payload(),
            "symbol_model": self.symbol_model.canonical_payload(),
            "unwind_recipe": self.unwind_recipe.canonical_payload(),
            "location_recipe": self.location_recipe.canonical_payload(),
            "source_identity_manifest_ref": self.source_identity_manifest_ref.canonical_payload(),
            "required_debug_capabilities": self.required_debug_capabilities,
            "interpretation_schema_versions": {
                key: version.canonical()
                for key, version in self.interpretation_schema_versions
            },
        }

    def canonical_digest(self) -> str:
        return canonical_structured_digest(self.bundle_schema, self.canonical_payload())


@dataclass(frozen=True, slots=True)
class ImageDebugBundleRef:
    ref_schema: str
    artifact_ref: ArtifactRef
    digest_algorithm: str
    bundle_digest: str

    def __post_init__(self) -> None:
        if self.ref_schema != "hsx.image-debug-bundle-ref/1":
            raise ValueError("ref_schema must be 'hsx.image-debug-bundle-ref/1'")
        if not isinstance(self.artifact_ref, ArtifactRef):
            raise TypeError("artifact_ref must be ArtifactRef")
        if self.digest_algorithm != "sha256":
            raise ValueError("digest_algorithm must be 'sha256'")
        _require_hex64(self.bundle_digest, "bundle_digest")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "ref_schema": self.ref_schema,
            "artifact_ref": self.artifact_ref.canonical_payload(),
            "digest_algorithm": self.digest_algorithm,
            "bundle_digest": self.bundle_digest,
        }


@dataclass(frozen=True, slots=True)
class ImageDebugBindingPayload:
    binding_schema: str
    loaded_image_ref: LoadedImageRef
    image_debug_bundle_ref: ImageDebugBundleRef
    accepted_architecture_descriptor_ref: str
    accepted_abi_descriptor_ref: str
    accepted_image_debug_capability_profile: str

    def __post_init__(self) -> None:
        if self.binding_schema != "hsx.image-debug-binding/1":
            raise ValueError("binding_schema must be 'hsx.image-debug-binding/1'")
        if not isinstance(self.loaded_image_ref, LoadedImageRef):
            raise TypeError("loaded_image_ref must be LoadedImageRef")
        if not isinstance(self.image_debug_bundle_ref, ImageDebugBundleRef):
            raise TypeError("image_debug_bundle_ref must be ImageDebugBundleRef")
        _require_nonempty(
            self.accepted_architecture_descriptor_ref,
            "accepted_architecture_descriptor_ref",
            controls=True,
        )
        _require_nonempty(self.accepted_abi_descriptor_ref, "accepted_abi_descriptor_ref", controls=True)
        _require_nonempty(
            self.accepted_image_debug_capability_profile,
            "accepted_image_debug_capability_profile",
            controls=True,
        )

    def canonical_payload(self) -> dict[str, object]:
        return {
            "binding_schema": self.binding_schema,
            "loaded_image_ref": self.loaded_image_ref.canonical_payload(),
            "image_debug_bundle_ref": self.image_debug_bundle_ref.canonical_payload(),
            "accepted_architecture_descriptor_ref": self.accepted_architecture_descriptor_ref,
            "accepted_abi_descriptor_ref": self.accepted_abi_descriptor_ref,
            "accepted_image_debug_capability_profile": self.accepted_image_debug_capability_profile,
        }

    def canonical_digest(self) -> str:
        return canonical_structured_digest(self.binding_schema, self.canonical_payload())


@dataclass(frozen=True, slots=True)
class ImageDebugBinding:
    payload: ImageDebugBindingPayload
    binding_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, ImageDebugBindingPayload):
            raise TypeError("payload must be ImageDebugBindingPayload")
        _require_hex64(self.binding_digest, "binding_digest")


def validate_source_logical_id(logical_id: str) -> None:
    _require_nonempty(logical_id, "logical_id", controls=True)
    if unicodedata.normalize("NFC", logical_id) != logical_id:
        raise ValueError("logical_id must be Unicode NFC")
    if "\\" in logical_id:
        raise ValueError("logical_id must use '/' separators")
    if logical_id.startswith("/") or logical_id.startswith("//"):
        raise ValueError("logical_id must be artifact-relative")
    if re.match(r"^[A-Za-z]:", logical_id):
        raise ValueError("logical_id must not be drive-qualified")
    parts = logical_id.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("logical_id contains an empty, dot, or dot-dot segment")


@dataclass(frozen=True, slots=True)
class SourceRef:
    image_debug_bundle_ref: ImageDebugBundleRef
    logical_id: str
    content_digest: ContentDigest
    byte_length: CanonicalUInt64

    def __post_init__(self) -> None:
        if not isinstance(self.image_debug_bundle_ref, ImageDebugBundleRef):
            raise TypeError("image_debug_bundle_ref must be ImageDebugBundleRef")
        validate_source_logical_id(self.logical_id)
        if not isinstance(self.content_digest, ContentDigest):
            raise TypeError("content_digest must be ContentDigest")
        if not isinstance(self.byte_length, CanonicalUInt64):
            raise TypeError("byte_length must be CanonicalUInt64")

    def canonical_payload(self) -> dict[str, object]:
        return {
            "image_debug_bundle_ref": self.image_debug_bundle_ref.canonical_payload(),
            "logical_id": self.logical_id,
            "content_digest": self.content_digest.canonical_payload(),
            "byte_length": self.byte_length.canonical(),
        }


@dataclass(frozen=True, slots=True)
class StopEpochId:
    value: str

    def __post_init__(self) -> None:
        _require_nonempty(self.value, "value", controls=True)


@dataclass(frozen=True, slots=True)
class StopToken:
    target: TargetRef
    image: LoadedImageRef
    opaque_token: str
    transition_revision: int

    def __post_init__(self) -> None:
        if not isinstance(self.target, TargetRef):
            raise TypeError("target must be TargetRef")
        if not isinstance(self.image, LoadedImageRef):
            raise TypeError("image must be LoadedImageRef")
        if self.image.target_ref != self.target:
            raise ValueError("image target must equal target")
        _require_nonempty(self.opaque_token, "opaque_token", controls=True)
        _require_int(self.transition_revision, "transition_revision")


class SnapshotStability(str, Enum):
    IMMUTABLE = "immutable"
    REVISION_PINNED = "revision_pinned"
    BEST_EFFORT_LIVE = "best_effort_live"


_register_contract_enums(SnapshotStability)


@dataclass(frozen=True, slots=True)
class InspectionSnapshotRef:
    target: TargetRef
    image: LoadedImageRef
    stop_token: StopToken
    snapshot_token: str
    transition_revision: int
    inspection_revision: int
    supported_read_sets: frozenset[str]
    stability: SnapshotStability
    evidence_grade: EvidenceGrade

    def __post_init__(self) -> None:
        if not isinstance(self.target, TargetRef):
            raise TypeError("target must be TargetRef")
        if not isinstance(self.image, LoadedImageRef):
            raise TypeError("image must be LoadedImageRef")
        if not isinstance(self.stop_token, StopToken):
            raise TypeError("stop_token must be StopToken")
        if self.image.target_ref != self.target:
            raise ValueError("image target must equal target")
        if self.stop_token.target != self.target or self.stop_token.image != self.image:
            raise ValueError("stop_token identities must equal snapshot identities")
        _require_nonempty(self.snapshot_token, "snapshot_token", controls=True)
        _require_int(self.transition_revision, "transition_revision")
        _require_int(self.inspection_revision, "inspection_revision")
        if self.transition_revision != self.stop_token.transition_revision:
            raise ValueError("transition_revision must equal stop_token transition_revision")
        if isinstance(self.supported_read_sets, str) or not isinstance(
            self.supported_read_sets, (set, frozenset, tuple, list)
        ):
            raise TypeError("supported_read_sets must be a collection")
        read_sets = frozenset(self.supported_read_sets)
        if not all(isinstance(item, str) for item in read_sets):
            raise TypeError("supported_read_sets must contain strings")
        unknown = read_sets - _READ_SETS
        if unknown:
            raise ValueError(f"unsupported read set(s): {sorted(unknown)!r}")
        if not isinstance(self.stability, SnapshotStability):
            raise TypeError("stability must be SnapshotStability")
        if not isinstance(self.evidence_grade, EvidenceGrade):
            raise TypeError("evidence_grade must be EvidenceGrade")
        object.__setattr__(self, "supported_read_sets", read_sets)


@dataclass(frozen=True, slots=True)
class EpochBinding:
    stop_epoch_id: StopEpochId
    controller_generation: GenerationStamp
    stop_token: StopToken
    snapshot: InspectionSnapshotRef
    evidence_grade: EvidenceGrade

    def __post_init__(self) -> None:
        if not isinstance(self.stop_epoch_id, StopEpochId):
            raise TypeError("stop_epoch_id must be StopEpochId")
        if not isinstance(self.controller_generation, GenerationStamp):
            raise TypeError("controller_generation must be GenerationStamp")
        if not isinstance(self.stop_token, StopToken):
            raise TypeError("stop_token must be StopToken")
        if not isinstance(self.snapshot, InspectionSnapshotRef):
            raise TypeError("snapshot must be InspectionSnapshotRef")
        if not isinstance(self.evidence_grade, EvidenceGrade):
            raise TypeError("evidence_grade must be EvidenceGrade")
        if (
            self.controller_generation.evidence_grade is not self.evidence_grade
            or self.snapshot.evidence_grade is not self.evidence_grade
        ):
            raise ValueError("controller, snapshot, and epoch evidence grades must match")
        if self.evidence_grade is not EvidenceGrade.PORTABLE:
            raise ValueError("a coherent EpochBinding requires PORTABLE evidence")
        if self.snapshot.stability is SnapshotStability.BEST_EFFORT_LIVE:
            raise ValueError("best-effort live evidence cannot form a coherent EpochBinding")
        if self.snapshot.stop_token != self.stop_token:
            raise ValueError("snapshot stop_token must equal stop_token")


@dataclass(frozen=True, slots=True)
class InspectionContext:
    target: TargetRef
    image: LoadedImageRef
    epoch: EpochBinding

    def __post_init__(self) -> None:
        if not isinstance(self.target, TargetRef):
            raise TypeError("target must be TargetRef")
        if not isinstance(self.image, LoadedImageRef):
            raise TypeError("image must be LoadedImageRef")
        if not isinstance(self.epoch, EpochBinding):
            raise TypeError("epoch must be EpochBinding")
        if self.image.target_ref != self.target:
            raise ValueError("image target must equal context target")
        if self.epoch.stop_token.target != self.target:
            raise ValueError("stop token target must equal context target")
        if self.epoch.stop_token.image != self.image:
            raise ValueError("stop token image must equal context image")
        if self.epoch.snapshot.target != self.target or self.epoch.snapshot.image != self.image:
            raise ValueError("snapshot identities must equal context identities")
        generation = self.epoch.controller_generation
        if (
            generation.executive_instance_id != self.target.executive.value
            or generation.target_id != self.target.target_id
            or generation.target_generation != self.target.target_generation
        ):
            raise ValueError("controller generation must equal context target identity")


def _binding_failure(code: str, message: str) -> ResolutionResult[ImageDebugBinding]:
    return ResolutionResult(
        status=ResolutionStatus.ARTIFACT_MISMATCH,
        binding=None,
        values=(),
        diagnostics=(Diagnostic(code, message, component="debug_binding"),),
    )


class DebugBindingValidator:
    """Shared exhaustive first-match validator for portable debug bindings."""

    @staticmethod
    def validate(
        binding: ImageDebugBinding,
        bundle_identity: ImageDebugBundleIdentityPayload,
        architecture: ArchitectureDescriptor,
        abi: AbiDescriptorRef,
    ) -> ResolutionResult[ImageDebugBinding]:
        if not isinstance(binding, ImageDebugBinding):
            raise TypeError("binding must be ImageDebugBinding")
        if not isinstance(bundle_identity, ImageDebugBundleIdentityPayload):
            raise TypeError("bundle_identity must be ImageDebugBundleIdentityPayload")
        if not isinstance(abi, AbiDescriptorRef):
            raise TypeError("abi must be AbiDescriptorRef")
        from .addresses import ArchitectureDescriptor

        if not isinstance(architecture, ArchitectureDescriptor):
            raise TypeError("architecture must be ArchitectureDescriptor")
        architecture_ref = architecture.ref

        payload = binding.payload
        bundle_ref = payload.image_debug_bundle_ref
        if payload.loaded_image_ref.artifact_ref != bundle_ref.artifact_ref:
            return _binding_failure("artifact_ref_mismatch", "loaded image and bundle artifacts differ")
        if bundle_identity.artifact_ref != bundle_ref.artifact_ref:
            return _binding_failure("artifact_ref_mismatch", "bundle identity and bundle ref artifacts differ")
        if bundle_identity.canonical_digest() != bundle_ref.bundle_digest:
            return _binding_failure("bundle_digest_mismatch", "bundle identity digest differs")
        if payload.canonical_digest() != binding.binding_digest:
            return _binding_failure("binding_digest_mismatch", "binding payload digest differs")
        if payload.accepted_architecture_descriptor_ref != architecture_ref.ref:
            return _binding_failure(
                "binding_architecture_ref_mismatch", "binding architecture ref differs"
            )
        if (
            bundle_identity.architecture_descriptor.ref != architecture_ref.ref
            or bundle_identity.architecture_descriptor.digest != architecture_ref.digest
        ):
            return _binding_failure("bundle_architecture_mismatch", "bundle architecture differs")
        if payload.accepted_abi_descriptor_ref != abi.ref:
            return _binding_failure("binding_abi_ref_mismatch", "binding ABI ref differs")
        if (
            bundle_identity.abi_descriptor.ref != abi.ref
            or bundle_identity.abi_descriptor.digest != abi.digest
        ):
            return _binding_failure("bundle_abi_mismatch", "bundle ABI differs")
        return ResolutionResult(
            status=ResolutionStatus.RESOLVED,
            binding=binding,
            values=(binding,),
            diagnostics=(),
        )


def _context_failure(status: ContextBindingStatus, code: str, message: str) -> ContextBindingResult:
    return ContextBindingResult(status, None, (Diagnostic(code, message, component="epoch"),))


class ControllerEpochAdapter:
    """Read-only typed seam from the signed RF-002 StopEpoch record."""

    @staticmethod
    def bind(
        controller_epoch: StopEpoch,
        target: TargetRef,
        image: LoadedImageRef,
    ) -> ContextBindingResult:
        if not isinstance(controller_epoch, StopEpoch):
            raise TypeError("controller_epoch must be contracts.StopEpoch")
        if not isinstance(target, TargetRef):
            raise TypeError("target must be TargetRef")
        if not isinstance(image, LoadedImageRef):
            raise TypeError("image must be LoadedImageRef")

        stop_token = controller_epoch.stop_token
        snapshot = controller_epoch.snapshot_ref
        if not isinstance(stop_token, StopToken) or not isinstance(snapshot, InspectionSnapshotRef):
            return _context_failure(
                ContextBindingStatus.UNAVAILABLE,
                "coherent_snapshot_unavailable",
                "typed stop and snapshot evidence is unavailable",
            )
        if (
            controller_epoch.evidence_grade is not EvidenceGrade.PORTABLE
            or snapshot.evidence_grade is not EvidenceGrade.PORTABLE
            or controller_epoch.evidence_grade is not snapshot.evidence_grade
            or snapshot.stability is SnapshotStability.BEST_EFFORT_LIVE
        ):
            return _context_failure(
                ContextBindingStatus.UNAVAILABLE,
                "portable_snapshot_evidence_unavailable",
                "portable coherent snapshot evidence is unavailable",
            )
        generation = controller_epoch.generation
        if (
            generation.executive_instance_id != target.executive.value
            or generation.target_id != target.target_id
            or generation.target_generation != target.target_generation
        ):
            return _context_failure(
                ContextBindingStatus.STALE,
                "controller_epoch_target_stale",
                "controller generation no longer names the target",
            )
        refs = (image.target_ref, stop_token.target, snapshot.target)
        if any(value != target for value in refs):
            return _context_failure(
                ContextBindingStatus.STALE,
                "epoch_target_stale",
                "epoch evidence names another target",
            )
        images = (image, stop_token.image, snapshot.image)
        if any(
            value.loaded_image_id != image.loaded_image_id
            or value.image_generation != image.image_generation
            for value in images[1:]
        ):
            return _context_failure(
                ContextBindingStatus.STALE,
                "loaded_image_stale",
                "epoch evidence names another loaded image generation",
            )
        if any(value.artifact_ref != image.artifact_ref for value in images[1:]):
            return _context_failure(
                ContextBindingStatus.ARTIFACT_MISMATCH,
                "epoch_artifact_mismatch",
                "epoch evidence names another artifact",
            )
        if (
            snapshot.stop_token != stop_token
            or snapshot.transition_revision != stop_token.transition_revision
        ):
            return _context_failure(
                ContextBindingStatus.STALE,
                "stop_token_stale",
                "snapshot stop token or transition revision differs",
            )
        epoch = EpochBinding(
            stop_epoch_id=StopEpochId(controller_epoch.epoch_id),
            controller_generation=generation,
            stop_token=stop_token,
            snapshot=snapshot,
            evidence_grade=controller_epoch.evidence_grade,
        )
        context = InspectionContext(target=target, image=image, epoch=epoch)
        return ContextBindingResult(ContextBindingStatus.BOUND, context, ())


__all__ = [
    "AbiDescriptorRef",
    "ArchitectureDescriptorRef",
    "ArtifactRef",
    "CanonicalUInt64",
    "ComponentDigestRef",
    "ContentDigest",
    "ControllerEpochAdapter",
    "DebugBindingValidator",
    "DescriptorDigestRef",
    "EpochBinding",
    "ExecutiveInstanceRef",
    "ImageDebugBinding",
    "ImageDebugBindingPayload",
    "ImageDebugBundleIdentityPayload",
    "ImageDebugBundleRef",
    "InspectionContext",
    "InspectionSnapshotRef",
    "LoadedImageRef",
    "RecipeSchemaRef",
    "SnapshotStability",
    "SourceRef",
    "StopEpochId",
    "StopToken",
    "StructuredDigest",
    "TargetRef",
    "canonical_json_bytes",
    "canonical_structured_digest",
    "validate_source_logical_id",
]

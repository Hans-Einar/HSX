from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from hsx_debugger.addresses import (
    AddressSpaceDescriptor,
    AddressSpaceId,
    ArchitectureDescriptor,
    ByteOrder,
    HsxAddress,
    HsxAddressRange,
    Permission,
    WrapPolicy,
)
from hsx_debugger.contracts import EvidenceGrade, GenerationStamp, StopEpoch
from hsx_debugger.identity import (
    AbiDescriptorRef,
    ArchitectureDescriptorRef,
    ArtifactRef,
    CanonicalUInt64,
    ComponentDigestRef,
    ContentDigest,
    ControllerEpochAdapter,
    DebugBindingValidator,
    DescriptorDigestRef,
    EpochBinding,
    ExecutiveInstanceRef,
    ImageDebugBinding,
    ImageDebugBindingPayload,
    ImageDebugBundleIdentityPayload,
    ImageDebugBundleRef,
    InspectionContext,
    InspectionSnapshotRef,
    LoadedImageRef,
    SnapshotStability,
    SourceRef,
    StopEpochId,
    StopToken,
    StructuredDigest,
    TargetRef,
    canonical_json_bytes,
    canonical_structured_digest,
)
from hsx_debugger.results import ContextBindingStatus, ResolutionStatus


ZERO = "0" * 64
SOURCE_DIGEST = "6caa23594d6f57fb795a2e73648f5c8ed9928a5e25798d3bb48545412ca164a0"
SYMBOL_DIGEST = "767ad5f9e1ae49abdc33dfd990e81fc3a5a6b064e23d2e44992dfe20f0d94a73"
BUNDLE_DIGEST = "61bc53ef9bf46d87dd6f434ddb43e9307921751faa37471323ea734f87105007"
BINDING_DIGEST = "b84f9e6618dea2f8c688bc4930a9915c80c1eea1be22b4233375616d272472f2"


def foundation():
    artifact = ArtifactRef(
        "hsx.artifact-ref/1",
        "application/vnd.hsx.hxe",
        CanonicalUInt64(1),
        CanonicalUInt64(0),
        ContentDigest("sha256", ZERO),
    )
    target = TargetRef(
        "target-01", ExecutiveInstanceRef("exec-01"), "opaque-target", 1, 41, 1
    )
    image = LoadedImageRef(
        "hsx.loaded-image-ref/1",
        target.executive,
        target,
        "image-01",
        CanonicalUInt64(1),
        artifact,
    )
    bundle_identity = ImageDebugBundleIdentityPayload(
        "hsx.image-debug-bundle/1",
        artifact,
        DescriptorDigestRef("arch-01", ZERO),
        DescriptorDigestRef("abi-01", ZERO),
        ComponentDigestRef("hsx.debug-component.symbol-model/1", SYMBOL_DIGEST),
        ComponentDigestRef("hsx.unwind-recipe/1", ZERO),
        ComponentDigestRef("hsx.location-recipe/1", ZERO),
        StructuredDigest("sha256", SOURCE_DIGEST),
        (),
        (),
    )
    bundle_ref = ImageDebugBundleRef(
        "hsx.image-debug-bundle-ref/1", artifact, "sha256", BUNDLE_DIGEST
    )
    payload = ImageDebugBindingPayload(
        "hsx.image-debug-binding/1",
        image,
        bundle_ref,
        "arch-01",
        "abi-01",
        "hsx.portable-debug-runtime/1",
    )
    binding = ImageDebugBinding(payload, BINDING_DIGEST)
    code = AddressSpaceId("code")
    data = AddressSpaceId("data")
    descriptor = ArchitectureDescriptor(
        ArchitectureDescriptorRef("arch-01", ZERO),
        CanonicalUInt64(1),
        "hsx-v1-fixed32",
        ByteOrder.LITTLE,
        ByteOrder.BIG,
        32,
        ByteOrder.LITTLE,
        2,
        (
            AddressSpaceDescriptor(
                code,
                "byte",
                8,
                16,
                (HsxAddressRange(HsxAddress(code, 0), 0x10000),),
                ByteOrder.BIG,
                1,
                WrapPolicy.FORBIDDEN,
                frozenset({Permission.READ, Permission.EXECUTE}),
            ),
            AddressSpaceDescriptor(
                data,
                "byte",
                8,
                24,
                (HsxAddressRange(HsxAddress(data, 0), 0x1000000),),
                ByteOrder.LITTLE,
                4,
                WrapPolicy.EXPLICIT,
                frozenset({Permission.READ, Permission.WRITE}),
            ),
        ),
        ("R0", "R1"),
        code,
        data,
        8,
        4,
    )
    abi = AbiDescriptorRef("abi-01", ZERO)
    return artifact, target, image, bundle_identity, bundle_ref, payload, binding, descriptor, abi


def portable_epoch(target: TargetRef, image: LoadedImageRef):
    generation = GenerationStamp(
        executive_instance_id=target.executive.value,
        session_generation=3,
        target_id=target.target_id,
        target_generation=target.target_generation,
        capability_generation=2,
        stream_generation=4,
        display_pid=target.display_pid,
        evidence_grade=EvidenceGrade.PORTABLE,
    )
    token = StopToken(target, image, "stop-7", 7)
    snapshot = InspectionSnapshotRef(
        target,
        image,
        token,
        "snapshot-9",
        7,
        9,
        frozenset({"registers", "memory", "disassembly"}),
        SnapshotStability.IMMUTABLE,
        EvidenceGrade.PORTABLE,
    )
    epoch = StopEpoch("epoch-1", generation, token, snapshot, EvidenceGrade.PORTABLE)
    return generation, token, snapshot, epoch


def test_frozen_bundle_and_binding_golden_vectors_are_byte_exact() -> None:
    _, _, _, identity, bundle_ref, payload, _, _, _ = foundation()
    expected_bundle = (
        '{"abi_descriptor":{"digest":"' + ZERO + '","ref":"abi-01"},'
        '"architecture_descriptor":{"digest":"' + ZERO + '","ref":"arch-01"},'
        '"artifact_ref":{"byte_length":"0","container_version":"1",'
        '"content_digest":{"algorithm":"sha256","value":"' + ZERO + '"},'
        '"media_type":"application/vnd.hsx.hxe","ref_schema":"hsx.artifact-ref/1"},'
        '"bundle_schema":"hsx.image-debug-bundle/1","interpretation_schema_versions":{},'
        '"location_recipe":{"canonical_component_digest":"' + ZERO + '",'
        '"schema":"hsx.location-recipe/1"},"required_debug_capabilities":[],'
        '"source_identity_manifest_ref":{"algorithm":"sha256","value":"' + SOURCE_DIGEST + '"},'
        '"symbol_model":{"canonical_component_digest":"' + SYMBOL_DIGEST + '",'
        '"schema":"hsx.debug-component.symbol-model/1"},'
        '"unwind_recipe":{"canonical_component_digest":"' + ZERO + '",'
        '"schema":"hsx.unwind-recipe/1"}}'
    ).encode()
    assert canonical_json_bytes(identity.canonical_payload()) == expected_bundle
    assert identity.canonical_digest() == BUNDLE_DIGEST == bundle_ref.bundle_digest
    assert payload.loaded_image_ref.canonical_payload()["target_ref"] == "target-01"
    assert payload.loaded_image_ref.canonical_payload()["executive_instance_ref"] == "exec-01"
    assert payload.canonical_digest() == BINDING_DIGEST


def test_frozen_empty_symbol_component_vector_is_byte_and_domain_exact() -> None:
    payload = {"component_schema": "hsx.debug-component.symbol-model/1", "records": ()}
    assert canonical_json_bytes(payload) == (
        b'{"component_schema":"hsx.debug-component.symbol-model/1","records":[]}'
    )
    assert canonical_structured_digest(
        "hsx.debug-component.symbol-model/1", payload
    ) == SYMBOL_DIGEST
    assert canonical_structured_digest(
        "hsx.debug-component.unwind-recipe/1", payload
    ) != SYMBOL_DIGEST


def test_serializer_normalizes_nfc_escapes_only_quote_backslash_and_rejects_invalid_tokens() -> None:
    payload = {"z": "caf\u0065\u0301/\\\"", "a": CanonicalUInt64(1), "b": True}
    assert canonical_json_bytes(payload) == (
        '{"a":"1","b":true,"z":"caf\u00e9/\\\\\\\""}'.encode("utf-8")
    )
    assert canonical_structured_digest("domain", {}) != canonical_structured_digest("other", {})
    for bad in ({"n": 1}, {"n": None}, {"n": 1.0}, {"n": "bad\x00"}):
        with pytest.raises((TypeError, ValueError)):
            canonical_json_bytes(bad)
    with pytest.raises(ValueError, match="NFC"):
        SourceRef(foundation()[4], "src/cafe\u0301.c", ContentDigest("sha256", ZERO), CanonicalUInt64(1))
    for logical_id in ("/abs.c", "C:/abs.c", "../x.c", "a//b.c", "a\\b.c", "a/./b.c"):
        with pytest.raises(ValueError):
            SourceRef(foundation()[4], logical_id, ContentDigest("sha256", ZERO), CanonicalUInt64(1))


def test_identity_values_are_deeply_immutable_case_sensitive_and_validate_cardinality() -> None:
    _, target, _, identity, *_ = foundation()
    capabilities = ["z-cap", "a-cap"]
    changed = replace(identity, required_debug_capabilities=capabilities)
    capabilities.append("later")
    assert changed.required_debug_capabilities == ("a-cap", "z-cap")
    assert replace(target, target_id="OPAQUE") != replace(target, target_id="opaque")
    with pytest.raises(FrozenInstanceError):
        target.target_id = "mutated"  # type: ignore[misc]
    for value in (-1, 1 << 64, True):
        with pytest.raises(ValueError):
            CanonicalUInt64(value)
    for digest in ("A" * 64, "0" * 63, "g" * 64):
        with pytest.raises(ValueError):
            ContentDigest("sha256", digest)


def test_debug_binding_validator_exhaustive_first_match_matrix() -> None:
    artifact, _, image, identity, bundle_ref, payload, binding, descriptor, abi = foundation()

    def code(result):
        return result.status, result.diagnostics[0].code if result.diagnostics else None

    assert code(DebugBindingValidator.validate(binding, identity, descriptor, abi)) == (
        ResolutionStatus.RESOLVED,
        None,
    )
    other_artifact = replace(artifact, content_digest=ContentDigest("sha256", "1" * 64))
    image_other_artifact = replace(image, artifact_ref=other_artifact)
    loaded_mismatch_payload = replace(payload, loaded_image_ref=image_other_artifact)
    loaded_mismatch = ImageDebugBinding(
        loaded_mismatch_payload, loaded_mismatch_payload.canonical_digest()
    )
    assert code(DebugBindingValidator.validate(loaded_mismatch, identity, descriptor, abi)) == (
        ResolutionStatus.ARTIFACT_MISMATCH,
        "artifact_ref_mismatch",
    )
    identity_artifact = replace(identity, artifact_ref=other_artifact)
    assert code(DebugBindingValidator.validate(binding, identity_artifact, descriptor, abi)) == (
        ResolutionStatus.ARTIFACT_MISMATCH,
        "artifact_ref_mismatch",
    )
    bad_bundle_ref = replace(bundle_ref, bundle_digest="1" * 64)
    bad_bundle_payload = replace(payload, image_debug_bundle_ref=bad_bundle_ref)
    bad_bundle = ImageDebugBinding(bad_bundle_payload, bad_bundle_payload.canonical_digest())
    assert code(DebugBindingValidator.validate(bad_bundle, identity, descriptor, abi))[1] == "bundle_digest_mismatch"
    assert code(DebugBindingValidator.validate(replace(binding, binding_digest="1" * 64), identity, descriptor, abi))[1] == "binding_digest_mismatch"
    wrong_arch_ref_payload = replace(payload, accepted_architecture_descriptor_ref="arch-x")
    wrong_arch_ref = ImageDebugBinding(wrong_arch_ref_payload, wrong_arch_ref_payload.canonical_digest())
    assert code(DebugBindingValidator.validate(wrong_arch_ref, identity, descriptor, abi))[1] == "binding_architecture_ref_mismatch"
    wrong_arch_identity = replace(identity, architecture_descriptor=DescriptorDigestRef("arch-01", "1" * 64))
    wrong_arch_bundle_ref = replace(bundle_ref, bundle_digest=wrong_arch_identity.canonical_digest())
    wrong_arch_payload = replace(payload, image_debug_bundle_ref=wrong_arch_bundle_ref)
    wrong_arch = ImageDebugBinding(wrong_arch_payload, wrong_arch_payload.canonical_digest())
    assert code(DebugBindingValidator.validate(wrong_arch, wrong_arch_identity, descriptor, abi))[1] == "bundle_architecture_mismatch"
    wrong_abi_ref_payload = replace(payload, accepted_abi_descriptor_ref="abi-x")
    wrong_abi_ref = ImageDebugBinding(wrong_abi_ref_payload, wrong_abi_ref_payload.canonical_digest())
    assert code(DebugBindingValidator.validate(wrong_abi_ref, identity, descriptor, abi))[1] == "binding_abi_ref_mismatch"
    wrong_abi_identity = replace(identity, abi_descriptor=DescriptorDigestRef("abi-01", "1" * 64))
    wrong_abi_bundle_ref = replace(bundle_ref, bundle_digest=wrong_abi_identity.canonical_digest())
    wrong_abi_payload = replace(payload, image_debug_bundle_ref=wrong_abi_bundle_ref)
    wrong_abi = ImageDebugBinding(wrong_abi_payload, wrong_abi_payload.canonical_digest())
    assert code(DebugBindingValidator.validate(wrong_abi, wrong_abi_identity, descriptor, abi))[1] == "bundle_abi_mismatch"


def test_controller_epoch_adapter_exact_status_code_matrix_and_context_fencing() -> None:
    artifact, target, image, *_ = foundation()
    generation, token, snapshot, epoch = portable_epoch(target, image)

    def outcome(value):
        result = ControllerEpochAdapter.bind(value, target, image)
        return result.status, result.diagnostics[0].code if result.diagnostics else None, result.context

    status, code, context = outcome(epoch)
    assert (status, code) == (ContextBindingStatus.BOUND, None)
    assert isinstance(context, InspectionContext)
    assert context.epoch.stop_epoch_id == StopEpochId("epoch-1")
    untyped = StopEpoch("epoch-u", generation, {"token": 1}, None, EvidenceGrade.PORTABLE)
    assert outcome(untyped)[:2] == (ContextBindingStatus.UNAVAILABLE, "coherent_snapshot_unavailable")
    best_live = replace(snapshot, stability=SnapshotStability.BEST_EFFORT_LIVE)
    assert outcome(StopEpoch("epoch-live", generation, token, best_live, EvidenceGrade.PORTABLE))[:2] == (
        ContextBindingStatus.UNAVAILABLE,
        "portable_snapshot_evidence_unavailable",
    )
    legacy_snapshot = replace(snapshot, evidence_grade=EvidenceGrade.LEGACY_DEGRADED)
    assert outcome(StopEpoch("epoch-grade", generation, token, legacy_snapshot, EvidenceGrade.PORTABLE))[:2] == (
        ContextBindingStatus.UNAVAILABLE,
        "portable_snapshot_evidence_unavailable",
    )
    stale_generation = replace(generation, target_generation=2)
    assert outcome(StopEpoch("epoch-g", stale_generation, token, snapshot, EvidenceGrade.PORTABLE))[:2] == (
        ContextBindingStatus.STALE,
        "controller_epoch_target_stale",
    )
    other_target = replace(target, target_id="other", canonical_ref="other-ref")
    other_image = replace(image, target_ref=other_target, executive_instance_ref=other_target.executive)
    other_token = StopToken(other_target, other_image, "stop-7", 7)
    other_snapshot = replace(snapshot, target=other_target, image=other_image, stop_token=other_token)
    assert outcome(StopEpoch("epoch-t", generation, other_token, other_snapshot, EvidenceGrade.PORTABLE))[:2] == (
        ContextBindingStatus.STALE,
        "epoch_target_stale",
    )
    newer_image = replace(image, loaded_image_id="image-new", image_generation=CanonicalUInt64(2))
    newer_token = StopToken(target, newer_image, "stop-7", 7)
    newer_snapshot = replace(snapshot, image=newer_image, stop_token=newer_token)
    assert outcome(StopEpoch("epoch-i", generation, newer_token, newer_snapshot, EvidenceGrade.PORTABLE))[:2] == (
        ContextBindingStatus.STALE,
        "loaded_image_stale",
    )
    other_artifact = replace(artifact, content_digest=ContentDigest("sha256", "2" * 64))
    artifact_image = replace(image, artifact_ref=other_artifact)
    artifact_token = StopToken(target, artifact_image, "stop-7", 7)
    artifact_snapshot = replace(snapshot, image=artifact_image, stop_token=artifact_token)
    assert outcome(StopEpoch("epoch-a", generation, artifact_token, artifact_snapshot, EvidenceGrade.PORTABLE))[:2] == (
        ContextBindingStatus.ARTIFACT_MISMATCH,
        "epoch_artifact_mismatch",
    )
    other_token_same_image = replace(token, opaque_token="stop-other")
    other_snapshot_same_image = replace(snapshot, stop_token=other_token_same_image)
    assert outcome(StopEpoch("epoch-s", generation, token, other_snapshot_same_image, EvidenceGrade.PORTABLE))[:2] == (
        ContextBindingStatus.STALE,
        "stop_token_stale",
    )
    for value in outcome(untyped)[2:], outcome(StopEpoch("epoch-g2", stale_generation, token, snapshot, EvidenceGrade.PORTABLE))[2:]:
        assert value == (None,)


def test_coherent_context_rejects_best_effort_degraded_and_identity_mismatch() -> None:
    _, target, image, *_ = foundation()
    generation, token, snapshot, _ = portable_epoch(target, image)
    with pytest.raises(ValueError, match="best-effort"):
        EpochBinding(
            StopEpochId("epoch"), generation, token,
            replace(snapshot, stability=SnapshotStability.BEST_EFFORT_LIVE),
            EvidenceGrade.PORTABLE,
        )
    legacy_generation = replace(generation, evidence_grade=EvidenceGrade.LEGACY_DEGRADED)
    legacy_snapshot = replace(snapshot, evidence_grade=EvidenceGrade.LEGACY_DEGRADED)
    with pytest.raises(ValueError, match="PORTABLE"):
        EpochBinding(StopEpochId("epoch"), legacy_generation, token, legacy_snapshot, EvidenceGrade.LEGACY_DEGRADED)
    epoch = EpochBinding(StopEpochId("epoch"), generation, token, snapshot, EvidenceGrade.PORTABLE)
    context = InspectionContext(target, image, epoch)
    other_target = replace(target, canonical_ref="other", target_id="other")
    with pytest.raises(ValueError, match="image target"):
        replace(context, target=other_target)

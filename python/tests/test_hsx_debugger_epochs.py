from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from hsx_debugger.contracts import EvidenceGrade, GenerationStamp
from hsx_debugger.epochs import StaleEpochError, StopEpochStore, UnknownEpochError


def generation(session: int = 1, stream: int = 2) -> GenerationStamp:
    return GenerationStamp(
        executive_instance_id=None,
        session_generation=session,
        target_id=None,
        target_generation=3,
        capability_generation=session,
        stream_generation=stream,
        display_pid=5,
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
    )


def test_opening_epoch_invalidates_previous_epoch_without_mutating_prior_store() -> None:
    original = StopEpochStore()
    first = original.open_epoch(
        epoch_id="epoch-1",
        generation=generation(),
        stop_token={"legacy": [1, 2, 4]},
        snapshot_ref=None,
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
    )
    second = first.open_epoch(
        epoch_id="epoch-2",
        generation=generation(),
        stop_token="legacy:1:2:seq:5",
        snapshot_ref={"snapshot": [2]},
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
    )

    assert original.active is None
    assert first.active is not None and first.active.epoch_id == "epoch-1"
    assert first.active.stop_token["legacy"] == (1, 2, 4)
    assert second.active is not None and second.active.epoch_id == "epoch-2"
    assert second.active.snapshot_ref["snapshot"] == (2,)
    assert second.invalidated_epoch_ids == frozenset({"epoch-1"})
    with pytest.raises(FrozenInstanceError):
        second.active.snapshot_ref = "changed"  # type: ignore[misc,union-attr]


def test_epoch_lookup_distinguishes_stale_unknown_and_wrong_generation() -> None:
    store = StopEpochStore().open_epoch(
        epoch_id="epoch-1",
        generation=generation(),
        stop_token="legacy:1:2:local:1",
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
    )

    assert store.get("epoch-1", generation()).epoch_id == "epoch-1"
    with pytest.raises(StaleEpochError):
        store.get("epoch-1", generation(session=2))
    with pytest.raises(UnknownEpochError):
        store.get("never-seen", generation())
    with pytest.raises(StaleEpochError):
        store.invalidate().get("epoch-1", generation())


def test_invalidated_or_active_epoch_id_can_never_be_rebound() -> None:
    store = StopEpochStore().open_epoch(
        epoch_id="epoch-1",
        generation=generation(),
        stop_token="stop-1",
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
    )
    with pytest.raises(ValueError, match="already been allocated"):
        store.open_epoch(
            epoch_id="epoch-1",
            generation=generation(),
            stop_token="stop-rebind",
            evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
        )
    with pytest.raises(ValueError, match="already been allocated"):
        store.invalidate().open_epoch(
            epoch_id="epoch-1",
            generation=generation(session=2),
            stop_token="stop-cross-generation",
            evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
        )


def test_legacy_tokens_are_local_generation_evidence_and_never_portable() -> None:
    store = StopEpochStore()
    sequence_token, unchanged_counter = store.local_legacy_token(generation(), 9)
    counter_token, next_counter = store.local_legacy_token(generation(), None)

    assert sequence_token == "legacy:1:2:seq:9"
    assert unchanged_counter == 0
    assert counter_token == "legacy:1:2:local:1"
    assert next_counter == 1


def test_generation_reset_invalidates_epoch_and_resets_local_counter() -> None:
    store = StopEpochStore(legacy_stop_counter=7).open_epoch(
        epoch_id="epoch-1",
        generation=generation(),
        stop_token="legacy:1:2:local:7",
        evidence_grade=EvidenceGrade.LEGACY_DEGRADED,
        legacy_stop_counter=7,
    )

    reset = store.reset_for_generation()

    assert reset.active is None
    assert reset.legacy_stop_counter == 0
    assert reset.invalidated_epoch_ids == frozenset({"epoch-1"})


def test_portable_epoch_requires_exact_portable_generation_evidence() -> None:
    portable = GenerationStamp(
        executive_instance_id="exec-1",
        session_generation=1,
        target_id="target-1",
        target_generation=1,
        capability_generation=1,
        stream_generation=1,
        display_pid=5,
        evidence_grade=EvidenceGrade.PORTABLE,
    )
    store = StopEpochStore().open_epoch(
        epoch_id="portable-epoch",
        generation=portable,
        stop_token={"stop_revision": 9},
        snapshot_ref={"snapshot_id": "snapshot-9"},
        evidence_grade=EvidenceGrade.PORTABLE,
    )

    assert store.get("portable-epoch", portable).evidence_grade is EvidenceGrade.PORTABLE
    with pytest.raises(StaleEpochError):
        store.get(
            "portable-epoch",
            GenerationStamp(
                executive_instance_id="exec-1",
                session_generation=1,
                target_id="target-1",
                target_generation=2,
                capability_generation=1,
                stream_generation=1,
                display_pid=5,
                evidence_grade=EvidenceGrade.PORTABLE,
            ),
        )

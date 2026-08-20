"""Immutable stop-epoch storage for the side-by-side debugger foundation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .contracts import EvidenceGrade, GenerationStamp, StopEpoch


class EpochLookupError(LookupError):
    """Base class for stable stop-epoch lookup failures."""


class StaleEpochError(EpochLookupError):
    """The epoch existed but has been invalidated or belongs to older continuity."""


class UnknownEpochError(EpochLookupError):
    """The epoch was never owned by this store."""


@dataclass(frozen=True, slots=True)
class StopEpochStore:
    """Persistent value object owning one active epoch and stable invalidation history."""

    active: StopEpoch | None = None
    invalidated_epoch_ids: frozenset[str] = field(default_factory=frozenset)
    legacy_stop_counter: int = 0

    def __post_init__(self) -> None:
        if self.active is not None and not isinstance(self.active, StopEpoch):
            raise TypeError("active must be StopEpoch or None")
        invalidated = frozenset(self.invalidated_epoch_ids)
        if any(not isinstance(epoch_id, str) or not epoch_id.strip() for epoch_id in invalidated):
            raise ValueError("invalidated epoch IDs must be non-empty strings")
        if self.active is not None and self.active.epoch_id in invalidated:
            raise ValueError("active epoch cannot also be invalidated")
        if (
            isinstance(self.legacy_stop_counter, bool)
            or not isinstance(self.legacy_stop_counter, int)
            or self.legacy_stop_counter < 0
        ):
            raise ValueError("legacy_stop_counter must be a non-negative integer")
        object.__setattr__(self, "invalidated_epoch_ids", invalidated)

    def open_epoch(
        self,
        *,
        epoch_id: str,
        generation: GenerationStamp,
        stop_token: Any,
        snapshot_ref: Any = None,
        evidence_grade: EvidenceGrade,
        legacy_stop_counter: int | None = None,
    ) -> StopEpochStore:
        """Return a store with one new epoch without ever rebinding an old epoch ID."""

        if not isinstance(epoch_id, str) or not epoch_id.strip():
            raise ValueError("epoch_id must be a non-empty string")
        if (
            epoch_id in self.invalidated_epoch_ids
            or (self.active is not None and self.active.epoch_id == epoch_id)
        ):
            raise ValueError("epoch_id has already been allocated")
        epoch = StopEpoch(
            epoch_id=epoch_id,
            generation=generation,
            stop_token=stop_token,
            snapshot_ref=snapshot_ref,
            evidence_grade=evidence_grade,
        )
        invalidated = self.invalidated_epoch_ids
        if self.active is not None:
            invalidated = invalidated | {self.active.epoch_id}
        counter = self.legacy_stop_counter if legacy_stop_counter is None else legacy_stop_counter
        return StopEpochStore(epoch, invalidated, counter)

    def invalidate(self) -> StopEpochStore:
        """Return an equivalent store with no active epoch."""

        if self.active is None:
            return self
        return StopEpochStore(
            active=None,
            invalidated_epoch_ids=self.invalidated_epoch_ids | {self.active.epoch_id},
            legacy_stop_counter=self.legacy_stop_counter,
        )

    def reset_for_generation(self) -> StopEpochStore:
        """Invalidate the active epoch and reset generation-local legacy sequencing."""

        invalidated = self.invalidated_epoch_ids
        if self.active is not None:
            invalidated = invalidated | {self.active.epoch_id}
        if self.active is None and self.legacy_stop_counter == 0:
            return self
        return StopEpochStore(None, invalidated, 0)

    def get(self, epoch_id: str, generation: GenerationStamp) -> StopEpoch:
        """Resolve only the active epoch for its exact continuity stamp."""

        if not isinstance(epoch_id, str) or not epoch_id.strip():
            raise ValueError("epoch_id must be a non-empty string")
        if not isinstance(generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        if self.active is not None and self.active.epoch_id == epoch_id:
            if self.active.generation != generation:
                raise StaleEpochError(epoch_id)
            return self.active
        if epoch_id in self.invalidated_epoch_ids:
            raise StaleEpochError(epoch_id)
        raise UnknownEpochError(epoch_id)

    def local_legacy_token(
        self, generation: GenerationStamp, sequence: int | None
    ) -> tuple[str, int]:
        """Build explicitly local legacy stop evidence; never claim portable continuity."""

        if not isinstance(generation, GenerationStamp):
            raise TypeError("generation must be GenerationStamp")
        if sequence is not None:
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 1:
                raise ValueError("sequence must be a positive integer")
            prefix = (
                f"legacy:{generation.session_generation}:"
                f"{generation.stream_generation}"
            )
            return (
                f"{prefix}:seq:{sequence}",
                self.legacy_stop_counter,
            )
        counter = self.legacy_stop_counter + 1
        prefix = (
            f"legacy:{generation.session_generation}:"
            f"{generation.stream_generation}"
        )
        return (
            f"{prefix}:local:{counter}",
            counter,
        )


__all__ = [
    "EpochLookupError",
    "StaleEpochError",
    "StopEpochStore",
    "UnknownEpochError",
]

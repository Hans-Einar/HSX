"""Exact, content-verified local source resolution for RF-004.

This module owns only the boundary between a portable :class:`SourceRef` and explicit
host-local locator policy.  It does not parse artifacts, inspect targets, choose frontend
navigation, or infer paths from basenames or the current working directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import os
from pathlib import Path

from .identity import ContentDigest, SourceRef, validate_source_logical_id
from .results import Diagnostic, ResolutionStatus, _register_contract_enums


class SourceDiscovery(str, Enum):
    OVERRIDE = "override"
    PREFIX = "prefix"
    SEARCH_ROOT = "search_root"


_register_contract_enums(SourceDiscovery)


def _as_tuple(value: object, field_name: str) -> tuple:
    if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)):
        raise TypeError(f"{field_name} must be a tuple or list")
    return tuple(value)


@dataclass(frozen=True, slots=True)
class ExactSourceOverride:
    source: SourceRef
    locator: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceRef):
            raise TypeError("source must be SourceRef")
        if not isinstance(self.locator, str):
            raise TypeError("locator must be a string")


@dataclass(frozen=True, slots=True)
class SourcePrefixMapping:
    logical_prefix: str
    local_root: str

    def __post_init__(self) -> None:
        if not isinstance(self.logical_prefix, str):
            raise TypeError("logical_prefix must be a string")
        if not isinstance(self.local_root, str):
            raise TypeError("local_root must be a string")


@dataclass(frozen=True, slots=True)
class SourceLocatorPolicy:
    exact_overrides: tuple[ExactSourceOverride, ...]
    prefix_mappings: tuple[SourcePrefixMapping, ...]
    search_roots: tuple[str, ...]

    def __post_init__(self) -> None:
        exact_overrides = _as_tuple(self.exact_overrides, "exact_overrides")
        prefix_mappings = _as_tuple(self.prefix_mappings, "prefix_mappings")
        search_roots = _as_tuple(self.search_roots, "search_roots")
        if not all(isinstance(value, ExactSourceOverride) for value in exact_overrides):
            raise TypeError("exact_overrides must contain ExactSourceOverride values")
        if not all(isinstance(value, SourcePrefixMapping) for value in prefix_mappings):
            raise TypeError("prefix_mappings must contain SourcePrefixMapping values")
        if not all(isinstance(value, str) for value in search_roots):
            raise TypeError("search_roots must contain strings")
        object.__setattr__(self, "exact_overrides", exact_overrides)
        object.__setattr__(self, "prefix_mappings", prefix_mappings)
        object.__setattr__(self, "search_roots", search_roots)


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    locator: str
    discovery: SourceDiscovery
    byte_length: int
    content_digest: ContentDigest
    content_matches: bool

    def __post_init__(self) -> None:
        if not isinstance(self.locator, str) or not self.locator:
            raise ValueError("locator must be a non-empty string")
        if type(self.discovery) is not SourceDiscovery:
            raise TypeError("discovery must be SourceDiscovery")
        if (
            isinstance(self.byte_length, bool)
            or not isinstance(self.byte_length, int)
            or self.byte_length < 0
        ):
            raise ValueError("byte_length must be an integer >= 0")
        if not isinstance(self.content_digest, ContentDigest):
            raise TypeError("content_digest must be ContentDigest")
        if not isinstance(self.content_matches, bool):
            raise TypeError("content_matches must be a bool")


@dataclass(frozen=True, slots=True)
class SourceResolution:
    status: ResolutionStatus
    source: SourceRef
    candidates: tuple[SourceCandidate, ...]
    resolved_locator: str | None
    diagnostics: tuple[Diagnostic, ...]

    def __post_init__(self) -> None:
        if type(self.status) is not ResolutionStatus:
            raise TypeError("status must be ResolutionStatus")
        if not isinstance(self.source, SourceRef):
            raise TypeError("source must be SourceRef")
        candidates = _as_tuple(self.candidates, "candidates")
        diagnostics = _as_tuple(self.diagnostics, "diagnostics")
        if not all(isinstance(value, SourceCandidate) for value in candidates):
            raise TypeError("candidates must contain SourceCandidate values")
        if not all(isinstance(value, Diagnostic) for value in diagnostics):
            raise TypeError("diagnostics must contain Diagnostic values")
        if self.resolved_locator is not None and (
            not isinstance(self.resolved_locator, str) or not self.resolved_locator
        ):
            raise ValueError("resolved_locator must be a non-empty string or None")
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "diagnostics", diagnostics)

        if self.status is ResolutionStatus.RESOLVED:
            if len(candidates) != 1 or self.resolved_locator != candidates[0].locator:
                raise ValueError("RESOLVED requires exactly its selected candidate")
            if not candidates[0].content_matches:
                raise ValueError("RESOLVED requires content_matches=true")
        elif self.resolved_locator is not None:
            raise ValueError("only RESOLVED may select a locator")

        if self.status in (ResolutionStatus.AMBIGUOUS, ResolutionStatus.CASE_COLLISION):
            if len(candidates) < 2:
                raise ValueError(f"{self.status.name} requires at least two candidates")
        elif self.status is ResolutionStatus.CONTENT_MISMATCH:
            if not candidates or any(value.content_matches for value in candidates):
                raise ValueError(
                    "CONTENT_MISMATCH requires only mismatching candidates"
                )
        elif self.status is not ResolutionStatus.RESOLVED and candidates:
            raise ValueError(f"{self.status.name} does not carry candidates")


@dataclass(frozen=True, slots=True)
class _ReadCandidate:
    public: SourceCandidate
    content: bytes


@dataclass(frozen=True, slots=True)
class _LocatorFailure:
    status: ResolutionStatus
    diagnostic: Diagnostic


def _diagnostic(code: str, message: str) -> Diagnostic:
    return Diagnostic(code, message, component="source_resolver")


def _resolution(
    status: ResolutionStatus,
    source: SourceRef,
    candidates: tuple[SourceCandidate, ...] = (),
    resolved_locator: str | None = None,
    *diagnostics: Diagnostic,
) -> SourceResolution:
    return SourceResolution(status, source, candidates, resolved_locator, diagnostics)


def _validate_locator(locator: str) -> str | None:
    if not locator:
        return "locator is empty"
    if "\x00" in locator or any(
        ord(character) < 32 or ord(character) == 127 for character in locator
    ):
        return "locator contains a NUL or control character"
    return None


def _join_locator(root: str, suffix: str) -> str:
    if not suffix:
        return root
    host_separators = (os.sep,) if os.altsep is None else (os.sep, os.altsep)
    separator = "" if root.endswith(host_separators) else os.sep
    return root + separator + os.sep.join(suffix.split("/"))


def _prefix_suffix(logical_id: str, logical_prefix: str) -> str | None:
    """Return a segment-safe exact-case suffix, or None when the prefix does not match."""

    if logical_prefix == "":
        return logical_id
    normalized_prefix = (
        logical_prefix[:-1] if logical_prefix.endswith("/") else logical_prefix
    )
    if not normalized_prefix:
        return logical_id
    if logical_id == normalized_prefix:
        return ""
    marker = normalized_prefix + "/"
    if logical_id.startswith(marker):
        return logical_id[len(marker) :]
    return None


def _read_candidate(
    locator: str, discovery: SourceDiscovery, source: SourceRef
) -> _ReadCandidate | _LocatorFailure | None:
    invalid = _validate_locator(locator)
    if invalid is not None:
        return _LocatorFailure(
            ResolutionStatus.CORRUPT,
            _diagnostic("source_locator_invalid", f"{invalid}: {locator!r}"),
        )

    path = Path(locator)
    try:
        if not path.exists():
            return None
        if not path.is_file():
            return _LocatorFailure(
                ResolutionStatus.CORRUPT,
                _diagnostic(
                    "source_locator_invalid",
                    f"source locator is not a file: {locator!r}",
                ),
            )
        content = path.read_bytes()
    except (OSError, ValueError) as exc:
        return _LocatorFailure(
            ResolutionStatus.CORRUPT,
            _diagnostic(
                "source_locator_invalid",
                f"source locator cannot be read exactly: {locator!r}: {exc}",
            ),
        )

    digest = hashlib.sha256(content).hexdigest()
    matches = (
        len(content) == source.byte_length.value
        and digest == source.content_digest.value
    )
    public = SourceCandidate(
        locator,
        discovery,
        len(content),
        ContentDigest("sha256", digest),
        matches,
    )
    return _ReadCandidate(public, content)


def _deduplicate(candidates: list[_ReadCandidate]) -> tuple[_ReadCandidate, ...]:
    seen: set[tuple[str, bytes]] = set()
    result: list[_ReadCandidate] = []
    for candidate in candidates:
        key = (candidate.public.locator, candidate.content)
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return tuple(result)


def _has_case_collision(candidates: tuple[_ReadCandidate, ...]) -> bool:
    for index, left in enumerate(candidates):
        left_locator = left.public.locator
        left_key = os.path.normcase(os.path.abspath(left_locator))
        for right in candidates[index + 1 :]:
            right_locator = right.public.locator
            if left_locator == right_locator:
                continue
            if left_key != os.path.normcase(os.path.abspath(right_locator)):
                continue
            try:
                if os.path.samefile(left_locator, right_locator):
                    return True
            except OSError:
                continue
    return False


def _finish_winning_tier(
    source: SourceRef, candidates: list[_ReadCandidate]
) -> SourceResolution:
    remaining = _deduplicate(candidates)
    public = tuple(value.public for value in remaining)
    if _has_case_collision(remaining):
        return _resolution(
            ResolutionStatus.CASE_COLLISION,
            source,
            public,
            None,
            _diagnostic(
                "source_locator_case_collision",
                "the host filesystem cannot address the candidate spellings separately",
            ),
        )
    if len(remaining) > 1:
        return _resolution(
            ResolutionStatus.AMBIGUOUS,
            source,
            public,
            None,
            _diagnostic(
                "source_locator_ambiguous",
                "multiple distinct existing locators remain in the winning tier",
            ),
        )
    candidate = remaining[0].public
    if candidate.content_matches:
        return _resolution(
            ResolutionStatus.RESOLVED, source, (candidate,), candidate.locator
        )
    return _resolution(
        ResolutionStatus.CONTENT_MISMATCH,
        source,
        (candidate,),
        None,
        _diagnostic(
            "source_content_mismatch",
            "the existing source locator does not match the required byte length and SHA-256",
        ),
    )


class SourceResolver:
    """Resolve one exact portable source identity using only explicit locator policy."""

    def resolve(
        self, source: SourceRef, policy: SourceLocatorPolicy
    ) -> SourceResolution:
        if not isinstance(source, SourceRef):
            raise TypeError("source must be SourceRef")
        if not isinstance(policy, SourceLocatorPolicy):
            raise TypeError("policy must be SourceLocatorPolicy")
        # Revalidate at the service boundary even though SourceRef also validates at creation.
        validate_source_logical_id(source.logical_id)

        overrides = tuple(
            override for override in policy.exact_overrides if override.source == source
        )
        if len(overrides) > 1:
            return _resolution(
                ResolutionStatus.CORRUPT,
                source,
                (),
                None,
                _diagnostic(
                    "source_override_duplicate",
                    "more than one exact override is configured for the SourceRef",
                ),
            )
        if overrides:
            override = overrides[0]
            result = _read_candidate(override.locator, SourceDiscovery.OVERRIDE, source)
            if isinstance(result, _LocatorFailure):
                return _resolution(result.status, source, (), None, result.diagnostic)
            if result is None:
                return _resolution(
                    ResolutionStatus.UNAVAILABLE,
                    source,
                    (),
                    None,
                    _diagnostic(
                        "source_locator_unavailable",
                        "the exact source override does not exist",
                    ),
                )
            return _finish_winning_tier(source, [result])

        matching: list[tuple[int, SourcePrefixMapping, str]] = []
        for mapping in policy.prefix_mappings:
            suffix = _prefix_suffix(source.logical_id, mapping.logical_prefix)
            if suffix is not None:
                effective_prefix = mapping.logical_prefix.rstrip("/")
                matching.append((len(effective_prefix), mapping, suffix))
        if matching:
            longest = max(value[0] for value in matching)
            prefix_candidates: list[_ReadCandidate] = []
            for length, mapping, suffix in matching:
                if length != longest:
                    continue
                invalid_root = _validate_locator(mapping.local_root)
                if invalid_root is not None:
                    return _resolution(
                        ResolutionStatus.CORRUPT,
                        source,
                        (),
                        None,
                        _diagnostic(
                            "source_locator_invalid",
                            f"{invalid_root}: {mapping.local_root!r}",
                        ),
                    )
                result = _read_candidate(
                    _join_locator(mapping.local_root, suffix),
                    SourceDiscovery.PREFIX,
                    source,
                )
                if isinstance(result, _LocatorFailure):
                    return _resolution(
                        result.status, source, (), None, result.diagnostic
                    )
                if result is not None:
                    prefix_candidates.append(result)
            if prefix_candidates:
                return _finish_winning_tier(source, prefix_candidates)

        root_candidates: list[_ReadCandidate] = []
        for root in policy.search_roots:
            invalid_root = _validate_locator(root)
            if invalid_root is not None:
                return _resolution(
                    ResolutionStatus.CORRUPT,
                    source,
                    (),
                    None,
                    _diagnostic("source_locator_invalid", f"{invalid_root}: {root!r}"),
                )
            result = _read_candidate(
                _join_locator(root, source.logical_id),
                SourceDiscovery.SEARCH_ROOT,
                source,
            )
            if isinstance(result, _LocatorFailure):
                return _resolution(result.status, source, (), None, result.diagnostic)
            if result is not None:
                root_candidates.append(result)
        if root_candidates:
            return _finish_winning_tier(source, root_candidates)

        return _resolution(
            ResolutionStatus.UNAVAILABLE,
            source,
            (),
            None,
            _diagnostic(
                "source_locator_unavailable",
                "no explicit locator in the applicable resolution tiers exists",
            ),
        )


__all__ = [
    "ExactSourceOverride",
    "SourceCandidate",
    "SourceDiscovery",
    "SourceLocatorPolicy",
    "SourcePrefixMapping",
    "SourceResolution",
    "SourceResolver",
]

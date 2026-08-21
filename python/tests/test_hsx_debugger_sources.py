from __future__ import annotations

from dataclasses import FrozenInstanceError
import hashlib
import os
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
if str(PYTHON_SRC) not in sys.path:
    sys.path.insert(0, str(PYTHON_SRC))

from hsx_debugger import (
    ArtifactRef,
    CanonicalUInt64,
    ContentDigest,
    ExactSourceOverride,
    ImageDebugBundleRef,
    ResolutionStatus,
    SourceDiscovery,
    SourceLocatorPolicy,
    SourcePrefixMapping,
    SourceRef,
    SourceResolver,
)


ZERO = "0" * 64
ARTIFACT = ArtifactRef(
    "hsx.artifact-ref/1",
    "application/vnd.hsx.hxe",
    CanonicalUInt64(1),
    CanonicalUInt64(0),
    ContentDigest("sha256", ZERO),
)
BUNDLE = ImageDebugBundleRef(
    "hsx.image-debug-bundle-ref/1", ARTIFACT, "sha256", "1" * 64
)


def source_ref(
    logical_id: str, content: bytes, *, length: int | None = None
) -> SourceRef:
    return SourceRef(
        BUNDLE,
        logical_id,
        ContentDigest("sha256", hashlib.sha256(content).hexdigest()),
        CanonicalUInt64(len(content) if length is None else length),
    )


def policy(
    *,
    overrides=(),
    prefixes=(),
    roots=(),
) -> SourceLocatorPolicy:
    return SourceLocatorPolicy(overrides, prefixes, roots)


def write(root: Path, logical_id: str, content: bytes) -> Path:
    path = root.joinpath(*logical_id.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_public_source_values_are_frozen_and_exported() -> None:
    source = source_ref("src/main.c", b"main")
    override = ExactSourceOverride(source, "local/main.c")
    locator_policy = SourceLocatorPolicy([override], [], ["root"])

    assert locator_policy.exact_overrides == (override,)
    assert locator_policy.prefix_mappings == ()
    assert locator_policy.search_roots == ("root",)
    assert [value.name for value in SourceDiscovery] == [
        "OVERRIDE",
        "PREFIX",
        "SEARCH_ROOT",
    ]
    assert [value.value for value in SourceDiscovery] == [
        "override",
        "prefix",
        "search_root",
    ]
    with pytest.raises(FrozenInstanceError):
        override.locator = "changed"  # type: ignore[misc]


def test_exact_override_resolves_only_after_digest_and_length_verification(
    tmp_path: Path,
) -> None:
    expected = b"int exact(void) { return 1; }\n"
    source = source_ref("src/exact.c", expected)
    locator = write(tmp_path / "project", source.logical_id, expected)

    result = SourceResolver().resolve(
        source,
        policy(
            overrides=(ExactSourceOverride(source, str(locator)),),
            roots=(str(tmp_path / "unused"),),
        ),
    )

    assert result.status is ResolutionStatus.RESOLVED
    assert result.source is source
    assert result.resolved_locator == str(locator)
    assert len(result.candidates) == 1
    assert result.candidates[0].discovery is SourceDiscovery.OVERRIDE
    assert result.candidates[0].byte_length == len(expected)
    assert result.candidates[0].content_matches is True


@pytest.mark.parametrize(
    ("locator", "expected_status", "diagnostic"),
    [
        ("", ResolutionStatus.CORRUPT, "source_locator_invalid"),
        ("missing.c", ResolutionStatus.UNAVAILABLE, "source_locator_unavailable"),
    ],
)
def test_exact_override_is_no_fallthrough(
    tmp_path: Path,
    locator: str,
    expected_status: ResolutionStatus,
    diagnostic: str,
) -> None:
    content = b"correct"
    source = source_ref("src/main.c", content)
    write(tmp_path / "search", source.logical_id, content)
    configured = locator if locator == "" else str(tmp_path / locator)

    result = SourceResolver().resolve(
        source,
        policy(
            overrides=(ExactSourceOverride(source, configured),),
            roots=(str(tmp_path / "search"),),
        ),
    )

    assert result.status is expected_status
    assert result.resolved_locator is None
    assert result.candidates == ()
    assert result.diagnostics[0].code == diagnostic


@pytest.mark.parametrize(
    ("source", "actual", "search_content"),
    [
        (source_ref("src/digest.c", b"expected"), b"different", b"expected"),
        (source_ref("src/length.c", b"expected", length=9), b"expected", b"expectedx"),
    ],
)
def test_one_existing_locator_reports_digest_or_length_mismatch(
    tmp_path: Path, source: SourceRef, actual: bytes, search_content: bytes
) -> None:
    locator = write(tmp_path / "override", source.logical_id, actual)
    write(tmp_path / "would-match-if-used", source.logical_id, search_content)

    result = SourceResolver().resolve(
        source,
        policy(
            overrides=(ExactSourceOverride(source, str(locator)),),
            roots=(str(tmp_path / "would-match-if-used"),),
        ),
    )

    assert result.status is ResolutionStatus.CONTENT_MISMATCH
    assert result.resolved_locator is None
    assert result.candidates[0].locator == str(locator)
    assert result.candidates[0].content_matches is False


def test_every_longest_prefix_mapping_is_collected_and_shorter_tiers_do_not_win(
    tmp_path: Path,
) -> None:
    expected = b"expected"
    source = source_ref("src/deep/main.c", expected)
    matching = write(tmp_path / "candidate-a", "main.c", expected)
    mismatching = write(tmp_path / "candidate-b", "main.c", b"other")
    write(tmp_path / "shorter", "deep/main.c", expected)
    write(tmp_path / "search", source.logical_id, expected)

    result = SourceResolver().resolve(
        source,
        policy(
            prefixes=(
                SourcePrefixMapping("src", str(tmp_path / "shorter")),
                SourcePrefixMapping("src/deep", str(tmp_path / "candidate-a")),
                SourcePrefixMapping("src/deep/", str(tmp_path / "candidate-b")),
            ),
            roots=(str(tmp_path / "search"),),
        ),
    )

    assert result.status is ResolutionStatus.AMBIGUOUS
    assert result.resolved_locator is None
    assert tuple(value.locator for value in result.candidates) == (
        str(matching),
        str(mismatching),
    )
    assert tuple(value.content_matches for value in result.candidates) == (True, False)
    assert all(value.discovery is SourceDiscovery.PREFIX for value in result.candidates)


def test_duplicate_exact_locator_and_bytes_are_deduplicated(tmp_path: Path) -> None:
    content = b"same"
    source = source_ref("src/same.c", content)
    locator = write(tmp_path / "mapped", "same.c", content)
    mapping = SourcePrefixMapping("src", str(tmp_path / "mapped"))

    result = SourceResolver().resolve(source, policy(prefixes=(mapping, mapping)))

    assert result.status is ResolutionStatus.RESOLVED
    assert result.resolved_locator == str(locator)
    assert len(result.candidates) == 1


def test_missing_prefix_candidates_fall_through_to_full_logical_id_search_root(
    tmp_path: Path,
) -> None:
    content = b"relocated"
    source = source_ref("src/relocated.c", content)
    relocated = write(tmp_path / "new-root", source.logical_id, content)

    result = SourceResolver().resolve(
        source,
        policy(
            prefixes=(SourcePrefixMapping("src", str(tmp_path / "old-root")),),
            roots=(str(tmp_path / "new-root"),),
        ),
    )

    assert result.status is ResolutionStatus.RESOLVED
    assert result.resolved_locator == str(relocated)
    assert result.candidates[0].discovery is SourceDiscovery.SEARCH_ROOT


def test_all_search_roots_are_one_ordered_winning_tier_without_first_choice(
    tmp_path: Path,
) -> None:
    expected = b"match"
    source = source_ref("src/unit.c", expected)
    first = write(tmp_path / "first", source.logical_id, expected)
    second = write(tmp_path / "second", source.logical_id, b"mismatch")

    result = SourceResolver().resolve(
        source, policy(roots=(str(tmp_path / "first"), str(tmp_path / "second")))
    )

    assert result.status is ResolutionStatus.AMBIGUOUS
    assert tuple(value.locator for value in result.candidates) == (
        str(first),
        str(second),
    )
    assert tuple(value.content_matches for value in result.candidates) == (True, False)


def test_no_basename_or_current_working_directory_guess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    content = b"do not guess"
    source = source_ref("src/alpha/unit.c", content)
    write(tmp_path, "unit.c", content)
    write(tmp_path / "elsewhere", "lib/beta/unit.c", content)
    monkeypatch.chdir(tmp_path)

    result = SourceResolver().resolve(source, policy())

    assert result.status is ResolutionStatus.UNAVAILABLE
    assert result.resolved_locator is None
    assert result.candidates == ()


@pytest.mark.parametrize(
    "locator_policy",
    [
        policy(prefixes=(SourcePrefixMapping("src", ""),)),
        policy(roots=("",)),
    ],
)
def test_empty_explicit_root_is_invalid_not_an_implicit_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    locator_policy: SourceLocatorPolicy,
) -> None:
    content = b"must not use cwd"
    source = source_ref("src/main.c", content)
    write(tmp_path, source.logical_id, content)
    monkeypatch.chdir(tmp_path)

    result = SourceResolver().resolve(source, locator_policy)

    assert result.status is ResolutionStatus.CORRUPT
    assert result.resolved_locator is None
    assert result.diagnostics[0].code == "source_locator_invalid"


@pytest.mark.parametrize(
    "logical_id",
    [
        "",
        "/src/main.c",
        "//server/share/main.c",
        "C:/src/main.c",
        "src\\main.c",
        "src//main.c",
        "./src/main.c",
        "src/../main.c",
        "src/cafe\u0301.c",
        "src/\x00main.c",
        "src/\x1fmain.c",
    ],
)
def test_portable_logical_id_rejections_are_mandatory(logical_id: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        source_ref(logical_id, b"content")


def test_case_distinct_locators_remain_distinct_without_global_casefold(
    tmp_path: Path,
) -> None:
    if os.path.normcase("Case") == os.path.normcase("case"):
        pytest.skip("host filesystem path comparison is case-insensitive")
    content = b"same content"
    source = source_ref("src/case.c", content)
    upper = write(tmp_path / "CaseRoot", source.logical_id, content)
    lower = write(tmp_path / "caseroot", source.logical_id, content)

    result = SourceResolver().resolve(
        source,
        policy(
            prefixes=(
                SourcePrefixMapping("src", str(tmp_path / "CaseRoot" / "src")),
                SourcePrefixMapping("src", str(tmp_path / "caseroot" / "src")),
            )
        ),
    )

    assert result.status is ResolutionStatus.AMBIGUOUS
    assert tuple(value.locator for value in result.candidates) == (
        str(upper),
        str(lower),
    )


def test_case_collision_is_separate_when_host_cannot_address_spellings(
    tmp_path: Path,
) -> None:
    if os.path.normcase("Case") != os.path.normcase("case"):
        pytest.skip("host filesystem can address case-distinct spellings")
    content = b"same content"
    source = source_ref("src/case.c", content)
    actual_root = tmp_path / "CaseRoot"
    write(actual_root, source.logical_id, content)
    alternate_root = tmp_path / "caseroot"

    result = SourceResolver().resolve(
        source,
        policy(
            prefixes=(
                SourcePrefixMapping("src", str(actual_root / "src")),
                SourcePrefixMapping("src", str(alternate_root / "src")),
            )
        ),
    )

    assert result.status is ResolutionStatus.CASE_COLLISION
    assert result.resolved_locator is None
    assert len(result.candidates) == 2


def test_symlink_is_locator_behavior_and_preserves_original_source_ref(
    tmp_path: Path,
) -> None:
    content = b"int symlinked(void) { return 4; }\n"
    source = source_ref("src/symlink.c", content)
    target = write(tmp_path / "shared", "module.c", content)
    symlink = tmp_path / "relocated" / "src" / "symlink.c"
    symlink.parent.mkdir(parents=True)
    try:
        symlink.symlink_to(target)
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314:
            pytest.skip("WinError1314: symlink privilege unavailable")
        pytest.skip(f"symlink unsupported by host: {exc}")
    except NotImplementedError as exc:
        pytest.skip(f"symlink unsupported by Python/filesystem: {exc}")

    result = SourceResolver().resolve(
        source, policy(roots=(str(tmp_path / "relocated"),))
    )

    assert result.status is ResolutionStatus.RESOLVED
    assert result.source is source
    assert result.resolved_locator == str(symlink)
    assert result.resolved_locator != str(target)

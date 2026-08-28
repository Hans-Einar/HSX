"""Classified executable legacy oracles for DBG-SL-001-005-001.

These tests deliberately describe current legacy behavior before RF-004 adapters and typed
services exist.  Assertions marked ``legacy_oracle_known_bad`` are evidence of behavior that
the frozen ``dbg.resolver-inspection/1`` contract changes or retires; they are not target
conformance tests.
"""

from __future__ import annotations

import ast
import errno
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_SRC = REPO_ROOT / "python"
for entry in (REPO_ROOT, PYTHON_SRC):
    if str(entry) not in sys.path:
        sys.path.append(str(entry))

from hsx_dap import HSXDebugAdapter
from hsx_dbg.symbols import SymbolIndex
from python.execd import ExecutiveState
from python.source_map import SourceMap


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "rf004"
MANIFEST_PATH = FIXTURE_DIR / "legacy_oracle_manifest.json"
SYMBOL_V1_PATH = FIXTURE_DIR / "legacy_symbols_v1.sym"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest() -> dict[str, Any]:
    return _load_json(MANIFEST_PATH)


def _case(case_id: str) -> dict[str, Any]:
    matches = [entry for entry in _manifest()["cases"] if entry["id"] == case_id]
    assert len(matches) == 1, f"oracle case {case_id!r} must be unique"
    return matches[0]


def _current_value(case_id: str) -> Any:
    return _case(case_id)["current_behavior"]["value"]


def _materialize_source_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[dict[str, Any], SourceMap]:
    template = _load_json(FIXTURE_DIR / "source_map_v1.template.json")
    monkeypatch.chdir(tmp_path)
    (tmp_path / template["project_root"]).mkdir(parents=True, exist_ok=True)
    for source in template["sources"]:
        for locator in source["oracle_existing_locators"]:
            target = tmp_path / locator
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source["oracle_content"], encoding="utf-8")
    source_map = SourceMap(
        project_root=Path(template["project_root"]),
        prefix_map=template["prefix_map"],
        sources=template["sources"],
    )
    return template, source_map


def _all_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _all_strings(key)
            yield from _all_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _all_strings(child)


def _symlink_skip_category(
    exc: BaseException,
    *,
    platform: str = sys.platform,
) -> str | None:
    if isinstance(exc, NotImplementedError):
        return "SKIP_SYMLINK_UNSUPPORTED"
    if not isinstance(exc, OSError):
        return None
    if platform == "win32" and getattr(exc, "winerror", None) == 1314:
        return "SKIP_SYMLINK_PRIVILEGE"
    unsupported_errnos = {
        value
        for name in ("ENOSYS", "ENOTSUP", "EOPNOTSUPP")
        if (value := getattr(errno, name, None)) is not None
    }
    if exc.errno in unsupported_errnos or (
        platform == "win32" and getattr(exc, "winerror", None) == 50
    ):
        return "SKIP_SYMLINK_UNSUPPORTED"
    return None


def test_oracle_manifest_is_complete_classified_and_nonconformant() -> None:
    manifest = _manifest()
    assert manifest["schema"] == "hsx.debug.rf004-legacy-oracle/1"
    assert manifest["slice"] == "DBG-SL-001-005-001"
    assert manifest["frozen_interface"] == "dbg.resolver-inspection/1"
    assert manifest["scope"] == "legacy_oracle_only"
    assert manifest["target_conformance"] is False

    required_ids = {
        "address_hidden_16bit_mask",
        "address_narrow_descriptor_overflow",
        "address_wide_descriptor_resolved_unmasked",
        "artifact_hxe_crc_mismatch",
        "artifact_malformed_json",
        "artifact_schema_version",
        "line_duplicate_candidate_order",
        "location_register_evidence",
        "location_stack_evidence",
        "source_case_colliding_logical_paths",
        "source_host_locator_case_collision",
        "source_duplicate_basename_alias",
        "source_basename_without_locator",
        "source_exact_requested_path",
        "source_first_candidate",
        "source_multiple_line_candidates",
        "source_prefix_map",
        "source_relocated_root",
        "source_symlink",
        "stack_fixed_r7_unwinding",
        "stack_mixed_live_read_coherence",
        "stack_partial_fp_cycle",
        "stack_partial_read_failure",
        "symbol_duplicate_candidate_order",
        "symbol_first_candidate",
        "sym_v1_functions_labels_locals_globals",
        "sym_v1_instruction_source_metadata",
        "sym_v1_memory_regions",
        "unknown_frame_fallback",
    }
    cases = manifest["cases"]
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))
    assert set(ids) == required_ids

    allowed = set(manifest["classifications"])
    assert allowed == {"preserve", "change_intentionally", "retire"}
    assert {case["classification"] for case in cases} == allowed
    frozen_categories = {
        "ContextBindingStatus.UNAVAILABLE",
        "InspectionStatus.COMPLETE",
        "InspectionStatus.CORRUPT",
        "InspectionStatus.PARTIAL",
        "InspectionStatus.UNAVAILABLE",
        "InspectionStatus.UNKNOWN_HANDLE",
        "MemoryRegion",
        "ResolutionStatus.AMBIGUOUS",
        "ResolutionStatus.ARTIFACT_MISMATCH",
        "ResolutionStatus.CASE_COLLISION",
        "ResolutionStatus.CORRUPT",
        "ResolutionStatus.RESOLVED",
        "ResolutionStatus.SCHEMA_UNSUPPORTED",
        "ResolutionStatus.UNAVAILABLE",
        "SourceRef",
    }
    for case in cases:
        assert case["classification"] in allowed
        assert case["provenance"]["kind"]
        assert case["provenance"]["path"]
        assert case["current_behavior"]["observation"]
        assert case["frozen_target"]["interface"]
        assert case["frozen_target"]["category"] in frozen_categories
        assert case["frozen_target"]["expectation"]
        assert case["legacy_output_is_target_conformance"] is False
        assert isinstance(case["known_bad_legacy_output"], bool)
        if case["classification"] == "retire":
            assert case["known_bad_legacy_output"] is True
    assert Counter(case["classification"] for case in cases) == {
        "preserve": 13,
        "change_intentionally": 8,
        "retire": 8,
    }


def test_frozen_address_and_source_boundaries_are_explicit() -> None:
    raw = _load_json(SYMBOL_V1_PATH)
    fixture_wide_address = next(
        item["address"]
        for item in raw["symbols"]["functions"]
        if item["name"] == "wide_address"
    )

    hidden_mask = _case("address_hidden_16bit_mask")
    narrow = _case("address_narrow_descriptor_overflow")
    wide = _case("address_wide_descriptor_resolved_unmasked")
    assert "address_category" not in hidden_mask["frozen_target"]
    assert narrow["inputs"]["address"] == fixture_wide_address == 0x10020
    assert narrow["inputs"]["descriptor"] == {
        "space": "code",
        "width_bits": 16,
        "legal_range_start": 0,
        "legal_range_length_units": 0x10000,
        "wrap_policy": "FORBIDDEN",
    }
    assert narrow["frozen_target"]["category"] == "ResolutionStatus.CORRUPT"
    assert narrow["frozen_target"]["address_category"] == "AddressStatus.OVERFLOW"
    assert wide["inputs"]["address"] == fixture_wide_address
    assert wide["inputs"]["descriptor"] == {
        "space": "code",
        "width_bits": 24,
        "legal_range_start": 0,
        "legal_range_length_units": 0x20000,
        "wrap_policy": "FORBIDDEN",
    }
    assert wide["frozen_target"]["category"] == "ResolutionStatus.RESOLVED"
    assert wide["frozen_target"]["address_category"] == "AddressStatus.VALID"
    assert wide["frozen_target"]["value"] == {
        "space": "code",
        "unsigned_value": 0x10020,
    }

    case_identity = _case("source_case_colliding_logical_paths")["frozen_target"]
    case_collision = _case("source_host_locator_case_collision")
    assert case_identity["category"] == "SourceRef"
    assert case_identity["logical_ids"] == ["src/Case.c", "src/case.c"]
    assert len(set(case_identity["logical_ids"])) == 2
    assert case_collision["inputs"] == {
        "source_logical_ids": case_identity["logical_ids"],
        "host_locator_capability": "cannot_address_both_exact_spellings",
    }
    assert case_collision["frozen_target"]["category"] == "ResolutionStatus.CASE_COLLISION"
    assert case_collision["frozen_target"]["resolved_locator"] is None

    basename_identity = _case("source_duplicate_basename_alias")["frozen_target"]
    no_locator = _case("source_basename_without_locator")
    ambiguity = _case("source_first_candidate")["frozen_target"]
    assert basename_identity["category"] == "SourceRef"
    assert basename_identity["logical_ids"] == [
        "src/alpha/unit.c",
        "lib/beta/unit.c",
    ]
    assert len(set(basename_identity["logical_ids"])) == 2
    assert no_locator["inputs"] == {
        "source_logical_id": "unit.c",
        "existing_winning_tier_locators": [],
    }
    assert no_locator["frozen_target"]["category"] == "ResolutionStatus.UNAVAILABLE"
    assert no_locator["frozen_target"]["resolved_locator"] is None
    assert ambiguity["source_logical_id"] == "src/ambiguous.c"
    assert ambiguity["winning_tier"] == "PREFIX"
    assert ambiguity["candidate_locators"] == [
        "candidate_a/src/ambiguous.c",
        "candidate_b/src/ambiguous.c",
    ]
    assert ambiguity["category"] == "ResolutionStatus.AMBIGUOUS"
    assert ambiguity["resolved_locator"] is None

    source_resolver_cases = [
        case
        for case in _manifest()["cases"]
        if case["frozen_target"]["interface"] == "SourceResolver.resolve"
    ]
    assert {
        case["id"]
        for case in source_resolver_cases
        if case["frozen_target"]["category"] == "ResolutionStatus.CASE_COLLISION"
    } == {"source_host_locator_case_collision"}


def test_oracle_fixtures_are_deterministic_and_have_no_host_locator_identity() -> None:
    fixture_paths = sorted(path for path in FIXTURE_DIR.iterdir() if path.is_file())
    assert [path.name for path in fixture_paths] == [
        "legacy_oracle_manifest.json",
        "legacy_symbols_image_mismatch.sym",
        "legacy_symbols_malformed.sym",
        "legacy_symbols_v1.sym",
        "legacy_symbols_version2.sym",
        "source_map_v1.template.json",
    ]
    forbidden_host_locator = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/(?:Users|home|tmp)/)")
    for path in fixture_paths:
        raw = path.read_bytes()
        assert raw.endswith(b"\n")
        if path.name == "legacy_symbols_malformed.sym":
            continue
        parsed_once = json.loads(raw.decode("utf-8"))
        parsed_twice = json.loads(path.read_text(encoding="utf-8"))
        assert parsed_once == parsed_twice
        assert not any(forbidden_host_locator.match(value) for value in _all_strings(parsed_once))


def test_preserve_sym_v1_instruction_source_metadata_and_candidate_order() -> None:
    raw = _load_json(SYMBOL_V1_PATH)
    assert raw["version"] == 1
    symbol_index = SymbolIndex(SYMBOL_V1_PATH)

    assert symbol_index.lookup_pc(0x100) == _current_value("sym_v1_instruction_source_metadata")
    assert symbol_index.lookup_symbol("shared") == _current_value("symbol_duplicate_candidate_order")
    assert symbol_index.lookup_line("src/main.c", 12) == _current_value("line_duplicate_candidate_order")


def test_preserve_sym_v1_functions_labels_locals_globals_and_memory_regions() -> None:
    raw = _load_json(SYMBOL_V1_PATH)
    symbol_index = SymbolIndex(SYMBOL_V1_PATH)
    expected = _current_value("sym_v1_functions_labels_locals_globals")

    assert symbol_index.lookup_symbol("main") == expected["function_main"]
    assert symbol_index.lookup_symbol("loop") == expected["label_loop"]
    for function_name, function_locals in expected["locals_for_function"].items():
        assert symbol_index.locals_for_function(function_name) == function_locals
    assert symbol_index.globals_list() == expected["globals_list"]
    assert raw["memory_regions"] == _current_value("sym_v1_memory_regions")


def test_legacy_oracle_known_bad_hidden_16bit_masks_are_observable() -> None:
    symbol_index = SymbolIndex(SYMBOL_V1_PATH)
    expected = _current_value("address_hidden_16bit_mask")

    assert symbol_index.lookup_symbol("wide_address") == expected["wide_address_lookup"]
    assert symbol_index.lookup_pc(expected["wide_instruction_alias"]) == symbol_index.lookup_pc(0x10004)
    assert symbol_index.lookup_pc(0x10004)["file"] == "src/wide.c"


def test_legacy_oracle_known_bad_case_and_basename_aliases_are_observable() -> None:
    symbol_index = SymbolIndex(SYMBOL_V1_PATH)
    case_expected = _current_value("source_case_colliding_logical_paths")
    basename_expected = _current_value("source_duplicate_basename_alias")

    assert symbol_index.lookup_line("src/Case.c", 50) == case_expected["src/Case.c"]
    assert symbol_index.lookup_line("src/case.c", 50) == case_expected["src/case.c"]
    assert symbol_index.lookup_line("unit.c", 40) == basename_expected["basename_query"]
    expected_candidates = basename_expected["full_path_unordered_candidates"]
    assert sorted(symbol_index.lookup_line("src/alpha/unit.c", 40)) == expected_candidates
    assert sorted(symbol_index.lookup_line("lib/beta/unit.c", 40)) == expected_candidates


def test_legacy_oracle_known_bad_frontend_selects_first_symbol_and_line_candidate() -> None:
    symbol_index = SymbolIndex(SYMBOL_V1_PATH)
    symbol_harness = SimpleNamespace(
        client=object(),
        current_pid=1,
        _symbol_mapper=symbol_index,
    )
    symbol_result = HSXDebugAdapter._lookup_symbol_metadata(symbol_harness, "shared")
    assert symbol_result == _current_value("symbol_first_candidate")

    line_harness = SimpleNamespace(
        _symbol_mapper=symbol_index,
        logger=logging.getLogger("rf004-legacy-oracle"),
        _parse_address=lambda _breakpoint: None,
    )
    line_result = HSXDebugAdapter._resolve_breakpoint_addresses(
        line_harness,
        "src/main.c",
        12,
        {},
    )
    assert line_result == _current_value("source_multiple_line_candidates")


def test_preserve_source_map_exact_prefix_and_relocated_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, source_map = _materialize_source_template(tmp_path, monkeypatch)

    exact = source_map.resolve("project_root/src/exact.c")
    prefix = source_map.resolve("./src/prefix.c")
    relocated = source_map.resolve("./src/relocated.c", search_roots=[Path("new_root")])

    assert exact.as_posix() == _current_value("source_exact_requested_path")
    assert prefix.as_posix() == _current_value("source_prefix_map")
    assert relocated.relative_to(tmp_path).as_posix() == _current_value("source_relocated_root")


def test_preserve_source_map_symlink_with_explicit_supported_or_skip_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    template, source_map = _materialize_source_template(tmp_path, monkeypatch)
    case = _case("source_symlink")
    assert case["platform_evidence"]["allowed_outcomes"] == [
        "SUPPORTED",
        "SKIP_SYMLINK_PRIVILEGE",
        "SKIP_SYMLINK_UNSUPPORTED",
    ]
    source = next(item for item in template["sources"] if item["case_id"] == "source_symlink")
    target = tmp_path / "shared" / "symlink.c"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source["oracle_content"], encoding="utf-8")
    locator = tmp_path / case["current_behavior"]["value"]
    locator.parent.mkdir(parents=True, exist_ok=True)
    try:
        locator.symlink_to(target)
    except NotImplementedError as exc:
        category = _symlink_skip_category(exc)
        assert category == "SKIP_SYMLINK_UNSUPPORTED"
        pytest.skip(f"{category}: {exc}")
    except OSError as exc:
        category = _symlink_skip_category(exc)
        if category is not None:
            pytest.skip(f"{category}: {exc}")
        raise

    resolved = source_map.resolve("./src/symlink.c", search_roots=[Path("new_root")])
    assert resolved == locator
    assert resolved.read_bytes() == target.read_bytes()


def test_symlink_skip_classification_is_narrow_and_portable() -> None:
    privilege = OSError(errno.EACCES, "symlink privilege unavailable")
    privilege.winerror = 1314
    unsupported = OSError(errno.ENOSYS, "symlink unsupported")
    unrelated = OSError(errno.EIO, "unrelated filesystem failure")

    assert _symlink_skip_category(privilege, platform="win32") == "SKIP_SYMLINK_PRIVILEGE"
    assert _symlink_skip_category(privilege, platform="linux") is None
    assert _symlink_skip_category(NotImplementedError()) == "SKIP_SYMLINK_UNSUPPORTED"
    assert _symlink_skip_category(unsupported) == "SKIP_SYMLINK_UNSUPPORTED"
    assert _symlink_skip_category(unrelated) is None


def test_legacy_oracle_known_bad_source_map_selects_first_existing_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, source_map = _materialize_source_template(tmp_path, monkeypatch)
    resolved = source_map.resolve("src/ambiguous.c")
    assert resolved.as_posix() == _current_value("source_first_candidate")
    assert (tmp_path / "candidate_b/src/ambiguous.c").exists()


def test_malformed_sym_records_corrupt_target_category() -> None:
    case = _case("artifact_malformed_json")
    assert case["frozen_target"]["category"] == "ResolutionStatus.CORRUPT"
    with pytest.raises(json.JSONDecodeError):
        SymbolIndex(FIXTURE_DIR / "legacy_symbols_malformed.sym")


def test_legacy_oracle_known_bad_version_and_image_mismatch_are_accepted() -> None:
    version_case = _case("artifact_schema_version")
    version_index = SymbolIndex(FIXTURE_DIR / "legacy_symbols_version2.sym")
    assert version_index.lookup_symbol("version_two") == version_case["current_behavior"]["value"]
    assert version_case["frozen_target"]["category"] == "ResolutionStatus.SCHEMA_UNSUPPORTED"

    mismatch_case = _case("artifact_hxe_crc_mismatch")
    mismatch_raw = _load_json(FIXTURE_DIR / "legacy_symbols_image_mismatch.sym")
    assert mismatch_raw["hxe_crc"] == mismatch_case["inputs"]["fixture_hxe_crc32"]
    assert mismatch_raw["hxe_crc"] != mismatch_case["inputs"]["expected_hxe_crc32"]
    mismatch_index = SymbolIndex(FIXTURE_DIR / "legacy_symbols_image_mismatch.sym")
    assert mismatch_index.lookup_symbol("wrong_image") == mismatch_case["current_behavior"]["value"]
    assert mismatch_case["frozen_target"]["category"] == "ResolutionStatus.ARTIFACT_MISMATCH"


def test_partial_stack_and_location_cases_reference_existing_executable_evidence() -> None:
    evidence_ids = {
        "location_register_evidence",
        "location_stack_evidence",
        "stack_fixed_r7_unwinding",
        "stack_partial_fp_cycle",
        "stack_partial_read_failure",
    }
    for case_id in evidence_ids:
        provenance = _case(case_id)["provenance"]
        assert provenance["kind"] == "existing_test_evidence"
        test_path = REPO_ROOT / provenance["path"]
        tree = ast.parse(test_path.read_text(encoding="utf-8"), filename=str(test_path))
        function_names = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert set(provenance["symbols"]) <= function_names


def test_legacy_oracle_known_bad_unknown_frame_falls_back_to_first_frame() -> None:
    first_frame = object()
    another_frame = object()
    harness = SimpleNamespace(_frames={7: first_frame, 8: another_frame})

    assert HSXDebugAdapter._resolve_frame(harness, 999) is first_frame
    assert _case("unknown_frame_fallback")["frozen_target"]["category"] == (
        "InspectionStatus.UNKNOWN_HANDLE"
    )


class _MixedReadStackHarness:
    """Duck-typed legacy stack receiver that makes the read revisions observable."""

    default_stack_frames = 4

    def __init__(self) -> None:
        self.read_revisions: list[int] = []

    def get_task(self, _pid: int) -> dict[str, Any]:
        return {"pid": 1}

    def request_dump_regs(self, _pid: int) -> dict[str, Any]:
        self.read_revisions.append(1)
        registers = [0] * 16
        registers[7] = 0x8010
        return {
            "pc": 0x100,
            "sp": 0x8000,
            "sp_effective": 0x8000,
            "fp": 0x8010,
            "regs": registers,
            "stack_base": 0x8000,
            "stack_limit": 0x8000,
            "stack_size": 0x100,
        }

    def _read_stack_words(self, _pid: int, _address: int, _count: int) -> list[int]:
        self.read_revisions.append(2)
        return [0, 0]

    def symbol_lookup_addr(self, _pid: int, _address: int) -> None:
        return None

    def symbol_lookup_line(self, _pid: int, _address: int) -> None:
        return None


def test_legacy_oracle_known_bad_stack_merges_mixed_live_read_revisions() -> None:
    harness = _MixedReadStackHarness()
    result = ExecutiveState.stack_info(harness, 1, max_frames=2)
    expected = _current_value("stack_mixed_live_read_coherence")

    assert harness.read_revisions == expected["read_revisions"]
    assert result["errors"] == expected["errors"]
    assert len(result["frames"]) == 1
    assert "context" not in result
    assert "snapshot" not in result
    target = _case("stack_mixed_live_read_coherence")["frozen_target"]
    assert target["category"] == "ContextBindingStatus.UNAVAILABLE"
    assert target["diagnostic"] == "portable_snapshot_evidence_unavailable"
    assert target["coherent_snapshot_unavailable_reserved_for"] == [
        "stop_token_absent_or_untyped",
        "snapshot_absent_or_untyped",
    ]

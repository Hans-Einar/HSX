"""Classified executable legacy oracles for DBG-SL-001-005-001.

These tests deliberately describe current legacy behavior before RF-004 adapters and typed
services exist.  Assertions marked ``legacy_oracle_known_bad`` are evidence of behavior that
the frozen ``dbg.resolver-inspection/1`` contract changes or retires; they are not target
conformance tests.
"""

from __future__ import annotations

import ast
import json
import logging
import re
import sys
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


def test_oracle_manifest_is_complete_classified_and_nonconformant() -> None:
    manifest = _manifest()
    assert manifest["schema"] == "hsx.debug.rf004-legacy-oracle/1"
    assert manifest["slice"] == "DBG-SL-001-005-001"
    assert manifest["frozen_interface"] == "dbg.resolver-inspection/1"
    assert manifest["scope"] == "legacy_oracle_only"
    assert manifest["target_conformance"] is False

    required_ids = {
        "address_hidden_16bit_mask",
        "artifact_hxe_crc_mismatch",
        "artifact_malformed_json",
        "artifact_schema_version",
        "line_duplicate_candidate_order",
        "location_register_evidence",
        "location_stack_evidence",
        "source_case_colliding_logical_paths",
        "source_duplicate_basename_alias",
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
    assert _case("address_hidden_16bit_mask")["frozen_target"]["address_category"] == (
        "AddressStatus.OVERFLOW"
    )


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
    assert symbol_index.locals_for_function("main")[0]["name"] == "counter"
    assert symbol_index.globals_list()[0]["name"] == expected["global"]
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
    ]
    source = next(item for item in template["sources"] if item["case_id"] == "source_symlink")
    target = tmp_path / "shared" / "symlink.c"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source["oracle_content"], encoding="utf-8")
    locator = tmp_path / case["current_behavior"]["value"]
    locator.parent.mkdir(parents=True, exist_ok=True)
    try:
        locator.symlink_to(target)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"SKIP_SYMLINK_PRIVILEGE: {exc}")

    resolved = source_map.resolve("./src/symlink.c", search_roots=[Path("new_root")])
    assert resolved == locator
    assert resolved.read_bytes() == target.read_bytes()


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
    assert target["diagnostic"] == "coherent_snapshot_unavailable"

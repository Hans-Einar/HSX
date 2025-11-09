from __future__ import annotations

import json
from argparse import Namespace
import importlib.util
from pathlib import Path

import pytest

from python import asm as hsx_asm
from python import hld
_HSX_CC_BUILD_SPEC = importlib.util.spec_from_file_location(
    "hsx_cc_build",
    Path(__file__).resolve().parents[1] / "hsx-cc-build.py",
)
if _HSX_CC_BUILD_SPEC is None or _HSX_CC_BUILD_SPEC.loader is None:  # pragma: no cover - load failure guard
    raise RuntimeError("Unable to load hsx-cc-build.py for testing")
_HSX_CC_BUILD = importlib.util.module_from_spec(_HSX_CC_BUILD_SPEC)
_HSX_CC_BUILD_SPEC.loader.exec_module(_HSX_CC_BUILD)
HSXBuilder = _HSX_CC_BUILD.HSXBuilder
_HSXBuildError = _HSX_CC_BUILD.HSXBuildError


def _build_hxo_hxe(tmp_path: Path) -> tuple[bytes, bytes]:
    asm_lines = [
        ".text\n",
        ".entry main\n",
        "main:\n",
        "    LDI R1, 1\n",
        "    LDI R2, 2\n",
        "    ADD R3, R1, R2\n",
        "    BRK 0\n",
    ]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, local_symbols = hsx_asm.assemble(
        asm_lines,
        for_object=True,
    )
    metadata = json.loads(json.dumps(hsx_asm.LAST_METADATA))
    hxo_path = tmp_path / "module.hxo"
    hsx_asm.write_hxo_object(
        hxo_path,
        code_words=list(code),
        rodata=bytes(rodata),
        entry=entry,
        entry_symbol=entry_symbol,
        externs=externs,
        imports_decl=imports_decl,
        relocs=list(relocs),
        exports=dict(exports),
        local_symbols=dict(local_symbols),
        metadata=metadata,
    )
    hxe_path = tmp_path / "module.hxe"
    hld.write_hxe_v2(
        hxe_path,
        code_words=list(code),
        entry=entry,
        rodata=bytes(rodata),
        metadata=metadata,
        app_name="determinism-test",
        allow_multiple=False,
    )
    return hxo_path.read_bytes(), hxe_path.read_bytes()


def test_toolchain_outputs_are_deterministic(tmp_path: Path) -> None:
    first_hxo, first_hxe = _build_hxo_hxe(tmp_path)
    second_hxo, second_hxe = _build_hxo_hxe(tmp_path)
    assert first_hxo == second_hxo
    assert first_hxe == second_hxe


def _make_builder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> HSXBuilder:
    monkeypatch.chdir(tmp_path)
    stdlib_dir = tmp_path / "lib" / "hsx_std"
    stdlib_dir.mkdir(parents=True, exist_ok=True)
    stdlib_path = stdlib_dir / "stdlib.mvasm"
    if not stdlib_path.exists():
        stdlib_path.write_text("// stdlib stub\n", encoding="utf-8")
    args = Namespace(
        verbose=False,
        directory=None,
        build_dir=str(tmp_path / "build" / "debug"),
        debug=True,
        with_stdlib=False,
        clean=False,
        app_name=None,
        output=None,
        jobs=None,
        no_make=True,
    )
    return HSXBuilder(args)


def test_sources_json_deterministic_default_epoch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    builder = _make_builder(tmp_path, monkeypatch)
    source = tmp_path / "main.c"
    source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    builder.generate_sources_json([source])
    first_bytes = (builder.build_dir / "sources.json").read_bytes()
    builder.generate_sources_json([source])
    second_bytes = (builder.build_dir / "sources.json").read_bytes()
    assert first_bytes == second_bytes
    payload = json.loads(first_bytes.decode("utf-8"))
    assert payload["build_time"] == "1970-01-01T00:00:00Z"


def test_sources_json_respects_source_date_epoch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    builder = _make_builder(tmp_path, monkeypatch)
    source = tmp_path / "util.c"
    source.write_text("int util(void) { return 1; }\n", encoding="utf-8")
    builder.generate_sources_json([source])
    contents = (builder.build_dir / "sources.json").read_text(encoding="utf-8")
    payload = json.loads(contents)
    assert payload["build_time"] == "2023-11-14T22:13:20Z"
    # Second generation should keep the same timestamp
    builder.generate_sources_json([source])
    contents2 = (builder.build_dir / "sources.json").read_text(encoding="utf-8")
    assert contents == contents2

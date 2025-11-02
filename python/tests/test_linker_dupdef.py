from pathlib import Path

import pytest

from python import asm as hsx_asm
from python import hld as hsx_linker


def _write_object(source: str, path: Path) -> Path:
    lines = [line + "\n" for line in source.strip().splitlines()]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, local_symbols = hsx_asm.assemble(
        lines,
        for_object=True,
    )
    hsx_asm.write_hxo_object(
        path,
        code_words=code,
        rodata=rodata,
        entry=entry or 0,
        entry_symbol=entry_symbol,
        externs=externs,
        imports_decl=imports_decl,
        relocs=relocs,
        exports=exports,
        local_symbols=local_symbols,
        metadata=hsx_asm.LAST_METADATA,
    )
    return path


def test_linker_rejects_duplicate_symbol(tmp_path):
    src_a = """
    .text
    .export dup
    dup:
        RET
    """
    src_b = src_a

    obj_a = _write_object(src_a, tmp_path / "a.hxo")
    obj_b = _write_object(src_b, tmp_path / "b.hxo")

    with pytest.raises(ValueError, match="Duplicate symbol 'dup'"):
        hsx_linker.link_objects([obj_a, obj_b], tmp_path / "out.hxe")


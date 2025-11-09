import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_module(module_name: str, relative_path: str):
    root = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(module_name, root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


ASM = _load_module("asm", "asm.py")
LINKER = _load_module("hsx_linker", "hld.py")


def _build_object(source: str, path: Path) -> Path:
    text = textwrap.dedent(source).strip("\n")
    lines = [f"{line}\n" for line in text.splitlines()]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, local_symbols = ASM.assemble(
        lines,
        for_object=True,
    )
    ASM.write_hxo_object(
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
        metadata=ASM.LAST_METADATA,
    )
    return path


def test_linker_rejects_unresolved_imports(tmp_path):
    obj = _build_object(
        """
        .text
        .import ext_call
        .entry start
        start:
            CALL ext_call
            RET
        """,
        tmp_path / "missing.hxo",
    )

    with pytest.raises(ValueError, match="Unresolved imports"):
        LINKER.link_objects([obj], tmp_path / "out.hxe")

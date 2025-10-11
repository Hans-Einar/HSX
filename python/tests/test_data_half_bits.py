import importlib.util
from pathlib import Path


def _load_asm():
    root = Path(__file__).resolve().parents[1] / "asm.py"
    spec = importlib.util.spec_from_file_location("hsx_asm", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ASM = _load_asm()


def test_half_directive_preserves_raw_bits():
    lines = [
        ".data\n",
        "value:\n",
        "    .half 0x3C00, 0x0001\n",
    ]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _locals = ASM.assemble(lines)
    assert not rodata.startswith(b"\x00\x00")
    assert rodata[:4] == b"\x00\x3C\x01\x00"
    assert relocs == []

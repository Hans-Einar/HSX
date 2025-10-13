import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from python import asm as hsx_asm
import pytest


def _assemble(lines: list[str]) -> list[int]:
    code_words, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _locals = hsx_asm.assemble(lines)
    assert not relocs
    return code_words


def test_brk_encodes_opcode_and_immediate():
    lines = [
        ".text",
        ".entry start",
        "start:",
        "BRK",
        "BRK 5",
    ]
    code_words = _assemble(lines)
    assert code_words[0] == 0x7F000000
    assert code_words[1] == 0x7F000005


def test_brk_rejects_out_of_range_immediate():
    lines = [
        ".text",
        ".entry start",
        "start:",
        "BRK 300",
    ]
    with pytest.raises(ValueError):
        hsx_asm.assemble(lines)

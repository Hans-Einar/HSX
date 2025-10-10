import importlib.util
import textwrap
from pathlib import Path


def _load_asm():
    root = Path(__file__).resolve().parents[1] / "asm.py"
    spec = importlib.util.spec_from_file_location("hsx_asm", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ASM = _load_asm()


def assemble_source(src: str):
    text = textwrap.dedent(src)
    text = text.strip("\n")
    lines = [line + "\n" for line in text.splitlines()]
    return ASM.assemble(lines)


def test_data_section_emits_rodata_and_pointers():
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _local_symbols = assemble_source(
        """
        .data
        msg:
            .asciz "hi"
        table:
            .word msg
        .text
        .entry start
        start:
            LDI32 R1, msg
            RET
        """
    )
    assert not relocs
    assert exports.get('start', {}).get('section') == 'text'
    assert entry_symbol == 'start'
    assert entry == 0
    assert not externs
    assert not imports_decl
    assert rodata.startswith(b"hi\x00")
    assert len(rodata) == 7  # 3 bytes string + 4-byte pointer
    ptr = int.from_bytes(rodata[3:7], "little")
    assert ptr == ASM.RODATA_BASE
    assert code[1] == ASM.RODATA_BASE


def test_off16_fixup_for_data_offset():
    code, entry, *_ = assemble_source(
        """
        .data
            .byte 0xAA
        target:
            .byte 0xBB
        .text
        .entry start
        start:
            LDI R4, off16(target)
            RET
        """
    )
    # LDI encodes immediate in low 12 bits
    imm = code[0] & 0x0FFF
    assert imm == 1  # target is one byte after the first literal


def test_data_word_self_reference_requires_rodata_base():
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _local_symbols = assemble_source(
        """
        .data
        prefix:
            .byte 0
        label:
            .word label
        .text
        .entry start
        start:
            RET
        """
    )
    assert not relocs
    assert exports.get('start', {}).get('section') == 'text'
    assert entry_symbol == 'start'
    # word should point to its own absolute address in rodata
    offset = 1  # prefix byte
    expected = ASM.RODATA_BASE + offset
    value = int.from_bytes(rodata[offset:offset + 4], "little")
    assert value == expected
    assert len(code) == 1  # only RET

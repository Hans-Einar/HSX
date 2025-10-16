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
    text = textwrap.dedent(src).strip("\n")
    lines = [line + "\n" for line in text.splitlines()]
    return ASM.assemble(lines)


def test_local_relocations_resolved_in_image_mode():
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
            CALL foo
            JMP start
        foo:
            RET
        """
    )

    assert relocs == []
    assert not externs
    assert not imports_decl

    assert entry == 0
    assert entry_symbol == "start"

    # rodata should contain string + pointer to msg absolute address
    assert rodata.startswith(b"hi\x00"), rodata
    ptr_bytes = rodata[3:7]
    assert len(ptr_bytes) == 4
    ptr_value = int.from_bytes(ptr_bytes, "little")
    assert ptr_value == ASM.RODATA_BASE

    # LDI32 immediate is stored in the second word after the opcode
    assert code[1] == ASM.RODATA_BASE

    # CALL foo should be patched with the PC-relative offset to foo
    # start -> instructions: LDI32 (word 0 and 1), CALL foo (word 2), JMP start (word 3)
    # foo label is at offset 16 (4 instructions * 4 bytes)
    foo_addr = 16
    call_idx = 2
    call_pc = call_idx * 4
    call_word = code[call_idx]
    expected_offset_bytes = foo_addr - call_pc
    assert expected_offset_bytes % 4 == 0
    expected_offset_words = expected_offset_bytes // 4
    assert call_word & 0x0FFF == (expected_offset_words & 0x0FFF)

    # JMP start should loop back to address 0
    jmp_word = code[3]
    assert jmp_word & 0x0FFF == 0


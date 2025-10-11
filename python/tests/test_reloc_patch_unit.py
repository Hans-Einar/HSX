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


def test_set_imm12_positive():
    word = ASM.emit_word(ASM.OPC["LDI"], rd=3, imm=0)
    patched = ASM.set_imm12(word, 0x123)
    assert patched & 0x0FFF == 0x123


def test_set_imm12_negative():
    word = ASM.emit_word(ASM.OPC["JMP"], imm=0)
    patched = ASM.set_imm12(word, -8)
    assert patched & 0x0FFF == (0x1000 - 8)


def test_set_imm12_out_of_range_raises():
    word = ASM.emit_word(ASM.OPC["LDI"], imm=0)
    try:
        ASM.set_imm12(word, 4096)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for out-of-range immediate")


def test_patch_call_and_mem_offsets():
    base_call = ASM.emit_word(ASM.OPC["CALL"], imm=0)
    patched_call = ASM.set_imm12(base_call, 64)
    assert patched_call & 0x0FFF == 64

    base_mem = ASM.emit_word(ASM.OPC["LD"], rd=1, rs1=2, imm=0)
    patched_mem = ASM.set_imm12(base_mem, 255)
    assert patched_mem & 0x0FFF == 255


def test_ldi32_immediate_patched_via_assembler():
    lines = [
        ".data\n",
        "target:\n",
        "    .word 0\n",
        ".text\n",
        ".entry start\n",
        "start:\n",
        "    LDI32 R4, target\n",
        "    RET\n",
    ]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, local_symbols = ASM.assemble(lines)
    assert relocs == []
    target_info = local_symbols.get("target", {})
    assert target_info.get("section") == "data"
    abs_addr = target_info.get("abs_addr")
    assert abs_addr is not None
    assert code[1] == abs_addr

import importlib.util
import math
from pathlib import Path

from platforms.python.host_vm import MiniVM, f16_to_f32, f32_to_f16


def _load_asm():
    root = Path(__file__).resolve().parents[1] / "asm.py"
    spec = importlib.util.spec_from_file_location("hsx_asm", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ASM = _load_asm()


def test_f16_roundtrip_specials():
    assert f16_to_f32(0x0000) == 0.0
    assert math.copysign(1.0, f16_to_f32(0x8000)) < 0
    assert f16_to_f32(0x7C00) == float("inf")
    assert f16_to_f32(0xFC00) == float("-inf")
    assert math.isnan(f16_to_f32(0x7E00))

    # Subnormal round-trip retains magnitude in range
    sub = f16_to_f32(0x0001)
    assert 0 < sub < 2 ** -14
    assert f32_to_f16(sub) == 0x0001

    assert f32_to_f16(0.0) == 0x0000
    assert f32_to_f16(-0.0) & 0x8000
    assert f32_to_f16(float("inf")) == 0x7C00
    assert f32_to_f16(float("-inf")) == 0xFC00


def _assemble(lines):
    text = [line + "\n" for line in lines]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _locals = ASM.assemble(text)
    assert not relocs
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code)
    return code_bytes, entry, rodata


def test_f2i_truncates_toward_zero():
    half_pos = 0x3E00
    half_neg = 0xC200
    code, entry, rodata = _assemble([
        ".text",
        ".entry start",
        "start:",
        f"    LDI32 R1, {half_pos}",
        "    F2I R2, R1",
        f"    LDI32 R3, {half_neg}",
        "    F2I R4, R3",
        "    RET",
    ])
    vm = MiniVM(code, entry=entry, rodata=rodata)
    while vm.running:
        vm.step()
    expected_pos = int(f16_to_f32(half_pos)) & 0xFFFFFFFF
    expected_neg = int(f16_to_f32(half_neg)) & 0xFFFFFFFF
    assert vm.regs[2] == expected_pos
    assert vm.regs[4] == expected_neg

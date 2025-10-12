import importlib.util
import textwrap
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


def _run_program(source: str) -> MiniVM:
    text = textwrap.dedent(source).strip("\n")
    lines = [f"{line}\n" for line in text.splitlines()]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _locals = ASM.assemble(lines)
    assert not relocs
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code)
    vm = MiniVM(code_bytes, entry=entry, rodata=rodata)
    while vm.running:
        vm.step()
    return vm


def test_fp16_ops_round_ties_to_even():
    half_add_a = 0x0400
    half_add_b = 0x0401
    expected_add = f32_to_f16(f16_to_f32(half_add_a) + f16_to_f32(half_add_b))

    half_mul_a = 0x0400
    half_mul_b = 0x1000
    expected_mul = f32_to_f16(f16_to_f32(half_mul_a) * f16_to_f32(half_mul_b))

    half_div_a = 0x0A84
    half_div_b = 0x5200
    expected_div = f32_to_f16(f16_to_f32(half_div_a) / f16_to_f32(half_div_b))

    program = f"""
    .text
    .entry start
    start:
        LDI32 R1, 0x{half_add_a:08X}
        LDI32 R2, 0x{half_add_b:08X}
        FADD R3, R1, R2

        LDI32 R4, 0x{half_mul_b:08X}
        FMUL R5, R1, R4

        LDI32 R6, 0x{half_div_a:08X}
        LDI32 R7, 0x{half_div_b:08X}
        FDIV R8, R6, R7
        RET
    """

    vm = _run_program(program)

    assert vm.regs[3] & 0xFFFF == expected_add
    assert vm.regs[5] & 0xFFFF == expected_mul
    assert vm.regs[8] & 0xFFFF == expected_div

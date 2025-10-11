import importlib.util
from pathlib import Path

from platforms.python.host_vm import MiniVM


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_asm():
    root = Path(__file__).resolve().parents[1] / "asm.py"
    spec = importlib.util.spec_from_file_location("hsx_asm", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()
ASM = _load_asm()


def test_float_store_and_load_roundtrip():
    ir = """
@dst = global float 0.000000e+00
@src = global float 6.500000e+00

declare half @llvm.convert.to.fp16.f32(float)

define dso_local i32 @main() {
entry:
  %srcptr = getelementptr inbounds float, ptr @src, i32 0
  %val = load float, ptr %srcptr, align 4
  store float %val, ptr @dst, align 4
  %dstptr = getelementptr inbounds float, ptr @dst, i32 0
  %loaded = load float, ptr %dstptr, align 4
  %half = call half @llvm.convert.to.fp16.f32(float %loaded)
  ret i32 0
}
"""

    asm_text = HSX_LLC.compile_ll_to_mvasm(ir, trace=False)
    assert 'LD R' in asm_text
    assert asm_text.count('LD R') >= 2
    assert 'ST [R14+0], R' in asm_text

    lines = [line + "\n" for line in asm_text.splitlines()]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _locals = ASM.assemble(lines)
    assert not relocs
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code)
    vm = MiniVM(code_bytes, entry=entry, rodata=rodata)
    while vm.running:
        vm.step()
    assert vm.regs[0] == 0

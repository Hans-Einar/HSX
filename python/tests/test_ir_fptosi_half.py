import importlib.util
from pathlib import Path


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def compile_lines(ir_source: str):
    hsx_llc = _load_hsx_llc()
    asm = hsx_llc.compile_ll_to_mvasm(ir_source, trace=False)
    return [ln for ln in asm.splitlines() if ln and not ln.startswith(';')]


def test_fptosi_direct_half():
    ir = """define dso_local i32 @conv(half %h) {\nentry:\n  %r = fptosi half %h to i32\n  ret i32 %r\n}\n"""
    lines = compile_lines(ir)
    assert any(line.startswith('F2I ') for line in lines)
    assert lines[-3].startswith('MOV R0,')
    assert lines[-2] == 'POP R7'
    assert lines[-1] == 'RET'


def test_fptosi_via_float_alias():
    ir = """define dso_local i32 @via_float(half %h) {\nentry:\n  %f = fpext half %h to float\n  %r = fptosi float %f to i32\n  ret i32 %r\n}\n"""
    lines = compile_lines(ir)
    assert any(line.startswith('F2I ') for line in lines)
    assert not any(line.startswith('I2F ') for line in lines)


def test_fptosi_after_half_ops():
    ir = """define dso_local i32 @pipeline(half %a, half %b) {\nentry:\n  %sum = fadd half %a, %b\n  %wide = fpext half %sum to float\n  %back = fptrunc float %wide to half\n  %res = fadd half %back, %a\n  %out = fptosi half %res to i32\n  ret i32 %out\n}\n"""
    lines = compile_lines(ir)
    assert any(line.startswith('FADD ') for line in lines)
    assert any(line.startswith('F2I ') for line in lines)


def test_fp16_intrinsics_float_path():
    ir = """declare i16 @llvm.convert.to.fp16.f32(float)
declare float @llvm.convert.from.fp16.f32(i16)

define dso_local i32 @use_intrinsics(float %f, i16 %bits) {
entry:
  %h = call i16 @llvm.convert.to.fp16.f32(float %f)
  %res = call float @llvm.convert.from.fp16.f32(i16 %bits)
  %out = fptosi float %res to i32
  ret i32 %out
}
"""
    lines = compile_lines(ir)
    assert any(line.startswith('F2I ') for line in lines)
    assert not any('llvm.convert' in line for line in lines)


def test_fp16_intrinsics_literal():
    ir = """declare i16 @llvm.convert.to.fp16.f32(float)

define dso_local i16 @use_literal() {
entry:
  %h = call i16 @llvm.convert.to.fp16.f32(float 1.500000e+00)
  ret i16 %h
}
"""
    lines = compile_lines(ir)
    assert any(line.startswith('LDI') or line.startswith('LDI32') for line in lines)
    assert not any('llvm.convert' in line for line in lines)

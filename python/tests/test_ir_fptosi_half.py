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
    assert lines[-2].startswith('MOV R0,')
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

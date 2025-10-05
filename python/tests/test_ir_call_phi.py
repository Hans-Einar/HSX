import importlib.util
from pathlib import Path


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def compile_to_lines(src: str):
    hsx_llc = _load_hsx_llc()
    asm = hsx_llc.compile_ll_to_mvasm(src, trace=False)
    return [line.rstrip() for line in asm.splitlines() if line.rstrip() and not line.startswith(';')]


def test_phi_inserts_moves_per_predecessor():
    ll = """define dso_local i32 @phi_example(i1 %cond, i32 %a, i32 %b) {
entry:
  br i1 %cond, label %then, label %else
then:
  br label %merge
else:
  br label %merge
merge:
  %phi = phi i32 [ %a, %then ], [ %b, %else ]
  ret i32 %phi
}
"""
    lines = compile_to_lines(ll)
    # Expect phi moves emitted in predecessor blocks
    then_idx = lines.index('phi_example__then:')
    then_block = lines[then_idx: then_idx + 4]
    assert any(line.startswith('MOV') and 'R2' in line for line in then_block), "phi move missing for then predecessor"
    else_idx = lines.index('phi_example__else:')
    else_block = lines[else_idx: else_idx + 4]
    assert any(line.startswith('MOV') and 'R3' in line for line in else_block), "phi move missing for else predecessor"
    merge_idx = lines.index('phi_example__merge:')
    assert lines[merge_idx + 1] == 'MOV R0, R7'
    assert lines[merge_idx + 2] == 'RET'


def test_call_argument_lowering():
    ll = """declare i32 @callee(i32, i32)

define dso_local i32 @caller(i32 %x) {
entry:
  %r = call i32 @callee(i32 %x, i32 5)
  ret i32 %r
}
"""
    lines = compile_to_lines(ll)
    assert 'LDI R2, 5' in lines
    assert 'CALL callee' in lines
    assert 'MOV R5, R0' in lines
    assert lines[-2:] == ['MOV R0, R5', 'RET']


def test_half_ops_lowering():
    ll = """declare i32 @use_val(i32)

define dso_local i32 @half_ops(half %a, half %b) {
entry:
  %sum = fadd half %a, %b
  %wide = fpext half %sum to float
  %back = fptrunc float %wide to half
  %res = fadd half %back, %a
  %call = call i32 @use_val(i32 0)
  %sum2 = add i32 %call, 1
  ret i32 %sum2
}
"""
    lines = compile_to_lines(ll)
    assert any(line.startswith('FADD ') for line in lines)
    assert any(line.startswith('CALL use_val') for line in lines)
    assert lines[-2].startswith('MOV R0,')
    assert 'CALL use_val' in lines
    assert lines[-1] == 'RET'
    assert lines[-2].startswith('MOV R0,')

def test_externs_for_defined_functions():
    ll = """define dso_local i32 @foo() {\nentry:\n  ret i32 1\n}\n\ndefine dso_local i32 @main() {\nentry:\n  %r = call i32 @foo()\n  ret i32 %r\n}\n"""
    asm = _load_hsx_llc().compile_ll_to_mvasm(ll, trace=False)
    lines = [line for line in asm.splitlines() if line and not line.startswith(';')]
    assert lines[0] == '.entry main'
    assert lines[1] == '.extern foo'
    assert lines[2] == '.extern main'
    assert lines[3] == '.text'

def test_imports_for_external_call():
    ll = """declare i32 @ext(i32)\n\ndefine dso_local i32 @wrap(i32 %x) {\nentry:\n  %r = call i32 @ext(i32 %x)\n  ret i32 %r\n}\n"""
    asm = _load_hsx_llc().compile_ll_to_mvasm(ll, trace=False)
    assert '.import ext' in asm.splitlines()

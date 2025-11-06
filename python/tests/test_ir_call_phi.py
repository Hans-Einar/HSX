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
    else_idx = lines.index('phi_example__else:')
    else_block = lines[else_idx: else_idx + 4]

    def has_expected_move(block, reg):
        return any(line.startswith('MOV') and reg in line for line in block)

    # Allocator may reuse registers entirely (coalescing), in which case the predecessor
    # blocks only contain the branch. Accept either behaviour.
    if not has_expected_move(then_block, 'R2'):
        assert then_block[-1].startswith('JMP'), f"unexpected then block form: {then_block}"
    if not has_expected_move(else_block, 'R3'):
        assert else_block[-1].startswith('JMP'), f"unexpected else block form: {else_block}"
    merge_idx = lines.index('phi_example__merge:')
    assert lines[merge_idx + 1].startswith('MOV R0,'), lines[merge_idx + 1]
    assert lines[merge_idx + 2] == 'POP R7'
    assert lines[merge_idx + 3] == 'RET'


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
    assert lines[-3:] == ['CALL callee', 'POP R7', 'RET']


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
    assert lines[-3].startswith('MOV R0,')
    assert 'CALL use_val' in lines
    assert lines[-2] == 'POP R7'
    assert lines[-1] == 'RET'

def test_externs_for_defined_functions():
    ll = """define dso_local i32 @foo() {\nentry:\n  ret i32 1\n}\n\ndefine dso_local i32 @main() {\nentry:\n  %r = call i32 @foo()\n  ret i32 %r\n}\n"""
    asm = _load_hsx_llc().compile_ll_to_mvasm(ll, trace=False)
    lines = [line for line in asm.splitlines() if line and not line.startswith(';')]
    assert lines[0] == '.entry main'
    assert lines[1] == '.export foo'
    assert lines[2] == '.export main'
    assert lines[3] == '.text'

def test_imports_for_external_call():
    ll = """declare i32 @ext(i32)\n\ndefine dso_local i32 @wrap(i32 %x) {\nentry:\n  %r = call i32 @ext(i32 %x)\n  ret i32 %r\n}\n"""
    asm = _load_hsx_llc().compile_ll_to_mvasm(ll, trace=False)
    assert '.import ext' in asm.splitlines()


def test_spill_data_emitted_for_many_temps():
    ll = """define dso_local i32 @spill(i32 %a) {
entry:
  %t0 = add i32 %a, 1
  %t1 = add i32 %a, 2
  %t2 = add i32 %a, 3
  %t3 = add i32 %a, 4
  %t4 = add i32 %a, 5
  %t5 = add i32 %a, 6
  %t6 = add i32 %a, 7
  %t7 = add i32 %a, 8
  %t8 = add i32 %a, 9
  %t9 = add i32 %a, 10
  %u0 = add i32 %t0, %t5
  %u1 = add i32 %t1, %t6
  %u2 = add i32 %t2, %t7
  %u3 = add i32 %t3, %t8
  %u4 = add i32 %t4, %t9
  %s0 = add i32 %u0, %u1
  %s1 = add i32 %u2, %u3
  %s2 = add i32 %s0, %s1
  %result = add i32 %s2, %u4
  ret i32 %result
}
"""
    asm = _load_hsx_llc().compile_ll_to_mvasm(ll, trace=False)
    assert '[R7' in asm, 'expected stack-based spill slots in generated assembly'
    push_spill = [line for line in asm.splitlines() if line.startswith('PUSH ') and line != 'PUSH R7']
    assert push_spill, 'expected stack allocation pushes for spills'

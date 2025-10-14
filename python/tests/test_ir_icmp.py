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


def test_icmp_eq_and_sgt_lowering():
    ll = """define dso_local i32 @cmp(i32 %a, i32 %b) {
entry:
  %cmp = icmp eq i32 %a, %b
  %gt = icmp sgt i32 %a, %b
  %sum = add i32 %cmp, %gt
  ret i32 %sum
}
"""
    lines = compile_to_lines(ll)
    # expect diff computation
    assert any(line.startswith("SUB ") and ", R1, R2" in line for line in lines)
    # boolean default initialisation
    assert any(line.startswith("LDI ") and line.endswith(", 0") for line in lines)
    # mask load for signed comparison
    assert any(line.startswith("LDI32 ") and "2147483648" in line for line in lines)
    assert any(line.startswith("AND ") for line in lines)
    assert lines[-3].startswith("MOV R0,")
    assert lines[-2] == "POP R7"
    assert lines[-1] == "RET"


def test_icmp_slt_lowering():
    ll = """define dso_local i32 @cmp_slt(i32 %a, i32 %b) {
entry:
  %lt = icmp slt i32 %a, %b
  ret i32 %lt
}
"""
    lines = compile_to_lines(ll)
    assert any(line.startswith("SUB ") and ", R1, R2" in line for line in lines)
    assert any(line.startswith("LDI32 ") and "2147483648" in line for line in lines)
    assert any(line.startswith("AND ") for line in lines)
    assert lines[-3].startswith("MOV R0,")
    assert lines[-2] == "POP R7"
    assert lines[-1] == "RET"

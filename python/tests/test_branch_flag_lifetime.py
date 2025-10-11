import importlib.util
from pathlib import Path


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


hsx_llc = _load_hsx_llc()


def test_cmp_followed_by_branch_without_flag_clobber():
    ir = """
define i32 @test(i32 %a, i32 %b) {
entry:
  %cmp = icmp eq i32 %a, %b
  br i1 %cmp, label %true, label %false

true:
  ret i32 1

false:
  ret i32 0
}
"""

    asm_text = hsx_llc.compile_ll_to_mvasm(ir, trace=False)
    lines = [line.strip() for line in asm_text.splitlines() if line.strip() and not line.strip().startswith(';')]

    safe_ops = {"LDI", "LDI32", "MOV"}

    for idx, line in enumerate(lines):
        if not line.upper().startswith("CMP"):
            continue
        found_branch = False
        for follow in lines[idx + 1 :]:
            if follow.endswith(":"):
                continue
            op = follow.split()[0].upper()
            if op.startswith("J"):
                found_branch = True
                break
            assert op in safe_ops, f"Instruction '{follow}' clobbers flags between CMP and branch"
        assert found_branch, "CMP not followed by branch"

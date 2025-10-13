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


def test_call_with_more_than_three_arguments_spills_to_stack():
    ir = """
declare i32 @callee(i32, i32, i32, i32)

define i32 @main() {
entry:
  %v = call i32 @callee(i32 1, i32 2, i32 3, i32 4)
  ret i32 %v
}
"""

    asm = hsx_llc.compile_ll_to_mvasm(ir, trace=False)
    lines = [line.strip() for line in asm.splitlines() if line.strip() and not line.strip().startswith(";")]

    call_idx = next(i for i, line in enumerate(lines) if line.startswith("CALL callee"))
    push_lines = [line for line in lines[:call_idx] if line.startswith("PUSH")]
    pop_lines = [line for line in lines[call_idx + 1 :] if line.startswith("POP")]

    assert len(push_lines) == 1, f"Expected one stack push, saw {push_lines}"
    assert len(pop_lines) == 1, f"Expected one stack pop, saw {pop_lines}"
    assert push_lines[0] == "PUSH R12" or push_lines[0].startswith("PUSH R"), "Unexpected push operand"
    assert pop_lines[0] == "POP R12", "Stack cleanup should pop into R12"


def test_call_with_six_arguments_pushes_three_words():
    ir = """
declare i32 @callee(i32, i32, i32, i32, i32, i32)

define i32 @main() {
entry:
  %v = call i32 @callee(i32 1, i32 2, i32 3, i32 4, i32 5, i32 6)
  ret i32 %v
}
"""

    asm = hsx_llc.compile_ll_to_mvasm(ir, trace=False)
    lines = [line.strip() for line in asm.splitlines() if line.strip() and not line.strip().startswith(";")]

    call_idx = next(i for i, line in enumerate(lines) if line.startswith("CALL callee"))
    push_lines = [line for line in lines[:call_idx] if line.startswith("PUSH")]
    pop_lines = [line for line in lines[call_idx + 1 :] if line.startswith("POP")]

    assert len(push_lines) == 3
    assert len(pop_lines) == 3
    assert all(line.startswith("PUSH ") for line in push_lines)
    assert all(line == "POP R12" for line in pop_lines)

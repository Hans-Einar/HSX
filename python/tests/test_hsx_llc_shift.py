import importlib.util
import textwrap
from pathlib import Path


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc_shift", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()


def test_lower_integer_shifts():
    llvm_ir = textwrap.dedent(
        """
        define dso_local i32 @main(i32 %a, i32 %b) {
        entry:
          %lsl = shl i32 %a, %b
          %lsr = lshr i32 %a, %b
          %asr = ashr i32 %a, %b
          ret i32 %lsl
        }
        """
    ).strip()

    asm = HSX_LLC.compile_ll_to_mvasm(llvm_ir, trace=False)
    assert "LSL" in asm
    assert "LSR" in asm
    assert "ASR" in asm


def test_lower_shift_immediates():
    llvm_ir = textwrap.dedent(
        """
        define dso_local i32 @main(i32 %a) {
        entry:
          %lhs = shl i32 %a, 3
          %rhs = ashr i32 %lhs, 1
          ret i32 %rhs
        }
        """
    ).strip()

    asm = HSX_LLC.compile_ll_to_mvasm(llvm_ir, trace=False)
    assert "LSL" in asm
    assert "ASR" in asm
    assert "LDI" in asm or "LDI32" in asm

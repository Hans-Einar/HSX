import importlib.util
import textwrap
from pathlib import Path


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc_carry", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()


def test_lower_uadd_with_overflow():
    llvm_ir = textwrap.dedent(
        """
        %struct = type { i32, i1 }
        define dso_local i1 @carry(i32 %a, i32 %b, ptr %out) {
        entry:
          %sum = call { i32, i1 } @llvm.uadd.with.overflow.i32(i32 %a, i32 %b)
          %carry = extractvalue { i32, i1 } %sum, 1
          %value = extractvalue { i32, i1 } %sum, 0
          store i32 %value, ptr %out
          ret i1 %carry
        }
        """
    ).strip()

    asm = HSX_LLC.compile_ll_to_mvasm(llvm_ir, trace=False)
    assert asm.count("ADD") >= 1
    assert "ADC" in asm
    assert "LDI" in asm  # zero seed for ADC
    assert "RET" in asm

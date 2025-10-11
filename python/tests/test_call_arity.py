import importlib.util
from pathlib import Path

import pytest


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


hsx_llc = _load_hsx_llc()


def test_call_with_more_than_three_arguments_is_rejected():
    ir = """
declare i32 @callee(i32, i32, i32, i32)

define i32 @main() {
entry:
  %v = call i32 @callee(i32 1, i32 2, i32 3, i32 4)
  ret i32 %v
}
"""

    with pytest.raises(hsx_llc.ISelError, match="more than 3 args"):
        hsx_llc.compile_ll_to_mvasm(ir, trace=False)

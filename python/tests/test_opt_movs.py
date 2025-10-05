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


def test_optimize_basic_mov_collapse():
    original = ["LDI R12, 99", "MOV R6, R12", "RET"]
    optimized = hsx_llc.optimize_movs(original)
    assert optimized == ["LDI R6, 99", "RET"]
    # ensure original list is untouched
    assert original == ["LDI R12, 99", "MOV R6, R12", "RET"]

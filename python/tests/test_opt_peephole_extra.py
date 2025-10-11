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


def test_optimize_removes_redundant_self_mov():
    original = ["MOV R5, R5", "RET"]
    optimized = hsx_llc.optimize_movs(original)
    assert optimized == ["RET"]


def test_optimize_collapses_ldi32_then_mov():
    original = ["LDI32 R12, 0x12345678", "MOV R5, R12", "RET"]
    optimized = hsx_llc.optimize_movs(original)
    assert optimized == ["LDI32 R5, 0x12345678", "RET"]

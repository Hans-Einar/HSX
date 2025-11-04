from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()


def _compile(ir: str) -> None:
    HSX_LLC.compile_ll_to_mvasm(ir, trace=False)


def _get_reg_alloc(function_name: str) -> dict[str, object]:
    info = HSX_LLC.LAST_DEBUG_INFO or {}
    for entry in info.get("functions", []):
        if entry.get("function") == function_name:
            alloc = entry.get("register_allocation")
            if alloc:
                return alloc
    raise AssertionError(f"register_allocation entry missing for {function_name}")


def test_register_allocation_metrics_present():
    ir = """
define i32 @main(i32 %a, i32 %b) {
entry:
  %sum = add i32 %a, %b
  ret i32 %sum
}
"""

    _compile(ir)
    alloc = _get_reg_alloc("main")
    summary = (HSX_LLC.LAST_DEBUG_INFO or {}).get("register_allocation_summary")
    assert summary is not None, "register allocation summary missing"
    assert summary["total_functions"] >= 1
    assert summary["max_pressure"] >= alloc["max_pressure"]
    assert summary["total_spills"] >= alloc["spill_count"]
    for key in (
        "max_pressure",
        "spill_count",
        "reload_count",
        "stack_slots",
        "stack_bytes",
        "available_registers",
        "used_register_count",
        "used_registers",
    ):
        assert key in alloc, f"{key} missing from allocation metrics"
    assert alloc["spill_count"] == 0
    assert alloc["reload_count"] == 0
    assert alloc["stack_bytes"] == 0
    assert alloc["used_register_count"] >= 1
    for reg in alloc["used_registers"]:
        assert isinstance(reg, str) and reg.startswith("R")


def test_register_allocation_spill_metrics():
    ir = """
define dso_local i32 @main() {
entry:
  %v1 = add i32 0, 1
  %v2 = add i32 0, 2
  %v3 = add i32 0, 3
  %v4 = add i32 0, 4
  %v5 = add i32 0, 5
  %v6 = add i32 0, 6
  %v7 = add i32 0, 7
  %v8 = add i32 0, 8
  %v9 = add i32 0, 9
  %v10 = add i32 0, 10
  %s1 = add i32 %v1, %v2
  %s2 = add i32 %s1, %v3
  %s3 = add i32 %s2, %v4
  %s4 = add i32 %s3, %v5
  %s5 = add i32 %s4, %v6
  %s6 = add i32 %s5, %v7
  %s7 = add i32 %s6, %v8
  %s8 = add i32 %s7, %v9
  %s9 = add i32 %s8, %v10
  ret i32 %s9
}
"""

    _compile(ir)
    alloc = _get_reg_alloc("main")
    summary = (HSX_LLC.LAST_DEBUG_INFO or {}).get("register_allocation_summary")
    assert summary is not None
    assert alloc["spill_count"] > 0
    assert alloc["reload_count"] > 0
    assert alloc["stack_slots"] >= 1
    assert alloc["stack_bytes"] >= 4
    assert summary["total_spills"] >= alloc["spill_count"]
    assert "main" in summary["functions_with_spills"]

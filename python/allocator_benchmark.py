#!/usr/bin/env python3
"""
allocator_benchmark.py - quick metrics report for hsx-llc register allocation

Generates a set of representative LLVM IR snippets and compares allocator
metrics across feature toggles (coalescing and live-range splitting).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

import importlib.util
from pathlib import Path

try:
    from tabulate import tabulate
except ImportError:  # pragma: no cover - fallback for environments without tabulate
    tabulate = None

def _load_hsx_llc():
    root = Path(__file__).resolve().parent / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()


@dataclass
class BenchmarkCase:
    name: str
    ir: str
    function: str


def _load_real_ir(name: str) -> str:
    path = Path("examples/tests/build") / name / "main.ll"
    if not path.exists():
        raise RuntimeError(f"missing IR sample: {path}")
    return path.read_text()


CASES: List[BenchmarkCase] = [
    BenchmarkCase(
        name="phi_coalesce",
        function="phi_example",
        ir="""
define dso_local i32 @phi_example(i1 %cond, i32 %a, i32 %b) {
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
""",
    ),
    BenchmarkCase(
        name="branch_chain",
        function="branch_chain",
        ir="""
define dso_local i32 @branch_chain(i32 %a, i32 %b) {
entry:
  %cmp = icmp sgt i32 %a, %b
  br i1 %cmp, label %gt, label %le

gt:
  %v1 = add i32 %a, %b
  %v2 = mul i32 %v1, 2
  br label %join

le:
  %v3 = sub i32 %b, %a
  %v4 = mul i32 %v3, 3
  br label %join

join:
  %phi = phi i32 [ %v2, %gt ], [ %v4, %le ]
  ret i32 %phi
}
""",
    ),
    BenchmarkCase(
        name="spill_chain",
        function="main",
        ir="""
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
""",
    ),
    BenchmarkCase(
        name="split_demo",
        function="split_demo",
        ir="""
define dso_local i32 @split_demo(i32 %a) {
entry:
  %keep = add i32 %a, 1
  %t0 = add i32 0, 1
  %t1 = add i32 %t0, 2
  %t2 = add i32 %t1, 3
  %t3 = add i32 %t2, 4
  %t4 = add i32 %t3, 5
  %t5 = add i32 %t4, 6
  %t6 = add i32 %t5, 7
  %t7 = add i32 %t6, 8
  %t8 = add i32 %t7, 9
  %t9 = add i32 %t8, 10
  %t10 = add i32 %t9, 11
  %t11 = add i32 %t10, 12
  %t12 = add i32 %t11, 13
  %t13 = add i32 %t12, 14
  %t14 = add i32 %t13, 15
  %t15 = add i32 %t14, 16
  ret i32 %keep
}
""",
    ),
    BenchmarkCase(
        name="call_chain",
        function="caller",
        ir="""
define dso_local i32 @leaf(i32 %v) {
entry:
  %r = add i32 %v, 1
  ret i32 %r
}

define dso_local i32 @helper(i32 %v) {
entry:
  %t1 = call i32 @leaf(i32 %v)
  %t2 = call i32 @leaf(i32 %t1)
  ret i32 %t2
}

define dso_local i32 @caller(i32 %x) {
entry:
  %a = call i32 @helper(i32 %x)
  %b = call i32 @helper(i32 %a)
  ret i32 %b
}
""",
    ),
    BenchmarkCase(
        name="mixed_arith",
        function="mixed",
        ir="""
define dso_local i32 @mixed(float %f, float %g, i32 %x) {
entry:
  %sum = fadd float %f, %g
  %int = fptosi float %sum to i32
  %res = add i32 %int, %x
  ret i32 %res
}
""",
    ),
    BenchmarkCase(
        name="std_mailbox",
        function="main",
        ir=_load_real_ir("test_stdio_mailbox_c"),
    ),
    BenchmarkCase(
        name="mailbox_consumer",
        function="main",
        ir=_load_real_ir("test_mailbox_consumer_c"),
    ),
    BenchmarkCase(
        name="mailbox_producer",
        function="main",
        ir=_load_real_ir("test_mailbox_producer_c"),
    ),
    BenchmarkCase(
        name="real_call_phi",
        function="main",
        ir=_load_real_ir("test_ir_call_phi"),
    ),
    BenchmarkCase(
        name="real_fptosi_half",
        function="main",
        ir=_load_real_ir("test_ir_fptosi_half"),
    ),
    BenchmarkCase(
        name="real_globals",
        function="main",
        ir=_load_real_ir("test_ir_globals"),
    ),
    BenchmarkCase(
        name="real_half_main",
        function="main",
        ir=_load_real_ir("test_ir_half_main"),
    ),
    BenchmarkCase(
        name="real_icmp",
        function="main",
        ir=_load_real_ir("test_ir_icmp"),
    ),
    BenchmarkCase(
        name="real_linker",
        function="main",
        ir=_load_real_ir("test_linker"),
    ),
    BenchmarkCase(
        name="real_vm_exit",
        function="main",
        ir=_load_real_ir("test_vm_exit"),
    ),
]
MODES: List[Tuple[str, Dict[str, bool]]] = [
    ("baseline", {"coalesce": False, "split": False}),
    ("coalesce_only", {"coalesce": True, "split": False}),
    ("full", {"coalesce": True, "split": True}),
]

METRIC_KEYS = [
    "max_pressure",
    "spill_count",
    "reload_count",
    "stack_bytes",
    "proactive_splits",
]


def run_case(case: BenchmarkCase, mode: Dict[str, bool]) -> Dict[str, int]:
    HSX_LLC.compile_ll_to_mvasm(
        case.ir,
        trace=False,
        allocator_opts=mode,
    )
    info = HSX_LLC.LAST_DEBUG_INFO or {}
    functions = info.get("functions", [])
    for fn in functions:
        if fn.get("function") == case.function:
            alloc = fn.get("register_allocation", {})
            return {key: int(alloc.get(key, 0)) for key in METRIC_KEYS}
    raise RuntimeError(f"missing allocation data for {case.function} in case {case.name}")


def compute_summary(case: BenchmarkCase, results: Dict[str, Dict[str, int]]) -> Dict[str, int]:
    baseline = results["baseline"]
    full = results["full"]
    return {
        "spill_delta": baseline["spill_count"] - full["spill_count"],
        "stack_delta": baseline["stack_bytes"] - full["stack_bytes"],
    }


def format_table(data: Dict[str, Dict[str, Dict[str, int]]]) -> str:
    rows: List[List[str]] = []
    for case_name, case_data in data.items():
        for mode_name, metrics in case_data.items():
            rows.append(
                [case_name, mode_name]
                + [metrics.get(key, 0) for key in METRIC_KEYS]
            )
    headers = ["case", "mode"] + METRIC_KEYS
    if tabulate is None:
        widths = [max(len(str(col)), 12) for col in headers]
        fmt = "  ".join(f"{{:{w}}}" for w in widths)
        sep = "  ".join("-" * w for w in widths)
        lines = [fmt.format(*headers), sep]
        for row in rows:
            lines.append(fmt.format(*row))
        return "\n".join(lines)
    return tabulate(rows, headers=headers, tablefmt="github")


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Report hsx-llc register allocation metrics.")
    parser.add_argument("--json", help="write JSON report to file")
    args = parser.parse_args(list(argv) if argv is not None else None)

    report: Dict[str, Dict[str, Dict[str, int]]] = {}
    for case in CASES:
        case_results: Dict[str, Dict[str, int]] = {}
        for mode_name, mode in MODES:
            metrics = run_case(case, mode)
            case_results[mode_name] = metrics
        # Attach summary deltas for convenience
        summary = compute_summary(case, case_results)
        case_results["summary"] = summary
        report[case.name] = case_results

    table_data = {
        name: {mode: data for mode, data in results.items() if mode != "summary"}
        for name, results in report.items()
    }
    print(format_table(table_data))
    summary_rows: List[List[int]] = []
    for case, results in report.items():
        summary = results.get("summary", {})
        summary_rows.append(
            [case, summary.get("spill_delta", 0), summary.get("stack_delta", 0)]
        )
    print("\nSummary (baseline - full):")
    if tabulate is None:
        fmt = "{:<20}  {:>12}  {:>12}"
        print(fmt.format("case", "spill_delta", "stack_delta"))
        print("-" * 48)
        for row in summary_rows:
            print(fmt.format(row[0], row[1], row[2]))
    else:
        print(tabulate(summary_rows, headers=["case", "spill_delta", "stack_delta"], tablefmt="github"))

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover - CLI utility
    main()

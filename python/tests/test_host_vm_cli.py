import importlib.util
import subprocess
import sys
from pathlib import Path

import python.asm as hsx_asm


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


HSX_LLC = _load_hsx_llc()


def _build_hxe(tmp_path: Path, asm_source: str) -> Path:
    lines = [line + "\n" for line in asm_source.strip().splitlines()]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _local_symbols = hsx_asm.assemble(lines)
    assert not relocs, f"unexpected relocations: {relocs}"
    out = tmp_path / "prog.hxe"
    hsx_asm.write_hxe(code, entry or 0, out, rodata=rodata)
    return out


def _run_vm(tmp_path: Path, extra_args):
    repo_root = Path(__file__).resolve().parents[2]
    host_vm = repo_root / "platforms" / "python" / "host_vm.py"
    cmd = [sys.executable, str(host_vm)] + extra_args
    return subprocess.run(cmd, capture_output=True, text=True, cwd=tmp_path)


def test_max_steps_limits_execution(tmp_path):
    asm_source = """
    .text
    .entry start
start:
    JMP start
"""
    hxe = _build_hxe(tmp_path, asm_source)
    result = _run_vm(tmp_path, [str(hxe), "--max-steps", "5"])
    assert result.returncode == 0
    assert "[VM] Max steps 5 reached" in result.stdout
    assert "Halted" in result.stdout


def test_trace_file_receives_output(tmp_path):
    asm_source = """
    .text
    .entry start
start:
    LDI R1, 1
    RET
"""
    hxe = _build_hxe(tmp_path, asm_source)
    trace_path = tmp_path / "trace.log"
    result = _run_vm(tmp_path, [str(hxe), "--trace", "--trace-file", str(trace_path)])
    assert result.returncode == 0
    trace_text = trace_path.read_text(encoding="utf-8")
    assert "[TRACE]" in trace_text


def test_entry_symbol_override(tmp_path):
    asm_source = """
    .text
    .entry start
start:
    LDI R0, 1
    RET
alt:
    LDI R0, 7
    RET
"""
    hxe = _build_hxe(tmp_path, asm_source)
    result = _run_vm(tmp_path, [str(hxe), "--entry-symbol", "0x8"])
    assert result.returncode == 0
    assert "R0..R7: [7" in result.stdout


def test_register_allocator_spills_via_cli(tmp_path):
    ir_source = """
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

    asm_text = HSX_LLC.compile_ll_to_mvasm(ir_source, trace=False)
    assert "[R7" in asm_text, "expected stack-based spill slots in generated assembly"
    hxe = _build_hxe(tmp_path, asm_text)

    result = _run_vm(tmp_path, [str(hxe)])
    assert result.returncode == 0
    assert "R0..R7: [55" in result.stdout

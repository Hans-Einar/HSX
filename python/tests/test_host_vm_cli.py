import subprocess
import sys
from pathlib import Path

import python.asm as hsx_asm


def _build_hxe(tmp_path: Path, asm_source: str) -> Path:
    lines = [line + "\n" for line in asm_source.strip().splitlines()]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol = hsx_asm.assemble(lines)
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

import math

from python import asm as hsx_asm
from platforms.python.host_vm import MiniVM, f16_to_f32


def assemble(lines):
    code_words, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol = hsx_asm.assemble(lines)
    assert not relocs, f'Unresolved symbols: {relocs}'
    code_bytes = b"".join((w & 0xFFFFFFFF).to_bytes(4, "big") for w in code_words)
    return code_bytes, entry, rodata

def run_vm(lines, **vm_kwargs):
    code, entry, rodata = assemble(lines)
    vm = MiniVM(code, entry=entry, rodata=rodata, **vm_kwargs)
    while vm.running:
        vm.step()
    return vm


def test_svc_exit_stops_vm():
    lines = [
        ".entry",
        "LDI R0, 42",
        "SVC MOD=1 FN=0",
    ]
    vm = run_vm(lines)
    assert vm.regs[0] & 0xFFFFFFFF == 42
    assert not vm.running


def test_dev_libm_sin_returns_f16():
    lines = [
        ".entry",
        "LDI R1, 0",
        "SVC MOD=14 FN=0",
        "RET",
    ]
    vm = run_vm(lines, dev_libm=True)
    result = f16_to_f32(vm.regs[0] & 0xFFFF)
    assert math.isclose(result, math.sin(0.0), rel_tol=0.0, abs_tol=0.0)


def test_trace_file_receives_output(tmp_path):
    lines = [
        ".entry",
        "LDI R1, 1",
        "RET",
    ]
    trace_path = tmp_path / "trace.log"
    code, entry, rodata = assemble(lines)
    with trace_path.open("w", encoding="utf-8") as handle:
        vm = MiniVM(code, entry=entry, rodata=rodata, trace_file=handle)
        while vm.running:
            vm.step()
    contents = trace_path.read_text()
    assert "[TRACE]" in contents


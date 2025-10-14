import importlib.util
from pathlib import Path

from python import asm as hsx_asm
from platforms.python.host_vm import MiniVM


def _load_hsx_llc():
    root = Path(__file__).resolve().parents[1] / "hsx-llc.py"
    spec = importlib.util.spec_from_file_location("hsx_llc", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _assemble(lines):
    code_words, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _local_symbols = hsx_asm.assemble(lines)
    assert not relocs, f"Unresolved relocations: {relocs}"
    code_bytes = b"".join((w & 0xFFFFFFFF).to_bytes(4, "big") for w in code_words)
    return code_bytes, entry, rodata


def test_r7_counter_progresses():
    hsx_llc = _load_hsx_llc()
    ir = """
define dso_local i32 @main() {
entry:
  %counter = alloca i32, align 4
  store volatile i32 0, ptr %counter, align 4
  br label %loop

loop:
  %old = load volatile i32, ptr %counter, align 4
  %inc = add i32 %old, 1
  store volatile i32 %inc, ptr %counter, align 4
  %check = load volatile i32, ptr %counter, align 4
  %iszero = icmp eq i32 %check, 0
  br i1 %iszero, label %wrap, label %cont

wrap:
  store volatile i32 1, ptr %counter, align 4
  br label %cont

cont:
  br label %loop
}
"""
    asm_text = hsx_llc.compile_ll_to_mvasm(ir, trace=False)
    lines = [line.rstrip() for line in asm_text.splitlines() if line.strip()]
    code, entry, rodata = _assemble(lines)
    vm = MiniVM(code, entry=entry, rodata=rodata)

    observed: list[int] = []
    slot_addr: int | None = None
    for _ in range(256):
        vm.step()
        fp = vm.regs[7] & 0xFFFF
        if fp and slot_addr is None:
            slot_addr = (fp - 4) & 0xFFFF
        if slot_addr is not None:
            word = (
                vm.mem[slot_addr]
                | (vm.mem[(slot_addr + 1) & 0xFFFF] << 8)
                | (vm.mem[(slot_addr + 2) & 0xFFFF] << 16)
                | (vm.mem[(slot_addr + 3) & 0xFFFF] << 24)
            )
            observed.append(word & 0xFFFFFFFF)

    assert observed, "stack slot was never initialised"
    assert any(value > 0 for value in observed), "counter never incremented above zero"
    assert len(set(observed)) > 1, "counter value did not change over time"

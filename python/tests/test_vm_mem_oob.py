import importlib.util
from pathlib import Path

from platforms.python.host_vm import HSX_ERR_MEM_FAULT, MiniVM


def _load_asm():
    root = Path(__file__).resolve().parents[1] / "asm.py"
    spec = importlib.util.spec_from_file_location("hsx_asm", root)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ASM = _load_asm()


def _assemble(lines):
    text = [line + "\n" for line in lines]
    code, entry, externs, imports_decl, rodata, relocs, exports, entry_symbol, _locals = ASM.assemble(text)
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code)
    return code_bytes, entry, rodata


def test_ld_beyond_memory_traps():
    code, entry, rodata = _assemble([
        ".text",
        ".entry start",
        "start:",
        "    LDI32 R1, 0xFFFE",
        "    LD R2, [R1+0]",
        "    RET",
    ])
    vm = MiniVM(code, entry=entry, rodata=rodata)
    while vm.running:
        vm.step()
    assert vm.regs[0] == HSX_ERR_MEM_FAULT
    assert not vm.running


def test_store_beyond_memory_traps():
    code, entry, rodata = _assemble([
        ".text",
        ".entry start",
        "start:",
        "    LDI32 R1, 0xFFFF",
        "    LDI R2, 1",
        "    ST [R1+0], R2",
        "    RET",
    ])
    vm = MiniVM(code, entry=entry, rodata=rodata)
    while vm.running:
        vm.step()
    assert vm.regs[0] == HSX_ERR_MEM_FAULT

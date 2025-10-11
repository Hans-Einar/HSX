import importlib.util
from pathlib import Path

from platforms.python.host_vm import MiniVM


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


def test_unaligned_little_endian_loads():
    base_addr = 0x2000
    code, entry, rodata = _assemble([
        ".text",
        ".entry start",
        "start:",
        f"    LDI32 R1, {base_addr}",
        "    LD R2, [R1+0]",
        "    LD R3, [R1+1]",
        "    LDH R4, [R1+2]",
        "    RET",
    ])

    vm = MiniVM(code, entry=entry, rodata=rodata)
    vm.mem[base_addr : base_addr + 5] = bytes([0x11, 0x22, 0x33, 0x44, 0x55])

    while vm.running:
        vm.step()

    assert vm.regs[2] == 0x44332211
    assert vm.regs[3] == 0x55443322
    assert vm.regs[4] == 0x4433

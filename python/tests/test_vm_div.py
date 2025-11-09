from python import asm as hsx_asm
from platforms.python.host_vm import MiniVM, HSX_ERR_DIV_ZERO, FLAG_Z


def _assemble(lines):
    (
        code_words,
        entry,
        _externs,
        _imports,
        rodata,
        relocs,
        _exports,
        _entry_symbol,
        _locals,
    ) = hsx_asm.assemble(lines)
    assert not relocs, f"Unresolved relocations: {relocs}"
    code = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code_words)
    return code, entry, rodata


def _run(lines, max_steps=16):
    code, entry, rodata = _assemble(lines)
    vm = MiniVM(code, entry=entry, rodata=rodata)
    steps = max_steps
    while vm.running and steps:
        vm.step()
        steps -= 1
    return vm


def test_div_basic_truncates_toward_zero():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 10",
        "    LDI R2, 3",
        "    DIV R3, R1, R2",
        "    LDI R4, -7",
        "    LDI R5, 2",
        "    DIV R6, R4, R5",
        "    LDI R7, -7",
        "    LDI R8, -3",
        "    DIV R9, R7, R8",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert vm.regs[3] == 3
    assert _signed(vm.regs[6]) == -3
    assert vm.regs[9] == 2  # -7 / -3 -> 2 (toward zero)


def test_div_updates_flags():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 8",
        "    LDI R2, 2",
        "    DIV R3, R1, R2",  # result 4
        "    LDI R4, 1",
        "    LDI R5, 2",
        "    DIV R6, R4, R5",  # result 0
        "    BRK 0",
    ]
    vm = _run(asm)
    assert vm.regs[3] == 4
    assert vm.regs[6] == 0
    assert vm.flags & FLAG_Z  # zero flag set after second division


def test_div_by_zero_traps():
    asm = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 5",
        "    LDI R2, 0",
        "    DIV R3, R1, R2",
        "    BRK 0",
    ]
    vm = _run(asm)
    assert not vm.running
    assert vm.regs[0] == HSX_ERR_DIV_ZERO
def _signed(val):
    return val if val < 0x80000000 else val - 0x100000000

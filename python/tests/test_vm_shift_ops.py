from python import asm as hsx_asm
from platforms.python.host_vm import MiniVM


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
        _local_symbols,
    ) = hsx_asm.assemble(lines)
    assert not relocs, f"Unresolved relocations: {relocs}"
    code_bytes = b"".join((word & 0xFFFFFFFF).to_bytes(4, "big") for word in code_words)
    return code_bytes, entry, rodata


def _run_program(asm_lines, max_steps=64):
    code, entry, rodata = _assemble(asm_lines)
    vm = MiniVM(code, entry=entry, rodata=rodata)
    steps = max_steps
    while vm.running and steps > 0:
        vm.step()
        steps -= 1
    return vm


def test_shift_ops_cover_edge_cases():
    asm_lines = [
        ".entry main",
        ".text",
        "main:",
        "    LDI R1, 0x1",
        "    LDI R2, 1",
        "    LDI32 R3, 0x80000000",
        "    LDI R4, 0x20",
        "    LDI R5, 0x21",
        "    LSL R6, R1, R2",
        "    LSR R7, R6, R2",
        "    ASR R8, R3, R2",
        "    LSL R9, R1, R4",
        "    LSR R10, R6, R4",
        "    ASR R11, R3, R5",
        "    LDI R0, 0",
        "    LSL R12, R0, R5",
        "    BRK 0",
    ]

    vm = _run_program(asm_lines)

    assert vm.regs[6] == 0x00000002  # LSL by 1
    assert vm.regs[7] == 0x00000001  # LSR undo shift
    assert vm.regs[8] == 0xC0000000  # ASR keeps sign
    assert vm.regs[9] == 0x00000001  # LSL wraps when shift == 32
    assert vm.regs[10] == 0x00000002  # LSR wraps when shift == 32
    assert vm.regs[11] == 0xC0000000  # ASR wraps shift amount (33 -> 1)
    assert vm.regs[12] == 0  # Shifted zero stays zero
    assert vm.flags & 0x1  # Zero flag set after final shift


def test_shift_by_zero_clears_overflow():
    asm_lines = [
        ".entry main",
        ".text",
        "main:",
        "    LDI32 R1, 0x7FFFFFFF",
        "    ADD R2, R1, R1",  # sets overflow
        "    LDI R3, 0",
        "    LSR R4, R1, R3",  # shift by 0 must clear V
        "    BRK 0",
    ]

    vm = _run_program(asm_lines)

    assert (vm.flags & 0x8) == 0, "Overflow flag should be cleared after zero-width shift"
